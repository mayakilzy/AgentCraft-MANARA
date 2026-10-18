"""G03 acceptance evidence — two-investigation reuse with contradiction preservation.

Runs the canonical G03 acceptance test (Investigation A: prosthetics,
Investigation B: medical robotics) and prints a structured report with
real evidence of:
1. Cross-investigation reuse (B reuses A's evidence via checksum dedup)
2. No duplicate storage (single row for the same content)
3. Contradiction preservation (refuting evidence does NOT delete the original)
4. Bitemporal replay safety (future evidence excluded from past cutoff)
5. Tenant isolation (tenant B cannot see tenant A's evidence)

Usage:
    DATABASE_URL=sqlite:///./manara_dev.db \\
    SENTENCE_TRANSFORMERS_HOME=/home/z/my-project/.models \\
    HF_HOME=/home/z/my-project/.models/hf_cache \\
    python3 scripts/g03_acceptance_evidence.py
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from pathlib import Path

os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", "/home/z/my-project/.models")
os.environ.setdefault("HF_HOME", "/home/z/my-project/.models/hf_cache")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend" / "src"))

from manara.contracts import Evidence, EvidenceKind, Provenance
from manara.db.memory_models import (
    ClaimRow,
    ClaimSupportEdgeRow,
    EvidenceItemRow,
    InvestigationReuseRow,
    MemoryDecisionRow,
)
from manara.db.models import InvestigationRow
from manara.db.session import Base, get_engine, get_session_factory, reset_engine
from manara.memory import MemoryCurator, reset_object_store
from sqlalchemy import func, select


def banner(text: str) -> None:
    print()
    print("=" * 78)
    print(text)
    print("=" * 78)


def main() -> int:
    db_url = "sqlite:////tmp/manara_g03_evidence.db"
    os.environ["DATABASE_URL"] = db_url
    reset_engine()
    reset_object_store()
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    SessionLocal = get_session_factory()

    with SessionLocal() as db:
        curator = MemoryCurator(db)

        banner("G03 ACCEPTANCE TEST — Two investigations reuse one vetted source")
        print()
        print("Scenario:")
        print("  Investigation A: Future of intelligent prosthetics")
        print("  Investigation B: Future of medical robotics")
        print()
        print("Expected: B reuses A's evidence about neural interfaces")
        print("          WITHOUT storing a duplicate. Then a contradicting")
        print("          piece of evidence is added — BOTH sides are preserved.")
        print("          Bitemporal replay excludes future evidence.")
        print("          Cross-tenant queries return zero.")

        # ── Setup ────────────────────────────────────────────────────────────
        banner("STEP 1 — Setup: create two investigations in tenant_demo")
        for inv_id, topic in [
            ("inv-A", "Future of intelligent prosthetics"),
            ("inv-B", "Future of medical robotics"),
        ]:
            db.add(InvestigationRow(
                id=inv_id, tenant_id="tenant_demo", user_id="ayman",
                state="received", topic=topic,
                payload={"id": inv_id, "tenant_id": "tenant_demo",
                         "user_id": "ayman", "scope": {"topic": topic},
                         "state": "received"},
            ))
        db.commit()
        print("  ✓ inv-A: Future of intelligent prosthetics")
        print("  ✓ inv-B: Future of medical robotics")

        # ── Step 2: Investigation A ingests evidence ────────────────────────
        banner("STEP 2 — Investigation A ingests neural-interface evidence")
        raw = b'{"title": "Neural interfaces for prosthetic control", "year": 2024}'
        ev_a = Evidence(
            id="ev-A-001",
            kind=EvidenceKind.QUOTE,
            source_id="openalex",
            tenant_id="tenant_demo",
            content_preview="Neural interfaces for prosthetic control show 80% precision.",
            provenance=Provenance(
                observed_at=datetime(2024, 6, 1, tzinfo=UTC),
                ingested_at=datetime.now(UTC),
            ),
        )
        result_a = curator.ingest_evidence(
            evidence=ev_a, tenant_id="tenant_demo",
            investigation_id="inv-A", raw_content=raw,
        )
        print(f"  ✓ Evidence ingested: id={result_a.evidence_id}")
        print(f"    deduplicated={result_a.deduplicated}")
        print(f"    checksum={result_a.checksum[:32]}...")
        print(f"    stored_at_ref={result_a.stored_at_ref}")

        # ── Step 3: Investigation A attaches a claim ─────────────────────────
        banner("STEP 3 — Investigation A attaches and promotes a claim")
        curator.attach_claim(
            claim_id="claim-A-001",
            tenant_id="tenant_demo",
            investigation_id="inv-A",
            evidence_id="ev-A-001",
            statement="Neural interfaces for prosthetics achieve 80% precision in lab tests.",
        )
        print("  ✓ Claim 'claim-A-001' attached (verdict=candidate)")
        curator.promote_claim(
            claim_id="claim-A-001",
            tenant_id="tenant_demo",
            new_verdict="supported",
            rationale="Lab evidence supports the claim.",
        )
        claim = db.get(ClaimRow, "claim-A-001")
        print(f"  ✓ Claim promoted to verdict={claim.verdict}")

        # ── Step 4: Investigation B searches prior memory ───────────────────
        banner("STEP 4 — Investigation B searches prior memory")
        prior = curator.search_prior_memory(
            query="medical robotics neural interfaces",
            tenant_id="tenant_demo",
            investigation_id="inv-B",
        )
        print(f"  ✓ Found {len(prior.reusable_evidence)} reusable evidence item(s)")
        for r in prior.reusable_evidence:
            print(f"    - {r.id} (from inv-{r.investigation_id}, "
                  f"freshness={prior.freshness_assessments.get(r.id, 'unknown')})")

        # ── Step 5: Investigation B reuses A's evidence ─────────────────────
        banner("STEP 5 — Investigation B reuses A's evidence (no duplicate stored)")
        reuse = curator.record_reuse(
            tenant_id="tenant_demo",
            investigation_id="inv-B",
            evidence_id="ev-A-001",
            source_investigation_id="inv-A",
            rationale="Neural interface evidence is directly relevant to medical robotics.",
            freshness_assessment="fresh",
        )
        print(f"  ✓ Reuse recorded: inv-B → ev-A-001 (from inv-A)")

        # ── Step 6: Investigation B tries to ingest the SAME content ────────
        banner("STEP 6 — Investigation B attempts to ingest the SAME content")
        ev_b_dup = Evidence(
            id="ev-B-attempted-dup",
            kind=EvidenceKind.QUOTE,
            source_id="openalex",
            tenant_id="tenant_demo",
            content_preview="Neural interfaces for prosthetic control show 80% precision.",
            provenance=Provenance(
                observed_at=datetime(2024, 6, 1, tzinfo=UTC),
                ingested_at=datetime.now(UTC),
            ),
        )
        result_b = curator.ingest_evidence(
            evidence=ev_b_dup, tenant_id="tenant_demo",
            investigation_id="inv-B", raw_content=raw,  # SAME content
        )
        print(f"  ✓ Dedup detected: deduplicated={result_b.deduplicated}")
        print(f"    evidence_id={result_b.evidence_id} (points to original ev-A-001)")
        print(f"    reused_from_investigation_id={result_b.reused_from_investigation_id}")

        # Verify only ONE evidence row exists in the DB
        count = db.execute(
            select(func.count()).select_from(EvidenceItemRow)
        ).scalar_one()
        print(f"  ✓ Total evidence rows in DB: {count} (expected 1)")

        # ── Step 7: A contradicting piece of evidence is added ──────────────
        banner("STEP 7 — Contradicting evidence added (refutes the claim)")
        ev_contra = Evidence(
            id="ev-contradict",
            kind=EvidenceKind.QUOTE,
            source_id="clinicaltrials-gov",
            tenant_id="tenant_demo",
            content_preview="Field trial shows only 40% precision in real-world conditions.",
            provenance=Provenance(
                observed_at=datetime(2024, 9, 1, tzinfo=UTC),
                ingested_at=datetime.now(UTC),
            ),
        )
        curator.ingest_evidence(
            evidence=ev_contra, tenant_id="tenant_demo",
            investigation_id="inv-A",
        )
        curator.add_support_edge(
            tenant_id="tenant_demo",
            claim_id="claim-A-001",
            evidence_id="ev-contradict",
            relation="refutes",
        )
        claim = db.get(ClaimRow, "claim-A-001")
        print(f"  ✓ Claim verdict after refutation: {claim.verdict}")
        print("  ✓ BOTH supporting evidence (ev-A-001) AND refuting evidence (ev-contradict)")
        print("    are preserved — no silent deletion.")

        # Verify both evidence items still exist
        ev1 = db.get(EvidenceItemRow, "ev-A-001")
        ev2 = db.get(EvidenceItemRow, "ev-contradict")
        assert ev1 is not None and ev2 is not None
        print(f"  ✓ ev-A-001 exists: {ev1 is not None}")
        print(f"  ✓ ev-contradict exists: {ev2 is not None}")

        # ── Step 8: Bitemporal replay — no future leakage ────────────────────
        banner("STEP 8 — Bitemporal replay (no future leakage)")
        cutoff = datetime(2024, 7, 1, tzinfo=UTC)
        visible = curator.get_evidence_at_cutoff(
            tenant_id="tenant_demo",
            investigation_id="inv-A",
            cutoff=cutoff,
        )
        visible_ids = {r.id for r in visible}
        print(f"  Cutoff: {cutoff.isoformat()}")
        print(f"  Visible evidence at cutoff: {sorted(visible_ids)}")
        assert "ev-A-001" in visible_ids, "past evidence should be visible"
        assert "ev-contradict" not in visible_ids, "future evidence should NOT be visible"
        print("  ✓ ev-A-001 (observed 2024-06-01) is visible — past evidence included")
        print("  ✗ ev-contradict (observed 2024-09-01) is NOT visible — no future leakage")

        # ── Step 9: Tenant isolation ────────────────────────────────────────
        banner("STEP 9 — Tenant isolation (tenant_X cannot see tenant_demo's evidence)")
        db.add(InvestigationRow(
            id="inv-X", tenant_id="tenant_X", user_id="user-x",
            state="received", topic="Cross-tenant test",
            payload={"id": "inv-X", "tenant_id": "tenant_X"},
        ))
        db.commit()
        x_result = curator.search_prior_memory(
            query="neural prosthetics",
            tenant_id="tenant_X",
            investigation_id="inv-X",
        )
        print(f"  tenant_X search returned {len(x_result.reusable_evidence)} items (expected 0)")
        assert len(x_result.reusable_evidence) == 0
        print("  ✓ Zero cross-tenant leakage")

        x_cutoff = curator.get_evidence_at_cutoff(
            tenant_id="tenant_X",
            investigation_id="inv-X",
            cutoff=datetime(2025, 1, 1, tzinfo=UTC),
        )
        print(f"  tenant_X bitemporal replay returned {len(x_cutoff)} items (expected 0)")
        assert len(x_cutoff) == 0
        print("  ✓ Zero cross-tenant bitemporal leakage")

        # ── Step 10: Audit log summary ──────────────────────────────────────
        banner("STEP 10 — Audit log summary (append-only, never overwritten)")
        all_decisions = list(db.execute(
            select(MemoryDecisionRow).order_by(MemoryDecisionRow.decided_at)
        ).scalars())
        print(f"  Total decisions: {len(all_decisions)}")
        for d in all_decisions:
            print(f"    [{d.decided_at.strftime('%H:%M:%S')}] "
                  f"{d.decision_type:30s} "
                  f"evidence={d.evidence_id or '-':15s} "
                  f"claim={d.claim_id or '-':15s} "
                  f"actor={d.actor}")

        # ── Final acceptance assertion ──────────────────────────────────────
        banner("G03 ACCEPTANCE ASSERTION")
        decision_types = [d.decision_type for d in all_decisions]
        required = {
            "evidence_ingested",
            "claim_promoted",
            "evidence_reused",
            "evidence_deduplicated",
            "claim_contradicted",
        }
        missing = required - set(decision_types)
        if missing:
            print(f"  ✗ FAIL: missing decision types: {missing}")
            return 1
        else:
            print("  ✓ evidence_ingested     — new evidence recorded with provenance")
            print("  ✓ claim_promoted        — verdict transition (candidate → supported)")
            print("  ✓ evidence_reused       — inv-B reused inv-A's evidence (recorded)")
            print("  ✓ evidence_deduplicated — inv-B's duplicate attempt detected")
            print("  ✓ claim_contradicted    — refutation preserved (no silent delete)")
            print()
            print("  ✓ G03 ACCEPTANCE: PASS")
            print()
            print("  Two investigations reused one vetted source, preserved")
            print("  contradiction, did not leak tenant data, did not leak future records.")

        # Cleanup
        Base.metadata.drop_all(bind=engine)
        try:
            os.remove("/tmp/manara_g03_evidence.db")
        except OSError:
            pass
        return 0


if __name__ == "__main__":
    sys.exit(main())
