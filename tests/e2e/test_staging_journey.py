"""
STAGING-PRE-01 Strict Browser Acceptance Test.

Per owner (Staging-PRE-01):
> "اختبارات القبول الأساسية لا يجوز أن تنجح عندما تكون خطواتها الأساسية متجاوزة."
> "افصل اختبارات Blocker Report عن اختبارات Research Deliverable."

Result codes:
  0 = ALL PASS
  1 = AT LEAST ONE FAIL
  2 = SKIPPED (Playwright not available)

Run:
    python tests/e2e/test_staging_journey.py
"""

from __future__ import annotations

import sys
import os


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright, expect
    except ImportError:
        print("=" * 60)
        print("STAGING E2E TEST: SKIPPED")
        print("=" * 60)
        print()
        print("BLOCKER: Playwright not installed.")
        print("  pip install playwright && playwright install chromium")
        print()
        print("Per owner: 'لا تعتبر نجاح tsc بديلاً عن اختبار المتصفح.'")
        return 2

    FRONTEND_URL = os.environ.get("MANARA_FRONTEND_URL", "http://localhost:5173")
    BACKEND_URL = os.environ.get("MANARA_BACKEND_URL", "http://localhost:8000")

    tests: list[tuple[str, str]] = []  # (name, "PASS" | "FAIL" | "SKIP")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})

        # Helper to collect console errors
        console_errors: list[str] = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        # ── Test 1: Homepage loads with textarea ────────────────────────────
        try:
            page.goto(FRONTEND_URL, timeout=15000)
            page.wait_for_selector("textarea", timeout=10000)
            tests.append(("Homepage loads with textarea", "PASS"))
        except Exception as e:
            tests.append(("Homepage loads with textarea", f"FAIL: {e}"))

        # ── Test 2: Status API returns 200 ──────────────────────────────────
        try:
            response = page.request.get(f"{BACKEND_URL}/status")
            assert response.ok, f"status API returned {response.status}"
            status_data = response.json()
            assert status_data["app"] == "MANARA"
            tests.append(("Status API returns 200 with MANARA", "PASS"))
        except Exception as e:
            tests.append(("Status API returns 200 with MANARA", f"FAIL: {e}"))

        # ── Test 3: Compose mold via API (strict — must return investigation_id) ──
        investigation_id = None
        try:
            response = page.request.post(
                f"{BACKEND_URL}/mold-factory/compose",
                data={"query": "Future of waste recycling technologies in the next ten years"},
                headers={"Content-Type": "application/json"},
            )
            assert response.ok, f"compose API returned {response.status}"
            mold_data = response.json()
            # MUST have a real investigation_id (not null, not inv-session)
            assert mold_data.get("investigation_id"), "investigation_id is null or missing"
            assert mold_data["investigation_id"].startswith("inv-"), \
                f"investigation_id doesn't start with 'inv-': {mold_data['investigation_id']}"
            investigation_id = mold_data["investigation_id"]
            tests.append(("Compose returns real investigation_id (inv-xxx)", "PASS"))
        except Exception as e:
            tests.append(("Compose returns real investigation_id (inv-xxx)", f"FAIL: {e}"))

        # ── Test 4: Mold has coverage and gaps ──────────────────────────────
        try:
            assert mold_data is not None, "mold_data not available"
            assert len(mold_data.get("detected_needs", [])) > 0, "no detected needs"
            assert "is_complete" in mold_data, "is_complete missing"
            assert "deliverable_type" in mold_data, "deliverable_type missing"
            tests.append(("Mold has needs, coverage, deliverable_type", "PASS"))
        except Exception as e:
            tests.append(("Mold has needs, coverage, deliverable_type", f"FAIL: {e}"))

        # ── Test 5: Enter question in UI and get result ─────────────────────
        try:
            textarea = page.query_selector("textarea")
            assert textarea is not None
            textarea.fill("Future of intelligent prosthetics and neural interfaces")
            button = page.query_selector("button:has-text('Compose')") or \
                     page.query_selector("button:has-text('حلّل')")
            assert button is not None
            button.click()
            page.wait_for_selector("text=Analysis Result", timeout=60000)
            tests.append(("UI compose: question → Analysis Result", "PASS"))
        except Exception as e:
            tests.append(("UI compose: question → Analysis Result", f"FAIL: {e}"))

        # ── Test 6: investigation_id appears in UI ───────────────────────────
        try:
            body = page.text_content("body")
            assert "inv-" in body, "investigation_id (inv-xxx) not found in UI"
            tests.append(("investigation_id visible in UI", "PASS"))
        except Exception as e:
            tests.append(("investigation_id visible in UI", f"FAIL: {e}"))

        # ── Test 7: Create publication via API (strict — must use real inv_id) ──
        publication_id = None
        try:
            assert investigation_id is not None, "no investigation_id from Test 3"
            response = page.request.post(
                f"{BACKEND_URL}/publishing/publications",
                data={
                    "investigation_id": investigation_id,
                    "output_type": "research_dossier",
                    "title": "Test Dossier",
                    "scope": {"topic": "Test"},
                },
                headers={"Content-Type": "application/json"},
            )
            assert response.ok, f"publication API returned {response.status}"
            pub_data = response.json()
            assert pub_data.get("publication_id"), "no publication_id in response"
            publication_id = pub_data["publication_id"]
            tests.append(("Publication created with real investigation_id", "PASS"))
        except Exception as e:
            tests.append(("Publication created with real investigation_id", f"FAIL: {e}"))

        # ── Test 8: Download publication (strict — must be non-empty) ────────
        try:
            assert publication_id is not None, "no publication_id from Test 7"
            response = page.request.get(
                f"{BACKEND_URL}/publishing/publications/{publication_id}/download?format=markdown"
            )
            assert response.ok, f"download returned {response.status}"
            content = response.text()
            assert len(content) > 0, "downloaded content is empty"
            assert "Test Dossier" in content or "dossier" in content.lower(), \
                "downloaded content doesn't contain expected title"
            tests.append(("Download produces non-empty file with correct content", "PASS"))
        except Exception as e:
            tests.append(("Download produces non-empty file with correct content", f"FAIL: {e}"))

        # ── Test 9: No critical JavaScript errors ───────────────────────────
        try:
            critical_errors = [e for e in console_errors if "Uncaught" in e or "TypeError" in e]
            assert len(critical_errors) == 0, f"{len(critical_errors)} critical JS errors: {critical_errors[:3]}"
            tests.append(("No critical JavaScript errors", "PASS"))
        except Exception as e:
            tests.append(("No critical JavaScript errors", f"FAIL: {e}"))

        # ── Test 10: Page refresh preserves context ──────────────────────────
        try:
            page.reload(timeout=15000)
            page.wait_for_timeout(2000)
            body = page.text_content("body")
            # After refresh, localStorage should preserve the investigation context
            if "تحقيق نشط" in body or "Active Investigation" in body:
                tests.append(("Investigation context preserved after refresh", "PASS"))
            else:
                tests.append(("Investigation context preserved after refresh", "FAIL: context not found after reload"))
        except Exception as e:
            tests.append(("Investigation context preserved after refresh", f"FAIL: {e}"))

        # ── Test 11: Screenshot ──────────────────────────────────────────────
        try:
            page.screenshot(path="tests/e2e/screenshot_staging.png", full_page=True)
            tests.append(("Screenshot saved", "PASS"))
        except Exception as e:
            tests.append(("Screenshot saved", f"FAIL: {e}"))

        browser.close()

    # Print results
    print("\n" + "=" * 60)
    print("STAGING E2E TEST RESULTS (STRICT)")
    print("=" * 60)
    passed = 0
    failed = 0
    for name, result in tests:
        status = result.split(":")[0] if ":" in result else result
        print(f"  [{'✓' if status == 'PASS' else '✗'}] {name}: {result}")
        if status == "PASS":
            passed += 1
        else:
            failed += 1
    print(f"\n{passed} PASS, {failed} FAIL")
    print()
    if failed > 0:
        print("⚠ Some tests FAILED — do NOT consider Staging accepted.")
    else:
        print("✓ All tests PASSED — Staging journey is verified.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
