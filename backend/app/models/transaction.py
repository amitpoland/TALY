from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.common import TimestampMixin


class Transaction(TimestampMixin, Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    transaction_no: Mapped[str] = mapped_column(unique=True, nullable=False)
    settlement_id: Mapped[int | None] = mapped_column(ForeignKey("settlements.id"))
    transaction_type: Mapped[str] = mapped_column(nullable=False)
    transaction_date: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(nullable=False)
    gross_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    gross_currency: Mapped[str | None] = mapped_column(ForeignKey("currencies.code"))
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    posted_at: Mapped[str | None]
    reversed_transaction_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id"))
    reversal_reason: Mapped[str | None] = mapped_column(Text)

