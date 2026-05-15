from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.common import TimestampMixin


class Settlement(TimestampMixin, Base):
    __tablename__ = "settlements"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    settlement_no: Mapped[str] = mapped_column(unique=True, nullable=False)
    title: Mapped[str] = mapped_column(nullable=False)
    primary_party_id: Mapped[int | None] = mapped_column(ForeignKey("parties.id"))
    status: Mapped[str] = mapped_column(nullable=False)
    base_currency: Mapped[str] = mapped_column(ForeignKey("currencies.code"), nullable=False)
    opened_at: Mapped[str] = mapped_column(nullable=False)
    closed_at: Mapped[str | None]
    closed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_pending_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), default=Decimal("0"), nullable=False
    )
    approved_pending_currency: Mapped[str | None] = mapped_column(ForeignKey("currencies.code"))
    approved_pending_reason: Mapped[str | None] = mapped_column(Text)

