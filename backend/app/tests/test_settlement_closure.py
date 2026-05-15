from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.audit_log import AuditLog
from app.models.role import Role
from app.models.settlement import Settlement
from app.models.transaction import Transaction
from app.models.user import User
from app.models.common import utcnow


def create_user(db: Session) -> User:
    role = db.query(Role).filter(Role.name == "admin").one()
    user = User(username="settlement-admin", password_hash="test", full_name="Settlement Admin", role_id=role.id)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_account(db: Session, code: str, account_type: str = "cash", currency: str = "USD") -> Account:
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


def create_settlement(db: Session, status: str = "open", number: str = "SET-CLOSE-1") -> Settlement:
    settlement = Settlement(
        settlement_no=number,
        title=number,
        status=status,
        base_currency="USD",
        opened_at=utcnow(),
    )
    db.add(settlement)
    db.commit()
    db.refresh(settlement)
    return settlement


def post(client: TestClient, path: str, payload: dict) -> dict:
    response = client.post(path, json={"payload": payload, "confirmation": {"confirmed_by_user": True}})
    assert response.status_code == 201, response.text
    return response.json()


def make_balanced_settlement(client: TestClient, db: Session, user: User, settlement: Settlement):
    cash = create_account(db, f"CASH-{settlement.id}")
    equity = create_account(db, f"EQUITY-{settlement.id}", "owner_equity")
    clearing = create_account(db, f"CLEARING-{settlement.id}", "clearing")
    post(
        client,
        "/transactions/opening-balance/post",
        {
            "transaction_date": "2026-05-15",
            "created_by_user_id": user.id,
            "account_id": cash.id,
            "equity_account_id": equity.id,
            "amount": "100.00",
            "currency": "USD",
        },
    )
    post(
        client,
        "/transactions/receipt/post",
        {
            "transaction_date": "2026-05-15",
            "created_by_user_id": user.id,
            "settlement_id": settlement.id,
            "receiving_account_id": cash.id,
            "clearing_account_id": clearing.id,
            "gross_amount": "50.00",
            "principal_amount": "50.00",
            "currency": "USD",
        },
    )
    post(
        client,
        "/transactions/payment/post",
        {
            "transaction_date": "2026-05-15",
            "created_by_user_id": user.id,
            "settlement_id": settlement.id,
            "paying_account_id": cash.id,
            "clearing_account_id": clearing.id,
            "amount": "50.00",
            "currency": "USD",
        },
    )
    return cash, clearing


def test_close_balanced_settlement_and_audit(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    settlement = create_settlement(db_session)
    make_balanced_settlement(client, db_session, user, settlement)

    preview = client.post(f"/settlements/{settlement.id}/close/preview", json={"user_id": user.id})
    response = client.post(f"/settlements/{settlement.id}/close", json={"user_id": user.id})

    db_session.refresh(settlement)
    assert preview.status_code == 200
    assert preview.json()["can_close"] is True
    assert settlement.status == "closed"
    assert response.json()["status"] == "closed"
    assert db_session.query(AuditLog).filter(AuditLog.action == "close_settlement").count() == 1


def test_block_unbalanced_settlement_closure(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    settlement = create_settlement(db_session)
    cash = create_account(db_session, "CASH-U")
    clearing = create_account(db_session, "CLEARING-U", "clearing")
    post(
        client,
        "/transactions/receipt/post",
        {
            "transaction_date": "2026-05-15",
            "created_by_user_id": user.id,
            "settlement_id": settlement.id,
            "receiving_account_id": cash.id,
            "clearing_account_id": clearing.id,
            "gross_amount": "10.00",
            "principal_amount": "10.00",
            "currency": "USD",
        },
    )

    response = client.post(f"/settlements/{settlement.id}/close", json={"user_id": user.id})

    assert response.status_code == 400
    db_session.refresh(settlement)
    assert settlement.status == "open"


def test_approve_pending_closure_stores_values(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    settlement = create_settlement(db_session)
    cash = create_account(db_session, "CASH-P")
    clearing = create_account(db_session, "CLEARING-P", "clearing")
    post(
        client,
        "/transactions/receipt/post",
        {
            "transaction_date": "2026-05-15",
            "created_by_user_id": user.id,
            "settlement_id": settlement.id,
            "receiving_account_id": cash.id,
            "clearing_account_id": clearing.id,
            "gross_amount": "10.00",
            "principal_amount": "10.00",
            "currency": "USD",
        },
    )

    response = client.post(
        f"/settlements/{settlement.id}/close",
        json={
            "user_id": user.id,
            "approved_pending_amount": "10.00",
            "approved_pending_currency": "USD",
            "approved_pending_reason": "Approved small pending balance",
            "admin_approved_pending": True,
        },
    )

    db_session.refresh(settlement)
    assert response.status_code == 200
    assert settlement.status == "closed"
    assert settlement.approved_pending_amount == Decimal("10.000000")
    assert settlement.approved_pending_currency == "USD"
    assert settlement.approved_pending_reason == "Approved small pending balance"
    assert db_session.query(AuditLog).filter(AuditLog.action == "close_settlement_with_pending_approval").count() == 1


def test_block_transaction_posting_into_closed_settlement(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    settlement = create_settlement(db_session, status="closed")
    cash = create_account(db_session, "CASH-CLOSED")
    clearing = create_account(db_session, "CLEARING-CLOSED", "clearing")

    response = client.post(
        "/transactions/receipt/preview",
        json={
            "transaction_date": "2026-05-15",
            "created_by_user_id": user.id,
            "settlement_id": settlement.id,
            "receiving_account_id": cash.id,
            "clearing_account_id": clearing.id,
            "gross_amount": "10.00",
            "principal_amount": "10.00",
            "currency": "USD",
        },
    )

    assert response.status_code == 400


def test_block_transaction_posting_into_cancelled_settlement(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    settlement = create_settlement(db_session, status="cancelled")
    cash = create_account(db_session, "CASH-CANCELLED")
    clearing = create_account(db_session, "CLEARING-CANCELLED", "clearing")

    response = client.post(
        "/transactions/receipt/preview",
        json={
            "transaction_date": "2026-05-15",
            "created_by_user_id": user.id,
            "settlement_id": settlement.id,
            "receiving_account_id": cash.id,
            "clearing_account_id": clearing.id,
            "gross_amount": "10.00",
            "principal_amount": "10.00",
            "currency": "USD",
        },
    )

    assert response.status_code == 400


def test_reopen_closed_settlement_with_reason_and_audit(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    settlement = create_settlement(db_session, status="closed")

    response = client.post(f"/settlements/{settlement.id}/reopen", json={"user_id": user.id, "reason": "Need correction"})

    db_session.refresh(settlement)
    assert response.status_code == 200
    assert settlement.status == "reopened"
    assert db_session.query(AuditLog).filter(AuditLog.action == "reopen_settlement").count() == 1


def test_block_reopen_without_reason(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    settlement = create_settlement(db_session, status="closed")

    response = client.post(f"/settlements/{settlement.id}/reopen", json={"user_id": user.id, "reason": ""})

    assert response.status_code == 422


def test_cancel_empty_settlement_and_audit(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    settlement = create_settlement(db_session)

    response = client.post(f"/settlements/{settlement.id}/cancel", json={"user_id": user.id, "reason": "No longer needed"})

    db_session.refresh(settlement)
    assert response.status_code == 200
    assert settlement.status == "cancelled"
    assert db_session.query(AuditLog).filter(AuditLog.action == "cancel_settlement").count() == 1


def test_block_cancel_with_active_posted_transactions(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    settlement = create_settlement(db_session)
    cash = create_account(db_session, "CASH-ACTIVE")
    clearing = create_account(db_session, "CLEARING-ACTIVE", "clearing")
    post(
        client,
        "/transactions/receipt/post",
        {
            "transaction_date": "2026-05-15",
            "created_by_user_id": user.id,
            "settlement_id": settlement.id,
            "receiving_account_id": cash.id,
            "clearing_account_id": clearing.id,
            "gross_amount": "10.00",
            "principal_amount": "10.00",
            "currency": "USD",
        },
    )

    response = client.post(f"/settlements/{settlement.id}/cancel", json={"user_id": user.id})

    assert response.status_code == 400


def test_allow_cancel_when_all_transactions_reversed(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    settlement = create_settlement(db_session)
    cash = create_account(db_session, "CASH-REV")
    clearing = create_account(db_session, "CLEARING-REV", "clearing")
    receipt = post(
        client,
        "/transactions/receipt/post",
        {
            "transaction_date": "2026-05-15",
            "created_by_user_id": user.id,
            "settlement_id": settlement.id,
            "receiving_account_id": cash.id,
            "clearing_account_id": clearing.id,
            "gross_amount": "10.00",
            "principal_amount": "10.00",
            "currency": "USD",
        },
    )
    post(
        client,
        f"/transactions/{receipt['transaction_id']}/reverse/post",
        {"created_by_user_id": user.id, "transaction_date": "2026-05-15", "reversal_reason": "Cancel case"},
    )

    response = client.post(f"/settlements/{settlement.id}/cancel", json={"user_id": user.id})

    db_session.refresh(settlement)
    assert response.status_code == 200
    assert settlement.status == "cancelled"


def test_closure_preview_does_not_persist_status(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    settlement = create_settlement(db_session)
    make_balanced_settlement(client, db_session, user, settlement)

    response = client.post(f"/settlements/{settlement.id}/close/preview", json={"user_id": user.id})

    db_session.refresh(settlement)
    assert response.status_code == 200
    assert settlement.status == "open"


def test_multiple_currencies_must_balance_by_original_currency(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    settlement = create_settlement(db_session, number="SET-MULTI-CURRENCY")
    usd_cash = create_account(db_session, "CASH-MULTI-USD")
    usd_clearing = create_account(db_session, "CLEARING-MULTI-USD", "clearing")
    eur_cash = create_account(db_session, "CASH-MULTI-EUR", currency="EUR")
    eur_clearing = create_account(db_session, "CLEARING-MULTI-EUR", "clearing", "EUR")

    post(
        client,
        "/transactions/receipt/post",
        {
            "transaction_date": "2026-05-15",
            "created_by_user_id": user.id,
            "settlement_id": settlement.id,
            "receiving_account_id": usd_cash.id,
            "clearing_account_id": usd_clearing.id,
            "gross_amount": "25.00",
            "principal_amount": "25.00",
            "currency": "USD",
        },
    )
    post(
        client,
        "/transactions/receipt/post",
        {
            "transaction_date": "2026-05-15",
            "created_by_user_id": user.id,
            "settlement_id": settlement.id,
            "receiving_account_id": eur_cash.id,
            "clearing_account_id": eur_clearing.id,
            "gross_amount": "10.00",
            "principal_amount": "10.00",
            "currency": "EUR",
        },
    )
    post(
        client,
        "/transactions/payment/post",
        {
            "transaction_date": "2026-05-15",
            "created_by_user_id": user.id,
            "settlement_id": settlement.id,
            "paying_account_id": usd_cash.id,
            "clearing_account_id": usd_clearing.id,
            "amount": "25.00",
            "currency": "USD",
        },
    )

    preview = client.post(f"/settlements/{settlement.id}/close/preview", json={"user_id": user.id})

    assert preview.status_code == 200
    body = preview.json()
    assert body["can_close"] is False
    assert Decimal(body["principal_balance_by_currency"]["USD"]) == Decimal("0.000000")
    assert Decimal(body["principal_balance_by_currency"]["EUR"]) == Decimal("10.000000")


def test_fx_gain_loss_excluded_from_principal_balance(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    settlement = create_settlement(db_session, number="SET-FX-EXCLUDED")
    source = create_account(db_session, "FX-SET-SOURCE-USD")
    target = create_account(db_session, "FX-SET-TARGET-AED", currency="AED")
    equity = create_account(db_session, "FX-SET-EQUITY-USD", "owner_equity")
    clearing_usd = create_account(db_session, "FX-SET-CLEAR-USD", "clearing")
    clearing_aed = create_account(db_session, "FX-SET-CLEAR-AED", "clearing", "AED")
    gain_loss = create_account(db_session, "FX-SET-GL-AED", "fx_gain_loss", "AED")
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
            "base_currency": "AED",
            "original_rate": "3.90",
        },
    )
    post(
        client,
        "/transactions/fx-conversion/post",
        {
            "transaction_date": "2026-05-15",
            "created_by_user_id": user.id,
            "settlement_id": settlement.id,
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
        },
    )

    balance = client.get(f"/settlements/{settlement.id}/balance")
    preview = client.post(f"/settlements/{settlement.id}/close/preview", json={"user_id": user.id})

    assert balance.status_code == 200
    assert balance.json()["balances"] == {}
    assert preview.status_code == 200
    assert preview.json()["can_close"] is True
    assert Decimal(preview.json()["fx_gain_loss_summary"]["AED"]) == Decimal("10.000000")


def test_settlement_affecting_charge_blocks_closure_until_approved(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    settlement = create_settlement(db_session, number="SET-CHARGE-AFFECTS")
    cash = create_account(db_session, "CASH-CHARGE-AFFECTS")
    equity = create_account(db_session, "EQUITY-CHARGE-AFFECTS", "owner_equity")
    expense = create_account(db_session, "EXP-CHARGE-AFFECTS", "expense")
    post(
        client,
        "/transactions/opening-balance/post",
        {
            "transaction_date": "2026-05-15",
            "created_by_user_id": user.id,
            "account_id": cash.id,
            "equity_account_id": equity.id,
            "amount": "25.00",
            "currency": "USD",
        },
    )
    post(
        client,
        "/transactions/expense/post",
        {
            "transaction_date": "2026-05-15",
            "created_by_user_id": user.id,
            "settlement_id": settlement.id,
            "payment_account_id": cash.id,
            "expense_account_id": expense.id,
            "amount": "5.00",
            "currency": "USD",
            "expense_type": "transfer_charge",
            "affects_settlement": True,
        },
    )

    blocked = client.post(f"/settlements/{settlement.id}/close", json={"user_id": user.id})
    approved = client.post(
        f"/settlements/{settlement.id}/close",
        json={
            "user_id": user.id,
            "approved_pending_amount": "5.00",
            "approved_pending_currency": "USD",
            "approved_pending_reason": "Charge remains in settlement",
            "admin_approved_pending": True,
        },
    )

    assert blocked.status_code == 400
    assert approved.status_code == 200


def test_reopen_then_allows_new_posting(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    settlement = create_settlement(db_session, number="SET-REOPEN-POST")
    _, clearing = make_balanced_settlement(client, db_session, user, settlement)
    client.post(f"/settlements/{settlement.id}/close", json={"user_id": user.id})
    reopen = client.post(f"/settlements/{settlement.id}/reopen", json={"user_id": user.id, "reason": "Add late receipt"})
    cash = create_account(db_session, "CASH-REOPEN-LATE")

    receipt = post(
        client,
        "/transactions/receipt/post",
        {
            "transaction_date": "2026-05-15",
            "created_by_user_id": user.id,
            "settlement_id": settlement.id,
            "receiving_account_id": cash.id,
            "clearing_account_id": clearing.id,
            "gross_amount": "7.00",
            "principal_amount": "7.00",
            "currency": "USD",
        },
    )

    assert reopen.status_code == 200
    assert receipt["status"] == "posted"


def test_cancel_already_cancelled_settlement_blocked(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    settlement = create_settlement(db_session, status="cancelled", number="SET-CANCELLED-TWICE")

    response = client.post(f"/settlements/{settlement.id}/cancel", json={"user_id": user.id})

    assert response.status_code == 400


def test_closing_cancelled_settlement_blocked(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    settlement = create_settlement(db_session, status="cancelled", number="SET-CANCELLED-CLOSE")

    response = client.post(f"/settlements/{settlement.id}/close", json={"user_id": user.id})

    assert response.status_code == 400


def test_reopening_cancelled_settlement_blocked(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    settlement = create_settlement(db_session, status="cancelled", number="SET-CANCELLED-REOPEN")

    response = client.post(f"/settlements/{settlement.id}/reopen", json={"user_id": user.id, "reason": "Wrong status"})

    assert response.status_code == 400


def test_pending_closure_values_survive_reopen_and_reclose(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    settlement = create_settlement(db_session, number="SET-PENDING-CYCLE")
    cash = create_account(db_session, "CASH-PENDING-CYCLE")
    clearing = create_account(db_session, "CLEARING-PENDING-CYCLE", "clearing")
    post(
        client,
        "/transactions/receipt/post",
        {
            "transaction_date": "2026-05-15",
            "created_by_user_id": user.id,
            "settlement_id": settlement.id,
            "receiving_account_id": cash.id,
            "clearing_account_id": clearing.id,
            "gross_amount": "11.00",
            "principal_amount": "11.00",
            "currency": "USD",
        },
    )

    first_close = client.post(
        f"/settlements/{settlement.id}/close",
        json={
            "user_id": user.id,
            "approved_pending_amount": "11.00",
            "approved_pending_currency": "USD",
            "approved_pending_reason": "Original pending",
            "admin_approved_pending": True,
        },
    )
    reopen = client.post(f"/settlements/{settlement.id}/reopen", json={"user_id": user.id, "reason": "Review pending"})
    second_close = client.post(
        f"/settlements/{settlement.id}/close",
        json={
            "user_id": user.id,
            "approved_pending_amount": "11.00",
            "approved_pending_currency": "USD",
            "approved_pending_reason": "Reapproved pending",
            "admin_approved_pending": True,
        },
    )

    db_session.refresh(settlement)
    assert first_close.status_code == 200
    assert reopen.status_code == 200
    assert second_close.status_code == 200
    assert settlement.status == "closed"
    assert settlement.approved_pending_amount == Decimal("11.000000")
    assert settlement.approved_pending_currency == "USD"
    assert settlement.approved_pending_reason == "Reapproved pending"


def test_closure_preview_leaves_database_unchanged(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    settlement = create_settlement(db_session, number="SET-PREVIEW-UNCHANGED")
    make_balanced_settlement(client, db_session, user, settlement)
    before = {
        "status": settlement.status,
        "closed_at": settlement.closed_at,
        "closed_by_user_id": settlement.closed_by_user_id,
        "approved_pending_amount": settlement.approved_pending_amount,
        "approved_pending_currency": settlement.approved_pending_currency,
        "audit_count": db_session.query(AuditLog).count(),
        "transaction_count": db_session.query(Transaction).count(),
    }

    response = client.post(f"/settlements/{settlement.id}/close/preview", json={"user_id": user.id})

    db_session.refresh(settlement)
    assert response.status_code == 200
    assert settlement.status == before["status"]
    assert settlement.closed_at == before["closed_at"]
    assert settlement.closed_by_user_id == before["closed_by_user_id"]
    assert settlement.approved_pending_amount == before["approved_pending_amount"]
    assert settlement.approved_pending_currency == before["approved_pending_currency"]
    assert db_session.query(AuditLog).count() == before["audit_count"]
    assert db_session.query(Transaction).count() == before["transaction_count"]


def test_settlement_balance_after_reversal_chain_is_zero(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    settlement = create_settlement(db_session, number="SET-REVERSAL-BALANCE")
    cash = create_account(db_session, "CASH-REVERSAL-BALANCE")
    clearing = create_account(db_session, "CLEARING-REVERSAL-BALANCE", "clearing")
    receipt = post(
        client,
        "/transactions/receipt/post",
        {
            "transaction_date": "2026-05-15",
            "created_by_user_id": user.id,
            "settlement_id": settlement.id,
            "receiving_account_id": cash.id,
            "clearing_account_id": clearing.id,
            "gross_amount": "13.00",
            "principal_amount": "13.00",
            "currency": "USD",
        },
    )
    post(
        client,
        f"/transactions/{receipt['transaction_id']}/reverse/post",
        {"created_by_user_id": user.id, "transaction_date": "2026-05-15", "reversal_reason": "Settlement correction"},
    )

    balance = client.get(f"/settlements/{settlement.id}/balance")

    assert balance.status_code == 200
    assert Decimal(balance.json()["balances"]["USD"]) == Decimal("0.000000")
    assert balance.json()["is_balanced_by_currency"] is True
