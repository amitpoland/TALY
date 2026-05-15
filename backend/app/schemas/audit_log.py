from app.schemas.common import ORMModel


class AuditLogRead(ORMModel):
    id: int
    user_id: int | None
    action: str
    entity_type: str
    entity_id: int | None
    before_json: str | None
    after_json: str | None
    reason: str | None
    created_at: str

