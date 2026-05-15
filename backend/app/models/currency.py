from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Currency(Base):
    __tablename__ = "currencies"

    code: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)
    decimal_places: Mapped[int] = mapped_column(default=2, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

