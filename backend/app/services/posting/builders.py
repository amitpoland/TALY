from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.enums import (
    AccountType,
    ComponentType,
    Direction,
    ProfitabilityEffectType,
    SettlementEffectType,
    TransactionType,
)
from app.schemas.posting import (
    ExpensePayload,
    OpeningBalancePayload,
    PaymentPayload,
    ReceiptPayload,
    TransferPayload,
)
from app.services.posting.account_balance_service import preview_balance_effects
from app.services.posting.dtos import ComponentDraft, LedgerEntryDraft, PostingPreview
from app.services.posting.validation import (
    MOVEMENT_ACCOUNT_TYPES,
    ensure_account_currency,
    ensure_account_type,
    ensure_currency,
    ensure_positive,
    ensure_settlement_open,
    ensure_sufficient_balance,
    ensure_user,
    get_account,
)


def _settlement_effect(components: list[ComponentDraft]) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = {}
    for component in components:
        if not component.affects_settlement:
            continue
        sign = Decimal("1")
        if component.settlement_effect_type in {
            SettlementEffectType.PRINCIPAL_OUT.value,
            SettlementEffectType.ADJUSTMENT_OUT.value,
        }:
            sign = Decimal("-1")
        totals[component.currency] = totals.get(component.currency, Decimal("0")) + sign * component.amount
    return totals


def _profitability_effect(components: list[ComponentDraft]) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = {}
    for component in components:
        if not component.affects_profitability:
            continue
        sign = Decimal("1") if component.profitability_effect_type == ProfitabilityEffectType.INCOME.value else Decimal("-1")
        totals[component.currency] = totals.get(component.currency, Decimal("0")) + sign * component.amount
    return totals


def _preview(
    db: Session,
    *,
    transaction_type: str,
    gross_amount: Decimal | None,
    gross_currency: str | None,
    components: list[ComponentDraft],
    ledger_entries: list[LedgerEntryDraft],
    warnings: list[str] | None = None,
) -> PostingPreview:
    return PostingPreview(
        transaction_type=transaction_type,
        gross_amount=gross_amount,
        gross_currency=gross_currency,
        components=components,
        ledger_entries=ledger_entries,
        account_balance_effects=preview_balance_effects(db, ledger_entries),
        settlement_effect=_settlement_effect(components),
        profitability_effect=_profitability_effect(components),
        warnings=warnings or [],
        errors=[],
    )


def build_opening_balance_preview(db: Session, payload: OpeningBalancePayload) -> PostingPreview:
    ensure_positive(payload.amount)
    ensure_user(db, payload.created_by_user_id)
    ensure_currency(db, payload.currency)
    account = get_account(db, payload.account_id)
    equity_account = get_account(db, payload.equity_account_id)
    if account.id == equity_account.id:
        raise HTTPException(status_code=400, detail="Opening account and equity account cannot be the same")
    ensure_account_currency(account, payload.currency)
    ensure_account_currency(equity_account, payload.currency)
    if account.current_balance != 0 or account.opening_balance != 0:
        raise HTTPException(status_code=400, detail="Opening balance can only be posted to a zero-balance account")

    if account.account_type in {
        AccountType.COMMISSION_INCOME.value,
        AccountType.COMMISSION_PAYABLE.value,
        AccountType.OWNER_EQUITY.value,
    }:
        entries = [
            LedgerEntryDraft(equity_account.id, payload.amount, Decimal("0"), payload.currency, "Opening balance"),
            LedgerEntryDraft(account.id, Decimal("0"), payload.amount, payload.currency, "Opening balance"),
        ]
    else:
        entries = [
            LedgerEntryDraft(account.id, payload.amount, Decimal("0"), payload.currency, "Opening balance"),
            LedgerEntryDraft(equity_account.id, Decimal("0"), payload.amount, payload.currency, "Opening balance"),
        ]
    components = [
        ComponentDraft(
            1,
            ComponentType.OPENING_BALANCE.value,
            payload.amount,
            payload.currency,
            Direction.IN.value,
            account_id=account.id,
            notes="Opening balances are posted through transactions",
        )
    ]
    return _preview(
        db,
        transaction_type=TransactionType.OPENING_BALANCE.value,
        gross_amount=payload.amount,
        gross_currency=payload.currency,
        components=components,
        ledger_entries=entries,
    )


def build_receipt_preview(db: Session, payload: ReceiptPayload) -> PostingPreview:
    ensure_user(db, payload.created_by_user_id)
    ensure_settlement_open(db, payload.settlement_id)
    ensure_currency(db, payload.currency)
    receiving = get_account(db, payload.receiving_account_id)
    clearing = get_account(db, payload.clearing_account_id)
    ensure_account_currency(receiving, payload.currency)
    ensure_account_currency(clearing, payload.currency)
    ensure_account_type(receiving, MOVEMENT_ACCOUNT_TYPES, "Receiving")

    components = [
        ComponentDraft(1, ComponentType.GROSS_RECEIPT.value, payload.gross_amount, payload.currency, Direction.IN.value, account_id=receiving.id),
        ComponentDraft(
            2,
            ComponentType.PRINCIPAL.value,
            payload.principal_amount,
            payload.currency,
            Direction.IN.value,
            account_id=clearing.id,
            affects_settlement=payload.settlement_id is not None,
            settlement_effect_type=SettlementEffectType.PRINCIPAL_IN.value,
        ),
    ]
    entries = [
        LedgerEntryDraft(receiving.id, payload.gross_amount, Decimal("0"), payload.currency, "Receipt"),
        LedgerEntryDraft(clearing.id, Decimal("0"), payload.principal_amount, payload.currency, "Receipt principal"),
    ]
    if payload.commission_amount > 0:
        commission_account = get_account(db, payload.commission_income_account_id)
        ensure_account_currency(commission_account, payload.currency)
        ensure_account_type(commission_account, {AccountType.COMMISSION_INCOME.value}, "Commission income")
        components.append(
            ComponentDraft(
                3,
                ComponentType.YOUR_COMMISSION.value,
                payload.commission_amount,
                payload.currency,
                Direction.IN.value,
                account_id=commission_account.id,
                affects_profitability=True,
                profitability_effect_type=ProfitabilityEffectType.INCOME.value,
                linked_detail_type="commission",
            )
        )
        entries.append(
            LedgerEntryDraft(
                commission_account.id,
                Decimal("0"),
                payload.commission_amount,
                payload.currency,
                "Included commission",
            )
        )
    return _preview(db, transaction_type=TransactionType.RECEIPT.value, gross_amount=payload.gross_amount, gross_currency=payload.currency, components=components, ledger_entries=entries)


def build_payment_preview(db: Session, payload: PaymentPayload) -> PostingPreview:
    ensure_positive(payload.amount)
    ensure_user(db, payload.created_by_user_id)
    ensure_settlement_open(db, payload.settlement_id)
    ensure_currency(db, payload.currency)
    paying = get_account(db, payload.paying_account_id)
    clearing = get_account(db, payload.clearing_account_id)
    ensure_account_currency(paying, payload.currency)
    ensure_account_currency(clearing, payload.currency)
    ensure_account_type(paying, MOVEMENT_ACCOUNT_TYPES, "Paying")
    warning = ensure_sufficient_balance(paying, payload.amount, permission_granted=False)

    components = [
        ComponentDraft(
            1,
            ComponentType.PRINCIPAL.value,
            payload.amount,
            payload.currency,
            Direction.OUT.value,
            account_id=clearing.id,
            affects_settlement=payload.settlement_id is not None,
            settlement_effect_type=SettlementEffectType.PRINCIPAL_OUT.value,
        )
    ]
    entries = [
        LedgerEntryDraft(clearing.id, payload.amount, Decimal("0"), payload.currency, "Payment principal"),
        LedgerEntryDraft(paying.id, Decimal("0"), payload.amount, payload.currency, "Payment"),
    ]
    return _preview(db, transaction_type=TransactionType.PAYMENT.value, gross_amount=payload.amount, gross_currency=payload.currency, components=components, ledger_entries=entries, warnings=[warning] if warning else [])


def build_cash_handover_preview(db: Session, payload: TransferPayload) -> PostingPreview:
    return _build_transfer_preview(
        db,
        payload,
        transaction_type=TransactionType.CASH_HANDOVER.value,
        component_type=ComponentType.CASH_MOVEMENT.value,
        allowed_types={AccountType.CASH.value, AccountType.AGENT_WALLET.value, AccountType.CUSTOMER_WALLET.value},
    )


def build_bank_transfer_preview(db: Session, payload: TransferPayload) -> PostingPreview:
    return _build_transfer_preview(
        db,
        payload,
        transaction_type=TransactionType.BANK_TRANSFER.value,
        component_type=ComponentType.BANK_MOVEMENT.value,
        allowed_types={AccountType.BANK.value},
    )


def _build_transfer_preview(
    db: Session,
    payload: TransferPayload,
    *,
    transaction_type: str,
    component_type: str,
    allowed_types: set[str],
) -> PostingPreview:
    ensure_positive(payload.amount)
    ensure_user(db, payload.created_by_user_id)
    ensure_settlement_open(db, payload.settlement_id)
    ensure_currency(db, payload.currency)
    from_account = get_account(db, payload.from_account_id)
    to_account = get_account(db, payload.to_account_id)
    ensure_account_currency(from_account, payload.currency)
    ensure_account_currency(to_account, payload.currency)
    ensure_account_type(from_account, allowed_types, "From")
    ensure_account_type(to_account, allowed_types, "To")
    warning = ensure_sufficient_balance(from_account, payload.amount, permission_granted=False)
    components = [
        ComponentDraft(1, component_type, payload.amount, payload.currency, Direction.OUT.value, account_id=from_account.id),
        ComponentDraft(2, component_type, payload.amount, payload.currency, Direction.IN.value, account_id=to_account.id),
    ]
    entries = [
        LedgerEntryDraft(to_account.id, payload.amount, Decimal("0"), payload.currency, transaction_type),
        LedgerEntryDraft(from_account.id, Decimal("0"), payload.amount, payload.currency, transaction_type),
    ]
    return _preview(db, transaction_type=transaction_type, gross_amount=payload.amount, gross_currency=payload.currency, components=components, ledger_entries=entries, warnings=[warning] if warning else [])


def build_expense_preview(db: Session, payload: ExpensePayload) -> PostingPreview:
    ensure_positive(payload.amount)
    ensure_user(db, payload.created_by_user_id)
    ensure_settlement_open(db, payload.settlement_id)
    ensure_currency(db, payload.currency)
    payment_account = get_account(db, payload.payment_account_id)
    expense_account = get_account(db, payload.expense_account_id)
    ensure_account_currency(payment_account, payload.currency)
    ensure_account_currency(expense_account, payload.currency)
    ensure_account_type(payment_account, MOVEMENT_ACCOUNT_TYPES, "Payment")
    ensure_account_type(expense_account, {AccountType.EXPENSE.value, AccountType.BANK_CHARGE_EXPENSE.value}, "Expense")
    warning = ensure_sufficient_balance(payment_account, payload.amount, permission_granted=False)
    components = [
        ComponentDraft(
            1,
            ComponentType.EXPENSE.value,
            payload.amount,
            payload.currency,
            Direction.OUT.value,
            account_id=expense_account.id,
            affects_settlement=payload.affects_settlement,
            settlement_effect_type=SettlementEffectType.CHARGE_IN_SETTLEMENT.value if payload.affects_settlement else None,
            affects_profitability=True,
            profitability_effect_type=ProfitabilityEffectType.EXPENSE.value,
            linked_detail_type="expense",
            notes=payload.expense_type,
        )
    ]
    entries = [
        LedgerEntryDraft(expense_account.id, payload.amount, Decimal("0"), payload.currency, "Expense"),
        LedgerEntryDraft(payment_account.id, Decimal("0"), payload.amount, payload.currency, "Expense payment"),
    ]
    return _preview(db, transaction_type=TransactionType.EXPENSE.value, gross_amount=payload.amount, gross_currency=payload.currency, components=components, ledger_entries=entries, warnings=[warning] if warning else [])
