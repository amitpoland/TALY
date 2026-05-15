from decimal import Decimal

from pydantic import BaseModel, field_validator

from app.schemas.common import MoneyModel, ORMModel


class SettlementCreate(BaseModel):
    settlement_no: str
    title: str
    primary_party_id: int | None = None
    base_currency: str = "USD"

    @field_validator("settlement_no", "title", "base_currency")
    @classmethod
    def required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Value is required")
        return value.strip()


class SettlementUpdate(BaseModel):
    title: str | None = None
    primary_party_id: int | None = None
    base_currency: str | None = None

    @field_validator("title", "base_currency")
    @classmethod
    def optional_text(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Value cannot be blank")
        return value.strip() if value is not None else None


class SettlementRead(ORMModel):
    id: int
    settlement_no: str
    title: str
    primary_party_id: int | None
    status: str
    base_currency: str
    opened_at: str
    closed_at: str | None
    closed_by_user_id: int | None
    approved_pending_amount: Decimal
    approved_pending_currency: str | None
    approved_pending_reason: str | None


class SettlementCloseRequest(MoneyModel):
    user_id: int
    approved_pending_amount: Decimal = Decimal("0")
    approved_pending_currency: str | None = None
    approved_pending_reason: str | None = None
    admin_approved_pending: bool = False


class SettlementReopenRequest(BaseModel):
    user_id: int
    reason: str
    admin_approved_reopen: bool = True

    @field_validator("reason")
    @classmethod
    def reason_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Reopen reason is required")
        return value


class SettlementCancelRequest(BaseModel):
    user_id: int
    reason: str | None = None


class SettlementClosurePreviewRead(BaseModel):
    settlement_id: int
    settlement_no: str
    status: str
    principal_balance_by_currency: dict[str, Decimal]
    profitability_summary: dict[str, Decimal]
    fx_gain_loss_summary: dict[str, Decimal]
    commissions_summary: dict[str, Decimal]
    expenses_summary: dict[str, Decimal]
    pending_amount: Decimal | None = None
    pending_currency: str | None = None
    warnings: list[str]
    errors: list[str]
    can_close: bool
