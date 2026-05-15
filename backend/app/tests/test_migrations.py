from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_alembic_migration_creates_foundation_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "migration.sqlite3"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

    command.upgrade(cfg, "head")

    engine = create_engine(f"sqlite:///{db_path}")
    tables = set(inspect(engine).get_table_names())

    assert "users" in tables
    assert "roles" in tables
    assert "parties" in tables
    assert "accounts" in tables
    assert "audit_logs" in tables
    assert "transaction_components" in tables
    assert "ledger_entries" in tables

