import json

from sqlalchemy.orm import Session

from app.models.app_setting import AppSetting
from app.models.common import utcnow
from app.models.currency import Currency
from app.models.role import Role


ROLE_PERMISSIONS = {
    "admin": [
        "manage_users",
        "manage_master_data",
        "view_audit_logs",
        "approve_negative_bank",
        "approve_negative_wallet",
        "approve_base_currency_closure",
    ],
    "manager": [
        "manage_master_data",
        "view_audit_logs",
        "approve_negative_bank",
        "approve_negative_wallet",
    ],
    "operator": ["manage_master_data"],
    "viewer": [],
}

CURRENCIES = [
    ("USD", "US Dollar", 2),
    ("EUR", "Euro", 2),
    ("PLN", "Polish Zloty", 2),
    ("AED", "UAE Dirham", 2),
    ("INR", "Indian Rupee", 2),
]

SETTINGS = {
    "base_currency": {"code": "USD"},
    "fx_lot_consumption": {"method": "fifo", "show_weighted_average": True},
    "negative_balance_policy": {
        "cash": "blocked",
        "bank": "permission_required",
        "wallet": "permission_required",
    },
    "settlement_closure_policy": {
        "default": "zero_by_original_currency",
        "base_currency_only": "admin_approval_required",
    },
}


def seed_foundation_data(db: Session) -> None:
    now = utcnow()
    for name, permissions in ROLE_PERMISSIONS.items():
        role = db.query(Role).filter(Role.name == name).one_or_none()
        if role is None:
            db.add(
                Role(
                    name=name,
                    permissions_json=json.dumps(permissions),
                    created_at=now,
                    updated_at=now,
                )
            )

    for code, name, decimal_places in CURRENCIES:
        currency = db.get(Currency, code)
        if currency is None:
            db.add(
                Currency(
                    code=code,
                    name=name,
                    decimal_places=decimal_places,
                    is_active=True,
                )
            )

    for key, value in SETTINGS.items():
        setting = db.query(AppSetting).filter(AppSetting.key == key).one_or_none()
        if setting is None:
            db.add(AppSetting(key=key, value_json=json.dumps(value), updated_at=now))

    db.commit()

