from fastapi.testclient import TestClient


def test_roles_are_listed(client: TestClient) -> None:
    response = client.get("/roles")
    assert response.status_code == 200
    assert {role["name"] for role in response.json()} >= {"admin", "manager", "operator", "viewer"}


def test_create_user_hashes_password_and_audits(client: TestClient) -> None:
    role_id = next(role["id"] for role in client.get("/roles").json() if role["name"] == "admin")
    response = client.post(
        "/users",
        json={
            "username": "admin",
            "password": "change-me",
            "full_name": "Admin User",
            "role_id": role_id,
        },
    )

    assert response.status_code == 201
    assert "password" not in response.json()

    logs = client.get("/audit-logs").json()
    assert any(log["action"] == "create_user" for log in logs)

