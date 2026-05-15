from app.schemas.common import ORMModel


class RoleRead(ORMModel):
    id: int
    name: str
    permissions_json: str

