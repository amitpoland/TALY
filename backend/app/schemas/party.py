from pydantic import BaseModel

from app.core.enums import PartyType
from app.schemas.common import ORMModel


class PartyCreate(BaseModel):
    party_type: PartyType
    name: str
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    default_currency: str | None = None
    notes: str | None = None


class PartyUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    default_currency: str | None = None
    notes: str | None = None
    is_active: bool | None = None


class PartyRead(ORMModel):
    id: int
    party_type: str
    name: str
    phone: str | None
    email: str | None
    address: str | None
    default_currency: str | None
    notes: str | None
    is_active: bool

