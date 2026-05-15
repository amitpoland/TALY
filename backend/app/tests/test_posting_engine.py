from decimal import Decimal

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.ledger_entry import LedgerEntry
from app.models.role import Role
from app.models.settlement import Settlement
from app.models.transaction import Transaction
from app.models.transaction_component import TransactionComponent
from app.models.user import User
from app.models.common import utcnow
from app.services.posting.validation import ensure_posted_transaction_is_immutable


def create_user(db: Session) -> User:
    role = db.query(Role).filter(Role.name == "admin").one()
    user = User(
        username="poster",
        password_hash="test",
        full_name="Poster",
        role_id=role.id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_account(
    db: Session,
    code: str,
    account_type: str,
    currency: str = "USD",
    party_id: int | None = None,
) -> Account:
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


def create_settlement(db: Session) -> Settlement:
    settlement = Settlement(
        settlement_no="SET-0001",
        title="Test settlement",
        status="open",
        base_currency="USD",
        opened_at=utcnow(),
    )
    db.add(settlement)
    db.commit()
    db.refresh(settlement)
    return settlement


def post(client: TestClient, path: str, payload: dict) -> dict:
    response = client.post(
        path,
        json={
            "payload": payload,
            "confirmation": {"confirmed_by_user": True},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def opening_payload(user: User, account: Account, equity: Account, amount: str = "1000.00") -> dict:
    return {
        "transaction_date": "2026-05-15",
        "created_by_user_id": user.id,
        "account_id": account.id,
        "equity_account_id": equity.id,
        "amount": amount,
        "currency": account.currency,
    }


def test_opening_balance_transaction_updates_balances(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    cash = create_account(db_session, "CASH-USD", "cash")
    equity = create_account(db_session, "EQUITY-USD", "owner_equity")

    result = post(client, "/transactions/opening-balance/post", opening_payload(user, cash, equity))

    db_session.refresh(cash)
    db_session.refresh(equity)
    assert result["transaction_type"] == "opening_balance"
    assert cash.current_balance == Decimal("1000.000000")
    assert cash.opening_balance == Decimal("1000.000000")
    assert equity.current_balance == Decimal("1000.000000")


def test_receipt_with_included_commission_posts_components_and_ledger(
    client: TestClient, db_session: Session
) -> None:
    user = create_user(db_session)
    settlement = create_settlement(db_session)
    cash = create_account(db_session, "CASH-USD", "cash")
    clearing = create_account(db_session, "CLEARING-USD", "clearing")
    commission = create_account(db_session, "COMM-USD", "commission_income")

    payload = {
        "transaction_date": "2026-05-15",
        "created_by_user_id": user.id,
        "settlement_id": settlement.id,
        "receiving_account_id": cash.id,
        "clearing_account_id": clearing.id,
        "gross_amount": "100.00",
        "principal_amount": "98.00",
        "commission_amount": "2.00",
        "commission_income_account_id": commission.id,
        "currency": "USD",
    }
    preview = client.post("/transactions/receipt/preview", json=payload)
    assert preview.status_code == 200
    assert len(preview.json()["components"]) == 3

    result = post(client, "/transactions/receipt/post", payload)

    db_session.refresh(cash)
    db_session.refresh(clearing)
    db_session.refresh(commission)
    assert result["status"] == "posted"
    assert cash.current_balance == Decimal("100.000000")
    assert clearing.current_balance == Decimal("-98.000000")
    assert commission.current_balance == Decimal("2.000000")
    assert db_session.query(TransactionComponent).count() == 3
    assert db_session.query(LedgerEntry).count() == 3


def test_payment_posting_updates_settlement_and_account_balances(
    client: TestClient, db_session: Session
) -> None:
    user = create_user(db_session)
    settlement = create_settlement(db_session)
    cash = create_account(db_session, "CASH-USD", "cash")
    equity = create_account(db_session, "EQUITY-USD", "owner_equity")
    clearing = create_account(db_session, "CLEARING-USD", "clearing")
    post(client, "/transactions/opening-balance/post", opening_payload(user, cash, equity, "100.00"))

    result = post(
        client,
        "/transactions/payment/post",
        {
            "transaction_date": "2026-05-15",
            "created_by_user_id": user.id,
            "settlement_id": settlement.id,
            "paying_account_id": cash.id,
            "clearing_account_id": clearing.id,
            "amount": "25.00",
            "currency": "USD",
        },
    )

    db_session.refresh(cash)
    db_session.refresh(clearing)
    assert result["transaction_type"] == "payment"
    assert cash.current_balance == Decimal("75.000000")
    assert clearing.current_balance == Decimal("25.000000")
    balance = client.get(f"/settlements/{settlement.id}/balance")
    assert balance.status_code == 200
    assert balance.json()["balances"]["USD"] == -25


def test_cash_handover_and_bank_transfer(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    cash_a = create_account(db_session, "CASH-A-USD", "cash")
    cash_b = create_account(db_session, "CASH-B-USD", "cash")
    bank_a = create_account(db_session, "BANK-A-USD", "bank")
    bank_b = create_account(db_session, "BANK-B-USD", "bank")
    equity = create_account(db_session, "EQUITY-USD", "owner_equity")
    post(client, "/transactions/opening-balance/post", opening_payload(user, cash_a, equity, "100.00"))
    post(client, "/transactions/opening-balance/post", opening_payload(user, bank_a, equity, "200.00"))

    cash_result = post(
        client,
        "/transactions/cash-handover/post",
        {
            "transaction_date": "2026-05-15",
            "created_by_user_id": user.id,
            "from_account_id": cash_a.id,
            "to_account_id": cash_b.id,
            "amount": "40.00",
            "currency": "USD",
        },
    )
    bank_result = post(
        client,
        "/transactions/bank-transfer/post",
        {
            "transaction_date": "2026-05-15",
            "created_by_user_id": user.id,
            "from_account_id": bank_a.id,
            "to_account_id": bank_b.id,
            "amount": "125.00",
            "currency": "USD",
        },
    )

    db_session.refresh(cash_a)
    db_session.refresh(cash_b)
    db_session.refresh(bank_a)
    db_session.refresh(bank_b)
    assert cash_result["transaction_type"] == "cash_handover"
    assert bank_result["transaction_type"] == "bank_transfer"
    assert cash_a.current_balance == Decimal("60.000000")
    assert cash_b.current_balance == Decimal("40.000000")
    assert bank_a.current_balance == Decimal("75.000000")
    assert bank_b.current_balance == Decimal("125.000000")


def test_expense_posting_creates_detail_and_profitability_effect(
    client: TestClient, db_session: Session
) -> None:
    user = create_user(db_session)
    bank = create_account(db_session, "BANK-USD", "bank")
    expense = create_account(db_session, "BANK-CHARGE-USD", "bank_charge_expense")
    equity = create_account(db_session, "EQUITY-USD", "owner_equity")
    post(client, "/transactions/opening-balance/post", opening_payload(user, bank, equity, "100.00"))

    result = post(
        client,
        "/transactions/expense/post",
        {
            "transaction_date": "2026-05-15",
            "created_by_user_id": user.id,
            "payment_account_id": bank.id,
            "expense_account_id": expense.id,
            "amount": "5.00",
            "currency": "USD",
            "expense_type": "bank_charge",
        },
    )

    db_session.refresh(bank)
    db_session.refresh(expense)
    assert Decimal(result["profitability_effect"]["USD"]) == Decimal("-5.00")
    assert bank.current_balance == Decimal("95.000000")
    assert expense.current_balance == Decimal("5.000000")


def test_reversal_creates_inverse_entries_and_marks_original_reversed(
    client: TestClient, db_session: Session
) -> None:
    user = create_user(db_session)
    cash = create_account(db_session, "CASH-USD", "cash")
    equity = create_account(db_session, "EQUITY-USD", "owner_equity")
    original = post(client, "/transactions/opening-balance/post", opening_payload(user, cash, equity, "50.00"))

    reversal = post(
        client,
        f"/transactions/{original['transaction_id']}/reverse/post",
        {
            "created_by_user_id": user.id,
            "transaction_date": "2026-05-15",
            "reversal_reason": "Wrong opening amount",
        },
    )

    db_session.refresh(cash)
    original_txn = db_session.get(Transaction, original["transaction_id"])
    assert reversal["transaction_type"] == "reversal"
    assert original_txn.status == "reversed"
    assert cash.current_balance == Decimal("0.000000")


def test_reversal_clears_settlement_balance(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    settlement = create_settlement(db_session)
    cash = create_account(db_session, "CASH-USD", "cash")
    clearing = create_account(db_session, "CLEARING-USD", "clearing")
    commission = create_account(db_session, "COMM-USD", "commission_income")

    original = post(
        client,
        "/transactions/receipt/post",
        {
            "transaction_date": "2026-05-15",
            "created_by_user_id": user.id,
            "settlement_id": settlement.id,
            "receiving_account_id": cash.id,
            "clearing_account_id": clearing.id,
            "gross_amount": "100.00",
            "principal_amount": "98.00",
            "commission_amount": "2.00",
            "commission_income_account_id": commission.id,
            "currency": "USD",
        },
    )
    before = client.get(f"/settlements/{settlement.id}/balance")
    assert before.json()["balances"]["USD"] == 98

    post(
        client,
        f"/transactions/{original['transaction_id']}/reverse/post",
        {
            "created_by_user_id": user.id,
            "transaction_date": "2026-05-15",
            "reversal_reason": "Wrong receipt",
        },
    )

    after = client.get(f"/settlements/{settlement.id}/balance")
    assert after.json()["balances"]["USD"] == 0
    assert after.json()["is_balanced_by_currency"] is True


def test_validation_failures_and_immutable_protection(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    cash = create_account(db_session, "CASH-USD", "cash")
    clearing = create_account(db_session, "CLEARING-USD", "clearing")

    response = client.post(
        "/transactions/payment/preview",
        json={
            "transaction_date": "2026-05-15",
            "created_by_user_id": user.id,
            "paying_account_id": cash.id,
            "clearing_account_id": clearing.id,
            "amount": "1.00",
            "currency": "USD",
        },
    )
    assert response.status_code == 400
    assert "Cash negative balance is blocked" in response.text

    tx = Transaction(
        transaction_no="TXN-IMMUTABLE",
        transaction_type="receipt",
        transaction_date="2026-05-15",
        status="posted",
        created_by_user_id=user.id,
    )
    with pytest.raises(HTTPException):
        ensure_posted_transaction_is_immutable(tx)
