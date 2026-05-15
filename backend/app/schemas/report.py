from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class ReportFilters(BaseModel):
    date_from: str | None = None
    date_to: str | None = None
    currency: str | None = None
    party_id: int | None = None
    account_id: int | None = None
    settlement_id: int | None = None


class ReportRead(BaseModel):
    filters: ReportFilters
    rows: list[dict[str, Any]] = Field(default_factory=list)
    totals: dict[str, Decimal] = Field(default_factory=dict)


class DashboardReportRead(BaseModel):
    filters: ReportFilters
    cash_balances: dict[str, Decimal]
    bank_balances: dict[str, Decimal]
    pending_settlements: int
    closed_settlements: int
    commission_earned: dict[str, Decimal]
    expenses: dict[str, Decimal]
    fx_profit_loss: dict[str, Decimal]
    net_profitability: dict[str, Decimal]

