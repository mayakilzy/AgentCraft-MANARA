"""
Phase C2 — Seed dev-isolated fixtures for Page 02 visual verification.

This script populates a DEV SQLite database with a synthetic investigation
that contains Evidence, Claims, and Relationship Edges — to test the
populated state of the Investigation Workspace React UI.

CRITICAL DOCUMENTATION (per handoff Section 8 + reference README rule 2):
- This data is SYNTHETIC DEV FIXTURE DATA, not real research findings.
- It honors the real API contracts (POST /memory/evidence,
  POST /memory/evidence/{id}/claims, POST /memory/claims/{id}/support,
  POST /mold-factory/compose, POST /mold-factory/investigations/{id}/workflow,
  POST /mold-factory/investigations/{id}/transition, PATCH verdict).
- It is loaded into a dev SQLite DB (manara_dev.db) — NOT production.
- The "research question" is a generic example query from the Home page
  examples list; the "evidence" content is fabricated for visual testing
  only and must NEVER be presented as verified scientific findings.
- No real arXiv/PubMed/OpenAlex/Crossref sources are claimed — the
  source_id values are synthetic dev IDs (dev-src-001..005).

Run: python3 /home/z/my-project/scripts/page02_phaseC_seed_fixtures.py
"""
import json
import sys
import time
import urllib.request
import urllib.error

API_BASE = "http://127.0.0.1:8000"
TIMEOUT = 15

def post(path, body):
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else b""
        print(f"  ERROR POST {path}: HTTP {e.code} — {body[:300]}")
        return None
    except Exception as e:
        print(f"  ERROR POST {path}: {e}")
        return None

def patch(path, body):
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="PATCH",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else b""
        print(f"  ERROR PATCH {path}: HTTP {e.code} — {body[:300]}")
        return None

def get(path):
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"  ERROR GET {path}: {e}")
        return None

def wait_for_backend(max_wait=60):
    print("Waiting for backend to be ready...")
    for i in range(max_wait):
        try:
            with urllib.request.urlopen(f"{API_BASE}/status", timeout=2) as r:
                if r.status == 200:
                    print(f"  Backend ready after {i+1}s")
                    return True
        except Exception:
            time.sleep(1)
    print("  Backend not ready after 60s")
    return False

def main():
    if not wait_for_backend():
        sys.exit(1)

    # === 1. Compose investigation (creates the investigation row + mold) ===
    print("\n=== Step 1: Compose investigation ===")
    query = "How are additive manufacturing technologies transforming prosthetics?"
    comp = post("/mold-factory/compose", {"query": query})
    if not comp:
        sys.exit(1)
    inv_id = comp["investigation_id"]
    print(f"  Created investigation: {inv_id}")
    print(f"  Query: {query}")
    print(f"  Mold: {comp.get('mold_recipe_id')}")
    print(f"  Deliverable type: {comp.get('deliverable_type')}")
    print(f"  Detected needs: {len(comp.get('detected_needs', []))}")
    print(f"  Coverage entries: {len(comp.get('coverage', []))}")

    # === 2. Initialize workflow (POST auto-creates the workflow row) ===
    print("\n=== Step 2: Initialize workflow ===")
    wf = post(f"/mold-factory/investigations/{inv_id}/workflow", {})
    if wf:
        print(f"  Initial state: {wf.get('state')}")
    else:
        print("  (Workflow may already exist; continuing)")

    # === 3. Transition through several states to populate audit history ===
    print("\n=== Step 3: Transition through FSM states ===")
    transitions = [
        "scoped",
        "coverage_checked",
        "building_capabilities",
        "mold_ready",
        "acquiring",
        "normalizing",
    ]
    for target in transitions:
        result = post(f"/mold-factory/investigations/{inv_id}/transition", {
            "target_state": target,
            "actor": "dev-fixture-seeder",
            "rationale": f"Dev fixture: advance to {target} for visual testing",
        })
        if result:
            print(f"  -> {target}: transitioned={result.get('transitioned')} blocker={result.get('blocker')}")
        else:
            print(f"  -> {target}: failed")
        time.sleep(0.1)

    # === 4. Ingest 5 evidence items (synthetic dev data) ===
    print("\n=== Step 4: Ingest 5 synthetic evidence items ===")
    evidence_items = []
    sources = [
        ("dev-src-001", "openalex", "Academic literature (dev fixture)"),
        ("dev-src-002", "openalex", "Patent metadata (dev fixture)"),
        ("dev-src-003", "openalex", "Clinical paper (dev fixture)"),
        ("dev-src-004", "internal", "Internal report (dev fixture)"),
        ("dev-src-005", "openalex", "Survey paper (dev fixture)"),
    ]
    for i, (src_id, src_type, desc) in enumerate(sources, 1):
        ev_id = f"dev-ev-{i:03d}-{inv_id[-6:]}"
        evidence_contract = {
            "id": ev_id,
            "schema_version": "1.0.0",
            "kind": "quote" if i % 2 == 1 else "data",
            "source_id": src_id,
            "tenant_id": "tenant_demo",
            "content_preview": f"[DEV FIXTURE] {desc}. This is synthetic content for visual testing only — not a real research finding.",
            "structured_payload": {
                "dev_fixture": True,
                "synthetic": True,
                "index": i,
                "description": desc,
            },
            "provenance": {
                "observed_at": "2025-09-15T10:00:00Z",
                "ingested_at": "2025-10-01T12:00:00Z",
                "known_at": "2025-10-01T12:00:00Z",
            },
        }
        result = post("/memory/evidence", {
            "evidence": evidence_contract,
            "investigation_id": inv_id,
            "actor": "dev-fixture-seeder",
        })
        if result:
            print(f"  Evidence {i}: id={result.get('evidence_id')} dedup={result.get('deduplicated')}")
            evidence_items.append((ev_id, src_id))
        else:
            print(f"  Evidence {i}: failed")
        time.sleep(0.05)

    # === 5. Attach 5 claims (one per evidence) ===
    print("\n=== Step 5: Attach 5 claims (one per evidence) ===")
    claim_statements = [
        "Additive manufacturing reduces prosthetic socket production time by approximately 60% compared to traditional methods (dev fixture, not a real measurement).",
        "3D-printed prosthetics show comparable durability to traditional manufacturing in laboratory stress tests (dev fixture, not a verified result).",
        "Patient satisfaction scores are higher with custom-fit 3D-printed sockets according to a small clinical survey (dev fixture, not peer-reviewed).",
        "Material costs for additive manufacturing remain higher than bulk traditional production at low volumes (dev fixture, indicative only).",
        "Regulatory pathways for 3D-printed medical devices are evolving but not yet standardized across jurisdictions (dev fixture observation).",
    ]
    verdicts_cycle = ["candidate", "supported", "contested", "refuted", "superseded"]
    claims = []
    for i, (ev_id, src_id) in enumerate(evidence_items):
        claim_id = f"dev-cl-{i+1:03d}-{inv_id[-6:]}"
        verdict = verdicts_cycle[i % len(verdicts_cycle)]
        result = post(f"/memory/evidence/{ev_id}/claims", {
            "claim_id": claim_id,
            "evidence_id": ev_id,
            "statement": claim_statements[i],
            "verdict": verdict,
            "independence_group": f"dev-group-{i//2 + 1}",
        })
        if result is not None:
            print(f"  Claim {i+1}: id={claim_id} verdict={verdict}")
            claims.append((claim_id, ev_id, verdict))
        time.sleep(0.05)

    # === 6. Add 6 relationship edges (mix of supports/refutes/qualifies) ===
    print("\n=== Step 6: Add 6 relationship edges ===")
    edges_to_add = [
        # (claim_id, evidence_id, relation, weight, notes)
        (claims[0][0], claims[0][1], "supports", 1.0, "Dev fixture: claim-1 supports claim-1's evidence"),
        (claims[1][0], claims[1][1], "supports", 0.8, "Dev fixture: claim-2 supports its evidence"),
        (claims[2][0], claims[2][1], "qualifies", 0.5, "Dev fixture: claim-3 qualifies (small sample size)"),
        (claims[3][0], claims[3][1], "refutes", 0.7, "Dev fixture: claim-4 refutes cost-effectiveness"),
        (claims[4][0], claims[0][1], "qualifies", 0.4, "Dev fixture: claim-5 cross-references ev-1 (regulatory context)"),
        (claims[1][0], claims[2][1], "supports", 0.6, "Dev fixture: claim-2 cross-supports ev-3 (clinical correlation)"),
    ]
    for claim_id, ev_id, relation, weight, notes in edges_to_add:
        result = post(f"/memory/claims/{claim_id}/support", {
            "evidence_id": ev_id,
            "relation": relation,
            "weight": weight,
            "notes": notes,
        })
        if result is not None:
            print(f"  Edge: {claim_id} {relation} {ev_id} (w={weight})")
        time.sleep(0.05)

    # === 7. Patch one claim's verdict to demonstrate promotion ===
    print("\n=== Step 7: Promote one claim's verdict (demonstrate PATCH) ===")
    if claims:
        promote_claim = claims[0][0]
        result = patch(f"/memory/claims/{promote_claim}/verdict", {
            "new_verdict": "supported",
            "rationale": "Dev fixture: promote claim-1 from candidate to supported to demonstrate verdict promotion UI.",
            "actor": "dev-fixture-seeder",
        })
        if result is not None:
            print(f"  Promoted {promote_claim} -> supported")

    # === 8. Verify state via GET endpoints ===
    print("\n=== Step 8: Verify seeded data via GET ===")
    ev_list = get(f"/memory/investigations/{inv_id}/evidence")
    cl_list = get(f"/memory/investigations/{inv_id}/claims")
    ed_list = get(f"/memory/investigations/{inv_id}/edges")
    wf_state = get(f"/mold-factory/investigations/{inv_id}/workflow")
    inv_detail = get(f"/mold-factory/investigations/{inv_id}")
    print(f"  Investigation ID: {inv_id}")
    print(f"  Topic: {inv_detail.get('topic', '?')[:80] if inv_detail else '?'}")
    print(f"  Workflow state: {wf_state.get('state') if wf_state else '?'}")
    print(f"  Transitions recorded: {len(wf_state.get('transitions', [])) if wf_state else 0}")
    print(f"  Evidence items: {len(ev_list) if ev_list else 0}")
    print(f"  Claims: {len(cl_list) if cl_list else 0}")
    print(f"  Edges: {len(ed_list) if ed_list else 0}")

    print(f"\n=== DONE. Investigation ID for visual testing: {inv_id} ===")
    print("Use this ID in the URL: http://localhost:5173/?investigationId=" + inv_id)
    print("Or in the Home page compose flow, then click 'Open Investigation Workspace'.")

    # Save the ID to a file for the screenshot script to pick up
    with open("/home/z/my-project/scripts/.dev_investigation_id", "w") as f:
        f.write(inv_id)
    print(f"(Investigation ID saved to /home/z/my-project/scripts/.dev_investigation_id)")

if __name__ == "__main__":
    main()
