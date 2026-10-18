"""G01-R1 acceptance evidence — Multi-Capability Coverage search.

Demonstrates the fix for the owner's G01 review:

> "The system retrieved patent-intelligence correctly, but it also returned
> agriculture and energy engines, while academic-publications and clinical-
> trials were missing — despite being essential."

This script runs the new ``search_multi_coverage`` pipeline on four
benchmark queries and prints the BEFORE (original G01 search) vs AFTER
(G01-R1 multi-coverage) comparison.

Usage:
    DATABASE_URL=sqlite:///./manara_dev.db \\
    SENTENCE_TRANSFORMERS_HOME=/home/z/my-project/.models \\
    HF_HOME=/home/z/my-project/.models/hf_cache \\
    python3 scripts/g01r1_acceptance_evidence.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", "/home/z/my-project/.models")
os.environ.setdefault("HF_HOME", "/home/z/my-project/.models/hf_cache")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend" / "src"))

from manara.db.session import Base, get_engine, get_session_factory, reset_engine
from manara.registry import SEED_CAPABILITIES, CapabilityRegistry


def banner(text: str) -> None:
    print()
    print("=" * 78)
    print(text)
    print("=" * 78)


def main() -> int:
    db_url = "sqlite:////tmp/manara_g01r1_evidence.db"
    os.environ["DATABASE_URL"] = db_url
    reset_engine()
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        reg = CapabilityRegistry(db)

        banner("STEP 1 — Seeding 8 capability cards")
        for cap in SEED_CAPABILITIES:
            reg.create_capability(cap, tenant_id="tenant_demo")
            print(f"  ✓ {cap.id}")

        queries = [
            (
                "Future of intelligent prosthetics and neural interfaces through 2035",
                "PROSTHETICS (English)",
                {"search.academic-publications", "search.patent-intelligence", "search.clinical-trials"},
            ),
            (
                "مستقبل الأطراف الصناعية الذكية والواجهات العصبية حتى 2035",
                "PROSTHETICS (Arabic)",
                {"search.academic-publications", "search.patent-intelligence", "search.clinical-trials"},
            ),
            (
                "Track Li-ion battery pack cost per kWh from 2015 to 2024",
                "BATTERY (English)",
                {"search.energy-ev-datasets"},
            ),
            (
                "Assess worldwide recycling technologies and market direction to 2035",
                "RECYCLING (English)",
                {"search.waste-recycling-statistics"},
            ),
            (
                "Track diplomatic events and conflict indicators in the Middle East",
                "GEOPOLITICS (English)",
                {"search.geopolitical-events"},
            ),
            (
                "براءات اختراع في مجال الروبوتات الطبية",
                "PATENTS (Arabic)",
                {"search.patent-intelligence"},
            ),
        ]

        total_precision = 0.0
        total_recall = 0.0
        n = 0

        for query, label, expected in queries:
            banner(f"QUERY: {label}")
            print(f"  Text:     {query}")
            print(f"  Expected: {sorted(expected)}")
            print()

            # BEFORE: original G01 search
            print("  ── BEFORE (original G01 search) ──")
            before = reg.search(query, tenant_id="tenant_demo", top_k=10)
            before_ids = {h.capability.id for h in before.hits}
            before_precision = (
                len(before_ids & expected) / len(before_ids) if before_ids else 0.0
            )
            before_recall = (
                len(before_ids & expected) / len(expected) if expected else 0.0
            )
            for h in before.hits:
                marker = "✓" if h.capability.id in expected else "✗"
                print(f"    {marker} {h.capability.id:42s}  score={h.final_score:.3f}")
            print(f"    → precision={before_precision:.3f}, recall={before_recall:.3f}")
            print()

            # AFTER: G01-R1 multi-coverage search
            print("  ── AFTER (G01-R1 multi-coverage) ──")
            after = reg.search_multi_coverage(query, tenant_id="tenant_demo")
            after_ids = {h.capability.id for h in after.hits}
            after_precision = (
                len(after_ids & expected) / len(after_ids) if after_ids else 0.0
            )
            after_recall = (
                len(after_ids & expected) / len(expected) if expected else 0.0
            )

            # Print detected needs
            print("    Detected research needs:")
            for d in after.decomposition.detected_needs:
                tag = "(implicit)" if d.relevance <= 0.5 else ""
                print(f"      • {d.need:25s} relevance={d.relevance:.3f} {tag}")
            print()

            print("    Coverage map (need → engine):")
            for c in after.coverage_map:
                marker = "✓" if c.capability_id in expected else " "
                print(f"      {marker} {c.need:25s} → {c.capability_id:42s}  fit={c.need_fit_score:.3f}")
            print()

            print("    Hits (ranked):")
            for h in after.hits:
                marker = "✓" if h.capability.id in expected else "✗"
                print(f"      {marker} {h.capability.id:42s}  score={h.final_score:.3f}")
            print(f"    → precision={after_precision:.3f}, recall={after_recall:.3f}")

            if after.gaps:
                print(f"    Coverage gaps: {len(after.gaps)}")
                for g in after.gaps[:3]:
                    print(f"      ⚠ {g}")

            print()
            print(f"  DELTA: precision {before_precision:.3f} → {after_precision:.3f}, "
                  f"recall {before_recall:.3f} → {after_recall:.3f}")

            total_precision += after_precision
            total_recall += after_recall
            n += 1

        banner("AGGREGATE PRECISION/RECALL (G01-R1 multi-coverage)")
        avg_p = total_precision / n if n else 0.0
        avg_r = total_recall / n if n else 0.0
        print(f"  Average precision: {avg_p:.3f}")
        print(f"  Average recall:    {avg_r:.3f}")
        print(f"  Acceptance threshold: precision ≥ 0.75, recall ≥ 0.75")
        if avg_p >= 0.75 and avg_r >= 0.75:
            print("  ✓ G01-R1 ACCEPTANCE: PASS")
        else:
            print("  ✗ G01-R1 ACCEPTANCE: FAIL")
            return 1

        # Cleanup
        Base.metadata.drop_all(bind=engine)
        try:
            os.remove("/tmp/manara_g01r1_evidence.db")
        except OSError:
            pass
        return 0


if __name__ == "__main__":
    sys.exit(main())
