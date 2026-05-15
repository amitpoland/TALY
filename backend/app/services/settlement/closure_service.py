from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.settlement import Settlement
from app.models.transaction import Transaction
from app.models.transaction_component import TransactionComponent
from app.models.common import utcnow
from app.schemas.settlement import SettlementCloseRequest, SettlementClosurePreviewRead
from app.services.audit_service import write_audit_log
from app.services.settlement.balance_service import calculate_settlement_balance


def _component_totals(db: Session, settlement_id: int) -> tuple[dict[str, Decimal], dict[str, Decimal], dict[str, Decimal], dict[str, Decimal]]:
    rows = (
        db.query(TransactionComponent)
        .join(Transaction, Transaction.id == TransactionComponent.transaction_id)
        .filter(TransactionComponent.settlement_id == settlement_id)
        .filter(Transaction.status.in_(["posted", "reversed"]))
        .all()
    )
    profitability: dict[str, Decimal] = {}
    fx: dict[str, Decimal] = {}
    commissions: dict[str, Decimal] = {}
    expenses: dict[str, Decimal] = {}
    for component in rows:
        if component.affects_profitability:
            sign = Decimal("1") if component.profitability_effect_type in {"income", "fx_gain"} else Decimal("-1")
            profitability[component.currency] = profitability.get(component.currency, Decimal("0")) + sign * component.amount
        if component.component_type in {"fx_gain", "fx_loss"}:
            sign = Decimal("1") if component.component_type == "fx_gain" else Decimal("-1")
            fx[component.currency] = fx.get(component.currency, Decimal("0")) + sign * component.amount
        if component.component_type in {"your_commission", "agent_commission", "commission_payable", "commission_paid"}:
            commissions[component.currency] = commissions.get(component.currency, Decimal("0")) + component.amount
        if component.component_type in {"expense", "fx_charge", "bank_charge"}:
            expenses[component.currency] = expenses.get(component.currency, Decimal("0")) + component.amount
    return profitability, fx, commissions, expenses


def build_close_preview(db: Session, settlement_id: int, request: SettlementCloseRequest) -> SettlementClosurePreviewRead:
    settlement = db.get(Settlement, settlement_id)
    if settlement is None:
        raise HTTPException(status_code=404, detail="Settlement not found")
    if settlement.status in {"closed", "cancelled"}:
        raise HTTPException(status_code=400, detail="Settlement is already closed or cancelled")

    balance = calculate_settlement_balance(db, settlement_id)
    balances: dict[str, Decimal] = balance["balances"]
    profitability, fx, commissions, expenses = _component_totals(db, settlement_id)
    warnings: list[str] = []
    errors: list[str] = []
    non_zero = {currency: amount for currency, amount in balances.items() if amount != 0}

    pending_amount = request.approved_pending_amount if request.approved_pending_amount != 0 else None
    pending_currency = request.approved_pending_currency
    if non_zero:
        if not request.admin_approved_pending:
            errors.append("Settlement is not balanced by original currency")
        elif pending_amount is None or pending_currency is None or not request.approved_pending_reason:
            errors.append("Approved pending amount, currency, and reason are required")
        else:
            expected = non_zero.get(pending_currency)
            if expected is None or expected != pending_amount:
                errors.append("Approved pending amount must match the remaining currency balance")
            warnings.append("Settlement will close with approved pending balance")

    return SettlementClosurePreviewRead(
        settlement_id=settlement.id,
        settlement_no=settlement.settlement_no,
        status=settlement.status,
        principal_balance_by_currency=balances,
        profitability_summary=profitability,
        fx_gain_loss_summary=fx,
        commissions_summary=commissions,
        expenses_summary=expenses,
        pending_amount=pending_amount,
        pending_currency=pending_currency,
        warnings=warnings,
        errors=errors,
        can_close=not errors,
    )


def close_settlement(db: Session, settlement_id: int, request: SettlementCloseRequest) -> tuple[Settlement, AuditLog]:
    preview = build_close_preview(db, settlement_id, request)
    if not preview.can_close:
        raise HTTPException(status_code=400, detail=preview.errors)
    settlement = db.get(Settlement, settlement_id)
    before = {
        "status": settlement.status,
        "approved_pending_amount": str(settlement.approved_pending_amount),
        "approved_pending_currency": settlement.approved_pending_currency,
    }
    settlement.status = "closed"
    settlement.closed_at = utcnow()
    settlement.closed_by_user_id = request.user_id
    action = "close_settlement"
    if request.approved_pending_amount != 0:
        settlement.approved_pending_amount = request.approved_pending_amount
        settlement.approved_pending_currency = request.approved_pending_currency
        settlement.approved_pending_reason = request.approved_pending_reason
        action = "close_settlement_with_pending_approval"
    audit = write_audit_log(
        db,
        action=action,
        entity_type="settlement",
        entity_id=settlement.id,
        user_id=request.user_id,
        before=before,
        after={
            "status": settlement.status,
            "approved_pending_amount": str(settlement.approved_pending_amount),
            "approved_pending_currency": settlement.approved_pending_currency,
            "closed_at": settlement.closed_at,
        },
        reason=request.approved_pending_reason,
    )
    db.commit()
    db.refresh(settlement)
    return settlement, audit


def reopen_settlement(db: Session, settlement_id: int, *, user_id: int, reason: str, admin_approved_reopen: bool) -> tuple[Settlement, AuditLog]:
    settlement = db.get(Settlement, settlement_id)
    if settlement is None:
        raise HTTPException(status_code=404, detail="Settlement not found")
    if settlement.status != "closed":
        raise HTTPException(status_code=400, detail="Only closed settlements can be reopened")
    if not reason.strip():
        raise HTTPException(status_code=400, detail="Reopen reason is required")
    if not admin_approved_reopen:
        raise HTTPException(status_code=400, detail="Admin approval is required to reopen settlement")
    before = {"status": settlement.status, "closed_at": settlement.closed_at}
    settlement.status = "reopened"
    settlement.closed_at = None
    settlement.closed_by_user_id = None
    audit = write_audit_log(
        db,
        action="reopen_settlement",
        entity_type="settlement",
        entity_id=settlement.id,
        user_id=user_id,
        before=before,
        after={"status": settlement.status},
        reason=reason,
    )
    db.commit()
    db.refresh(settlement)
    return settlement, audit


def cancel_settlement(db: Session, settlement_id: int, *, user_id: int, reason: str | None = None) -> tuple[Settlement, AuditLog]:
    settlement = db.get(Settlement, settlement_id)
    if settlement is None:
        raise HTTPException(status_code=404, detail="Settlement not found")
    if settlement.status in {"closed", "cancelled"}:
        raise HTTPException(status_code=400, detail="Closed or cancelled settlements cannot be cancelled")
    transactions = db.query(Transaction).filter(Transaction.settlement_id == settlement_id).all()
    active = [txn for txn in transactions if txn.status == "posted" and txn.transaction_type != "reversal"]
    if active:
        raise HTTPException(status_code=400, detail="Cannot cancel settlement with active posted transactions")
    before = {"status": settlement.status}
    settlement.status = "cancelled"
    audit = write_audit_log(
        db,
        action="cancel_settlement",
        entity_type="settlement",
        entity_id=settlement.id,
        user_id=user_id,
        before=before,
        after={"status": settlement.status},
        reason=reason,
    )
    db.commit()
    db.refresh(settlement)
    return settlement, audit
