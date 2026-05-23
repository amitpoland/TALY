from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.exchange_rate_lot import ExchangeRateLot
from app.models.fx_conversion import FxConversion
from app.models.fx_lot_consumption import FxLotConsumption
from app.models.transaction_component import TransactionComponent
from app.models.role import Role
from app.models.transaction import Transaction
from app.models.user import User


def create_user(db: Session) -> User:
    role = db.query(Role).filter(Role.name == "admin").one()
    user = User(
        username="fx-poster",
        password_hash="test",
        full_name="FX Poster",
        role_id=role.id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_account(db: Session, code: str, account_type: str, currency: str) -> Account:
    account = Account(
        account_code=code,
        name=code,
        account_type=account_type,
        currency=currency,
        opening_balance=Decimal("0"),
        current_balance=Decimal("0"),
        is_active=True,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def post(client: TestClient, path: str, payload: dict) -> dict:
    response = client.post(path, json={"payload": payload, "confirmation": {"confirmed_by_user": True}})
    assert response.status_code == 201, response.text
    return response.json()


def opening_payload(user: User, account: Account, equity: Account, amount: str, rate: str) -> dict:
    return {
        "transaction_date": "2026-05-15",
        "created_by_user_id": user.id,
        "account_id": account.id,
        "equity_account_id": equity.id,
        "amount": amount,
        "currency": account.currency,
        "base_currency": "AED",
        "original_rate": rate,
    }


def fx_accounts(db: Session):
    source = create_account(db, "CASH-USD", "cash", "USD")
    target = create_account(db, "CASH-AED", "cash", "AED")
    equity = create_account(db, "EQUITY-USD", "owner_equity", "USD")
    clearing_usd = create_account(db, "FX-CLEARING-USD", "clearing", "USD")
    clearing_aed = create_account(db, "FX-CLEARING-AED", "clearing", "AED")
    gain_loss = create_account(db, "FX-GL-AED", "fx_gain_loss", "AED")
    charge = create_account(db, "FX-CHARGE-AED", "expense", "AED")
    return source, target, equity, clearing_usd, clearing_aed, gain_loss, charge


def fx_payload(user: User, source: Account, target: Account, clearing_usd: Account, clearing_aed: Account, gain_loss: Account, **overrides) -> dict:
    payload = {
        "transaction_date": "2026-05-15",
        "created_by_user_id": user.id,
        "from_account_id": source.id,
        "to_account_id": target.id,
        "source_clearing_account_id": clearing_usd.id,
        "target_clearing_account_id": clearing_aed.id,
        "fx_gain_loss_account_id": gain_loss.id,
        "from_amount": "100.00",
        "to_amount": "400.00",
        "from_currency": "USD",
        "to_currency": "AED",
        "base_currency": "AED",
    }
    payload.update(overrides)
    return payload


def test_transaction_wise_fx_conversion(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    source, target, equity, clearing_usd, clearing_aed, gain_loss, _ = fx_accounts(db_session)
    post(client, "/transactions/opening-balance/post", opening_payload(user, source, equity, "100.00", "3.90"))
    lot = db_session.query(ExchangeRateLot).one()

    result = post(
        client,
        "/transactions/fx-conversion/post",
        fx_payload(user, source, target, clearing_usd, clearing_aed, gain_loss, costing_method="transaction_wise", source_lot_id=lot.id),
    )

    conversion = db_session.query(FxConversion).one()
    consumption = db_session.query(FxLotConsumption).one()
    assert result["transaction_type"] == "currency_exchange"
    assert conversion.costing_method == "transaction_wise"
    assert conversion.original_base_value == Decimal("390.000000")
    assert consumption.exchange_rate_lot_id == lot.id


def test_fifo_lot_consumption_and_weighted_average_display(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    source, target, equity, clearing_usd, clearing_aed, gain_loss, _ = fx_accounts(db_session)
    clearing = create_account(db_session, "CLEARING-USD", "clearing", "USD")
    post(client, "/transactions/opening-balance/post", opening_payload(user, source, equity, "100.00", "3.90"))
    post(
        client,
        "/transactions/receipt/post",
        {
            "transaction_date": "2026-05-15",
            "created_by_user_id": user.id,
            "receiving_account_id": source.id,
            "clearing_account_id": clearing.id,
            "gross_amount": "100.00",
            "principal_amount": "100.00",
            "currency": "USD",
            "base_currency": "AED",
            "original_rate": "3.95",
        },
    )

    preview = client.post(
        "/transactions/fx-conversion/preview",
        json=fx_payload(user, source, target, clearing_usd, clearing_aed, gain_loss, from_amount="150.00", to_amount="600.00"),
    )
    assert preview.status_code == 200
    assert Decimal(preview.json()["fx_detail"]["weighted_avg_rate"]) == Decimal("3.916666666666666666666666667")

    post(
        client,
        "/transactions/fx-conversion/post",
        fx_payload(user, source, target, clearing_usd, clearing_aed, gain_loss, from_amount="150.00", to_amount="600.00"),
    )
    lots = db_session.query(ExchangeRateLot).order_by(ExchangeRateLot.id).all()
    assert lots[0].remaining_amount == Decimal("0.000000")
    assert lots[0].status == "consumed"
    assert lots[1].remaining_amount == Decimal("50.000000")
    assert lots[1].status == "partially_consumed"
    consumptions = db_session.query(FxLotConsumption).order_by(FxLotConsumption.id).all()
    assert [row.consumed_amount for row in consumptions] == [
        Decimal("100.000000"),
        Decimal("50.000000"),
    ]


def test_fx_gain_and_loss_components(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    source, target, equity, clearing_usd, clearing_aed, gain_loss, _ = fx_accounts(db_session)
    post(client, "/transactions/opening-balance/post", opening_payload(user, source, equity, "200.00", "3.90"))

    gain = post(client, "/transactions/fx-conversion/post", fx_payload(user, source, target, clearing_usd, clearing_aed, gain_loss, from_amount="100.00", to_amount="400.00"))
    loss = post(client, "/transactions/fx-conversion/post", fx_payload(user, source, target, clearing_usd, clearing_aed, gain_loss, from_amount="100.00", to_amount="380.00"))

    assert Decimal(gain["profitability_effect"]["AED"]) == Decimal("10.00")
    assert Decimal(loss["profitability_effect"]["AED"]) == Decimal("-10.00")
    db_session.refresh(gain_loss)
    assert gain_loss.current_balance == Decimal("0.000000")


def test_fx_charge(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    source, target, equity, clearing_usd, clearing_aed, gain_loss, charge = fx_accounts(db_session)
    post(client, "/transactions/opening-balance/post", opening_payload(user, source, equity, "100.00", "3.90"))

    result = post(
        client,
        "/transactions/fx-conversion/post",
        fx_payload(user, source, target, clearing_usd, clearing_aed, gain_loss, fx_charge="2.00", fx_charge_account_id=charge.id),
    )

    db_session.refresh(target)
    db_session.refresh(charge)
    assert Decimal(result["profitability_effect"]["AED"]) == Decimal("8.00")
    assert target.current_balance == Decimal("398.000000")
    assert charge.current_balance == Decimal("2.000000")


def test_preview_leaves_lot_balances_unchanged(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    source, target, equity, clearing_usd, clearing_aed, gain_loss, _ = fx_accounts(db_session)
    post(client, "/transactions/opening-balance/post", opening_payload(user, source, equity, "100.00", "3.90"))
    lot = db_session.query(ExchangeRateLot).one()

    response = client.post(
        "/transactions/fx-conversion/preview",
        json=fx_payload(user, source, target, clearing_usd, clearing_aed, gain_loss, from_amount="60.00", to_amount="240.00"),
    )

    db_session.refresh(lot)
    assert response.status_code == 200
    assert lot.remaining_amount == Decimal("100.000000")
    assert lot.remaining_base_value == Decimal("390.000000")
    assert lot.status == "open"
    assert db_session.query(FxLotConsumption).count() == 0
    assert db_session.query(FxConversion).count() == 0


def test_partial_lot_consumption_marks_partially_consumed(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    source, target, equity, clearing_usd, clearing_aed, gain_loss, _ = fx_accounts(db_session)
    post(client, "/transactions/opening-balance/post", opening_payload(user, source, equity, "100.00", "3.90"))

    post(
        client,
        "/transactions/fx-conversion/post",
        fx_payload(user, source, target, clearing_usd, clearing_aed, gain_loss, from_amount="40.00", to_amount="160.00"),
    )

    lot = db_session.query(ExchangeRateLot).one()
    assert lot.remaining_amount == Decimal("60.000000")
    assert lot.remaining_base_value == Decimal("234.000000")
    assert lot.status == "partially_consumed"


def test_exact_full_lot_consumption_marks_consumed(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    source, target, equity, clearing_usd, clearing_aed, gain_loss, _ = fx_accounts(db_session)
    post(client, "/transactions/opening-balance/post", opening_payload(user, source, equity, "100.00", "3.90"))

    post(client, "/transactions/fx-conversion/post", fx_payload(user, source, target, clearing_usd, clearing_aed, gain_loss))

    lot = db_session.query(ExchangeRateLot).one()
    assert lot.remaining_amount == Decimal("0.000000")
    assert lot.remaining_base_value == Decimal("0.000000")
    assert lot.status == "consumed"


def test_insufficient_lot_blocked(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    source, target, equity, clearing_usd, clearing_aed, gain_loss, _ = fx_accounts(db_session)
    post(
        client,
        "/transactions/opening-balance/post",
        {
            "transaction_date": "2026-05-15",
            "created_by_user_id": user.id,
            "account_id": source.id,
            "equity_account_id": equity.id,
            "amount": "100.00",
            "currency": "USD",
        },
    )

    response = client.post(
        "/transactions/fx-conversion/preview",
        json=fx_payload(user, source, target, clearing_usd, clearing_aed, gain_loss, from_amount="100.00", to_amount="400.00"),
    )

    assert response.status_code == 400
    assert "Insufficient FX lots" in response.text


def test_fx_preview_allows_negative_bank_or_wallet_with_permission(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    source = create_account(db_session, "BANK-FX-USD", "bank", "USD")
    target = create_account(db_session, "CASH-FX-AED", "cash", "AED")
    equity = create_account(db_session, "EQUITY-FX-USD", "owner_equity", "USD")
    clearing_usd = create_account(db_session, "FX-NEG-CLEARING-USD", "clearing", "USD")
    clearing_aed = create_account(db_session, "FX-NEG-CLEARING-AED", "clearing", "AED")
    gain_loss = create_account(db_session, "FX-NEG-GL-AED", "fx_gain_loss", "AED")
    post(client, "/transactions/opening-balance/post", opening_payload(user, source, equity, "100.00", "3.90"))
    source.current_balance = Decimal("50.000000")
    db_session.add(source)
    db_session.commit()

    blocked = client.post(
        "/transactions/fx-conversion/preview",
        json=fx_payload(user, source, target, clearing_usd, clearing_aed, gain_loss, from_amount="80.00", to_amount="320.00"),
    )
    allowed = client.post(
        "/transactions/fx-conversion/preview",
        json=fx_payload(user, source, target, clearing_usd, clearing_aed, gain_loss, from_amount="80.00", to_amount="320.00", allow_negative_balance=True),
    )

    assert blocked.status_code == 400
    assert "Negative balance requires permission" in blocked.text
    assert allowed.status_code == 200
    assert "Negative balance allowed by permission" in allowed.text


def test_fx_reversal_restores_balances_and_lots(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    source, target, equity, clearing_usd, clearing_aed, gain_loss, _ = fx_accounts(db_session)
    post(client, "/transactions/opening-balance/post", opening_payload(user, source, equity, "100.00", "3.90"))

    fx = post(client, "/transactions/fx-conversion/post", fx_payload(user, source, target, clearing_usd, clearing_aed, gain_loss))
    lot = db_session.query(ExchangeRateLot).one()
    assert lot.remaining_amount == Decimal("0.000000")

    post(
        client,
        f"/transactions/{fx['transaction_id']}/reverse/post",
        {
            "created_by_user_id": user.id,
            "transaction_date": "2026-05-15",
            "reversal_reason": "Cancel FX",
        },
    )

    db_session.refresh(source)
    db_session.refresh(target)
    db_session.refresh(lot)
    original = db_session.get(Transaction, fx["transaction_id"])
    assert original.status == "reversed"
    assert source.current_balance == Decimal("100.000000")
    assert target.current_balance == Decimal("0.000000")
    assert lot.remaining_amount == Decimal("100.000000")
    assert lot.status == "open"


def test_reversing_opening_balance_blocked_after_lot_consumed(
    client: TestClient, db_session: Session
) -> None:
    user = create_user(db_session)
    source, target, equity, clearing_usd, clearing_aed, gain_loss, _ = fx_accounts(db_session)
    opening = post(client, "/transactions/opening-balance/post", opening_payload(user, source, equity, "100.00", "3.90"))
    post(client, "/transactions/fx-conversion/post", fx_payload(user, source, target, clearing_usd, clearing_aed, gain_loss))

    response = client.post(
        f"/transactions/{opening['transaction_id']}/reverse/preview",
        json={
            "created_by_user_id": user.id,
            "transaction_date": "2026-05-15",
            "reversal_reason": "Cannot undo consumed lot",
        },
    )

    assert response.status_code == 400
    assert "consumed FX lots" in response.text


def test_reversing_receipt_blocked_after_lot_consumed(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    source, target, _, clearing_usd, clearing_aed, gain_loss, _ = fx_accounts(db_session)
    clearing = create_account(db_session, "CLEARING-USD", "clearing", "USD")
    receipt = post(
        client,
        "/transactions/receipt/post",
        {
            "transaction_date": "2026-05-15",
            "created_by_user_id": user.id,
            "receiving_account_id": source.id,
            "clearing_account_id": clearing.id,
            "gross_amount": "100.00",
            "principal_amount": "100.00",
            "currency": "USD",
            "base_currency": "AED",
            "original_rate": "3.90",
        },
    )
    post(client, "/transactions/fx-conversion/post", fx_payload(user, source, target, clearing_usd, clearing_aed, gain_loss))

    response = client.post(
        f"/transactions/{receipt['transaction_id']}/reverse/preview",
        json={
            "created_by_user_id": user.id,
            "transaction_date": "2026-05-15",
            "reversal_reason": "Cannot undo consumed receipt lot",
        },
    )

    assert response.status_code == 400
    assert "consumed FX lots" in response.text


def test_gain_loss_component_does_not_affect_settlement_by_default(
    client: TestClient, db_session: Session
) -> None:
    user = create_user(db_session)
    source, target, equity, clearing_usd, clearing_aed, gain_loss, _ = fx_accounts(db_session)
    post(client, "/transactions/opening-balance/post", opening_payload(user, source, equity, "100.00", "3.90"))

    fx = post(client, "/transactions/fx-conversion/post", fx_payload(user, source, target, clearing_usd, clearing_aed, gain_loss))

    components = (
        db_session.query(TransactionComponent)
        .filter(TransactionComponent.transaction_id == fx["transaction_id"])
        .filter(TransactionComponent.component_type.in_(["fx_gain", "fx_loss"]))
        .all()
    )
    assert components
    assert all(component.affects_profitability for component in components)
    assert all(not component.affects_settlement for component in components)


def test_no_float_usage_in_fx_service_paths() -> None:
    from pathlib import Path

    service_text = "\n".join(
        path.read_text()
        for path in [
            Path("backend/app/services/posting/fx_lot_service.py"),
            Path("backend/app/services/posting/builders.py"),
            Path("backend/app/services/posting/posting_service.py"),
        ]
    )
    assert "float(" not in service_text
    assert ": float" not in service_text
