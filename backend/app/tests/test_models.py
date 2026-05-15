from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.enums import ACCOUNT_NORMAL_BALANCE, AccountType, NormalBalance
from app.models.account import Account


def test_money_fields_use_decimal(db_session: Session) -> None:
    account = Account(
        account_code="CASH-USD",
        name="Main Cash USD",
        account_type=AccountType.CASH.value,
        currency="USD",
        opening_balance=Decimal("0"),
        current_balance=Decimal("0"),
    )
    db_session.add(account)
    db_session.commit()

    saved = db_session.query(Account).filter(Account.account_code == "CASH-USD").one()
    assert isinstance(saved.current_balance, Decimal)


def test_normal_balance_policy_is_final_decision() -> None:
    assert ACCOUNT_NORMAL_BALANCE[AccountType.CASH] == NormalBalance.DEBIT
    assert ACCOUNT_NORMAL_BALANCE[AccountType.BANK] == NormalBalance.DEBIT
    assert ACCOUNT_NORMAL_BALANCE[AccountType.EXPENSE] == NormalBalance.DEBIT
    assert ACCOUNT_NORMAL_BALANCE[AccountType.COMMISSION_INCOME] == NormalBalance.CREDIT
    assert ACCOUNT_NORMAL_BALANCE[AccountType.OWNER_EQUITY] == NormalBalance.CREDIT

