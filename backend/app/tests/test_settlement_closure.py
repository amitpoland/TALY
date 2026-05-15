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


def create_account(db: Session, code: str, account_type: str = "cash") -> Account:
    account = Account(
        account_code=code,
        name=code,
        account_type=account_type,
        currency="USD",
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
