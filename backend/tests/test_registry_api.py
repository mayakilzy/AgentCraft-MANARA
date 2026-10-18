"""API smoke tests for /registry endpoints (G01)."""

from __future__ import annotations

import os

os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", "/home/z/my-project/.models")
os.environ.setdefault("HF_HOME", "/home/z/my-project/.models/hf_cache")

from fastapi.testclient import TestClient


def test_list_capabilities_empty(client: TestClient) -> None:
    r = client.get("/registry/capabilities")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 0
    assert body["capabilities"] == []


def test_seed_endpoint_loads_eight_cards(client: TestClient) -> None:
    r = client.post("/registry/capabilities/seed")
    assert r.status_code in (200, 201)
    body = r.json()
    assert body["total_created"] == 8
    assert len(body["seeded"]) == 8
    assert len(body["skipped"]) == 0


def test_seed_endpoint_is_idempotent(client: TestClient) -> None:
    # First call: all 8 seeded
    r1 = client.post("/registry/capabilities/seed")
    assert r1.json()["total_created"] == 8
    # Second call: all 8 skipped
    r2 = client.post("/registry/capabilities/seed")
    assert r2.json()["total_created"] == 0
    assert len(r2.json()["skipped"]) == 8


def test_get_capability_after_seed(client: TestClient) -> None:
    client.post("/registry/capabilities/seed")
    r = client.get("/registry/capabilities/search.academic-publications")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "search.academic-publications"
    assert body["display_name"] == "Academic Publications Search"
    assert "patents" not in body["tags"]  # this card's tags don't include patents
    assert "publications" in body["tags"]


def test_get_nonexistent_capability_returns_404_envelope(client: TestClient) -> None:
    r = client.get("/registry/capabilities/search.does-not-exist")
    assert r.status_code == 404
    body = r.json()
    # Either our uniform envelope or FastAPI default
    assert body.get("code") == "not_found" or body.get("detail")


def test_search_returns_results_with_reasons(client: TestClient) -> None:
    """The owner's acceptance test, executed via the API."""
    client.post("/registry/capabilities/seed")
    r = client.get(
        "/registry/search",
        params={"q": "Future of intelligent prosthetics and neural interfaces through 2035"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["query"].startswith("Future of intelligent prosthetics")
    assert len(body["hits"]) > 0

    # Every hit must carry matched_by reasons
    for hit in body["hits"]:
        assert len(hit["matched_by"]) > 0, f"hit {hit['capability_id']} has no matched_by"

    # Stage traces must cover all 5 stages
    stages = [t["stage"] for t in body["stage_traces"]]
    assert "1_filter" in stages
    assert "2_hybrid" in stages
    assert "3_rerank" in stages
    assert "4_validate" in stages
    assert "5_return" in stages


def test_search_battery_query_returns_energy_engine(client: TestClient) -> None:
    client.post("/registry/capabilities/seed")
    r = client.get(
        "/registry/search",
        params={"q": "Track Li-ion battery pack cost per kWh from 2015 to 2024"},
    )
    body = r.json()
    hit_ids = [h["capability_id"] for h in body["hits"]]
    assert "search.energy-ev-datasets" in hit_ids, (
        f"energy-ev-datasets missing from battery query: {hit_ids}"
    )


def test_promote_capability_changes_status(client: TestClient) -> None:
    client.post("/registry/capabilities/seed")
    r = client.patch(
        "/registry/capabilities/search.academic-publications/promote",
        json={
            "reviewer": "ayman",
            "rationale": "Card reviewed and approved for production use.",
            "decision": "approved",
            "test_matrix_ref": "tests/test_registry_api.py",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["decision"] == "approved"
    assert body["reviewer"] == "ayman"
    assert body["new_status"] == "approved"
    assert body["previous_status"] == "candidate"

    # Verify the change persisted
    r2 = client.get("/registry/capabilities/search.academic-publications")
    body2 = r2.json()
    assert body2["status"] == "approved"
    assert body2["approved_by"] == "ayman"


def test_promote_nonexistent_returns_404(client: TestClient) -> None:
    r = client.patch(
        "/registry/capabilities/search.does-not-exist/promote",
        json={
            "reviewer": "ayman",
            "rationale": "Attempting to promote a non-existent capability.",
        },
    )
    assert r.status_code == 404


def test_delete_capability(client: TestClient) -> None:
    client.post("/registry/capabilities/seed")
    r = client.delete("/registry/capabilities/search.academic-publications")
    assert r.status_code == 200
    assert r.json() == {"deleted": True}

    # Verify it's gone
    r2 = client.get("/registry/capabilities/search.academic-publications")
    assert r2.status_code == 404


def test_list_evaluations_empty(client: TestClient) -> None:
    client.post("/registry/capabilities/seed")
    r = client.get("/registry/capabilities/search.academic-publications/evaluations")
    assert r.status_code == 200
    assert r.json() == []


def test_add_evaluation(client: TestClient) -> None:
    client.post("/registry/capabilities/seed")
    r = client.post(
        "/registry/capabilities/search.academic-publications/evaluations",
        json={
            "evaluator": "glm",
            "benchmark_query_set": "g01-acceptance-v1",
            "precision": 0.85,
            "recall": 0.78,
            "false_positive_misuse_rate": 0.05,
            "notes": "MiniLM shows strong cross-domain recall on prosthetics test.",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert "id" in body
    assert body["capability_id"] == "search.academic-publications"

    # Verify it shows up in the list
    r2 = client.get("/registry/capabilities/search.academic-publications/evaluations")
    evals = r2.json()
    assert len(evals) == 1
    assert evals[0]["evaluator"] == "glm"
    assert evals[0]["precision"] == 0.85


def test_add_relationship(client: TestClient) -> None:
    client.post("/registry/capabilities/seed")
    r = client.post(
        "/registry/capabilities/search.academic-publications/relationships",
        json={
            "to_capability_id": "search.patent-intelligence",
            "kind": "complements",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["from_capability_id"] == "search.academic-publications"
    assert body["to_capability_id"] == "search.patent-intelligence"
    assert body["kind"] == "complements"


def test_reindex_embeddings(client: TestClient) -> None:
    client.post("/registry/capabilities/seed")
    r = client.post("/registry/capabilities/search.academic-publications/reindex")
    assert r.status_code == 200
    body = r.json()
    assert body["capability_id"] == "search.academic-publications"
    assert body["embeddings_regenerated"] > 0
    assert body["model"] == "paraphrase-multilingual-MiniLM-L12-v2"


def test_status_reports_g01_capabilities(client: TestClient) -> None:
    """The /status endpoint must honestly list G01 + G02 + G03 capabilities."""
    r = client.get("/status")
    body = r.json()
    caps = body["capabilities"]
    # G01 capabilities must be listed
    assert "registry:capability_crud" in caps
    assert "registry:hybrid_search_text_plus_semantic" in caps
    assert "registry:miniLM_embeddings_384_multilingual" in caps
    assert "registry:negative_example_reranker" in caps
    assert "registry:8_seed_capability_cards" in caps
    # G01-R1 multi-capability coverage
    assert "registry:multi_capability_coverage_search" in caps
    # G02 Foundry capabilities
    assert "foundry:openalex_connector" in caps
    assert "foundry:sandbox_test_pipeline" in caps
    # G03 Cumulative knowledge memory
    assert "memory:evidence_ingestion_dedup_aware" in caps
    assert "memory:contradiction_preservation" in caps
    assert "memory:bitemporal_provenance_no_future_leakage" in caps
    # G04 Mold Factory capabilities
    assert "mold_factory:unknown_domain_detector" in caps
    assert "mold_factory:mold_architect" in caps
    assert "mold_factory:gap_analysis_honest_no_fabrication" in caps
    # G05 Agent Factory capabilities
    assert "agents:generalist_vs_specialist_resolver" in caps
    assert "agents:ephemeral_runtime_instantiate_execute_terminate" in caps
    # G06+ items must remain in not_implemented
    not_impl = body["not_implemented"]
    assert "real_forecasting" in not_impl  # G06
    assert "live_llm_execution" in not_impl  # mock only in sandbox
    assert "multi_tenant_authn" in not_impl  # G03+
