"""Integration tests for the registration and login flow against a real Postgres."""

from httpx import AsyncClient


async def test_register_then_login_returns_tokens(client: AsyncClient) -> None:
    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "ada@example.com",
            "password": "supersecret123",
            "full_name": "Ada Lovelace",
        },
    )
    assert register_response.status_code == 201
    assert register_response.json()["email"] == "ada@example.com"

    login_response = await client.post(
        "/api/v1/auth/login", json={"email": "ada@example.com", "password": "supersecret123"}
    )
    assert login_response.status_code == 200
    body = login_response.json()
    assert "access_token" in body
    assert "refresh_token" in body


async def test_register_duplicate_email_returns_409(client: AsyncClient) -> None:
    payload = {"email": "dupe@example.com", "password": "supersecret123"}
    first = await client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201

    second = await client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409


async def test_login_with_wrong_password_returns_401(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register", json={"email": "bob@example.com", "password": "correctpassword"}
    )
    response = await client.post(
        "/api/v1/auth/login", json={"email": "bob@example.com", "password": "wrongpassword"}
    )
    assert response.status_code == 401


async def test_protected_route_without_token_returns_401(client: AsyncClient) -> None:
    response = await client.get("/api/v1/documents")
    assert response.status_code == 401
