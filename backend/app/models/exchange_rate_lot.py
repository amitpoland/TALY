from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.common import TimestampMixin


class ExchangeRateLot(TimestampMixin, Base):
    __tablename__ = "exchange_rate_lots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    currency: Mapped[str] = mapped_column(ForeignKey("currencies.code"), nullable=False)
    base_currency: Mapped[str] = mapped_column(ForeignKey("currencies.code"), nullable=False)
    source_transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), nullable=False)
    original_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    remaining_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    original_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    original_base_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    remaining_base_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    status: Mapped[str] = mapped_column(nullable=False)

