from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.report import DashboardReportRead, ReportFilters, ReportRead
from app.services.reporting import report_service

router = APIRouter(prefix="/reports", tags=["reports"])


def _filters(
    date_from: str | None = None,
    date_to: str | None = None,
    currency: str | None = None,
    party_id: int | None = None,
    account_id: int | None = None,
    settlement_id: int | None = None,
) -> ReportFilters:
    return ReportFilters(
        date_from=date_from,
        date_to=date_to,
        currency=currency,
        party_id=party_id,
        account_id=account_id,
        settlement_id=settlement_id,
    )


@router.get("/dashboard", response_model=DashboardReportRead)
def dashboard(filters: ReportFilters = Depends(_filters), db: Session = Depends(get_db)):
    return report_service.dashboard_report(db, filters)


@router.get("/cash", response_model=ReportRead)
def cash(filters: ReportFilters = Depends(_filters), db: Session = Depends(get_db)):
    return report_service.cash_report(db, filters)


@router.get("/bank", response_model=ReportRead)
def bank(filters: ReportFilters = Depends(_filters), db: Session = Depends(get_db)):
    return report_service.bank_report(db, filters)


@router.get("/customer-ledger", response_model=ReportRead)
def customer_ledger(filters: ReportFilters = Depends(_filters), db: Session = Depends(get_db)):
    return report_service.customer_ledger(db, filters)


@router.get("/agent-ledger", response_model=ReportRead)
def agent_ledger(filters: ReportFilters = Depends(_filters), db: Session = Depends(get_db)):
    return report_service.agent_ledger(db, filters)


@router.get("/settlement-chain", response_model=ReportRead)
def settlement_chain(filters: ReportFilters = Depends(_filters), db: Session = Depends(get_db)):
    return report_service.settlement_chain_report(db, filters)


@router.get("/commission-earned", response_model=ReportRead)
def commission_earned(filters: ReportFilters = Depends(_filters), db: Session = Depends(get_db)):
    return report_service.commission_earned_report(db, filters)


@router.get("/commission-paid", response_model=ReportRead)
def commission_paid(filters: ReportFilters = Depends(_filters), db: Session = Depends(get_db)):
    return report_service.commission_paid_report(db, filters)


@router.get("/expenses", response_model=ReportRead)
def expenses(filters: ReportFilters = Depends(_filters), db: Session = Depends(get_db)):
    return report_service.expense_report(db, filters)


@router.get("/bank-charges", response_model=ReportRead)
def bank_charges(filters: ReportFilters = Depends(_filters), db: Session = Depends(get_db)):
    return report_service.bank_charges_report(db, filters)


@router.get("/fx-profit-loss", response_model=ReportRead)
def fx_profit_loss(filters: ReportFilters = Depends(_filters), db: Session = Depends(get_db)):
    return report_service.fx_profit_loss_report(db, filters)


@router.get("/currency-exposure", response_model=ReportRead)
def currency_exposure(filters: ReportFilters = Depends(_filters), db: Session = Depends(get_db)):
    return report_service.currency_exposure_report(db, filters)


@router.get("/pending-settlements", response_model=ReportRead)
def pending_settlements(filters: ReportFilters = Depends(_filters), db: Session = Depends(get_db)):
    return report_service.pending_settlements_report(db, filters)


@router.get("/closed-settlements", response_model=ReportRead)
def closed_settlements(filters: ReportFilters = Depends(_filters), db: Session = Depends(get_db)):
    return report_service.closed_settlements_report(db, filters)


@router.get("/daily-cash-closing", response_model=ReportRead)
def daily_cash_closing(filters: ReportFilters = Depends(_filters), db: Session = Depends(get_db)):
    return report_service.daily_cash_closing_report(db, filters)


@router.get("/monthly-profitability", response_model=ReportRead)
def monthly_profitability(filters: ReportFilters = Depends(_filters), db: Session = Depends(get_db)):
    return report_service.monthly_profitability_report(db, filters)
