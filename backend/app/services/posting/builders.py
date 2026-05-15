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
    FxConversionPayload,
    OpeningBalancePayload,
    PaymentPayload,
    ReceiptPayload,
    TransferPayload,
)
from app.services.posting.account_balance_service import preview_balance_effects
from app.services.posting.dtos import ComponentDraft, LedgerEntryDraft, PostingPreview
from app.services.posting.fx_lot_service import plan_fifo_lot_consumption
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
    fx_detail: dict[str, Decimal | str] | None = None,
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
        fx_detail=fx_detail,
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


def build_fx_conversion_preview(db: Session, payload: FxConversionPayload) -> PostingPreview:
    ensure_user(db, payload.created_by_user_id)
    ensure_settlement_open(db, payload.settlement_id)
    ensure_currency(db, payload.from_currency)
    ensure_currency(db, payload.to_currency)
    ensure_currency(db, payload.base_currency)
    from_account = get_account(db, payload.from_account_id)
    to_account = get_account(db, payload.to_account_id)
    source_clearing = get_account(db, payload.source_clearing_account_id)
    target_clearing = get_account(db, payload.target_clearing_account_id)
    gain_loss_account = get_account(db, payload.fx_gain_loss_account_id)
    ensure_account_currency(from_account, payload.from_currency)
    ensure_account_currency(to_account, payload.to_currency)
    ensure_account_currency(source_clearing, payload.from_currency)
    ensure_account_currency(target_clearing, payload.base_currency)
    ensure_account_currency(gain_loss_account, payload.base_currency)
    ensure_account_type(from_account, MOVEMENT_ACCOUNT_TYPES, "FX source")
    ensure_account_type(to_account, MOVEMENT_ACCOUNT_TYPES, "FX target")
    ensure_account_type(source_clearing, {AccountType.CLEARING.value}, "Source clearing")
    ensure_account_type(target_clearing, {AccountType.CLEARING.value}, "Target clearing")
    ensure_account_type(gain_loss_account, {AccountType.FX_GAIN_LOSS.value}, "FX gain/loss")
    charge_account = None
    if payload.fx_charge > 0:
        charge_account = get_account(db, payload.fx_charge_account_id)
        ensure_account_currency(charge_account, payload.base_currency)
        ensure_account_type(charge_account, {AccountType.EXPENSE.value, AccountType.BANK_CHARGE_EXPENSE.value}, "FX charge")

    ensure_sufficient_balance(from_account, payload.from_amount, permission_granted=False)
    if payload.fx_charge > payload.to_amount and to_account.account_type == AccountType.CASH.value:
        raise HTTPException(status_code=400, detail="Cash negative balance is blocked")
    lot_plan = plan_fifo_lot_consumption(
        db,
        account_id=from_account.id,
        currency=payload.from_currency,
        base_currency=payload.base_currency,
        amount=payload.from_amount,
        allow_insufficient_lots=payload.allow_insufficient_lots,
        source_lot_id=payload.source_lot_id,
    )
    actual_base_value = payload.to_amount
    fx_difference = actual_base_value - lot_plan.original_base_value
    actual_rate = actual_base_value / payload.from_amount

    components = [
        ComponentDraft(1, ComponentType.CASH_MOVEMENT.value, payload.from_amount, payload.from_currency, Direction.OUT.value, account_id=from_account.id),
        ComponentDraft(2, ComponentType.CASH_MOVEMENT.value, payload.to_amount, payload.to_currency, Direction.IN.value, account_id=to_account.id),
    ]
    entries = [
        LedgerEntryDraft(source_clearing.id, payload.from_amount, Decimal("0"), payload.from_currency, "FX source clearing"),
        LedgerEntryDraft(from_account.id, Decimal("0"), payload.from_amount, payload.from_currency, "FX source out"),
    ]

    if fx_difference >= 0:
        if fx_difference > 0:
            components.append(
                ComponentDraft(
                    3,
                    ComponentType.FX_GAIN.value,
                    fx_difference,
                    payload.base_currency,
                    Direction.IN.value,
                    account_id=gain_loss_account.id,
                    affects_profitability=True,
                    profitability_effect_type=ProfitabilityEffectType.INCOME.value,
                    linked_detail_type="fx_conversion",
                )
            )
        entries.extend(
            [
                LedgerEntryDraft(to_account.id, payload.to_amount, Decimal("0"), payload.to_currency, "FX target in"),
                LedgerEntryDraft(target_clearing.id, Decimal("0"), lot_plan.original_base_value, payload.base_currency, "FX target clearing"),
            ]
        )
        if fx_difference > 0:
            entries.append(
                LedgerEntryDraft(gain_loss_account.id, Decimal("0"), fx_difference, payload.base_currency, "FX gain")
            )
    else:
        fx_loss = -fx_difference
        components.append(
            ComponentDraft(
                3,
                ComponentType.FX_LOSS.value,
                fx_loss,
                payload.base_currency,
                Direction.OUT.value,
                account_id=gain_loss_account.id,
                affects_profitability=True,
                profitability_effect_type=ProfitabilityEffectType.EXPENSE.value,
                linked_detail_type="fx_conversion",
            )
        )
        entries.extend(
            [
                LedgerEntryDraft(to_account.id, payload.to_amount, Decimal("0"), payload.to_currency, "FX target in"),
                LedgerEntryDraft(gain_loss_account.id, fx_loss, Decimal("0"), payload.base_currency, "FX loss"),
                LedgerEntryDraft(target_clearing.id, Decimal("0"), lot_plan.original_base_value, payload.base_currency, "FX target clearing"),
            ]
        )

    if payload.fx_charge > 0:
        sequence_no = 4 if len(components) > 2 else 3
        components.append(
            ComponentDraft(
                sequence_no,
                ComponentType.FX_CHARGE.value,
                payload.fx_charge,
                payload.base_currency,
                Direction.OUT.value,
                account_id=charge_account.id,
                affects_profitability=True,
                profitability_effect_type=ProfitabilityEffectType.EXPENSE.value,
                linked_detail_type="expense",
                notes="fx_charge",
            )
        )
        entries.extend(
            [
                LedgerEntryDraft(charge_account.id, payload.fx_charge, Decimal("0"), payload.base_currency, "FX charge"),
                LedgerEntryDraft(to_account.id, Decimal("0"), payload.fx_charge, payload.base_currency, "FX charge paid"),
            ]
        )

    fx_detail = {
        "costing_method": payload.costing_method,
        "from_amount": payload.from_amount,
        "to_amount": payload.to_amount,
        "original_base_value": lot_plan.original_base_value,
        "actual_base_value": actual_base_value,
        "weighted_avg_rate": lot_plan.weighted_avg_rate,
        "actual_rate": actual_rate,
        "fx_difference": fx_difference,
        "fx_charge": payload.fx_charge,
    }
    return _preview(
        db,
        transaction_type=TransactionType.CURRENCY_EXCHANGE.value,
        gross_amount=payload.from_amount,
        gross_currency=payload.from_currency,
        components=components,
        ledger_entries=entries,
        fx_detail=fx_detail,
    )
