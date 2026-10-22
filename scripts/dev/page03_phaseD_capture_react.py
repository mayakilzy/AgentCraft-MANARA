"""
Phase D3 (v3) — Capture React Memory Explorer screenshots.
Correct selectors for the actual Sidebar text labels.
"""
import os, sys, time, urllib.request, json
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT_DIR = Path("/home/z/my-project/workspace/page03_reference/react_screenshots")
OUT_DIR.mkdir(parents=True, exist_ok=True)

REACT_URL = "http://127.0.0.1:5173"
BACKEND_URL = "http://127.0.0.1:8000"
INVESTIGATION_ID = open("/home/z/my-project/scripts/.dev_investigation_id").read().strip()

VIEWPORTS = [
    ("01_en_desktop_1536x1024", 1536, 1024, "en", False),
    ("02_ar_desktop_1536x1024", 1536, 1024, "ar", False),
    ("03_en_mobile_375x812",     375,  812,  "en", True),
    ("04_ar_mobile_375x812",     375,  812,  "ar", True),
    ("05_ar_tablet_768x1024",    768,  1024, "ar", False),
]

def wait_for(url, label, timeout=30):
    for i in range(timeout):
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200: return True
        except: time.sleep(1)
    return False

def click_if_exists(page, selector, timeout=5000):
    """Click an element if it exists, using force=True to bypass visibility checks."""
    loc = page.locator(selector)
    if loc.count() > 0:
        loc.first.click(force=True, timeout=timeout)
        return True
    return False

def main():
    if not wait_for(BACKEND_URL + "/health", "Backend"): sys.exit(1)
    if not wait_for(REACT_URL + "/", "Vite dev"): sys.exit(1)
    print(f"Seeded investigation: {INVESTIGATION_ID}")

    captured = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for name, w, h, lang, is_mobile in VIEWPORTS:
            ctx = browser.new_context(
                viewport={"width": w, "height": h},
                device_scale_factor=2,
                is_mobile=is_mobile,
                has_touch=is_mobile,
                locale="en-US" if lang == "en" else "ar-SA",
            )
            page = ctx.new_page()
            try:
                page.goto(REACT_URL, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Step 1: Fill textarea + compose
                page.wait_for_selector("textarea", timeout=10000)
                page.fill("textarea", "How are additive manufacturing technologies transforming prosthetics?")
                page.wait_for_timeout(500)
                page.locator("button:has-text('Start Investigation')").click(force=True, timeout=10000)
                page.wait_for_selector("text=Investigation ID", timeout=60000)
                page.wait_for_timeout(1000)

                # Step 2: Click "Open Investigation Workspace" button
                click_if_exists(page, "button:has-text('Open Investigation Workspace')")
                page.wait_for_timeout(1500)

                # Step 3: Switch to seeded investigation
                click_if_exists(page, "button:has-text('Switch investigation')")
                page.wait_for_timeout(500)
                click_if_exists(page, f"button:has-text('{INVESTIGATION_ID[:16]}')")
                page.wait_for_timeout(2000)

                # Step 4: Navigate to Memory Explorer via sidebar
                # On mobile, open the hamburger menu first using JS (bypasses visibility checks)
                if is_mobile:
                    page.evaluate("""() => {
                        const menuBtn = document.querySelector('button[aria-label="Menu"]') ||
                                        document.querySelector('button[aria-label="القائمة"]');
                        if (menuBtn) menuBtn.click();
                    }""")
                    page.wait_for_timeout(1000)

                # Click "Memory Explorer" sidebar nav item
                # Use JS click for reliability (bypasses Playwright visibility checks)
                page.evaluate("""() => {
                    const links = document.querySelectorAll('a');
                    for (const link of links) {
                        if (link.textContent.includes('Memory Explorer') ||
                            link.textContent.includes('مستكشف الذاكرة')) {
                            link.click();
                            break;
                        }
                    }
                }""")
                page.wait_for_timeout(3000)

                # Step 5: If AR, toggle language
                if lang == "ar":
                    for sel in ["button:has-text('العربية')", "button[aria-label*='Language']",
                                "button:has-text('AR')", "header button:has-text('EN')"]:
                        loc = page.locator(sel)
                        if loc.count() > 0:
                            loc.first.click(force=True, timeout=5000)
                            page.wait_for_timeout(1000)
                            break

                page.wait_for_timeout(2000)

                # Capture
                full_out = OUT_DIR / f"{name}_full.png"
                page.screenshot(path=str(full_out), full_page=True)
                vp_out = OUT_DIR / f"{name}_viewport.png"
                page.screenshot(path=str(vp_out), full_page=False)
                captured.append(name)
                print(f"  ✓ captured: {name} (full={full_out.stat().st_size}b)")
            except Exception as e:
                print(f"  ✗ FAILED: {name} — {str(e)[:200]}")
                try:
                    page.screenshot(path=str(OUT_DIR / f"{name}_error.png"), full_page=True)
                except: pass
            finally:
                ctx.close()
        browser.close()
    print(f"\nTotal: {len(captured)} viewports captured")

if __name__ == "__main__":
    main()
