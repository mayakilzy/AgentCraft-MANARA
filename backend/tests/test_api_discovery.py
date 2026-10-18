"""Tests for the /discovery endpoint (synthetic only)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_discovery_returns_200(client: TestClient) -> None:
    r = client.get("/discovery")
    assert r.status_code == 200


def test_discovery_is_labeled_synthetic(client: TestClient) -> None:
    r = client.get("/discovery")
    body = r.json()
    assert body["label"] == "synthetic"
    assert body["data_origin"] == "hardcoded_in_process_example"
    assert "SYNTHETIC" in body["warning"].upper() or "SYNTHETIC" in body["capability"]["display_name"].upper()


def test_discovery_capability_is_example_only(client: TestClient) -> None:
    r = client.get("/discovery")
    body = r.json()
    cap = body["capability"]
    # The synthetic capability MUST be in `discovered` state — never `approved`.
    assert cap["status"] == "discovered"
    # The synthetic capability MUST NOT carry any connector IDs.
    assert cap["connector_ids"] == []
    assert cap["graph"]["uses_connector"] == []


def test_discovery_capability_matches_spec_example_shape(client: TestClient) -> None:
    """The synthetic card mirrors examples/capability_patent_intelligence.yaml."""
    r = client.get("/discovery")
    cap = r.json()["capability"]
    assert cap["id"] == "search.patent-innovation"
    assert cap["kind"] == "search-engine"
    assert "patents" in cap["tags"]
    # The spec example ships 5 positive + 3 negative examples.
    assert len(cap["positive_examples"]) == 5
    assert len(cap["negative_examples"]) == 3
    # Multilingual
    assert cap["keywords_en"]
    assert cap["keywords_ar"]


def test_discovery_warning_is_present(client: TestClient) -> None:
    r = client.get("/discovery")
    body = r.json()
    assert "SYNTHETIC" in body["warning"].upper()
    assert "G02" in body["warning"]  # cross-reference to the next mission
