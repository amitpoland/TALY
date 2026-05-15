from fastapi.testclient import TestClient


def test_create_and_update_party_writes_audit_log(client: TestClient) -> None:
    response = client.post(
        "/parties",
        json={
            "party_type": "customer",
            "name": "Client A",
            "default_currency": "USD",
        },
    )
    assert response.status_code == 201
    party_id = response.json()["id"]

    update = client.patch(f"/parties/{party_id}", json={"phone": "+48123456789"})
    assert update.status_code == 200
    assert update.json()["phone"] == "+48123456789"

    logs = client.get("/audit-logs").json()
    actions = [log["action"] for log in logs]
    assert "create_party" in actions
    assert "update_party" in actions


def test_party_rejects_unknown_currency(client: TestClient) -> None:
    response = client.post(
        "/parties",
        json={
            "party_type": "customer",
            "name": "Client B",
            "default_currency": "ZZZ",
        },
    )
    assert response.status_code == 400

