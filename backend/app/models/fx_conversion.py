from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.common import utcnow


class FxConversion(Base):
    __tablename__ = "fx_conversions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), nullable=False)
    settlement_id: Mapped[int | None] = mapped_column(ForeignKey("settlements.id"))
    from_account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    to_account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    from_currency: Mapped[str] = mapped_column(ForeignKey("currencies.code"), nullable=False)
    to_currency: Mapped[str] = mapped_column(ForeignKey("currencies.code"), nullable=False)
    from_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    to_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    costing_method: Mapped[str] = mapped_column(nullable=False)
    original_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    actual_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    weighted_avg_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    base_currency: Mapped[str] = mapped_column(ForeignKey("currencies.code"), nullable=False)
    original_base_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    actual_base_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    fx_difference: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    fx_charge: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"), nullable=False)
    created_at: Mapped[str] = mapped_column(default=utcnow, nullable=False)

