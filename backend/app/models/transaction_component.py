from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.common import utcnow


class TransactionComponent(Base):
    __tablename__ = "transaction_components"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), nullable=False)
    settlement_id: Mapped[int | None] = mapped_column(ForeignKey("settlements.id"))
    sequence_no: Mapped[int] = mapped_column(nullable=False)
    component_group: Mapped[str | None]
    component_type: Mapped[str] = mapped_column(nullable=False)
    party_id: Mapped[int | None] = mapped_column(ForeignKey("parties.id"))
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    currency: Mapped[str] = mapped_column(ForeignKey("currencies.code"), nullable=False)
    direction: Mapped[str] = mapped_column(nullable=False)
    affects_settlement: Mapped[bool] = mapped_column(default=False, nullable=False)
    settlement_effect_type: Mapped[str | None]
    affects_profitability: Mapped[bool] = mapped_column(default=False, nullable=False)
    profitability_effect_type: Mapped[str | None]
    linked_detail_type: Mapped[str | None]
    linked_detail_id: Mapped[int | None]
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(default=utcnow, nullable=False)

