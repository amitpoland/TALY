from fastapi import FastAPI

from app.api import accounts, audit_logs, health, parties, roles, settlements, transactions, users


def create_app() -> FastAPI:
    app = FastAPI(title="Multi-Currency Brokerage Clearing & Commission Ledger API")
    app.include_router(health.router)
    app.include_router(roles.router)
    app.include_router(users.router)
    app.include_router(parties.router)
    app.include_router(accounts.router)
    app.include_router(transactions.router)
    app.include_router(settlements.router)
    app.include_router(audit_logs.router)
    return app


app = create_app()
