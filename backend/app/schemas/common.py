from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MoneyModel(BaseModel):
    @field_validator("*", mode="before")
    @classmethod
    def reject_float_money(cls, value):
        if isinstance(value, float):
            raise ValueError("Money values must be strings, integers, or Decimal; floats are not allowed")
        return value


def decimal_zero() -> Decimal:
    return Decimal("0")

