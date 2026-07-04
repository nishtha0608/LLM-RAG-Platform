"""Centralized exception handlers so errors return a consistent JSON shape."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.logging_config import get_logger

logger = get_logger(__name__)


class RagPlatformError(Exception):
    """Base class for domain errors that should not leak stack traces to clients."""


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RagPlatformError)
    async def handle_domain_error(_request: Request, exc: RagPlatformError) -> JSONResponse:
        logger.warning("domain_error", error=str(exc))
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(exc)})

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled_exception", error=str(exc), exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )
