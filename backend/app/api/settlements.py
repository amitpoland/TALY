from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.common import utcnow
from app.models.currency import Currency
from app.models.party import Party
from app.schemas.settlement import (
    SettlementCancelRequest,
    SettlementCloseRequest,
    SettlementClosurePreviewRead,
    SettlementCreate,
    SettlementRead,
    SettlementReopenRequest,
    SettlementUpdate,
)
from app.models.settlement import Settlement
from app.services.audit_service import write_audit_log
from app.services.settlement.balance_service import calculate_settlement_balance
from app.services.settlement.closure_service import build_close_preview, cancel_settlement, close_settlement, reopen_settlement

router = APIRouter(prefix="/settlements", tags=["settlements"])


def _ensure_currency(db: Session, code: str) -> None:
    if db.get(Currency, code) is None:
        raise HTTPException(status_code=400, detail=f"Currency {code} does not exist")


def _ensure_party(db: Session, party_id: int | None) -> None:
    if party_id is not None and db.get(Party, party_id) is None:
        raise HTTPException(status_code=400, detail="Party does not exist")


def _settlement_snapshot(settlement: Settlement) -> dict[str, object]:
    return {
        "id": settlement.id,
        "settlement_no": settlement.settlement_no,
        "title": settlement.title,
        "primary_party_id": settlement.primary_party_id,
        "status": settlement.status,
        "base_currency": settlement.base_currency,
    }


@router.get("", response_model=list[SettlementRead])
def list_settlements(db: Session = Depends(get_db)) -> list[Settlement]:
    return db.query(Settlement).order_by(Settlement.opened_at.desc(), Settlement.id.desc()).all()


@router.post("", response_model=SettlementRead, status_code=status.HTTP_201_CREATED)
def create_settlement(payload: SettlementCreate, db: Session = Depends(get_db)) -> Settlement:
    if db.query(Settlement).filter(Settlement.settlement_no == payload.settlement_no).one_or_none():
        raise HTTPException(status_code=409, detail="Settlement number already exists")
    _ensure_currency(db, payload.base_currency)
    _ensure_party(db, payload.primary_party_id)
    settlement = Settlement(
        settlement_no=payload.settlement_no,
        title=payload.title,
        primary_party_id=payload.primary_party_id,
        status="open",
        base_currency=payload.base_currency,
        opened_at=utcnow(),
    )
    db.add(settlement)
    db.flush()
    write_audit_log(
        db,
        action="create_settlement",
        entity_type="settlement",
        entity_id=settlement.id,
        after=_settlement_snapshot(settlement),
    )
    db.commit()
    db.refresh(settlement)
    return settlement


@router.get("/{settlement_id}", response_model=SettlementRead)
def get_settlement(settlement_id: int, db: Session = Depends(get_db)) -> Settlement:
    settlement = db.get(Settlement, settlement_id)
    if settlement is None:
        raise HTTPException(status_code=404, detail="Settlement not found")
    return settlement


@router.patch("/{settlement_id}", response_model=SettlementRead)
def update_settlement(settlement_id: int, payload: SettlementUpdate, db: Session = Depends(get_db)) -> Settlement:
    settlement = db.get(Settlement, settlement_id)
    if settlement is None:
        raise HTTPException(status_code=404, detail="Settlement not found")
    if settlement.status in {"closed", "cancelled"}:
        raise HTTPException(status_code=400, detail="Closed or cancelled settlements cannot be edited")
    values = payload.model_dump(exclude_unset=True)
    if "base_currency" in values and values["base_currency"] is not None:
        _ensure_currency(db, values["base_currency"])
    if "primary_party_id" in values:
        _ensure_party(db, values["primary_party_id"])
    before = _settlement_snapshot(settlement)
    for key, value in values.items():
        setattr(settlement, key, value)
    db.flush()
    write_audit_log(
        db,
        action="update_settlement",
        entity_type="settlement",
        entity_id=settlement.id,
        before=before,
        after=_settlement_snapshot(settlement),
    )
    db.commit()
    db.refresh(settlement)
    return settlement


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
