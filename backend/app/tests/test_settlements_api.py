from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.party import Party
from app.models.settlement import Settlement
from app.models.common import utcnow


def create_party(db: Session) -> Party:
    party = Party(party_type="customer", name="Settlement Customer", default_currency="USD", is_active=True)
    db.add(party)
    db.commit()
    db.refresh(party)
    return party


def create_settlement(db: Session, status: str = "open") -> Settlement:
    settlement = Settlement(
        settlement_no=f"CRUD-{status.upper()}",
        title=f"{status.title()} Settlement",
        status=status,
        base_currency="USD",
        opened_at=utcnow(),
        approved_pending_amount=Decimal("0"),
    )
    db.add(settlement)
    db.commit()
    db.refresh(settlement)
    return settlement


def test_create_list_and_get_settlement(client: TestClient, db_session: Session) -> None:
    party = create_party(db_session)

    create_response = client.post(
        "/settlements",
        json={
            "settlement_no": "SET-CRUD-001",
            "title": "Client settlement chain",
            "primary_party_id": party.id,
            "base_currency": "USD",
        },
    )
    list_response = client.get("/settlements")

    assert create_response.status_code == 201
    body = create_response.json()
    assert body["settlement_no"] == "SET-CRUD-001"
    assert body["status"] == "open"
    assert body["primary_party_id"] == party.id
    assert list_response.status_code == 200
    assert any(row["settlement_no"] == "SET-CRUD-001" for row in list_response.json())
    assert db_session.query(AuditLog).filter(AuditLog.action == "create_settlement").count() == 1

    get_response = client.get(f"/settlements/{body['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["title"] == "Client settlement chain"


def test_create_settlement_validates_currency_party_and_unique_number(client: TestClient, db_session: Session) -> None:
    settlement = create_settlement(db_session)

    duplicate = client.post("/settlements", json={"settlement_no": settlement.settlement_no, "title": "Duplicate", "base_currency": "USD"})
    bad_currency = client.post("/settlements", json={"settlement_no": "BAD-CUR", "title": "Bad currency", "base_currency": "XXX"})
    bad_party = client.post("/settlements", json={"settlement_no": "BAD-PARTY", "title": "Bad party", "primary_party_id": 999, "base_currency": "USD"})

    assert duplicate.status_code == 409
    assert bad_currency.status_code == 400
    assert bad_party.status_code == 400


def test_patch_open_settlement_and_audit(client: TestClient, db_session: Session) -> None:
    settlement = create_settlement(db_session)
    party = create_party(db_session)

    response = client.patch(
        f"/settlements/{settlement.id}",
        json={"title": "Updated title", "primary_party_id": party.id, "base_currency": "EUR"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Updated title"
    assert body["primary_party_id"] == party.id
    assert body["base_currency"] == "EUR"
    assert db_session.query(AuditLog).filter(AuditLog.action == "update_settlement").count() == 1


def test_patch_closed_or_cancelled_settlement_blocked(client: TestClient, db_session: Session) -> None:
    closed = create_settlement(db_session, "closed")
    cancelled = create_settlement(db_session, "cancelled")

    closed_response = client.patch(f"/settlements/{closed.id}", json={"title": "No edit"})
    cancelled_response = client.patch(f"/settlements/{cancelled.id}", json={"title": "No edit"})

    assert closed_response.status_code == 400
    assert cancelled_response.status_code == 400


def test_get_missing_settlement_returns_404(client: TestClient) -> None:
    response = client.get("/settlements/999")

    assert response.status_code == 404
