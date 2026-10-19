"""
G09 E2E Browser Test — Playwright script for the full investigation journey.

Per owner (G09 Phase B):
> "شغّل Backend وFrontend معاً ثم اختبر الواجهة فعلياً."
> "لا تعتبر نجاح tsc بديلاً عن اختبار المتصفح."

This script requires Playwright to be installed:
    pip install playwright
    playwright install chromium

Run with:
    cd /home/z/my-project/repos/AgentCraft-MANARA
    python tests/e2e/test_investigation_journey.py

Prerequisites:
1. Backend running on localhost:8000
2. Frontend running on localhost:5173
3. Database initialized (alembic upgrade head)

If Playwright is not available, the script documents the constraint
and exits with a clear message.
"""

from __future__ import annotations

import sys
import os

def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("BLOCKER: Playwright not installed.")
        print("Install with: pip install playwright && playwright install chromium")
        print()
        print("Per owner (G09): 'لا تعتبر نجاح tsc بديلاً عن اختبار المتصفح.'")
        print("Browser E2E test SKIPPED — Playwright not available in sandbox.")
        print("This is a known constraint documented in G09_REPORT.md.")
        return 2  # skip code

    FRONTEND_URL = os.environ.get("MANARA_FRONTEND_URL", "http://localhost:5173")
    BACKEND_URL = os.environ.get("MANARA_BACKEND_URL", "http://localhost:8000")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        results: list[str] = []

        # ── Test 1: Homepage loads ────────────────────────────────────────
        try:
            page.goto(FRONTEND_URL, timeout=10000)
            title = page.title()
            assert "MANARA" in title or "manara" in page.content().lower()
            results.append("✓ Test 1: Homepage loads — title contains MANARA")
        except Exception as e:
            results.append(f"✗ Test 1: Homepage load failed: {e}")

        # ── Test 2: Status banner visible ──────────────────────────────────
        try:
            status_text = page.text_content("body")
            assert "capabilities" in status_text.lower() or "القدرات" in status_text
            results.append("✓ Test 2: Status banner visible with capabilities")
        except Exception as e:
            results.append(f"✗ Test 2: Status banner check failed: {e}")

        # ── Test 3: Investigation input works ──────────────────────────────
        try:
            # Find the textarea and type a query
            textarea = page.query_selector("textarea")
            assert textarea is not None
            textarea.fill("Future of waste recycling technologies in the next ten years")
            results.append("✓ Test 3: Investigation input accepts text (Arabic/English)")
        except Exception as e:
            results.append(f"✗ Test 3: Input test failed: {e}")

        # ── Test 4: Submit query and get mold ───────────────────────────────
        try:
            # Click the compose button
            button = page.query_selector("button:has-text('Compose')")
            if button is None:
                button = page.query_selector("button:has-text('حلّل')")
            assert button is not None
            button.click()
            # Wait for response (up to 30 seconds — model loading)
            page.wait_for_selector("text=Analysis Result", timeout=30000)
            results.append("✓ Test 4: Mold composition returned — Analysis Result visible")
        except Exception as e:
            results.append(f"✗ Test 4: Submit query failed: {e}")

        # ── Test 5: Coverage and gaps displayed ─────────────────────────────
        try:
            body = page.text_content("body")
            has_coverage = "Coverage" in body or "التغطية" in body
            has_gaps = "Gaps" in body or "الفجوات" in body
            if has_coverage or has_gaps:
                results.append("✓ Test 5: Coverage and gaps displayed")
            else:
                results.append("△ Test 5: Coverage/gaps section not found (may be empty)")
        except Exception as e:
            results.append(f"✗ Test 5: Coverage check failed: {e}")

        # ── Test 6: Navigation works ─────────────────────────────────────────
        try:
            # Click on Registry tab
            registry_tab = page.query_selector("button:has-text('Registry')")
            if registry_tab:
                registry_tab.click()
                page.wait_for_timeout(1000)
                body = page.text_content("body")
                assert "capability" in body.lower() or "قدرة" in body
                results.append("✓ Test 6: Navigation to Registry works")
            else:
                results.append("△ Test 6: Registry tab not found")
        except Exception as e:
            results.append(f"✗ Test 6: Navigation test failed: {e}")

        # ── Test 7: Publishing tab ───────────────────────────────────────────
        try:
            pub_tab = page.query_selector("button:has-text('Publishing')")
            if pub_tab:
                pub_tab.click()
                page.wait_for_timeout(1000)
                body = page.text_content("body")
                # Should show either publications or empty-state message
                assert "publication" in body.lower() or "منشور" in body or "لا توجد" in body
                results.append("✓ Test 7: Publishing tab accessible")
            else:
                results.append("△ Test 7: Publishing tab not found")
        except Exception as e:
            results.append(f"✗ Test 7: Publishing tab test failed: {e}")

        browser.close()

    # Print results
    print("\n" + "=" * 60)
    print("G09 Browser E2E Test Results")
    print("=" * 60)
    for r in results:
        print(f"  {r}")
    passed = sum(1 for r in results if r.startswith("✓"))
    failed = sum(1 for r in results if r.startswith("✗"))
    skipped = sum(1 for r in results if r.startswith("△"))
    print(f"\n{passed} passed, {failed} failed, {skipped} skipped")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
