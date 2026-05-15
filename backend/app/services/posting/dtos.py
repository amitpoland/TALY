from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ComponentDraft:
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


@dataclass(frozen=True)
class LedgerEntryDraft:
    account_id: int
    debit: Decimal
    credit: Decimal
    currency: str
    description: str | None = None


@dataclass(frozen=True)
class BalanceEffect:
    account_id: int
    before: Decimal
    after: Decimal
    currency: str


@dataclass(frozen=True)
class PostingPreview:
    transaction_type: str
    gross_amount: Decimal | None
    gross_currency: str | None
    components: list[ComponentDraft]
    ledger_entries: list[LedgerEntryDraft]
    account_balance_effects: list[BalanceEffect]
    settlement_effect: dict[str, Decimal]
    profitability_effect: dict[str, Decimal]
    warnings: list[str]
    errors: list[str]

