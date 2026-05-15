from app.schemas.common import ORMModel


class CurrencyRead(ORMModel):
    code: str
    name: str
    decimal_places: int
    is_active: bool
