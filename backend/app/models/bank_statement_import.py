from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey

from app.db.session import Base
from app.models.common import utcnow


class BankStatementImport(Base):
    __tablename__ = "bank_statement_imports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bank_account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    file_name: Mapped[str] = mapped_column(nullable=False)
    file_type: Mapped[str] = mapped_column(nullable=False)
    file_hash: Mapped[str] = mapped_column(nullable=False, unique=True)
    imported_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    imported_at: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[str] = mapped_column(default=utcnow, nullable=False)

