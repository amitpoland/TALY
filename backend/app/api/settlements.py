from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.settlement import SettlementCancelRequest, SettlementCloseRequest, SettlementClosurePreviewRead, SettlementReopenRequest
from app.models.settlement import Settlement
from app.services.settlement.balance_service import calculate_settlement_balance
from app.services.settlement.closure_service import build_close_preview, cancel_settlement, close_settlement, reopen_settlement

router = APIRouter(prefix="/settlements", tags=["settlements"])


@router.get("/{settlement_id}/balance")
def get_settlement_balance(settlement_id: int, db: Session = Depends(get_db)):
    return calculate_settlement_balance(db, settlement_id)


@router.post("/{settlement_id}/close/preview", response_model=SettlementClosurePreviewRead)
def preview_close_settlement(settlement_id: int, payload: SettlementCloseRequest, db: Session = Depends(get_db)):
    return build_close_preview(db, settlement_id, payload)


@router.post("/{settlement_id}/close")
def post_close_settlement(settlement_id: int, payload: SettlementCloseRequest, db: Session = Depends(get_db)):
    settlement, audit = close_settlement(db, settlement_id, payload)
    return {"settlement_id": settlement.id, "status": settlement.status, "audit_log_id": audit.id}


@router.post("/{settlement_id}/reopen")
def post_reopen_settlement(settlement_id: int, payload: SettlementReopenRequest, db: Session = Depends(get_db)):
    settlement, audit = reopen_settlement(
        db,
        settlement_id,
        user_id=payload.user_id,
        reason=payload.reason,
        admin_approved_reopen=payload.admin_approved_reopen,
    )
    return {"settlement_id": settlement.id, "status": settlement.status, "audit_log_id": audit.id}


@router.post("/{settlement_id}/cancel")
def post_cancel_settlement(settlement_id: int, payload: SettlementCancelRequest, db: Session = Depends(get_db)):
    settlement, audit = cancel_settlement(db, settlement_id, user_id=payload.user_id, reason=payload.reason)
    return {"settlement_id": settlement.id, "status": settlement.status, "audit_log_id": audit.id}
