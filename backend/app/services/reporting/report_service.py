from collections import defaultdict
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.enums import AccountType, ComponentType, ProfitabilityEffectType, TransactionStatus
from app.models.account import Account
from app.models.ledger_entry import LedgerEntry
from app.models.party import Party
from app.models.settlement import Settlement
from app.models.transaction import Transaction
from app.models.transaction_component import TransactionComponent
from app.schemas.report import DashboardReportRead, ReportFilters, ReportRead


POSTED_STATUSES = {TransactionStatus.POSTED.value, TransactionStatus.REVERSED.value}


def _zero() -> Decimal:
    return Decimal("0")


def _amount(value: Decimal | None) -> Decimal:
    return value if value is not None else Decimal("0")


def _matches_common_filters(
    *,
    transaction: Transaction,
    currency: str,
    account_id: int | None,
    party_id: int | None,
    settlement_id: int | None,
    filters: ReportFilters,
) -> bool:
    if transaction.status not in POSTED_STATUSES:
        return False
    if filters.date_from and transaction.transaction_date < filters.date_from:
        return False
    if filters.date_to and transaction.transaction_date > filters.date_to:
        return False
    if filters.currency and currency != filters.currency:
        return False
    if filters.account_id and account_id != filters.account_id:
        return False
    if filters.party_id and party_id != filters.party_id:
        return False
    if filters.settlement_id and settlement_id != filters.settlement_id:
        return False
    return True


def _ledger_rows(db: Session, filters: ReportFilters, account_types: set[str] | None = None) -> list[tuple[LedgerEntry, Transaction, Account]]:
    rows = (
        db.query(LedgerEntry, Transaction, Account)
        .join(Transaction, Transaction.id == LedgerEntry.transaction_id)
        .join(Account, Account.id == LedgerEntry.account_id)
        .filter(Transaction.status.in_(POSTED_STATUSES))
        .all()
    )
    result: list[tuple[LedgerEntry, Transaction, Account]] = []
    for entry, transaction, account in rows:
        if account_types and account.account_type not in account_types:
            continue
        if not _matches_common_filters(
            transaction=transaction,
            currency=entry.currency,
            account_id=entry.account_id,
            party_id=account.party_id,
            settlement_id=entry.settlement_id,
            filters=filters,
        ):
            continue
        result.append((entry, transaction, account))
    return result


def _component_rows(
    db: Session,
    filters: ReportFilters,
    component_types: set[str] | None = None,
) -> list[tuple[TransactionComponent, Transaction, Account | None]]:
    rows = (
        db.query(TransactionComponent, Transaction, Account)
        .join(Transaction, Transaction.id == TransactionComponent.transaction_id)
        .outerjoin(Account, Account.id == TransactionComponent.account_id)
        .filter(Transaction.status.in_(POSTED_STATUSES))
        .all()
    )
    result: list[tuple[TransactionComponent, Transaction, Account | None]] = []
    for component, transaction, account in rows:
        if component_types and component.component_type not in component_types:
            continue
        party_id = component.party_id if component.party_id is not None else (account.party_id if account else None)
        account_id = component.account_id
        if not _matches_common_filters(
            transaction=transaction,
            currency=component.currency,
            account_id=account_id,
            party_id=party_id,
            settlement_id=component.settlement_id,
            filters=filters,
        ):
            continue
        result.append((component, transaction, account))
    return result


def _ledger_account_report(db: Session, filters: ReportFilters, account_types: set[str]) -> ReportRead:
    grouped: dict[tuple[int, str], dict[str, object]] = {}
    totals: dict[str, Decimal] = defaultdict(_zero)
    for entry, _, account in _ledger_rows(db, filters, account_types):
        key = (account.id, entry.currency)
        if key not in grouped:
            grouped[key] = {
                "account_id": account.id,
                "account_code": account.account_code,
                "account_name": account.name,
                "account_type": account.account_type,
                "currency": entry.currency,
                "debit": Decimal("0"),
                "credit": Decimal("0"),
                "balance": Decimal("0"),
            }
        grouped[key]["debit"] += _amount(entry.debit)
        grouped[key]["credit"] += _amount(entry.credit)
        grouped[key]["balance"] += _amount(entry.debit) - _amount(entry.credit)
        totals[entry.currency] += _amount(entry.debit) - _amount(entry.credit)
    rows = sorted(grouped.values(), key=lambda row: (str(row["currency"]), str(row["account_code"])))
    return ReportRead(filters=filters, rows=rows, totals=dict(totals))


def cash_report(db: Session, filters: ReportFilters) -> ReportRead:
    return _ledger_account_report(db, filters, {AccountType.CASH.value})


def bank_report(db: Session, filters: ReportFilters) -> ReportRead:
    return _ledger_account_report(db, filters, {AccountType.BANK.value})


def _party_ledger(db: Session, filters: ReportFilters, party_type: str, account_types: set[str]) -> ReportRead:
    rows: list[dict[str, object]] = []
    totals: dict[str, Decimal] = defaultdict(_zero)
    for entry, transaction, account in _ledger_rows(db, filters, account_types):
        if account.party_id is None:
            continue
        party = db.get(Party, account.party_id)
        if party is None or party.party_type != party_type:
            continue
        amount = _amount(entry.debit) - _amount(entry.credit)
        totals[entry.currency] += amount
        rows.append(
            {
                "transaction_id": transaction.id,
                "transaction_no": transaction.transaction_no,
                "transaction_date": transaction.transaction_date,
                "transaction_type": transaction.transaction_type,
                "party_id": party.id,
                "party_name": party.name,
                "account_id": account.id,
                "account_code": account.account_code,
                "currency": entry.currency,
                "debit": entry.debit,
                "credit": entry.credit,
                "balance_effect": amount,
                "description": entry.description,
            }
        )
    rows.sort(key=lambda row: (str(row["transaction_date"]), int(row["transaction_id"])))
    return ReportRead(filters=filters, rows=rows, totals=dict(totals))


def customer_ledger(db: Session, filters: ReportFilters) -> ReportRead:
    return _party_ledger(db, filters, "customer", {AccountType.CUSTOMER_WALLET.value})


def agent_ledger(db: Session, filters: ReportFilters) -> ReportRead:
    return _party_ledger(db, filters, "agent", {AccountType.AGENT_WALLET.value})


def settlement_chain_report(db: Session, filters: ReportFilters) -> ReportRead:
    rows: list[dict[str, object]] = []
    totals: dict[str, Decimal] = defaultdict(_zero)
    for component, transaction, account in _component_rows(db, filters):
        if component.settlement_id is None:
            continue
        amount = _settlement_signed_amount(component)
        if component.affects_settlement:
            totals[component.currency] += amount
        rows.append(
            {
                "settlement_id": component.settlement_id,
                "transaction_id": transaction.id,
                "transaction_no": transaction.transaction_no,
                "transaction_date": transaction.transaction_date,
                "transaction_type": transaction.transaction_type,
                "component_type": component.component_type,
                "amount": component.amount,
                "currency": component.currency,
                "direction": component.direction,
                "affects_settlement": component.affects_settlement,
                "settlement_effect_type": component.settlement_effect_type,
                "settlement_amount": amount if component.affects_settlement else Decimal("0"),
                "account_id": component.account_id,
                "account_code": account.account_code if account else None,
            }
        )
    rows.sort(key=lambda row: (int(row["settlement_id"]), str(row["transaction_date"]), int(row["transaction_id"]), str(row["component_type"])))
    return ReportRead(filters=filters, rows=rows, totals=dict(totals))


def _settlement_signed_amount(component: TransactionComponent) -> Decimal:
    sign = Decimal("-1") if component.settlement_effect_type in {"principal_out", "adjustment_out"} else Decimal("1")
    return sign * component.amount


def _profitability_signed_amount(component: TransactionComponent) -> Decimal:
    sign = Decimal("1") if component.profitability_effect_type == ProfitabilityEffectType.INCOME.value else Decimal("-1")
    return sign * component.amount


def _component_report(
    db: Session,
    filters: ReportFilters,
    component_types: set[str],
    *,
    account_types: set[str] | None = None,
    profitability_only: bool = False,
) -> ReportRead:
    rows: list[dict[str, object]] = []
    totals: dict[str, Decimal] = defaultdict(_zero)
    for component, transaction, account in _component_rows(db, filters, component_types):
        if account_types and (account is None or account.account_type not in account_types):
            continue
        if profitability_only and not component.affects_profitability:
            continue
        amount = _profitability_signed_amount(component) if component.affects_profitability else component.amount
        totals[component.currency] += amount
        rows.append(
            {
                "transaction_id": transaction.id,
                "transaction_no": transaction.transaction_no,
                "transaction_date": transaction.transaction_date,
                "transaction_type": transaction.transaction_type,
                "settlement_id": component.settlement_id,
                "component_id": component.id,
                "component_type": component.component_type,
                "account_id": component.account_id,
                "account_code": account.account_code if account else None,
                "amount": component.amount,
                "currency": component.currency,
                "profitability_amount": amount,
                "notes": component.notes,
            }
        )
    rows.sort(key=lambda row: (str(row["transaction_date"]), int(row["transaction_id"]), int(row["component_id"])))
    return ReportRead(filters=filters, rows=rows, totals=dict(totals))


def commission_earned_report(db: Session, filters: ReportFilters) -> ReportRead:
    return _component_report(db, filters, {ComponentType.YOUR_COMMISSION.value}, profitability_only=True)


def commission_paid_report(db: Session, filters: ReportFilters) -> ReportRead:
    return _component_report(db, filters, {"agent_commission", "commission_paid", "commission_payable"}, profitability_only=False)


def expense_report(db: Session, filters: ReportFilters) -> ReportRead:
    return _component_report(db, filters, {ComponentType.EXPENSE.value, ComponentType.FX_CHARGE.value}, profitability_only=True)


def bank_charges_report(db: Session, filters: ReportFilters) -> ReportRead:
    return _component_report(
        db,
        filters,
        {ComponentType.EXPENSE.value, "bank_charge"},
        account_types={AccountType.BANK_CHARGE_EXPENSE.value},
        profitability_only=True,
    )


def fx_profit_loss_report(db: Session, filters: ReportFilters) -> ReportRead:
    return _component_report(db, filters, {ComponentType.FX_GAIN.value, ComponentType.FX_LOSS.value}, profitability_only=True)


def currency_exposure_report(db: Session, filters: ReportFilters) -> ReportRead:
    account_types = {
        AccountType.CASH.value,
        AccountType.BANK.value,
        AccountType.CUSTOMER_WALLET.value,
        AccountType.AGENT_WALLET.value,
        AccountType.FX_DEALER_WALLET.value,
    }
    rows = _ledger_account_report(db, filters, account_types).rows
    totals: dict[str, Decimal] = defaultdict(_zero)
    for row in rows:
        totals[str(row["currency"])] += row["balance"]
    return ReportRead(filters=filters, rows=rows, totals=dict(totals))


def _settlement_report(db: Session, filters: ReportFilters, statuses: set[str]) -> ReportRead:
    rows: list[dict[str, object]] = []
    query = db.query(Settlement).filter(Settlement.status.in_(statuses)).all()
    for settlement in query:
        if filters.settlement_id and settlement.id != filters.settlement_id:
            continue
        if filters.currency and settlement.base_currency != filters.currency:
            continue
        rows.append(
            {
                "settlement_id": settlement.id,
                "settlement_no": settlement.settlement_no,
                "title": settlement.title,
                "status": settlement.status,
                "base_currency": settlement.base_currency,
                "opened_at": settlement.opened_at,
                "closed_at": settlement.closed_at,
                "approved_pending_amount": settlement.approved_pending_amount,
                "approved_pending_currency": settlement.approved_pending_currency,
                "approved_pending_reason": settlement.approved_pending_reason,
            }
        )
    rows.sort(key=lambda row: str(row["settlement_no"]))
    return ReportRead(filters=filters, rows=rows, totals={})


def pending_settlements_report(db: Session, filters: ReportFilters) -> ReportRead:
    return _settlement_report(db, filters, {"open", "reopened"})


def closed_settlements_report(db: Session, filters: ReportFilters) -> ReportRead:
    return _settlement_report(db, filters, {"closed"})


def daily_cash_closing_report(db: Session, filters: ReportFilters) -> ReportRead:
    daily: dict[tuple[str, str], dict[str, object]] = {}
    running: dict[str, Decimal] = defaultdict(_zero)
    rows = sorted(_ledger_rows(db, filters, {AccountType.CASH.value}), key=lambda row: (row[0].entry_date, row[0].currency, row[0].id))
    for entry, _, _ in rows:
        key = (entry.entry_date, entry.currency)
        if key not in daily:
            daily[key] = {
                "date": entry.entry_date,
                "currency": entry.currency,
                "cash_in": Decimal("0"),
                "cash_out": Decimal("0"),
                "net_movement": Decimal("0"),
                "closing_balance": Decimal("0"),
            }
        daily[key]["cash_in"] += _amount(entry.debit)
        daily[key]["cash_out"] += _amount(entry.credit)
        daily[key]["net_movement"] += _amount(entry.debit) - _amount(entry.credit)
    result = []
    for key in sorted(daily):
        row = daily[key]
        currency = str(row["currency"])
        running[currency] += row["net_movement"]
        row["closing_balance"] = running[currency]
        result.append(row)
    totals = {currency: amount for currency, amount in running.items()}
    return ReportRead(filters=filters, rows=result, totals=totals)


def monthly_profitability_report(db: Session, filters: ReportFilters) -> ReportRead:
    monthly: dict[tuple[str, str], dict[str, object]] = {}
    totals: dict[str, Decimal] = defaultdict(_zero)
    for component, transaction, _ in _component_rows(db, filters):
        if not component.affects_profitability:
            continue
        month = transaction.transaction_date[:7]
        key = (month, component.currency)
        if key not in monthly:
            monthly[key] = {
                "month": month,
                "currency": component.currency,
                "income": Decimal("0"),
                "expenses": Decimal("0"),
                "net_profitability": Decimal("0"),
            }
        amount = _profitability_signed_amount(component)
        if amount >= 0:
            monthly[key]["income"] += amount
        else:
            monthly[key]["expenses"] += -amount
        monthly[key]["net_profitability"] += amount
        totals[component.currency] += amount
    rows = [monthly[key] for key in sorted(monthly)]
    return ReportRead(filters=filters, rows=rows, totals=dict(totals))


def dashboard_report(db: Session, filters: ReportFilters) -> DashboardReportRead:
    cash = cash_report(db, filters).totals
    bank = bank_report(db, filters).totals
    commission = commission_earned_report(db, filters).totals
    expenses = expense_report(db, filters).totals
    fx = fx_profit_loss_report(db, filters).totals
    profitability = monthly_profitability_report(db, filters).totals
    pending = len(pending_settlements_report(db, filters).rows)
    closed = len(closed_settlements_report(db, filters).rows)
    return DashboardReportRead(
        filters=filters,
        cash_balances=cash,
        bank_balances=bank,
        pending_settlements=pending,
        closed_settlements=closed,
        commission_earned=commission,
        expenses=expenses,
        fx_profit_loss=fx,
        net_profitability=profitability,
    )

