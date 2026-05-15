from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.currency import Currency
from app.schemas.currency import CurrencyRead

router = APIRouter(prefix="/currencies", tags=["currencies"])


@router.get("", response_model=list[CurrencyRead])
def list_currencies(db: Session = Depends(get_db)) -> list[Currency]:
    return db.query(Currency).filter(Currency.is_active.is_(True)).order_by(Currency.code).all()
