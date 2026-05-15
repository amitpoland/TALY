"""backend foundation schema

Revision ID: 0001_backend_foundation
Revises:
Create Date: 2026-05-15
"""
from alembic import op
import sqlalchemy as sa


revision = "0001_backend_foundation"
down_revision = None
branch_labels = None
depends_on = None


money = sa.Numeric(18, 6)


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("permissions_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_table(
        "currencies",
        sa.Column("code", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("decimal_places", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(), nullable=False, unique=True),
        sa.Column("value_json", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_table(
        "parties",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("party_type", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("phone", sa.String()),
        sa.Column("email", sa.String()),
        sa.Column("address", sa.Text()),
        sa.Column("default_currency", sa.String(), sa.ForeignKey("currencies.code")),
        sa.Column("notes", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_code", sa.String(), nullable=False, unique=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("account_type", sa.String(), nullable=False),
        sa.Column("currency", sa.String(), sa.ForeignKey("currencies.code"), nullable=False),
        sa.Column("party_id", sa.Integer(), sa.ForeignKey("parties.id")),
        sa.Column("opening_balance", money, nullable=False, server_default="0"),
        sa.Column("current_balance", money, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_table(
        "settlements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("settlement_no", sa.String(), nullable=False, unique=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("primary_party_id", sa.Integer(), sa.ForeignKey("parties.id")),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("base_currency", sa.String(), sa.ForeignKey("currencies.code"), nullable=False),
        sa.Column("opened_at", sa.String(), nullable=False),
        sa.Column("closed_at", sa.String()),
        sa.Column("closed_by_user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("approved_pending_amount", money, nullable=False, server_default="0"),
        sa.Column("approved_pending_currency", sa.String(), sa.ForeignKey("currencies.code")),
        sa.Column("approved_pending_reason", sa.Text()),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("transaction_no", sa.String(), nullable=False, unique=True),
        sa.Column("settlement_id", sa.Integer(), sa.ForeignKey("settlements.id")),
        sa.Column("transaction_type", sa.String(), nullable=False),
        sa.Column("transaction_date", sa.String(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("gross_amount", money),
        sa.Column("gross_currency", sa.String(), sa.ForeignKey("currencies.code")),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("posted_at", sa.String()),
        sa.Column("reversed_transaction_id", sa.Integer(), sa.ForeignKey("transactions.id")),
        sa.Column("reversal_reason", sa.Text()),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_table(
        "transaction_components",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transactions.id"), nullable=False),
        sa.Column("settlement_id", sa.Integer(), sa.ForeignKey("settlements.id")),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("component_group", sa.String()),
        sa.Column("component_type", sa.String(), nullable=False),
        sa.Column("party_id", sa.Integer(), sa.ForeignKey("parties.id")),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id")),
        sa.Column("amount", money, nullable=False),
        sa.Column("currency", sa.String(), sa.ForeignKey("currencies.code"), nullable=False),
        sa.Column("direction", sa.String(), nullable=False),
        sa.Column("affects_settlement", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("settlement_effect_type", sa.String()),
        sa.Column("affects_profitability", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("profitability_effect_type", sa.String()),
        sa.Column("linked_detail_type", sa.String()),
        sa.Column("linked_detail_id", sa.Integer()),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transactions.id"), nullable=False),
        sa.Column("settlement_id", sa.Integer(), sa.ForeignKey("settlements.id")),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("entry_date", sa.String(), nullable=False),
        sa.Column("debit", money, nullable=False, server_default="0"),
        sa.Column("credit", money, nullable=False, server_default="0"),
        sa.Column("currency", sa.String(), sa.ForeignKey("currencies.code"), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_table(
        "commissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transactions.id"), nullable=False),
        sa.Column("settlement_id", sa.Integer(), sa.ForeignKey("settlements.id")),
        sa.Column("component_id", sa.Integer(), sa.ForeignKey("transaction_components.id")),
        sa.Column("commission_type", sa.String(), nullable=False),
        sa.Column("party_id", sa.Integer(), sa.ForeignKey("parties.id")),
        sa.Column("amount", money, nullable=False),
        sa.Column("currency", sa.String(), sa.ForeignKey("currencies.code"), nullable=False),
        sa.Column("calculation_method", sa.String(), nullable=False),
        sa.Column("rate", money),
        sa.Column("included_in_gross", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_table(
        "expenses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transactions.id"), nullable=False),
        sa.Column("settlement_id", sa.Integer(), sa.ForeignKey("settlements.id")),
        sa.Column("component_id", sa.Integer(), sa.ForeignKey("transaction_components.id")),
        sa.Column("expense_type", sa.String(), nullable=False),
        sa.Column("party_id", sa.Integer(), sa.ForeignKey("parties.id")),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id")),
        sa.Column("amount", money, nullable=False),
        sa.Column("currency", sa.String(), sa.ForeignKey("currencies.code"), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_table(
        "fx_conversions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transactions.id"), nullable=False),
        sa.Column("settlement_id", sa.Integer(), sa.ForeignKey("settlements.id")),
        sa.Column("from_account_id", sa.Integer(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("to_account_id", sa.Integer(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("from_currency", sa.String(), sa.ForeignKey("currencies.code"), nullable=False),
        sa.Column("to_currency", sa.String(), sa.ForeignKey("currencies.code"), nullable=False),
        sa.Column("from_amount", money, nullable=False),
        sa.Column("to_amount", money, nullable=False),
        sa.Column("costing_method", sa.String(), nullable=False),
        sa.Column("original_rate", money, nullable=False),
        sa.Column("actual_rate", money, nullable=False),
        sa.Column("weighted_avg_rate", money),
        sa.Column("base_currency", sa.String(), sa.ForeignKey("currencies.code"), nullable=False),
        sa.Column("original_base_value", money, nullable=False),
        sa.Column("actual_base_value", money, nullable=False),
        sa.Column("fx_difference", money, nullable=False),
        sa.Column("fx_charge", money, nullable=False, server_default="0"),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_table(
        "exchange_rate_lots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("currency", sa.String(), sa.ForeignKey("currencies.code"), nullable=False),
        sa.Column("base_currency", sa.String(), sa.ForeignKey("currencies.code"), nullable=False),
        sa.Column("source_transaction_id", sa.Integer(), sa.ForeignKey("transactions.id"), nullable=False),
        sa.Column("original_amount", money, nullable=False),
        sa.Column("remaining_amount", money, nullable=False),
        sa.Column("original_rate", money, nullable=False),
        sa.Column("original_base_value", money, nullable=False),
        sa.Column("remaining_base_value", money, nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_table(
        "fx_lot_consumptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fx_conversion_id", sa.Integer(), sa.ForeignKey("fx_conversions.id"), nullable=False),
        sa.Column("exchange_rate_lot_id", sa.Integer(), sa.ForeignKey("exchange_rate_lots.id"), nullable=False),
        sa.Column("consumed_amount", money, nullable=False),
        sa.Column("consumed_base_value", money, nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_table(
        "bank_statement_imports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bank_account_id", sa.Integer(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("file_name", sa.String(), nullable=False),
        sa.Column("file_type", sa.String(), nullable=False),
        sa.Column("file_hash", sa.String(), nullable=False, unique=True),
        sa.Column("imported_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("imported_at", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_table(
        "bank_statement_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("import_id", sa.Integer(), sa.ForeignKey("bank_statement_imports.id"), nullable=False),
        sa.Column("bank_account_id", sa.Integer(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("line_hash", sa.String(), nullable=False),
        sa.Column("line_date", sa.String(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("reference", sa.String()),
        sa.Column("debit", money, nullable=False, server_default="0"),
        sa.Column("credit", money, nullable=False, server_default="0"),
        sa.Column("currency", sa.String(), sa.ForeignKey("currencies.code"), nullable=False),
        sa.Column("balance_after", money),
        sa.Column("matched_transaction_id", sa.Integer(), sa.ForeignKey("transactions.id")),
        sa.Column("match_status", sa.String(), nullable=False, server_default="unmatched"),
        sa.Column("assigned_type", sa.String()),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_table(
        "attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("linked_entity_type", sa.String(), nullable=False),
        sa.Column("linked_entity_id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(), nullable=False),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("mime_type", sa.String()),
        sa.Column("uploaded_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.Integer()),
        sa.Column("before_json", sa.Text()),
        sa.Column("after_json", sa.Text()),
        sa.Column("reason", sa.Text()),
        sa.Column("created_at", sa.String(), nullable=False),
    )

    op.create_index("ix_accounts_type_currency", "accounts", ["account_type", "currency"])
    op.create_index("ix_accounts_party_id", "accounts", ["party_id"])
    op.create_index("ix_parties_type_name", "parties", ["party_type", "name"])
    op.create_index("ix_settlements_status", "settlements", ["status"])
    op.create_index("ix_transactions_date", "transactions", ["transaction_date"])
    op.create_index("ix_transactions_settlement_id", "transactions", ["settlement_id"])
    op.create_index("ix_components_transaction_id", "transaction_components", ["transaction_id"])
    op.create_index("ix_components_settlement_id", "transaction_components", ["settlement_id"])
    op.create_index("ix_ledger_account_currency", "ledger_entries", ["account_id", "currency"])
    op.create_index("ix_lots_account_currency_status", "exchange_rate_lots", ["account_id", "currency", "status"])
    op.create_index("ix_audit_entity", "audit_logs", ["entity_type", "entity_id"])
    op.create_index("ix_attachments_entity", "attachments", ["linked_entity_type", "linked_entity_id"])
    op.create_index("ux_bank_line_hash", "bank_statement_lines", ["import_id", "line_hash"], unique=True)


def downgrade() -> None:
    for table in [
        "audit_logs",
        "attachments",
        "bank_statement_lines",
        "bank_statement_imports",
        "fx_lot_consumptions",
        "exchange_rate_lots",
        "fx_conversions",
        "expenses",
        "commissions",
        "ledger_entries",
        "transaction_components",
        "transactions",
        "settlements",
        "accounts",
        "parties",
        "users",
        "app_settings",
        "currencies",
        "roles",
    ]:
        op.drop_table(table)

