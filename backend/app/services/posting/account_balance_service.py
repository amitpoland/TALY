from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.enums import ACCOUNT_NORMAL_BALANCE, AccountType, NormalBalance
from app.models.account import Account
from app.services.posting.dtos import BalanceEffect, LedgerEntryDraft


def calculate_new_balance(account: Account, debit: Decimal, credit: Decimal) -> Decimal:
    normal = ACCOUNT_NORMAL_BALANCE[AccountType(account.account_type)]
    if normal == NormalBalance.DEBIT:
        return account.current_balance + debit - credit
    return account.current_balance + credit - debit


def preview_balance_effects(db: Session, entries: list[LedgerEntryDraft]) -> list[BalanceEffect]:
    balances: dict[int, Decimal] = {}
    currencies: dict[int, str] = {}
    for entry in entries:
        account = db.get(Account, entry.account_id)
        if account is None:
            raise HTTPException(status_code=400, detail=f"Account {entry.account_id} does not exist")
        before = balances.get(account.id, account.current_balance)
        account_snapshot = Account(
            account_code=account.account_code,
            name=account.name,
            account_type=account.account_type,
            currency=account.currency,
            current_balance=before,
        )
        balances[account.id] = calculate_new_balance(account_snapshot, entry.debit, entry.credit)
        currencies[account.id] = account.currency
    return [
        BalanceEffect(account_id=account_id, before=db.get(Account, account_id).current_balance, after=after, currency=currencies[account_id])
        for account_id, after in balances.items()
    ]


def apply_ledger_entries_to_balances(db: Session, entries: list[LedgerEntryDraft]) -> None:
    for entry in entries:
        account = db.get(Account, entry.account_id)
        if account is None:
            raise HTTPException(status_code=400, detail=f"Account {entry.account_id} does not exist")
        account.current_balance = calculate_new_balance(account, entry.debit, entry.credit)

