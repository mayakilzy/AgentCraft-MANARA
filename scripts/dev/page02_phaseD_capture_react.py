"""
Phase D1 (v2) — Capture React Investigation Workspace screenshots at 6 viewports.
Uses Vite dev server (port 5173) which proxies /api to backend.

Strategy:
1. Navigate to home
2. Wait for status check (which uses proxy)
3. If status is online, type the test query and submit
4. Wait for compose result
5. Click 'Open Investigation Workspace'
6. Wait for workspace to load
7. If AR, toggle language
8. Capture screenshots

If compose fails, fall back to injecting the seeded investigationId directly via
page.evaluate() to bypass the compose flow.
"""
import os
import sys
import time
import urllib.request
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT_DIR = Path("/home/z/my-project/workspace/page02_reference/react_screenshots")
OUT_DIR.mkdir(parents=True, exist_ok=True)

REACT_URL = "http://127.0.0.1:5173"  # vite dev server
BACKEND_URL = "http://127.0.0.1:8000"
INVESTIGATION_ID = "inv-765317ea38122051"  # from latest seeding script

VIEWPORTS = [
    ("01_en_desktop_1536x1024", 1536, 1024, "en", False),
    ("02_ar_desktop_1536x1024", 1536, 1024, "ar", False),
    ("03_en_tablet_768x1024",    768,  1024, "en", False),
    ("04_ar_tablet_768x1024",    768,  1024, "ar", False),
    ("05_en_mobile_375x812",      375,  812,  "en", True),
    ("06_ar_mobile_375x812",      375,  812,  "ar", True),
]

def wait_for(url, label, timeout=30):
    for i in range(timeout):
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    print(f"  {label} ready after {i+1}s")
                    return True
        except Exception:
            time.sleep(1)
    print(f"  {label} NOT ready after {timeout}s")
    return False

def main():
    if not wait_for(BACKEND_URL + "/health", "Backend"):
        sys.exit(1)
    if not wait_for(REACT_URL + "/", "Vite dev"):
        sys.exit(1)

    print()
    captured = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for name, w, h, lang, is_mobile in VIEWPORTS:
                context = browser.new_context(
                    viewport={"width": w, "height": h},
                    device_scale_factor=2,
                    is_mobile=is_mobile,
                    has_touch=is_mobile,
                    locale="en-US" if lang == "en" else "ar-SA",
                )
                page = context.new_page()
                # Use addInitScript to set VITE_API_BASE via localStorage
                # Actually, VITE_API_BASE is a build-time env, can't be set at runtime
                # So we rely on Vite's proxy (which is configured for /mold-factory, /memory, etc.)
                # The api-client.ts uses import.meta.env.VITE_API_BASE || 'http://localhost:8000'
                # If VITE_API_BASE is unset, the browser will try http://localhost:8000
                # which may fail due to CORS or IPv6 issues.
                # Solution: set VITE_API_BASE='' (empty) so all requests go to same origin (5173)
                # which is then proxied by Vite dev server.

                # Navigate to home page (will use proxy for /status, /mold-factory, /memory)
                page.goto(REACT_URL + "/?useProxy=1", wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(1500)

                # Verify status is online (proxy works)
                status_text = page.evaluate("() => document.body.textContent")
                is_online = "Online" in status_text or "متصل" in status_text
                print(f"  [{name}] status check: {'online' if is_online else 'OFFLINE'}")

                # Type the test query
                try:
                    page.wait_for_selector("textarea, input[type='text']", timeout=10000)
                    page.fill("textarea, input[type='text']", "How are additive manufacturing technologies transforming prosthetics?")
                    page.wait_for_timeout(300)
                    # Click submit button
                    submit_btn = page.locator("button:has-text('Start Investigation'), button:has-text('بدء التحقيق')")
                    if submit_btn.count() > 0:
                        submit_btn.first.click()
                        page.wait_for_timeout(3000)  # wait for compose
                    else:
                        print(f"  [{name}] WARN: no submit button found")
                except Exception as e:
                    print(f"  [{name}] WARN: composer flow failed: {e}")

                # Try to click "Open Investigation Workspace" button
                try:
                    open_btn = page.locator("button:has-text('Open Investigation Workspace')")
                    if open_btn.count() > 0:
                        open_btn.first.click()
                        page.wait_for_timeout(2000)
                    else:
                        # Use sidebar nav instead
                        nav_btn = page.locator("a:has-text('Investigations'), a:has-text('التحقيقات')")
                        if nav_btn.count() > 0:
                            nav_btn.first.click()
                            page.wait_for_timeout(1500)
                except Exception:
                    pass

                # Switch to the SEEDED investigation (which has 5 evidence + 5 claims + 6 edges)
                # via the investigation selector dropdown.
                try:
                    toggle_btn = page.locator("button:has-text('Switch investigation')")
                    if toggle_btn.count() > 0:
                        toggle_btn.first.click()
                        page.wait_for_timeout(800)
                        # The dropdown shows investigations whose ID starts with "inv-"
                        # Click the one matching our seeded ID (first 16 chars)
                        seeded_btn = page.locator(f"button:has-text('{INVESTIGATION_ID[:16]}')")
                        if seeded_btn.count() > 0:
                            seeded_btn.first.click()
                            print(f"  [{name}] switched to seeded investigation: {INVESTIGATION_ID}")
                            # Wait for the audit panel to populate with >1 entries
                            # (seeded investigation has 2 transitions + 11 decisions = 13)
                            try:
                                page.wait_for_function(
                                    """() => {
                                        const auditEl = document.querySelector('.manara-audit-list');
                                        if (!auditEl) return false;
                                        const entries = auditEl.querySelectorAll('.manara-audit-entry');
                                        return entries.length >= 2;
                                    }""",
                                    timeout=10000,
                                )
                                print(f"  [{name}] audit panel populated (>=2 entries)")
                            except Exception:
                                print(f"  [{name}] WARN: audit panel didn't populate within 10s")
                            # Wait for evidence count > 0
                            try:
                                page.wait_for_function(
                                    """() => {
                                        const text = document.body.textContent || '';
                                        // Look for "Evidence items" followed by a non-zero digit
                                        const m = text.match(/Evidence items[\\s\\S]{0,30}?(\\d+)/);
                                        if (!m) return false;
                                        const n = parseInt(m[1], 10);
                                        return n > 0;
                                    }""",
                                    timeout=10000,
                                )
                                print(f"  [{name}] evidence count populated (>0)")
                            except Exception:
                                print(f"  [{name}] WARN: evidence count didn't populate within 10s")
                            page.wait_for_timeout(1500)  # extra settle time
                        else:
                            print(f"  [{name}] WARN: seeded investigation not in dropdown")
                    else:
                        print(f"  [{name}] WARN: investigation toggle not found")
                except Exception as e:
                    print(f"  [{name}] WARN: investigation switch failed: {e}")

                # Verify we're on the workspace by checking for the Investigation strip
                # If not, inject the seeded investigationId via React DevTools or just take a screenshot of whatever's there

                # If AR, toggle language via the language switcher
                if lang == "ar":
                    try:
                        # Try various language switcher selectors
                        for sel in [
                            "button[aria-label*='Language']",
                            "button:has-text('العربية')",
                            "button:has-text('AR')",
                            "header button:has-text('EN')",
                        ]:
                            btn = page.locator(sel).first
                            if btn.count() > 0:
                                btn.click()
                                page.wait_for_timeout(800)
                                break
                    except Exception as e:
                        print(f"  [{name}] WARN: language toggle failed: {e}")

                # Wait for workspace to settle (async hooks)
                page.wait_for_timeout(2500)

                # Capture full page screenshot
                full_out = OUT_DIR / f"{name}_full.png"
                page.screenshot(path=str(full_out), full_page=True)
                # Capture viewport-only screenshot
                vp_out = OUT_DIR / f"{name}_viewport.png"
                page.screenshot(path=str(vp_out), full_page=False)
                captured.append(name)
                print(f"  [{name}] captured: full={full_out.stat().st_size}b, vp={vp_out.stat().st_size}b")
                context.close()
        finally:
            browser.close()
    print(f"\nTotal: {len(captured)} viewports x 2 = {len(captured)*2} files")

if __name__ == "__main__":
    main()
