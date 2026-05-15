from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.common import utcnow


class Commission(Base):
    __tablename__ = "commissions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), nullable=False)
    settlement_id: Mapped[int | None] = mapped_column(ForeignKey("settlements.id"))
    component_id: Mapped[int | None] = mapped_column(ForeignKey("transaction_components.id"))
    commission_type: Mapped[str] = mapped_column(nullable=False)
    party_id: Mapped[int | None] = mapped_column(ForeignKey("parties.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    currency: Mapped[str] = mapped_column(ForeignKey("currencies.code"), nullable=False)
    calculation_method: Mapped[str] = mapped_column(nullable=False)
    rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    included_in_gross: Mapped[bool] = mapped_column(default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(default=utcnow, nullable=False)

