from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common import MoneyModel


class Confirmation(BaseModel):
    confirmed_by_user: bool = True
    confirmation_note: str | None = None


class PostingRequest(BaseModel):
    payload: dict
    confirmation: Confirmation


class PostingComponentRead(BaseModel):
    sequence_no: int
    component_type: str
    amount: Decimal
    currency: str
    direction: str
    account_id: int | None = None
    party_id: int | None = None
    affects_settlement: bool = False
    settlement_effect_type: str | None = None
    affects_profitability: bool = False
    profitability_effect_type: str | None = None
    linked_detail_type: str | None = None
    notes: str | None = None


class PostingLedgerEntryRead(BaseModel):
    account_id: int
    debit: Decimal
    credit: Decimal
    currency: str
    description: str | None = None


class BalanceEffectRead(BaseModel):
    account_id: int
    before: Decimal
    after: Decimal
    currency: str


class PostingPreviewRead(BaseModel):
    transaction_type: str
    gross_amount: Decimal | None
    gross_currency: str | None
    components: list[PostingComponentRead]
    ledger_entries: list[PostingLedgerEntryRead]
    account_balance_effects: list[BalanceEffectRead]
    settlement_effect: dict[str, Decimal]
    profitability_effect: dict[str, Decimal]
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class PostingResultRead(PostingPreviewRead):
    transaction_id: int
    transaction_no: str
    status: str
    posted_at: str
    audit_log_id: int | None


class BasePostingPayload(MoneyModel):
    transaction_date: str
    created_by_user_id: int
    settlement_id: int | None = None
    description: str | None = None


class OpeningBalancePayload(BasePostingPayload):
    account_id: int
    equity_account_id: int
    amount: Decimal
    currency: str


class ReceiptPayload(BasePostingPayload):
    receiving_account_id: int
    clearing_account_id: int
    gross_amount: Decimal
    principal_amount: Decimal
    currency: str
    commission_amount: Decimal = Decimal("0")
    commission_income_account_id: int | None = None

    @model_validator(mode="after")
    def validate_receipt_amounts(self):
        if self.gross_amount <= 0 or self.principal_amount <= 0:
            raise ValueError("Receipt amounts must be positive")
        if self.commission_amount < 0:
            raise ValueError("Commission cannot be negative")
        if self.principal_amount + self.commission_amount != self.gross_amount:
            raise ValueError("Principal plus included commission must equal gross amount")
        if self.commission_amount > 0 and self.commission_income_account_id is None:
            raise ValueError("Commission income account is required when commission is included")
        return self


class PaymentPayload(BasePostingPayload):
    paying_account_id: int
    clearing_account_id: int
    amount: Decimal
    currency: str


class TransferPayload(BasePostingPayload):
    from_account_id: int
    to_account_id: int
    amount: Decimal
    currency: str

    @model_validator(mode="after")
    def validate_transfer(self):
        if self.from_account_id == self.to_account_id:
            raise ValueError("From and to accounts cannot be the same")
        return self


class ExpensePayload(BasePostingPayload):
    payment_account_id: int
    expense_account_id: int
    amount: Decimal
    currency: str
    expense_type: str = "other"
    affects_settlement: bool = False


class ReversePayload(MoneyModel):
    created_by_user_id: int
    transaction_date: str
    reversal_reason: str

    @field_validator("reversal_reason")
    @classmethod
    def reason_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Reversal reason is required")
        return value
