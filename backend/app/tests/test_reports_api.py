from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.ledger_entry import LedgerEntry
from app.models.party import Party
from app.models.role import Role
from app.models.settlement import Settlement
from app.models.transaction import Transaction
from app.models.transaction_component import TransactionComponent
from app.models.user import User
from app.models.common import utcnow


def create_user(db: Session) -> User:
    role = db.query(Role).filter(Role.name == "admin").one()
    user = User(username="report-user", password_hash="test", full_name="Report User", role_id=role.id)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_party(db: Session, name: str, party_type: str) -> Party:
    party = Party(party_type=party_type, name=name, default_currency="USD", is_active=True)
    db.add(party)
    db.commit()
    db.refresh(party)
    return party


def create_account(db: Session, code: str, account_type: str, currency: str = "USD", party_id: int | None = None) -> Account:
    account = Account(
        account_code=code,
        name=code,
        account_type=account_type,
        currency=currency,
        party_id=party_id,
        opening_balance=Decimal("0"),
        current_balance=Decimal("0"),
        is_active=True,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def create_settlement(db: Session, number: str, status: str = "open") -> Settlement:
    settlement = Settlement(
        settlement_no=number,
        title=number,
        status=status,
        base_currency="USD",
        opened_at=utcnow(),
    )
    db.add(settlement)
    db.commit()
    db.refresh(settlement)
    return settlement


def post(client: TestClient, path: str, payload: dict) -> dict:
    response = client.post(path, json={"payload": payload, "confirmation": {"confirmed_by_user": True}})
    assert response.status_code == 201, response.text
    return response.json()


def add_manual_component(
    db: Session,
    *,
    user: User,
    transaction_no: str,
    transaction_date: str,
    component_type: str,
    amount: str,
    currency: str,
    account: Account,
    status: str = "posted",
    settlement_id: int | None = None,
    affects_profitability: bool = True,
    profitability_effect_type: str = "expense",
    affects_settlement: bool = False,
    settlement_effect_type: str | None = None,
) -> Transaction:
    transaction = Transaction(
        transaction_no=transaction_no,
        settlement_id=settlement_id,
        transaction_type="adjustment",
        transaction_date=transaction_date,
        status=status,
        gross_amount=Decimal(amount),
        gross_currency=currency,
        created_by_user_id=user.id,
        posted_at=utcnow() if status != "draft" else None,
    )
    db.add(transaction)
    db.flush()
    db.add(
        TransactionComponent(
            transaction_id=transaction.id,
            settlement_id=settlement_id,
            sequence_no=1,
            component_type=component_type,
            account_id=account.id,
            amount=Decimal(amount),
            currency=currency,
            direction="out",
            affects_settlement=affects_settlement,
            settlement_effect_type=settlement_effect_type,
            affects_profitability=affects_profitability,
            profitability_effect_type=profitability_effect_type,
        )
    )
    db.commit()
    db.refresh(transaction)
    return transaction


def seed_report_data(client: TestClient, db: Session):
    user = create_user(db)
    customer = create_party(db, "Customer One", "customer")
    agent = create_party(db, "Agent One", "agent")
    cash = create_account(db, "RPT-CASH", "cash")
    bank = create_account(db, "RPT-BANK", "bank")
    equity = create_account(db, "RPT-EQUITY", "owner_equity")
    clearing = create_account(db, "RPT-CLEARING", "clearing")
    commission = create_account(db, "RPT-COMMISSION", "commission_income")
    expense = create_account(db, "RPT-EXPENSE", "expense")
    bank_charge = create_account(db, "RPT-BANK-CHARGE", "bank_charge_expense")
    customer_wallet = create_account(db, "RPT-CUSTOMER-WALLET", "customer_wallet", party_id=customer.id)
    agent_wallet = create_account(db, "RPT-AGENT-WALLET", "agent_wallet", party_id=agent.id)
    settlement = create_settlement(db, "RPT-SET-CLOSED")
    pending = create_settlement(db, "RPT-SET-PENDING")

    post(client, "/transactions/opening-balance/post", {"transaction_date": "2026-05-01", "created_by_user_id": user.id, "account_id": cash.id, "equity_account_id": equity.id, "amount": "500.00", "currency": "USD"})
    post(client, "/transactions/opening-balance/post", {"transaction_date": "2026-05-01", "created_by_user_id": user.id, "account_id": bank.id, "equity_account_id": equity.id, "amount": "1000.00", "currency": "USD"})
    post(client, "/transactions/opening-balance/post", {"transaction_date": "2026-05-01", "created_by_user_id": user.id, "account_id": customer_wallet.id, "equity_account_id": equity.id, "amount": "70.00", "currency": "USD"})
    post(client, "/transactions/opening-balance/post", {"transaction_date": "2026-05-01", "created_by_user_id": user.id, "account_id": agent_wallet.id, "equity_account_id": equity.id, "amount": "30.00", "currency": "USD"})

    receipt = post(
        client,
        "/transactions/receipt/post",
        {
            "transaction_date": "2026-05-10",
            "created_by_user_id": user.id,
            "settlement_id": settlement.id,
            "receiving_account_id": cash.id,
            "clearing_account_id": clearing.id,
            "gross_amount": "100.00",
            "principal_amount": "95.00",
            "commission_amount": "5.00",
            "commission_income_account_id": commission.id,
            "currency": "USD",
        },
    )
    post(client, "/transactions/payment/post", {"transaction_date": "2026-05-11", "created_by_user_id": user.id, "settlement_id": settlement.id, "paying_account_id": cash.id, "clearing_account_id": clearing.id, "amount": "95.00", "currency": "USD"})
    client.post(f"/settlements/{settlement.id}/close", json={"user_id": user.id})

    post(client, "/transactions/expense/post", {"transaction_date": "2026-05-12", "created_by_user_id": user.id, "payment_account_id": cash.id, "expense_account_id": expense.id, "amount": "7.00", "currency": "USD", "expense_type": "office"})
    post(client, "/transactions/expense/post", {"transaction_date": "2026-05-13", "created_by_user_id": user.id, "payment_account_id": bank.id, "expense_account_id": bank_charge.id, "amount": "3.00", "currency": "USD", "expense_type": "bank_charge"})

    fx_source = create_account(db, "RPT-FX-SOURCE", "cash")
    fx_target = create_account(db, "RPT-FX-TARGET", "cash", "AED")
    fx_clear_usd = create_account(db, "RPT-FX-CLEAR-USD", "clearing")
    fx_clear_aed = create_account(db, "RPT-FX-CLEAR-AED", "clearing", "AED")
    fx_gl = create_account(db, "RPT-FX-GL", "fx_gain_loss", "AED")
    post(client, "/transactions/opening-balance/post", {"transaction_date": "2026-05-01", "created_by_user_id": user.id, "account_id": fx_source.id, "equity_account_id": equity.id, "amount": "100.00", "currency": "USD", "base_currency": "AED", "original_rate": "3.90"})
    post(client, "/transactions/fx-conversion/post", {"transaction_date": "2026-05-14", "created_by_user_id": user.id, "from_account_id": fx_source.id, "to_account_id": fx_target.id, "source_clearing_account_id": fx_clear_usd.id, "target_clearing_account_id": fx_clear_aed.id, "fx_gain_loss_account_id": fx_gl.id, "from_amount": "100.00", "to_amount": "400.00", "from_currency": "USD", "to_currency": "AED", "base_currency": "AED"})

    reversed_receipt = post(client, "/transactions/receipt/post", {"transaction_date": "2026-05-15", "created_by_user_id": user.id, "receiving_account_id": cash.id, "clearing_account_id": clearing.id, "gross_amount": "20.00", "principal_amount": "20.00", "currency": "USD"})
    post(client, f"/transactions/{reversed_receipt['transaction_id']}/reverse/post", {"transaction_date": "2026-05-15", "created_by_user_id": user.id, "reversal_reason": "Report reversal"})

    add_manual_component(db, user=user, transaction_no="RPT-COMM-PAID", transaction_date="2026-05-16", component_type="commission_paid", amount="2.00", currency="USD", account=agent_wallet)
    add_manual_component(db, user=user, transaction_no="RPT-DRAFT", transaction_date="2026-05-17", component_type="expense", amount="999.00", currency="USD", account=expense, status="draft")

    return {
        "user": user,
        "cash": cash,
        "bank": bank,
        "customer": customer,
        "agent": agent,
        "settlement": settlement,
        "pending": pending,
        "receipt": receipt,
    }


def total(response: dict, currency: str) -> Decimal:
    return Decimal(str(response["totals"][currency]))


def test_cash_report_by_currency_and_reversed_transactions_net(client: TestClient, db_session: Session) -> None:
    seed_report_data(client, db_session)

    response = client.get("/reports/cash?currency=USD")

    assert response.status_code == 200
    assert total(response.json(), "USD") == Decimal("498.000000")


def test_bank_report_by_currency(client: TestClient, db_session: Session) -> None:
    seed_report_data(client, db_session)

    response = client.get("/reports/bank")

    assert response.status_code == 200
    assert total(response.json(), "USD") == Decimal("997.000000")


def test_day_book_report_shows_daily_vouchers_and_currency_totals(client: TestClient, db_session: Session) -> None:
    seed_report_data(client, db_session)

    response = client.get("/reports/day-book?date_from=2026-05-10&date_to=2026-05-14")

    assert response.status_code == 200
    body = response.json()
    rows = body["rows"]
    receipt = next(row for row in rows if row["voucher_type"] == "receipt")
    payment = next(row for row in rows if row["voucher_type"] == "payment")
    fx = next(row for row in rows if row["voucher_type"] == "currency_exchange" and row["currency"] == "AED")
    assert Decimal(receipt["money_in"]) == Decimal("100.000000")
    assert Decimal(receipt["commission"]) == Decimal("5.000000")
    assert Decimal(payment["money_out"]) == Decimal("95.000000")
    assert Decimal(fx["money_in"]) == Decimal("400.000000")
    assert Decimal(fx["fx_difference"]) == Decimal("10.000000")
    assert Decimal(body["totals"]["USD_money_in"]) == Decimal("100.000000")
    assert Decimal(body["totals"]["USD_money_out"]) == Decimal("205.000000")
    assert Decimal(body["totals"]["AED_money_in"]) == Decimal("400.000000")


def test_customer_ledger(client: TestClient, db_session: Session) -> None:
    data = seed_report_data(client, db_session)

    response = client.get(f"/reports/customer-ledger?party_id={data['customer'].id}")

    assert response.status_code == 200
    assert total(response.json(), "USD") == Decimal("70.000000")
    assert response.json()["rows"][0]["party_name"] == "Customer One"


def test_agent_ledger(client: TestClient, db_session: Session) -> None:
    data = seed_report_data(client, db_session)

    response = client.get(f"/reports/agent-ledger?party_id={data['agent'].id}")

    assert response.status_code == 200
    assert total(response.json(), "USD") == Decimal("30.000000")
    assert response.json()["rows"][0]["party_name"] == "Agent One"


def test_settlement_chain_report(client: TestClient, db_session: Session) -> None:
    data = seed_report_data(client, db_session)

    response = client.get(f"/reports/settlement-chain?settlement_id={data['settlement'].id}")

    assert response.status_code == 200
    assert total(response.json(), "USD") == Decimal("0.000000")
    assert {row["component_type"] for row in response.json()["rows"]} >= {"principal", "gross_receipt", "your_commission"}


def test_commission_earned_report(client: TestClient, db_session: Session) -> None:
    seed_report_data(client, db_session)

    response = client.get("/reports/commission-earned")

    assert response.status_code == 200
    assert total(response.json(), "USD") == Decimal("5.000000")


def test_commission_paid_report(client: TestClient, db_session: Session) -> None:
    seed_report_data(client, db_session)

    response = client.get("/reports/commission-paid")

    assert response.status_code == 200
    assert total(response.json(), "USD") == Decimal("-2.000000")


def test_expense_ledger_and_draft_transactions_excluded(client: TestClient, db_session: Session) -> None:
    seed_report_data(client, db_session)

    response = client.get("/reports/expenses")

    assert response.status_code == 200
    assert total(response.json(), "USD") == Decimal("-10.000000")
    assert all(row["amount"] != "999.000000" for row in response.json()["rows"])


def test_bank_charges_report(client: TestClient, db_session: Session) -> None:
    seed_report_data(client, db_session)

    response = client.get("/reports/bank-charges")

    assert response.status_code == 200
    assert total(response.json(), "USD") == Decimal("-3.000000")


def test_fx_profit_loss_report(client: TestClient, db_session: Session) -> None:
    seed_report_data(client, db_session)

    response = client.get("/reports/fx-profit-loss")

    assert response.status_code == 200
    assert total(response.json(), "AED") == Decimal("10.000000")


def test_currency_exposure_report(client: TestClient, db_session: Session) -> None:
    seed_report_data(client, db_session)

    response = client.get("/reports/currency-exposure")

    assert response.status_code == 200
    assert total(response.json(), "USD") == Decimal("1595.000000")
    assert total(response.json(), "AED") == Decimal("400.000000")


def test_pending_and_closed_settlements_reports(client: TestClient, db_session: Session) -> None:
    data = seed_report_data(client, db_session)

    pending = client.get("/reports/pending-settlements")
    closed = client.get("/reports/closed-settlements")

    assert pending.status_code == 200
    assert closed.status_code == 200
    assert any(row["settlement_id"] == data["pending"].id for row in pending.json()["rows"])
    assert any(row["settlement_id"] == data["settlement"].id for row in closed.json()["rows"])


def test_daily_cash_closing(client: TestClient, db_session: Session) -> None:
    seed_report_data(client, db_session)

    response = client.get("/reports/daily-cash-closing?currency=USD")

    assert response.status_code == 200
    rows = response.json()["rows"]
    assert rows[-1]["date"] == "2026-05-15"
    assert Decimal(rows[-1]["closing_balance"]) == Decimal("498.000000")


def test_monthly_profitability(client: TestClient, db_session: Session) -> None:
    seed_report_data(client, db_session)

    response = client.get("/reports/monthly-profitability")

    assert response.status_code == 200
    assert total(response.json(), "USD") == Decimal("-7.000000")
    assert total(response.json(), "AED") == Decimal("10.000000")


def test_dashboard_summary(client: TestClient, db_session: Session) -> None:
    seed_report_data(client, db_session)

    response = client.get("/reports/dashboard")

    assert response.status_code == 200
    body = response.json()
    assert Decimal(body["cash_balances"]["USD"]) == Decimal("498.000000")
    assert Decimal(body["bank_balances"]["USD"]) == Decimal("997.000000")
    assert body["pending_settlements"] >= 1
    assert body["closed_settlements"] >= 1


def test_date_filters_work(client: TestClient, db_session: Session) -> None:
    seed_report_data(client, db_session)

    response = client.get("/reports/commission-earned?date_from=2026-05-11")

    assert response.status_code == 200
    assert response.json()["rows"] == []
    assert response.json()["totals"] == {}


def test_currency_filters_work(client: TestClient, db_session: Session) -> None:
    seed_report_data(client, db_session)

    response = client.get("/reports/fx-profit-loss?currency=USD")

    assert response.status_code == 200
    assert response.json()["rows"] == []
    assert response.json()["totals"] == {}


def test_commission_earned_and_paid_in_same_settlement(client: TestClient, db_session: Session) -> None:
    data = seed_report_data(client, db_session)
    agent_account = db_session.query(Account).filter(Account.account_code == "RPT-AGENT-WALLET").one()
    add_manual_component(
        db_session,
        user=data["user"],
        transaction_no="RPT-SET-COMM-PAID",
        transaction_date="2026-05-18",
        component_type="commission_paid",
        amount="1.50",
        currency="USD",
        account=agent_account,
        settlement_id=data["settlement"].id,
    )

    earned = client.get(f"/reports/commission-earned?settlement_id={data['settlement'].id}")
    paid = client.get(f"/reports/commission-paid?settlement_id={data['settlement'].id}")

    assert earned.status_code == 200
    assert paid.status_code == 200
    assert total(earned.json(), "USD") == Decimal("5.000000")
    assert total(paid.json(), "USD") == Decimal("-1.500000")


def test_expense_linked_to_settlement_and_general_expense_without_settlement(client: TestClient, db_session: Session) -> None:
    data = seed_report_data(client, db_session)
    cash = data["cash"]
    expense = db_session.query(Account).filter(Account.account_code == "RPT-EXPENSE").one()
    post(
        client,
        "/transactions/expense/post",
        {
            "transaction_date": "2026-05-19",
            "created_by_user_id": data["user"].id,
            "settlement_id": data["pending"].id,
            "payment_account_id": cash.id,
            "expense_account_id": expense.id,
            "amount": "4.00",
            "currency": "USD",
            "expense_type": "settlement_charge",
        },
    )

    linked = client.get(f"/reports/expenses?settlement_id={data['pending'].id}")
    general = client.get("/reports/expenses")

    assert linked.status_code == 200
    assert general.status_code == 200
    assert total(linked.json(), "USD") == Decimal("-4.000000")
    assert total(general.json(), "USD") == Decimal("-14.000000")
    assert any(row["settlement_id"] is None for row in general.json()["rows"])


def test_fx_gain_and_loss_in_same_month(client: TestClient, db_session: Session) -> None:
    data = seed_report_data(client, db_session)
    fx_account = db_session.query(Account).filter(Account.account_code == "RPT-FX-GL").one()
    add_manual_component(
        db_session,
        user=data["user"],
        transaction_no="RPT-FX-LOSS",
        transaction_date="2026-05-20",
        component_type="fx_loss",
        amount="6.00",
        currency="AED",
        account=fx_account,
        profitability_effect_type="expense",
    )

    response = client.get("/reports/fx-profit-loss")

    assert response.status_code == 200
    assert total(response.json(), "AED") == Decimal("4.000000")


def test_monthly_profitability_with_commission_expense_and_fx(client: TestClient, db_session: Session) -> None:
    data = seed_report_data(client, db_session)
    fx_account = db_session.query(Account).filter(Account.account_code == "RPT-FX-GL").one()
    add_manual_component(
        db_session,
        user=data["user"],
        transaction_no="RPT-FX-LOSS-MONTHLY",
        transaction_date="2026-05-20",
        component_type="fx_loss",
        amount="6.00",
        currency="AED",
        account=fx_account,
        profitability_effect_type="expense",
    )

    response = client.get("/reports/monthly-profitability")

    assert response.status_code == 200
    assert total(response.json(), "USD") == Decimal("-7.000000")
    assert total(response.json(), "AED") == Decimal("4.000000")


def test_account_report_after_reversal_nets_to_original_balance(client: TestClient, db_session: Session) -> None:
    data = seed_report_data(client, db_session)

    response = client.get(f"/reports/cash?account_id={data['cash'].id}")

    assert response.status_code == 200
    assert total(response.json(), "USD") == Decimal("498.000000")
    assert response.json()["rows"][0]["balance"] == "498.000000"


def test_settlement_chain_with_receipt_payment_expense_and_fx(client: TestClient, db_session: Session) -> None:
    data = seed_report_data(client, db_session)
    settlement = data["pending"]
    cash = data["cash"]
    clearing = db_session.query(Account).filter(Account.account_code == "RPT-CLEARING").one()
    expense = db_session.query(Account).filter(Account.account_code == "RPT-EXPENSE").one()
    fx_gl = db_session.query(Account).filter(Account.account_code == "RPT-FX-GL").one()
    post(client, "/transactions/receipt/post", {"transaction_date": "2026-05-18", "created_by_user_id": data["user"].id, "settlement_id": settlement.id, "receiving_account_id": cash.id, "clearing_account_id": clearing.id, "gross_amount": "12.00", "principal_amount": "12.00", "currency": "USD"})
    post(client, "/transactions/payment/post", {"transaction_date": "2026-05-19", "created_by_user_id": data["user"].id, "settlement_id": settlement.id, "paying_account_id": cash.id, "clearing_account_id": clearing.id, "amount": "12.00", "currency": "USD"})
    post(client, "/transactions/expense/post", {"transaction_date": "2026-05-20", "created_by_user_id": data["user"].id, "settlement_id": settlement.id, "payment_account_id": cash.id, "expense_account_id": expense.id, "amount": "1.00", "currency": "USD", "expense_type": "settlement_charge", "affects_settlement": True})
    add_manual_component(
        db_session,
        user=data["user"],
        transaction_no="RPT-SET-FX-GAIN",
        transaction_date="2026-05-20",
        component_type="fx_gain",
        amount="2.00",
        currency="AED",
        account=fx_gl,
        settlement_id=settlement.id,
        profitability_effect_type="income",
    )

    response = client.get(f"/reports/settlement-chain?settlement_id={settlement.id}")

    assert response.status_code == 200
    components = {row["component_type"] for row in response.json()["rows"]}
    assert {"gross_receipt", "principal", "expense", "fx_gain"}.issubset(components)
    assert total(response.json(), "USD") == Decimal("1.000000")


def test_date_boundary_filters_are_inclusive(client: TestClient, db_session: Session) -> None:
    seed_report_data(client, db_session)

    response = client.get("/reports/commission-earned?date_from=2026-05-10&date_to=2026-05-10")

    assert response.status_code == 200
    assert total(response.json(), "USD") == Decimal("5.000000")


def test_report_endpoints_reject_invalid_date_format(client: TestClient, db_session: Session) -> None:
    response = client.get("/reports/cash?date_from=15-05-2026")

    assert response.status_code == 422


def test_empty_reports_return_stable_schema(client: TestClient, db_session: Session) -> None:
    response = client.get("/reports/commission-earned?currency=EUR")

    assert response.status_code == 200
    assert response.json() == {
        "filters": {
            "date_from": None,
            "date_to": None,
            "currency": "EUR",
            "party_id": None,
            "account_id": None,
            "settlement_id": None,
        },
        "rows": [],
        "totals": {},
    }
