from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.fx_conversion import FxConversion
from app.models.party import Party
from app.models.role import Role
from app.models.transaction import Transaction
from app.models.user import User


def create_user(db: Session) -> User:
    role = db.query(Role).filter(Role.name == "admin").one()
    user = User(username="wallet-user", password_hash="test", full_name="Wallet User", role_id=role.id)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_party(db: Session) -> Party:
    party = Party(party_type="customer", name="VKS", default_currency="USD", is_active=True)
    db.add(party)
    db.commit()
    db.refresh(party)
    return party


def create_account(db: Session, code: str, account_type: str, currency: str, party_id: int | None = None) -> Account:
    account = Account(
        account_code=code,
        name=code,
        account_type=account_type,
        currency=currency,
        party_id=party_id,
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


def test_one_party_can_have_usd_and_eur_wallets(client: TestClient, db_session: Session) -> None:
    party = create_party(db_session)

    usd = client.post("/accounts", json={"account_code": "VKS-USD", "name": "VKS USD Wallet", "account_type": "customer_wallet", "currency": "USD", "party_id": party.id})
    eur = client.post("/accounts", json={"account_code": "VKS-EUR", "name": "VKS EUR Wallet", "account_type": "customer_wallet", "currency": "EUR", "party_id": party.id})

    assert usd.status_code == 201
    assert eur.status_code == 201
    assert usd.json()["party_id"] == party.id
    assert eur.json()["party_id"] == party.id
    assert usd.json()["currency"] == "USD"
    assert eur.json()["currency"] == "EUR"


def test_active_currencies_api_feeds_voucher_currency_dropdown(client: TestClient) -> None:
    response = client.get("/currencies")

    assert response.status_code == 200
    codes = {currency["code"] for currency in response.json()}
    assert {"USD", "EUR", "PLN", "AED", "INR"}.issubset(codes)


def test_receipts_into_party_usd_and_eur_wallets_report_separate_currency_balances(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    party = create_party(db_session)
    usd_wallet = create_account(db_session, "VKS-USD-WALLET", "customer_wallet", "USD", party.id)
    eur_wallet = create_account(db_session, "VKS-EUR-WALLET", "customer_wallet", "EUR", party.id)
    usd_clearing = create_account(db_session, "CLEAR-USD-WALLET", "clearing", "USD")
    eur_clearing = create_account(db_session, "CLEAR-EUR-WALLET", "clearing", "EUR")

    post(client, "/transactions/receipt/post", {"transaction_date": "2026-05-16", "created_by_user_id": user.id, "receiving_account_id": usd_wallet.id, "clearing_account_id": usd_clearing.id, "gross_amount": "100.00", "principal_amount": "100.00", "currency": "USD"})
    post(client, "/transactions/receipt/post", {"transaction_date": "2026-05-16", "created_by_user_id": user.id, "receiving_account_id": eur_wallet.id, "clearing_account_id": eur_clearing.id, "gross_amount": "200.00", "principal_amount": "200.00", "currency": "EUR", "base_currency": "USD", "original_rate": "1.10"})

    ledger = client.get(f"/reports/customer-ledger?party_id={party.id}")

    assert ledger.status_code == 200
    assert Decimal(ledger.json()["totals"]["USD"]) == Decimal("100.000000")
    assert Decimal(ledger.json()["totals"]["EUR"]) == Decimal("200.000000")
    assert {row["currency"] for row in ledger.json()["rows"]} == {"USD", "EUR"}


def test_fx_conversion_between_same_party_wallets_creates_transaction_and_reports_both_sides(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    party = create_party(db_session)
    usd_wallet = create_account(db_session, "VKS-FX-USD", "customer_wallet", "USD", party.id)
    eur_wallet = create_account(db_session, "VKS-FX-EUR", "customer_wallet", "EUR", party.id)
    eur_clearing = create_account(db_session, "FX-CLEAR-EUR-WALLET", "clearing", "EUR")
    usd_clearing = create_account(db_session, "FX-CLEAR-USD-WALLET", "clearing", "USD")
    fx_gl = create_account(db_session, "FX-GL-USD-WALLET", "fx_gain_loss", "USD")

    post(client, "/transactions/receipt/post", {"transaction_date": "2026-05-16", "created_by_user_id": user.id, "receiving_account_id": eur_wallet.id, "clearing_account_id": eur_clearing.id, "gross_amount": "100.00", "principal_amount": "100.00", "currency": "EUR", "base_currency": "USD", "original_rate": "1.10"})
    fx = post(
        client,
        "/transactions/fx-conversion/post",
        {
            "transaction_date": "2026-05-16",
            "created_by_user_id": user.id,
            "from_account_id": eur_wallet.id,
            "to_account_id": usd_wallet.id,
            "source_clearing_account_id": eur_clearing.id,
            "target_clearing_account_id": usd_clearing.id,
            "fx_gain_loss_account_id": fx_gl.id,
            "from_amount": "100.00",
            "to_amount": "115.00",
            "from_currency": "EUR",
            "to_currency": "USD",
            "base_currency": "USD",
        },
    )

    db_session.refresh(eur_wallet)
    db_session.refresh(usd_wallet)
    ledger = client.get(f"/reports/customer-ledger?party_id={party.id}")

    assert fx["transaction_id"] is not None
    assert db_session.query(Transaction).filter(Transaction.id == fx["transaction_id"]).one().transaction_type == "currency_exchange"
    assert db_session.query(FxConversion).one().fx_difference == Decimal("5.000000")
    assert eur_wallet.current_balance == Decimal("0.000000")
    assert usd_wallet.current_balance == Decimal("115.000000")
    assert ledger.status_code == 200
    assert Decimal(ledger.json()["totals"]["EUR"]) == Decimal("0.000000")
    assert Decimal(ledger.json()["totals"]["USD"]) == Decimal("115.000000")
    assert any(row["transaction_no"] == fx["transaction_no"] and row["currency"] == "EUR" for row in ledger.json()["rows"])
    assert any(row["transaction_no"] == fx["transaction_no"] and row["currency"] == "USD" for row in ledger.json()["rows"])
