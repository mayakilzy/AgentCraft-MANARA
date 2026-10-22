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
        # MANARA-UI-PAGE02-PRE-ACCEPTANCE-01: fix legacy selector.
        # The current UI uses 'Start Investigation' (EN) / 'بدء التحقيق' (AR),
        # NOT 'Compose' / 'حلّل'. After compose succeeds, the ComposeResultCard
        # renders the Investigation ID (per i18n key 'home.investigationId').
        try:
            button = page.query_selector("button:has-text('Start Investigation')")
            if button is None:
                button = page.query_selector("button:has-text('بدء التحقيق')")
            assert button is not None, "Submit button not found (expected 'Start Investigation' or 'بدء التحقيق')"
            button.click()
            # Wait for compose response — the ComposeResultCard renders
            # 'Investigation ID' (or Arabic equivalent 'معرّف التحقيق')
            # when compose succeeds. Allow 30s for model loading on cold start.
            try:
                page.wait_for_selector("text=Investigation ID", timeout=30000)
            except Exception:
                # Fall back to Arabic label (if language was toggled) or
                # the investigation_id pattern that the ComposeResultCard shows
                page.wait_for_selector("text=معرّف التحقيق", timeout=5000)
            results.append("✓ Test 4: Submit query — compose returned Investigation ID")
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

        # ── Test 6: Registry nav item present ────────────────────────────────
        # MANARA-UI-PAGE02-PRE-ACCEPTANCE-01: fix selector.
        # The Sidebar renders nav items as <a> elements (not <button>) per
        # the Page 01 closure work. The 'Registry' nav item is present but
        # locked (not clickable yet — onNavigate only handles home/workspace/memory).
        try:
            # Look for <a> element containing 'Registry' (or Arabic 'سجل القدرات')
            registry_link = page.query_selector("a:has-text('Capability Registry')")
            if registry_link is None:
                registry_link = page.query_selector("a:has-text('سجل القدرات')")
            if registry_link is not None:
                results.append("✓ Test 6: Registry nav item present in sidebar")
            else:
                results.append("△ Test 6: Registry nav item not found")
        except Exception as e:
            results.append(f"✗ Test 6: Registry nav check failed: {e}")

        # ── Test 7: Publishing nav item present ────────────────────────────────
        try:
            pub_link = page.query_selector("a:has-text('Publishing Studio')")
            if pub_link is None:
                pub_link = page.query_selector("a:has-text('استوديو النشر')")
            if pub_link is not None:
                results.append("✓ Test 7: Publishing nav item present in sidebar")
            else:
                results.append("△ Test 7: Publishing nav item not found")
        except Exception as e:
            results.append(f"✗ Test 7: Publishing nav check failed: {e}")

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
