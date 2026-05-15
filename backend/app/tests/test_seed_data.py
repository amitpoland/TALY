import json

from sqlalchemy.orm import Session

from app.models.app_setting import AppSetting
from app.models.currency import Currency
from app.models.role import Role


def test_seed_creates_roles_currencies_and_default_settings(db_session: Session) -> None:
    roles = {role.name for role in db_session.query(Role).all()}
    currencies = {currency.code for currency in db_session.query(Currency).all()}
    setting = db_session.query(AppSetting).filter(AppSetting.key == "base_currency").one()

    assert {"admin", "manager", "operator", "viewer"}.issubset(roles)
    assert {"USD", "EUR", "PLN", "AED", "INR"}.issubset(currencies)
    assert json.loads(setting.value_json) == {"code": "USD"}

