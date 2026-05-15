from dataclasses import dataclass
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.exchange_rate_lot import ExchangeRateLot
from app.models.fx_lot_consumption import FxLotConsumption


@dataclass(frozen=True)
class LotConsumptionDraft:
    lot_id: int
    consumed_amount: Decimal
    consumed_base_value: Decimal


@dataclass(frozen=True)
class LotConsumptionPlan:
    consumptions: list[LotConsumptionDraft]
    original_base_value: Decimal
    weighted_avg_rate: Decimal


def create_exchange_rate_lot(
    db: Session,
    *,
    account_id: int,
    currency: str,
    base_currency: str | None,
    source_transaction_id: int,
    amount: Decimal,
    original_rate: Decimal | None,
) -> ExchangeRateLot | None:
    if base_currency is None or original_rate is None:
        return None
    if base_currency == currency:
        return None
    if original_rate <= 0:
        raise HTTPException(status_code=400, detail="Original FX rate must be positive")

    base_value = amount * original_rate
    lot = ExchangeRateLot(
        account_id=account_id,
        currency=currency,
        base_currency=base_currency,
        source_transaction_id=source_transaction_id,
        original_amount=amount,
        remaining_amount=amount,
        original_rate=original_rate,
        original_base_value=base_value,
        remaining_base_value=base_value,
        status="open",
    )
    db.add(lot)
    return lot


def plan_fifo_lot_consumption(
    db: Session,
    *,
    account_id: int,
    currency: str,
    base_currency: str,
    amount: Decimal,
    allow_insufficient_lots: bool = False,
    source_lot_id: int | None = None,
) -> LotConsumptionPlan:
    query = (
            db.query(ExchangeRateLot)
            .filter(ExchangeRateLot.account_id == account_id)
            .filter(ExchangeRateLot.currency == currency)
            .filter(ExchangeRateLot.base_currency == base_currency)
            .filter(ExchangeRateLot.status.in_(["open", "partially_consumed"]))
        )
    if source_lot_id is not None:
        query = query.filter(ExchangeRateLot.id == source_lot_id)
    lots = query.order_by(ExchangeRateLot.id).all()

    remaining = amount
    consumptions: list[LotConsumptionDraft] = []
    original_base_value = Decimal("0")
    for lot in lots:
        if remaining <= 0:
            break
        consume_amount = min(remaining, lot.remaining_amount)
        if lot.remaining_amount == 0:
            continue
        ratio = consume_amount / lot.remaining_amount
        consume_base_value = lot.remaining_base_value * ratio
        consumptions.append(
            LotConsumptionDraft(
                lot_id=lot.id,
                consumed_amount=consume_amount,
                consumed_base_value=consume_base_value,
            )
        )
        original_base_value += consume_base_value
        remaining -= consume_amount

    if remaining > 0 and not allow_insufficient_lots:
        raise HTTPException(status_code=400, detail="Insufficient FX lots for source amount")
    if remaining > 0:
        raise HTTPException(status_code=400, detail="Insufficient lot override is not wired to admin permissions yet")
    if amount <= 0:
        raise HTTPException(status_code=400, detail="FX source amount must be positive")

    return LotConsumptionPlan(
        consumptions=consumptions,
        original_base_value=original_base_value,
        weighted_avg_rate=original_base_value / amount,
    )


def persist_lot_consumptions(
    db: Session,
    *,
    fx_conversion_id: int,
    plan: LotConsumptionPlan,
) -> None:
    for consumption in plan.consumptions:
        lot = db.get(ExchangeRateLot, consumption.lot_id)
        lot.remaining_amount -= consumption.consumed_amount
        lot.remaining_base_value -= consumption.consumed_base_value
        if lot.remaining_amount == 0:
            lot.status = "consumed"
        else:
            lot.status = "partially_consumed"
        db.add(
            FxLotConsumption(
                fx_conversion_id=fx_conversion_id,
                exchange_rate_lot_id=lot.id,
                consumed_amount=consumption.consumed_amount,
                consumed_base_value=consumption.consumed_base_value,
            )
        )


def restore_lot_consumptions_for_fx(db: Session, *, fx_conversion_id: int) -> None:
    consumptions = (
        db.query(FxLotConsumption)
        .filter(FxLotConsumption.fx_conversion_id == fx_conversion_id)
        .all()
    )
    for consumption in consumptions:
        lot = db.get(ExchangeRateLot, consumption.exchange_rate_lot_id)
        lot.remaining_amount += consumption.consumed_amount
        lot.remaining_base_value += consumption.consumed_base_value
        if lot.remaining_amount == lot.original_amount:
            lot.status = "open"
        else:
            lot.status = "partially_consumed"
