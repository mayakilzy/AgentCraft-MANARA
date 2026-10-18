"""Tests for the /status endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_status_returns_200(client: TestClient) -> None:
    r = client.get("/status")
    assert r.status_code == 200


def test_status_reports_app_metadata(client: TestClient) -> None:
    r = client.get("/status")
    body = r.json()
    assert body["app"] == "MANARA"
    assert body["version"].startswith("0.1.0")
    assert "G00" in body["build"]["mission"]
    assert body["build"]["code_repository"].endswith("AgentCraft-MANARA")


def test_status_lists_capabilities_honestly(client: TestClient) -> None:
    r = client.get("/status")
    body = r.json()
    caps = body["capabilities"]
    not_impl = body["not_implemented"]
    # Capabilities G00 actually delivers
    assert "typed_contracts:source" in caps
    assert "typed_contracts:investigation" in caps
    assert "api:status" in caps
    assert "api:discovery_synthetic_only" in caps
    # What G00 explicitly does NOT do
    assert "real_search" in not_impl
    assert "real_forecasting" in not_impl
    assert "production_deployment" in not_impl
    # No overlap between the two lists (the spec is explicit about honesty)
    assert not (set(caps) & set(not_impl))


def test_status_reports_database_kind_honestly(client: TestClient) -> None:
    r = client.get("/status")
    body = r.json()
    # In test profile, DATABASE_URL is sqlite, so the kind MUST say sqlite.
    assert body["database_url_kind"] == "sqlite"


def test_status_reports_synthetic_discovery_mode(client: TestClient) -> None:
    r = client.get("/status")
    body = r.json()
    assert body["discovery_mode"] == "synthetic"


def test_health_alias_works(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["app"] == "MANARA"
