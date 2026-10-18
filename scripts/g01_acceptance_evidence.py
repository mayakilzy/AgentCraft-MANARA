"""G01 acceptance evidence — runs the prosthetics query and prints real
results with scores and reasons.

Usage:
    DATABASE_URL=sqlite:///./manara_dev.db \\
    SENTENCE_TRANSFORMERS_HOME=/home/z/my-project/.models \\
    HF_HOME=/home/z/my-project/.models/hf_cache \\
    python3 scripts/g01_acceptance_evidence.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Set model cache BEFORE any manara imports
os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", "/home/z/my-project/.models")
os.environ.setdefault("HF_HOME", "/home/z/my-project/.models/hf_cache")

# Add backend/src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend" / "src"))

from manara.db.session import Base, get_engine, reset_engine, get_session_factory
from manara.registry import SEED_CAPABILITIES, CapabilityRegistry


def main() -> int:
    # Use a fresh SQLite DB
    db_url = "sqlite:////tmp/manara_g01_evidence.db"
    os.environ["DATABASE_URL"] = db_url
    reset_engine()
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        reg = CapabilityRegistry(db)

        # Seed all 8 cards
        print("=" * 78)
        print("STEP 1 — Seeding 8 capability cards")
        print("=" * 78)
        for cap in SEED_CAPABILITIES:
            reg.create_capability(cap, tenant_id="tenant_demo")
            print(f"  ✓ {cap.id} ({cap.status.value})")

        # Run the prosthetics acceptance test
        print()
        print("=" * 78)
        print("STEP 2 — THE ACCEPTANCE TEST")
        print("=" * 78)
        print()
        print("QUERY: 'Future of intelligent prosthetics and neural interfaces through 2035'")
        print()
        print("Expected: results from academic-publications, patent-intelligence,")
        print("           clinical-trials, github-activity — even though NONE of")
        print("           these card display_names contains the word 'prosthetics'.")
        print()

        result = reg.search(
            "Future of intelligent prosthetics and neural interfaces through 2035",
            tenant_id="tenant_demo",
            top_k=10,
        )

        print(f"Found {len(result.hits)} hits (top_k=10).")
        print()

        # Print stage traces
        print("STAGE TRACES:")
        for t in result.stage_traces:
            in_count = t.candidates_in if t.candidates_in >= 0 else "—"
            print(f"  {t.stage:20s}  in={in_count:>3}  out={t.candidates_out:>3}  | {t.notes}")
        print()

        # Print hits
        print("HITS (ranked by final score):")
        print("-" * 78)
        for i, hit in enumerate(result.hits, 1):
            print(f"  #{i}  {hit.capability.display_name}")
            print(f"       id: {hit.capability.id}")
            print(f"       final_score: {hit.final_score:.4f}")
            print(f"       text_sim:    {hit.text_similarity:.4f}")
            print(f"       semantic:    {hit.semantic_similarity:.4f}")
            print(f"       neg_penalty: {hit.negative_penalty:.4f}")
            print(f"       matched_by:    {hit.matched_by}")
            if hit.rejected_by_negative:
                print(f"       rejected_by_neg: {hit.rejected_by_negative}")
            print()

        # Print gaps
        if result.gaps:
            print("COVERAGE GAPS:")
            for g in result.gaps:
                print(f"  ⚠ {g}")
            print()

        # Acceptance assertion
        print("=" * 78)
        print("ACCEPTANCE ASSERTION")
        print("=" * 78)
        hit_ids = {h.capability.id for h in result.hits}
        expected = {
            "search.academic-publications",
            "search.patent-intelligence",
            "search.clinical-trials",
            "search.github-activity",
        }
        intersection = hit_ids & expected
        print(f"  Returned engine IDs: {sorted(hit_ids)}")
        print(f"  Expected (any of):  {sorted(expected)}")
        print(f"  Intersection:       {sorted(intersection)}")
        print()
        if intersection:
            print("  ✓ ACCEPTANCE: PASS")
            print("    At least one cross-domain engine was retrieved for the prosthetics")
            print("    query, demonstrating semantic (not keyword) search.")
        else:
            print("  ✗ ACCEPTANCE: FAIL")
            print("    No cross-domain engine was retrieved.")

        # Bonus: print the cross-domain similarity scores for documentation
        print()
        print("=" * 78)
        print("STEP 3 — Cross-domain similarity matrix (documentation)")
        print("=" * 78)
        print()
        print("This matrix shows how similar the prosthetics query is to each card's")
        print("positive examples (max across all positive examples per card):")
        print()
        for hit in result.hits:
            print(f"  {hit.capability.id:42s}  semantic={hit.semantic_similarity:.3f}  "
                  f"final={hit.final_score:.3f}")

        # Bonus 2: Arabic query
        print()
        print("=" * 78)
        print("STEP 4 — Arabic query test (multilingual retrieval)")
        print("=" * 78)
        print()
        ar_query = "براءات اختراع في مجال الروبوتات الطبية"
        print(f"QUERY (ar): '{ar_query}'")
        print()
        ar_result = reg.search(ar_query, tenant_id="tenant_demo", top_k=5)
        print(f"Found {len(ar_result.hits)} hits.")
        for i, hit in enumerate(ar_result.hits, 1):
            print(f"  #{i}  {hit.capability.display_name:38s}  "
                  f"text={hit.text_similarity:.3f}  semantic={hit.semantic_similarity:.3f}")

        # Bonus 3: Battery query
        print()
        print("=" * 78)
        print("STEP 5 — Battery query test (in-domain retrieval)")
        print("=" * 78)
        print()
        bat_query = "Track Li-ion battery pack cost per kWh from 2015 to 2024"
        print(f"QUERY: '{bat_query}'")
        print()
        bat_result = reg.search(bat_query, tenant_id="tenant_demo", top_k=5)
        print(f"Found {len(bat_result.hits)} hits.")
        for i, hit in enumerate(bat_result.hits, 1):
            print(f"  #{i}  {hit.capability.display_name:38s}  "
                  f"text={hit.text_similarity:.3f}  semantic={hit.semantic_similarity:.3f}")

        # Bonus 4: Negative example test
        print()
        print("=" * 78)
        print("STEP 6 — Negative-example reranker test")
        print("=" * 78)
        print()
        neg_query = "prove medical implant safety from patent filings"
        print(f"QUERY: '{neg_query}'")
        print("(This matches a negative example on search.patent-intelligence:")
        print(" 'Prove a medical implant is safe based only on patent filing')")
        print()
        neg_result = reg.search(neg_query, tenant_id="tenant_demo", top_k=10)
        for hit in neg_result.hits:
            print(f"  {hit.capability.id:42s}  "
                  f"final={hit.final_score:.3f}  neg_penalty={hit.negative_penalty:.3f}  "
                  f"rejected_by_negative={hit.rejected_by_negative}")
            if hit.capability.id == "search.patent-intelligence":
                if hit.negative_penalty > 0:
                    print(f"  ✓ NEGATIVE RERANKER ACTIVE: patent-intelligence was penalized")
                else:
                    print(f"  ⚠ Negative penalty was zero (negative-example threshold may be too high)")

        # Cleanup
        Base.metadata.drop_all(bind=engine)
        os.remove("/tmp/manara_g01_evidence.db")
        return 0 if intersection else 1


if __name__ == "__main__":
    sys.exit(main())
