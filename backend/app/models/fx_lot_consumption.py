from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.common import utcnow


class FxLotConsumption(Base):
    __tablename__ = "fx_lot_consumptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    fx_conversion_id: Mapped[int] = mapped_column(ForeignKey("fx_conversions.id"), nullable=False)
    exchange_rate_lot_id: Mapped[int] = mapped_column(
        ForeignKey("exchange_rate_lots.id"), nullable=False
    )
    consumed_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    consumed_base_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    created_at: Mapped[str] = mapped_column(default=utcnow, nullable=False)

