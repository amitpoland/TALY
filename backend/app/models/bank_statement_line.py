from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.common import utcnow


class BankStatementLine(Base):
    __tablename__ = "bank_statement_lines"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    import_id: Mapped[int] = mapped_column(ForeignKey("bank_statement_imports.id"), nullable=False)
    bank_account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    line_hash: Mapped[str] = mapped_column(nullable=False)
    line_date: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    reference: Mapped[str | None]
    debit: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"), nullable=False)
    credit: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"), nullable=False)
    currency: Mapped[str] = mapped_column(ForeignKey("currencies.code"), nullable=False)
    balance_after: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    matched_transaction_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id"))
    match_status: Mapped[str] = mapped_column(default="unmatched", nullable=False)
    assigned_type: Mapped[str | None]
    created_at: Mapped[str] = mapped_column(default=utcnow, nullable=False)

