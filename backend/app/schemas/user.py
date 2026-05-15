from pydantic import BaseModel

from app.schemas.common import ORMModel


class UserCreate(BaseModel):
    username: str
    password: str
    full_name: str
    role_id: int
    is_active: bool = True


class UserRead(ORMModel):
    id: int
    username: str
    full_name: str
    role_id: int
    is_active: bool

