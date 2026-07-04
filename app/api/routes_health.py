"""Liveness and readiness probes for Kubernetes."""

from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DbSession
from app.config import get_settings
from app.schemas import HealthStatus, ReadinessStatus

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus)
async def health() -> HealthStatus:
    settings = get_settings()
    return HealthStatus(status="ok", version="0.1.0", environment=settings.environment)


@router.get("/ready", response_model=ReadinessStatus)
async def ready(session: DbSession) -> ReadinessStatus:
    checks = {"database": False}
    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        checks["database"] = False

    overall = "ok" if all(checks.values()) else "degraded"
    return ReadinessStatus(status=overall, checks=checks)
