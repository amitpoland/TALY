from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.currency import Currency
from app.models.party import Party
from app.schemas.party import PartyCreate, PartyRead, PartyUpdate
from app.services.audit_service import write_audit_log

router = APIRouter(prefix="/parties", tags=["parties"])


def _ensure_currency(db: Session, code: str | None) -> None:
    if code and db.get(Currency, code) is None:
        raise HTTPException(status_code=400, detail=f"Currency {code} does not exist")


def _party_snapshot(party: Party) -> dict[str, object]:
    return {
        "id": party.id,
        "party_type": party.party_type,
        "name": party.name,
        "phone": party.phone,
        "email": party.email,
        "default_currency": party.default_currency,
        "is_active": party.is_active,
    }


@router.get("", response_model=list[PartyRead])
def list_parties(db: Session = Depends(get_db)) -> list[Party]:
    return db.query(Party).order_by(Party.name).all()


@router.post("", response_model=PartyRead, status_code=status.HTTP_201_CREATED)
def create_party(payload: PartyCreate, db: Session = Depends(get_db)) -> Party:
    _ensure_currency(db, payload.default_currency)
    party = Party(**payload.model_dump(mode="json"))
    db.add(party)
    db.flush()
    write_audit_log(
        db,
        action="create_party",
        entity_type="party",
        entity_id=party.id,
        after=_party_snapshot(party),
    )
    db.commit()
    db.refresh(party)
    return party


@router.get("/{party_id}", response_model=PartyRead)
def get_party(party_id: int, db: Session = Depends(get_db)) -> Party:
    party = db.get(Party, party_id)
    if party is None:
        raise HTTPException(status_code=404, detail="Party not found")
    return party


@router.patch("/{party_id}", response_model=PartyRead)
def update_party(party_id: int, payload: PartyUpdate, db: Session = Depends(get_db)) -> Party:
    party = db.get(Party, party_id)
    if party is None:
        raise HTTPException(status_code=404, detail="Party not found")
    _ensure_currency(db, payload.default_currency)
    before = _party_snapshot(party)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(party, key, value)
    db.flush()
    write_audit_log(
        db,
        action="update_party",
        entity_type="party",
        entity_id=party.id,
        before=before,
        after=_party_snapshot(party),
    )
    db.commit()
    db.refresh(party)
    return party

