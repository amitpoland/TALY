from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.settlement.balance_service import calculate_settlement_balance

router = APIRouter(prefix="/settlements", tags=["settlements"])


@router.get("/{settlement_id}/balance")
def get_settlement_balance(settlement_id: int, db: Session = Depends(get_db)):
    return calculate_settlement_balance(db, settlement_id)

