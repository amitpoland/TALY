from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.settlement import Settlement
from app.models.transaction import Transaction
from app.models.transaction_component import TransactionComponent


def calculate_settlement_balance(db: Session, settlement_id: int) -> dict[str, object]:
    settlement = db.get(Settlement, settlement_id)
    if settlement is None:
        raise HTTPException(status_code=404, detail="Settlement not found")

    rows = (
        db.query(TransactionComponent)
        .join(Transaction, Transaction.id == TransactionComponent.transaction_id)
        .filter(TransactionComponent.settlement_id == settlement_id)
        .filter(Transaction.status.in_(["posted", "reversed"]))
        .filter(TransactionComponent.affects_settlement.is_(True))
        .all()
    )

    balances: dict[str, Decimal] = {}
    for component in rows:
        sign = Decimal("1")
        if component.settlement_effect_type in {"principal_out", "adjustment_out"}:
            sign = Decimal("-1")
        balances[component.currency] = balances.get(component.currency, Decimal("0")) + sign * component.amount

    return {
        "settlement_id": settlement.id,
        "settlement_no": settlement.settlement_no,
        "status": settlement.status,
        "balances": balances,
        "is_balanced_by_currency": all(amount == 0 for amount in balances.values()),
    }
