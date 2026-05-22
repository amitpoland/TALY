from fastapi.testclient import TestClient


def test_create_account_with_zero_opening_balance(client: TestClient) -> None:
    response = client.post(
        "/accounts",
        json={
            "account_code": "CASH-USD",
            "name": "Main Cash USD",
            "account_type": "cash",
            "currency": "USD",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["opening_balance"] == "0.000000"
    assert body["current_balance"] == "0.000000"


def test_account_rejects_nonzero_opening_balance_until_posting_engine(client: TestClient) -> None:
    response = client.post(
        "/accounts",
        json={
            "account_code": "BANK-USD",
            "name": "Bank USD",
            "account_type": "bank",
            "currency": "USD",
            "opening_balance": "100.00",
        },
    )
    assert response.status_code == 422


def test_wallet_account_requires_party(client: TestClient) -> None:
    response = client.post(
        "/accounts",
        json={
            "account_code": "CLIENT-WALLET-USD",
            "name": "Client Wallet USD",
            "account_type": "customer_wallet",
            "currency": "USD",
        },
    )
    assert response.status_code == 400


def test_account_can_be_deactivated_and_restored(client: TestClient) -> None:
    created = client.post(
        "/accounts",
        json={
            "account_code": "DELETE-ME-USD",
            "name": "Delete Me USD",
            "account_type": "cash",
            "currency": "USD",
        },
    )
    assert created.status_code == 201
    account_id = created.json()["id"]

    deleted = client.delete(f"/accounts/{account_id}")
    assert deleted.status_code == 200
    assert deleted.json()["is_active"] is False

    restored = client.patch(f"/accounts/{account_id}", json={"is_active": True})
    assert restored.status_code == 200
    assert restored.json()["is_active"] is True
