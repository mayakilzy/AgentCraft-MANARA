"""Explicit error envelope for MANARA API.

The G00 mission demands "API errors explicit". We expose a uniform
``ErrorEnvelope`` shape with:

* ``code`` — a stable, machine-readable error code (snake_case).
* ``message`` — human-readable summary (Arabic/English aware).
* ``details`` — optional structured context (validation errors, etc.).
* ``trace_id`` — request identifier (no secrets, ever).
"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

# Use raw integer status codes so the module is robust against Starlette's
# deprecation/rename of HTTP_422_UNPROCESSABLE_ENTITY → HTTP_422_UNPROCESSABLE_CONTENT
# (the integer is part of the HTTP standard and does not change).
HTTP_404 = 404
HTTP_409 = 409
HTTP_422 = 422
HTTP_500 = 500
HTTP_503 = 503


class ErrorEnvelope(BaseModel):
    """Uniform error response shape."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., description="Stable, machine-readable error code (snake_case).")
    message: str = Field(..., description="Human-readable summary.")
    details: dict[str, Any] | list[Any] | None = Field(default=None)
    trace_id: str | None = Field(default=None, description="Request trace ID (no secrets).")


class ManaraError(Exception):
    """Base MANARA domain error.

    Subclasses (or direct instantiations) carry an explicit ``code`` so the
    API can map them deterministically. Raising ``ManaraError`` (or a
    subclass) anywhere in the codebase produces a uniform error envelope.
    """

    code: str = "manara_error"
    http_status: int = HTTP_500

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        http_status: int | None = None,
        details: dict[str, Any] | list[Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if http_status is not None:
            self.http_status = http_status
        self.details = details


class NotFoundError(ManaraError):
    code = "not_found"
    http_status = HTTP_404


class ValidationError(ManaraError):
    code = "validation_error"
    http_status = HTTP_422


class ConflictError(ManaraError):
    code = "conflict"
    http_status = HTTP_409


class ServiceUnavailableError(ManaraError):
    code = "service_unavailable"
    http_status = HTTP_503


def _trace_id(request: Request) -> str | None:
    """Best-effort trace ID extraction. NEVER log secrets here."""
    return (
        getattr(request.state, "trace_id", None)
        or request.headers.get("x-request-id")
        or request.headers.get("x-trace-id")
    )


async def manara_error_handler(request: Request, exc: ManaraError) -> JSONResponse:
    envelope = ErrorEnvelope(
        code=exc.code,
        message=exc.message,
        details=exc.details,
        trace_id=_trace_id(request),
    )
    return JSONResponse(
        status_code=exc.http_status,
        content=jsonable_encoder(envelope),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    envelope = ErrorEnvelope(
        code="validation_error",
        message="Request payload failed validation.",
        details=list(exc.errors()),
        trace_id=_trace_id(request),
    )
    return JSONResponse(
        status_code=HTTP_422,
        content=jsonable_encoder(envelope),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # NEVER leak the raw exception text in production (it may include env values).
    from manara.config import settings

    message = (
        f"Unhandled error: {type(exc).__name__}"
        if settings.env != "production"
        else "Internal server error."
    )
    envelope = ErrorEnvelope(
        code="internal_error",
        message=message,
        trace_id=_trace_id(request),
    )
    return JSONResponse(
        status_code=HTTP_500,
        content=jsonable_encoder(envelope),
    )


def register_error_handlers(app) -> None:  # type: ignore[no-untyped-def]
    """Register all MANARA error handlers on a FastAPI app."""
    app.add_exception_handler(ManaraError, manara_error_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)


__all__ = [
    "ConflictError",
    "ErrorEnvelope",
    "ManaraError",
    "NotFoundError",
    "ServiceUnavailableError",
    "ValidationError",
    "register_error_handlers",
]
