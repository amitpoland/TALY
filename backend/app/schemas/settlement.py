from decimal import Decimal

from pydantic import BaseModel, field_validator

from app.schemas.common import MoneyModel


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

