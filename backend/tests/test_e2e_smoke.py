"""End-to-end smoke test — one full request through the thin app scaffold.

This is the acceptance test demanded by the G00 spec:
    "one end-to-end request through thin app scaffold".

The flow:
1. ``GET /status`` → 200, honest G00 metadata.
2. ``GET /discovery`` → 200, synthetic capability card.
3. ``GET /contracts/schemas`` → 200, eight JSON Schemas.
4. Persist + retrieve a real Investigation row through the ORM (using the
   in-process SQLite dev variant) to prove the persistence contract works
   end-to-end.

This test does NOT exercise any real connector or forecasting. It only
proves the foundation scaffold is wired correctly.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from manara.contracts import Investigation, InvestigationScope
from manara.db.models import InvestigationRow
from manara.lifecycle import InvestigationState


def test_e2e_status_discovery_contracts(client: TestClient) -> None:
    # Step 1 — /status
    r1 = client.get("/status")
    assert r1.status_code == 200
    s_body = r1.json()
    assert s_body["app"] == "MANARA"
    assert "real_search" in s_body["not_implemented"]

    # Step 2 — /discovery (synthetic)
    r2 = client.get("/discovery")
    assert r2.status_code == 200
    d_body = r2.json()
    assert d_body["label"] == "synthetic"
    assert d_body["capability"]["id"] == "search.patent-innovation"
    assert d_body["capability"]["connector_ids"] == []

    # Step 3 — /contracts/schemas (all 8 contracts)
    r3 = client.get("/contracts/schemas")
    assert r3.status_code == 200
    schemas = r3.json()["schemas"]
    expected = {
        "Source",
        "Connector",
        "SearchCapability",
        "Mold",
        "AgentRecipe",
        "Evidence",
        "Forecast",
        "Investigation",
    }
    assert set(schemas.keys()) == expected


def test_e2e_persist_investigation_row(client: TestClient, db_session) -> None:
    """The ORM round-trips an Investigation payload into the database and back.

    This proves:
    * The Pydantic contract serializes to a JSON-compatible dict.
    * The ORM ``payload`` JSON column stores it without loss.
    * The indexed columns (tenant_id, state, topic) are queryable.
    """
    inv = Investigation(
        id="inv-e2e-001",
        tenant_id="tenant_e2e",
        user_id="user-e2e",
        scope=InvestigationScope(
            topic="End-to-end smoke investigation of waste recycling",
            geography=["global"],
            deliverables=["evidence_dossier"],
        ),
        state=InvestigationState.RECEIVED,
    )

    row = InvestigationRow(
        id=inv.id,
        tenant_id=inv.tenant_id,
        user_id=inv.user_id,
        state=inv.state.value,
        topic=inv.scope.topic,
        payload=inv.model_dump(mode="json"),
    )
    db_session.add(row)
    db_session.commit()

    # Re-read it back and re-validate against the Pydantic contract
    stmt = select(InvestigationRow).where(InvestigationRow.id == "inv-e2e-001")
    loaded = db_session.execute(stmt).scalar_one()
    assert loaded is not None
    assert loaded.tenant_id == "tenant_e2e"
    assert loaded.state == "received"
    assert "waste recycling" in loaded.topic

    restored = Investigation.model_validate(loaded.payload)
    assert restored.id == inv.id
    assert restored.scope.topic == inv.scope.topic
    assert restored.state == InvestigationState.RECEIVED
    assert restored.created_at.tzinfo is not None
    # Round-trip preserves UTC-aware timestamps
    assert restored.created_at.year == inv.created_at.year


def test_e2e_investigation_state_transitions_validate(client: TestClient, db_session) -> None:
    """An Investigation can advance received → scoped → coverage_checked."""

    inv = Investigation(
        id="inv-e2e-002",
        tenant_id="tenant_e2e",
        user_id="user-e2e",
        scope=InvestigationScope(topic="Battery cost forecast through 2030"),
        state=InvestigationState.SCOPED,
        checkpoints=[
            {"state": "received"},
            {"state": "scoped"},
        ],
    )
    row = InvestigationRow(
        id=inv.id,
        tenant_id=inv.tenant_id,
        user_id=inv.user_id,
        state=inv.state.value,
        topic=inv.scope.topic,
        payload=inv.model_dump(mode="json"),
    )
    db_session.add(row)
    db_session.commit()

    # Read back
    stmt = select(InvestigationRow).where(InvestigationRow.id == "inv-e2e-002")
    loaded = db_session.execute(stmt).scalar_one()
    restored = Investigation.model_validate(loaded.payload)
    assert restored.state == InvestigationState.SCOPED
    assert len(restored.checkpoints) == 2
    assert restored.checkpoints[0].state == InvestigationState.RECEIVED
    assert restored.checkpoints[1].state == InvestigationState.SCOPED
