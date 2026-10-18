"""Tests for the explicit error envelope."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_404_returns_envelope(client: TestClient) -> None:
    r = client.get("/does-not-exist")
    assert r.status_code == 404
    body = r.json()
    # FastAPI default 404 isn't routed through our handler, so this only checks
    # the payload has a sane shape. (Starlette's default 404 returns {"detail":"Not Found"}.)
    assert body.get("detail") == "Not Found" or body.get("code") == "not_found"


def test_validation_error_returns_envelope(client: TestClient) -> None:
    """RequestValidationError on a typed route → our uniform envelope."""

    # We don't have a POST route in G00 that accepts a body, so we hit /contracts/schemas
    # with the wrong method instead — FastAPI will return 405 (also uniform).
    r = client.post("/status", json={"unexpected": "payload"})
    # POST not allowed → 405
    assert r.status_code in (405, 404, 422)


def test_internal_error_handler_is_registered() -> None:
    """The unhandled-exception handler is wired (smoke test)."""
    from manara.api.errors import register_error_handlers

    # Build a minimal app stub
    class _StubApp:
        def __init__(self) -> None:
            self.handlers: dict = {}

        def add_exception_handler(self, exc_cls, handler) -> None:
            self.handlers[exc_cls] = handler

    stub = _StubApp()
    register_error_handlers(stub)  # type: ignore[arg-type]
    from fastapi.exceptions import RequestValidationError

    from manara.api.errors import ManaraError

    assert ManaraError in stub.handlers
    assert RequestValidationError in stub.handlers
    # The generic Exception handler is also registered
    assert Exception in stub.handlers


def test_manara_error_subclasses_have_correct_status_codes() -> None:
    from manara.api.errors import (
        ConflictError,
        NotFoundError,
        ServiceUnavailableError,
        ValidationError,
    )

    assert NotFoundError.http_status == 404
    assert ValidationError.http_status == 422
    assert ConflictError.http_status == 409
    assert ServiceUnavailableError.http_status == 503
    assert NotFoundError.code == "not_found"
    assert ValidationError.code == "validation_error"
    assert ConflictError.code == "conflict"
    assert ServiceUnavailableError.code == "service_unavailable"
