from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.common import TimestampMixin


class Party(TimestampMixin, Base):
    __tablename__ = "parties"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    party_type: Mapped[str] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    phone: Mapped[str | None]
    email: Mapped[str | None]
    address: Mapped[str | None] = mapped_column(Text)
    default_currency: Mapped[str | None] = mapped_column(ForeignKey("currencies.code"))
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    accounts = relationship("Account", back_populates="party")

