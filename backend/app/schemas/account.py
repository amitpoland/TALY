from decimal import Decimal

from pydantic import Field, field_validator

from app.core.enums import AccountType
from app.schemas.common import MoneyModel, ORMModel


class AccountCreate(MoneyModel):
    account_code: str
    name: str
    account_type: AccountType
    currency: str
    party_id: int | None = None
    opening_balance: Decimal = Field(default=Decimal("0"))

    @field_validator("opening_balance")
    @classmethod
    def opening_balance_must_wait_for_posting_engine(cls, value: Decimal) -> Decimal:
        if value != Decimal("0"):
            raise ValueError("Opening balances must be posted through opening balance transactions")
        return value


class AccountUpdate(MoneyModel):
    name: str | None = None
    is_active: bool | None = None


class AccountRead(ORMModel):
    id: int
    account_code: str
    name: str
    account_type: str
    currency: str
    party_id: int | None
    opening_balance: Decimal
    current_balance: Decimal
    is_active: bool

