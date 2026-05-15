from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.enums import AccountType
from app.models.account import Account
from app.models.currency import Currency
from app.models.settlement import Settlement
from app.models.transaction import Transaction
from app.models.user import User


MOVEMENT_ACCOUNT_TYPES = {
    AccountType.CASH.value,
    AccountType.BANK.value,
    AccountType.CUSTOMER_WALLET.value,
    AccountType.AGENT_WALLET.value,
    AccountType.FX_DEALER_WALLET.value,
}


def ensure_positive(amount: Decimal, label: str = "Amount") -> None:
    if amount <= 0:
        raise HTTPException(status_code=400, detail=f"{label} must be positive")


def get_account(db: Session, account_id: int) -> Account:
    account = db.get(Account, account_id)
    if account is None or not account.is_active:
        raise HTTPException(status_code=400, detail=f"Account {account_id} is not active or does not exist")
    return account


def ensure_user(db: Session, user_id: int) -> None:
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=400, detail="User is not active or does not exist")


def ensure_currency(db: Session, code: str) -> None:
    currency = db.get(Currency, code)
    if currency is None or not currency.is_active:
        raise HTTPException(status_code=400, detail=f"Currency {code} is not active or does not exist")


def ensure_settlement_open(db: Session, settlement_id: int | None) -> None:
    if settlement_id is None:
        return
    settlement = db.get(Settlement, settlement_id)
    if settlement is None:
        raise HTTPException(status_code=400, detail="Settlement does not exist")
    if settlement.status not in {"open", "reopened"}:
        raise HTTPException(status_code=400, detail="Settlement is not open for posting")


def ensure_account_currency(account: Account, currency: str) -> None:
    if account.currency != currency:
        raise HTTPException(status_code=400, detail=f"Account {account.id} currency does not match {currency}")


def ensure_account_type(account: Account, allowed: set[str], label: str) -> None:
    if account.account_type not in allowed:
        raise HTTPException(status_code=400, detail=f"{label} account type is not allowed")


def ensure_sufficient_balance(account: Account, credit_amount: Decimal, *, permission_granted: bool = False) -> str | None:
    resulting_balance = account.current_balance - credit_amount
    if resulting_balance >= 0:
        return None
    if account.account_type == AccountType.CASH.value:
        raise HTTPException(status_code=400, detail="Cash negative balance is blocked")
    if account.account_type in {
        AccountType.BANK.value,
        AccountType.CUSTOMER_WALLET.value,
        AccountType.AGENT_WALLET.value,
        AccountType.FX_DEALER_WALLET.value,
    }:
        if not permission_granted:
            raise HTTPException(status_code=400, detail="Negative balance requires permission")
        return "Negative balance allowed by permission"
    return None


def ensure_posted_transaction_is_immutable(transaction: Transaction) -> None:
    if transaction.status in {"posted", "reversed"}:
        raise HTTPException(status_code=400, detail="Posted transactions are immutable; use reversal")
