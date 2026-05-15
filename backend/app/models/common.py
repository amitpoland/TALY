from datetime import datetime, timezone

from sqlalchemy.orm import Mapped, mapped_column


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class TimestampMixin:
    created_at: Mapped[str] = mapped_column(default=utcnow, nullable=False)
    updated_at: Mapped[str] = mapped_column(default=utcnow, onupdate=utcnow, nullable=False)

