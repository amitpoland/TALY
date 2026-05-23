from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.enums import (
    ComponentType,
    Direction,
    TransactionStatus,
    TransactionType,
)
from app.models.account import Account
from app.models.commission import Commission
from app.models.expense import Expense
from app.models.exchange_rate_lot import ExchangeRateLot
from app.models.fx_conversion import FxConversion
from app.models.ledger_entry import LedgerEntry
from app.models.transaction import Transaction
from app.models.transaction_component import TransactionComponent
from app.models.common import utcnow
from app.schemas.posting import (
    AgentSettlementPayload,
    CrossCurrencyPaymentPayload,
    CrossCurrencyReceiptPayload,
    ExpensePayload,
    FxConversionPayload,
    OpeningBalancePayload,
    PaymentPayload,
    ReceiptPayload,
    ReversePayload,
    TransferPayload,
)
from app.services.audit_service import write_audit_log
from app.services.posting.account_balance_service import apply_ledger_entries_to_balances, preview_balance_effects
from app.services.posting.builders import (
    build_agent_settlement_preview,
    build_bank_transfer_preview,
    build_cash_handover_preview,
    build_cross_currency_payment_preview,
    build_cross_currency_receipt_preview,
    build_expense_preview,
    build_fx_conversion_preview,
    build_opening_balance_preview,
    build_payment_preview,
    build_receipt_preview,
)
from app.services.posting.dtos import ComponentDraft, LedgerEntryDraft, PostingPreview
from app.services.posting.fx_lot_service import (
    create_exchange_rate_lot,
    persist_lot_consumptions,
    plan_fifo_lot_consumption,
    restore_lot_consumptions_for_fx,
)


def _next_transaction_no(db: Session) -> str:
    count = db.query(Transaction).count() + 1
    return f"TXN-{count:06d}"


def _validate_ledger_balances(entries: list[LedgerEntryDraft]) -> None:
    totals: dict[str, Decimal] = {}
    for entry in entries:
        if entry.debit < 0 or entry.credit < 0:
            raise HTTPException(status_code=400, detail="Ledger entries cannot be negative")
        if entry.debit > 0 and entry.credit > 0:
            raise HTTPException(status_code=400, detail="Ledger entry cannot have both debit and credit")
        totals[entry.currency] = totals.get(entry.currency, Decimal("0")) + entry.debit - entry.credit
    unbalanced = {currency: total for currency, total in totals.items() if total != 0}
    if unbalanced:
        raise HTTPException(status_code=400, detail=f"Ledger entries are not balanced: {unbalanced}")


def _persist_preview(
    db: Session,
    *,
    preview: PostingPreview,
    payload,
    created_by_user_id: int,
    description: str | None,
    transaction_date: str,
    settlement_id: int | None,
    reversal_reason: str | None = None,
    reversed_transaction_id: int | None = None,
) -> tuple[Transaction, int | None]:
    _validate_ledger_balances(preview.ledger_entries)
    now = utcnow()
    transaction = Transaction(
        transaction_no=_next_transaction_no(db),
        settlement_id=settlement_id,
        transaction_type=preview.transaction_type,
        transaction_date=transaction_date,
        description=description,
        status=TransactionStatus.POSTED.value,
        gross_amount=preview.gross_amount,
        gross_currency=preview.gross_currency,
        created_by_user_id=created_by_user_id,
        posted_at=now,
        reversed_transaction_id=reversed_transaction_id,
        reversal_reason=reversal_reason,
    )
    db.add(transaction)
    db.flush()

    for component in preview.components:
        row = TransactionComponent(
            transaction_id=transaction.id,
            settlement_id=settlement_id,
            sequence_no=component.sequence_no,
            component_group=None,
            component_type=component.component_type,
            party_id=component.party_id,
            account_id=component.account_id,
            amount=component.amount,
            currency=component.currency,
            direction=component.direction,
            affects_settlement=component.affects_settlement,
            settlement_effect_type=component.settlement_effect_type,
            affects_profitability=component.affects_profitability,
            profitability_effect_type=component.profitability_effect_type,
            linked_detail_type=component.linked_detail_type,
            linked_detail_id=None,
            notes=component.notes,
        )
        db.add(row)
        db.flush()
        if component.linked_detail_type == "commission":
            db.add(
                Commission(
                    transaction_id=transaction.id,
                    settlement_id=settlement_id,
                    component_id=row.id,
                    commission_type="earned",
                    amount=component.amount,
                    currency=component.currency,
                    calculation_method="included",
                    included_in_gross=True,
                    notes=component.notes,
                )
            )
        if component.linked_detail_type == "expense":
            db.add(
                Expense(
                    transaction_id=transaction.id,
                    settlement_id=settlement_id,
                    component_id=row.id,
                    expense_type=component.notes or "other",
                    account_id=component.account_id,
                    amount=component.amount,
                    currency=component.currency,
                    description=description,
                )
            )

    for entry in preview.ledger_entries:
        db.add(
            LedgerEntry(
                transaction_id=transaction.id,
                settlement_id=settlement_id,
                account_id=entry.account_id,
                entry_date=transaction_date,
                debit=entry.debit,
                credit=entry.credit,
                currency=entry.currency,
                description=entry.description,
            )
        )
    apply_ledger_entries_to_balances(db, preview.ledger_entries)

    if preview.transaction_type == TransactionType.OPENING_BALANCE.value:
        account = db.get(Account, payload.account_id)
        account.opening_balance = payload.amount
        create_exchange_rate_lot(
            db,
            account_id=payload.account_id,
            currency=payload.currency,
            base_currency=payload.base_currency,
            source_transaction_id=transaction.id,
            amount=payload.amount,
            original_rate=payload.original_rate,
        )

    if preview.transaction_type in {TransactionType.RECEIPT.value, TransactionType.CROSS_CURRENCY_RECEIPT.value} and getattr(payload, "original_rate", None) is not None:
        lot_currency = getattr(payload, "currency", getattr(payload, "received_currency", None))
        create_exchange_rate_lot(
            db,
            account_id=payload.receiving_account_id,
            currency=lot_currency,
            base_currency=payload.base_currency,
            source_transaction_id=transaction.id,
            amount=payload.gross_amount,
            original_rate=payload.original_rate,
        )

    if preview.transaction_type == TransactionType.CURRENCY_EXCHANGE.value:
        fx_detail = preview.fx_detail or {}
        fx = FxConversion(
            transaction_id=transaction.id,
            settlement_id=settlement_id,
            from_account_id=payload.from_account_id,
            to_account_id=payload.to_account_id,
            from_currency=payload.from_currency,
            to_currency=payload.to_currency,
            from_amount=payload.from_amount,
            to_amount=payload.to_amount,
            costing_method=payload.costing_method,
            original_rate=fx_detail["weighted_avg_rate"],
            actual_rate=fx_detail["actual_rate"],
            weighted_avg_rate=fx_detail["weighted_avg_rate"],
            base_currency=payload.base_currency,
            original_base_value=fx_detail["original_base_value"],
            actual_base_value=fx_detail["actual_base_value"],
            fx_difference=fx_detail["fx_difference"],
            fx_charge=payload.fx_charge,
        )
        db.add(fx)
        db.flush()
        plan = plan_fifo_lot_consumption(
            db,
            account_id=payload.from_account_id,
            currency=payload.from_currency,
            base_currency=payload.base_currency,
            amount=payload.from_amount,
            allow_insufficient_lots=payload.allow_insufficient_lots,
            source_lot_id=payload.source_lot_id,
            fallback_rate=payload.to_amount / payload.from_amount,
        )
        persist_lot_consumptions(db, fx_conversion_id=fx.id, plan=plan)

    audit = write_audit_log(
        db,
        action=f"post_{preview.transaction_type}",
        entity_type="transaction",
        entity_id=transaction.id,
        user_id=created_by_user_id,
        after={
            "transaction_no": transaction.transaction_no,
            "transaction_type": transaction.transaction_type,
            "gross_amount": str(transaction.gross_amount) if transaction.gross_amount is not None else None,
            "gross_currency": transaction.gross_currency,
        },
        reason=reversal_reason,
    )
    db.flush()
    return transaction, audit.id


def post_opening_balance(db: Session, payload: OpeningBalancePayload) -> tuple[PostingPreview, Transaction, int | None]:
    preview = build_opening_balance_preview(db, payload)
    transaction, audit_id = _persist_preview(
        db,
        preview=preview,
        payload=payload,
        created_by_user_id=payload.created_by_user_id,
        description=payload.description,
        transaction_date=payload.transaction_date,
        settlement_id=payload.settlement_id,
    )
    db.commit()
    return preview, transaction, audit_id


def post_receipt(db: Session, payload: ReceiptPayload) -> tuple[PostingPreview, Transaction, int | None]:
    preview = build_receipt_preview(db, payload)
    transaction, audit_id = _persist_preview(db, preview=preview, payload=payload, created_by_user_id=payload.created_by_user_id, description=payload.description, transaction_date=payload.transaction_date, settlement_id=payload.settlement_id)
    db.commit()
    return preview, transaction, audit_id


def post_payment(db: Session, payload: PaymentPayload) -> tuple[PostingPreview, Transaction, int | None]:
    preview = build_payment_preview(db, payload)
    transaction, audit_id = _persist_preview(db, preview=preview, payload=payload, created_by_user_id=payload.created_by_user_id, description=payload.description, transaction_date=payload.transaction_date, settlement_id=payload.settlement_id)
    db.commit()
    return preview, transaction, audit_id


def post_cross_currency_receipt(db: Session, payload: CrossCurrencyReceiptPayload) -> tuple[PostingPreview, Transaction, int | None]:
    preview = build_cross_currency_receipt_preview(db, payload)
    transaction, audit_id = _persist_preview(db, preview=preview, payload=payload, created_by_user_id=payload.created_by_user_id, description=payload.description, transaction_date=payload.transaction_date, settlement_id=payload.settlement_id)
    db.commit()
    return preview, transaction, audit_id


def post_cross_currency_payment(db: Session, payload: CrossCurrencyPaymentPayload) -> tuple[PostingPreview, Transaction, int | None]:
    preview = build_cross_currency_payment_preview(db, payload)
    transaction, audit_id = _persist_preview(db, preview=preview, payload=payload, created_by_user_id=payload.created_by_user_id, description=payload.description, transaction_date=payload.transaction_date, settlement_id=payload.settlement_id)
    db.commit()
    return preview, transaction, audit_id


def post_agent_settlement(db: Session, payload: AgentSettlementPayload) -> tuple[PostingPreview, Transaction, int | None]:
    preview = build_agent_settlement_preview(db, payload)
    transaction, audit_id = _persist_preview(db, preview=preview, payload=payload, created_by_user_id=payload.created_by_user_id, description=payload.description, transaction_date=payload.transaction_date, settlement_id=payload.settlement_id)
    db.commit()
    return preview, transaction, audit_id


def post_cash_handover(db: Session, payload: TransferPayload) -> tuple[PostingPreview, Transaction, int | None]:
    preview = build_cash_handover_preview(db, payload)
    transaction, audit_id = _persist_preview(db, preview=preview, payload=payload, created_by_user_id=payload.created_by_user_id, description=payload.description, transaction_date=payload.transaction_date, settlement_id=payload.settlement_id)
    db.commit()
    return preview, transaction, audit_id


def post_bank_transfer(db: Session, payload: TransferPayload) -> tuple[PostingPreview, Transaction, int | None]:
    preview = build_bank_transfer_preview(db, payload)
    transaction, audit_id = _persist_preview(db, preview=preview, payload=payload, created_by_user_id=payload.created_by_user_id, description=payload.description, transaction_date=payload.transaction_date, settlement_id=payload.settlement_id)
    db.commit()
    return preview, transaction, audit_id


def post_expense(db: Session, payload: ExpensePayload) -> tuple[PostingPreview, Transaction, int | None]:
    preview = build_expense_preview(db, payload)
    transaction, audit_id = _persist_preview(db, preview=preview, payload=payload, created_by_user_id=payload.created_by_user_id, description=payload.description, transaction_date=payload.transaction_date, settlement_id=payload.settlement_id)
    db.commit()
    return preview, transaction, audit_id


def post_fx_conversion(db: Session, payload: FxConversionPayload) -> tuple[PostingPreview, Transaction, int | None]:
    preview = build_fx_conversion_preview(db, payload)
    transaction, audit_id = _persist_preview(db, preview=preview, payload=payload, created_by_user_id=payload.created_by_user_id, description=payload.description, transaction_date=payload.transaction_date, settlement_id=payload.settlement_id)
    db.commit()
    return preview, transaction, audit_id


def build_reversal_preview(db: Session, transaction_id: int, payload: ReversePayload) -> PostingPreview:
    original = db.get(Transaction, transaction_id)
    if original is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if original.status != TransactionStatus.POSTED.value:
        raise HTTPException(status_code=400, detail="Only posted transactions can be reversed")
    if db.query(Transaction).filter(Transaction.reversed_transaction_id == transaction_id).one_or_none():
        raise HTTPException(status_code=400, detail="Transaction has already been reversed")
    created_lots = (
        db.query(ExchangeRateLot)
        .filter(ExchangeRateLot.source_transaction_id == transaction_id)
        .all()
    )
    if any(lot.remaining_amount != lot.original_amount for lot in created_lots):
        raise HTTPException(status_code=400, detail="Cannot reverse transaction with consumed FX lots")

    original_components = (
        db.query(TransactionComponent)
        .filter(TransactionComponent.transaction_id == transaction_id)
        .order_by(TransactionComponent.sequence_no)
        .all()
    )
    original_entries = db.query(LedgerEntry).filter(LedgerEntry.transaction_id == transaction_id).all()

    def invert_direction(direction: str) -> str:
        if direction == Direction.IN.value:
            return Direction.OUT.value
        if direction == Direction.OUT.value:
            return Direction.IN.value
        return Direction.NEUTRAL.value

    def invert_settlement_effect(effect: str | None) -> str | None:
        pairs = {
            "principal_in": "principal_out",
            "principal_out": "principal_in",
            "adjustment_in": "adjustment_out",
            "adjustment_out": "adjustment_in",
        }
        return pairs.get(effect, effect)

    def invert_profitability_effect(effect: str | None) -> str | None:
        pairs = {"income": "expense", "expense": "income"}
        return pairs.get(effect, effect)

    components = [
        ComponentDraft(
            sequence_no=component.sequence_no,
            component_type=ComponentType.REVERSAL.value,
            amount=component.amount,
            currency=component.currency,
            direction=invert_direction(component.direction),
            account_id=component.account_id,
            party_id=component.party_id,
            affects_settlement=component.affects_settlement,
            settlement_effect_type=invert_settlement_effect(component.settlement_effect_type),
            affects_profitability=component.affects_profitability,
            profitability_effect_type=invert_profitability_effect(component.profitability_effect_type),
            notes=f"Reversal of {original.transaction_no}",
        )
        for component in original_components
    ]
    entries = [
        LedgerEntryDraft(
            account_id=entry.account_id,
            debit=entry.credit,
            credit=entry.debit,
            currency=entry.currency,
            description=f"Reversal of {original.transaction_no}",
        )
        for entry in original_entries
    ]
    return PostingPreview(
        transaction_type=TransactionType.REVERSAL.value,
        gross_amount=original.gross_amount,
        gross_currency=original.gross_currency,
        components=components,
        ledger_entries=entries,
        account_balance_effects=preview_balance_effects(db, entries),
        settlement_effect={},
        profitability_effect={},
        warnings=[],
        errors=[],
    )


def post_reversal(db: Session, transaction_id: int, payload: ReversePayload) -> tuple[PostingPreview, Transaction, int | None]:
    preview = build_reversal_preview(db, transaction_id, payload)
    original = db.get(Transaction, transaction_id)
    transaction, audit_id = _persist_preview(
        db,
        preview=preview,
        payload=payload,
        created_by_user_id=payload.created_by_user_id,
        description=f"Reversal of {original.transaction_no}",
        transaction_date=payload.transaction_date,
        settlement_id=original.settlement_id,
        reversal_reason=payload.reversal_reason,
        reversed_transaction_id=original.id,
    )
    original_fx = db.query(FxConversion).filter(FxConversion.transaction_id == original.id).one_or_none()
    if original_fx is not None:
        restore_lot_consumptions_for_fx(db, fx_conversion_id=original_fx.id)
    for lot in db.query(ExchangeRateLot).filter(ExchangeRateLot.source_transaction_id == original.id).all():
        lot.remaining_amount = Decimal("0")
        lot.remaining_base_value = Decimal("0")
        lot.status = "reversed"
    original.status = TransactionStatus.REVERSED.value
    db.commit()
    return preview, transaction, audit_id
