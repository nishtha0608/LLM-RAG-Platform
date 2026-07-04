"""Integration tests for liveness and readiness probes."""

from httpx import AsyncClient


async def test_health_endpoint_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_ready_endpoint_checks_database(client: AsyncClient) -> None:
    response = await client.get("/ready")
    assert response.status_code == 200
    assert response.json()["checks"]["database"] is True
