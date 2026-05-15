from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey

from app.db.session import Base
from app.models.common import utcnow


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    linked_entity_type: Mapped[str] = mapped_column(nullable=False)
    linked_entity_id: Mapped[int] = mapped_column(nullable=False)
    file_name: Mapped[str] = mapped_column(nullable=False)
    file_path: Mapped[str] = mapped_column(nullable=False)
    mime_type: Mapped[str | None]
    uploaded_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[str] = mapped_column(default=utcnow, nullable=False)

