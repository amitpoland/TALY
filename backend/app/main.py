from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.api import accounts, audit_logs, currencies, health, parties, reports, roles, settlements, transactions, users

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def create_app() -> FastAPI:
    app = FastAPI(title="Multi-Currency Brokerage Clearing & Commission Ledger API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(currencies.router)
    app.include_router(roles.router)
    app.include_router(users.router)
    app.include_router(parties.router)
    app.include_router(accounts.router)
    app.include_router(transactions.router)
    app.include_router(settlements.router)
    app.include_router(reports.router)
    app.include_router(audit_logs.router)

    if FRONTEND_DIST.exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="frontend-assets")

        @app.get("/")
        def frontend_index():
            return FileResponse(FRONTEND_DIST / "index.html")

        @app.get("/{path:path}")
        def frontend_spa(path: str):
            if path.startswith(("accounts", "api", "audit-logs", "currencies", "health", "parties", "reports", "roles", "settlements", "transactions", "users")):
                return FileResponse(FRONTEND_DIST / "index.html")
            return FileResponse(FRONTEND_DIST / "index.html")

    return app


app = create_app()
