"""
Phase A4 — Capture standalone HTML reference screenshots at required viewports.
Starts its own HTTP server in-process, then uses Playwright.
"""
import os
import sys
import threading
import http.server
import socketserver
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path("/home/z/my-project/workspace/page03_reference/manara_page03_approved_source")
OUT_DIR = Path("/home/z/my-project/workspace/page03_reference/screenshots")
OUT_DIR.mkdir(parents=True, exist_ok=True)

Handler = http.server.SimpleHTTPRequestHandler
class QuietHandler(Handler):
    def log_message(self, *a, **kw): pass
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

PORT = 8766
httpd = None
def start_server():
    global httpd
    os.chdir(ROOT)
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), QuietHandler)
    httpd.serve_forever()

server_thread = threading.Thread(target=start_server, daemon=True)
server_thread.start()
time.sleep(1.0)
print(f"HTTP server started on 127.0.0.1:{PORT}", flush=True)

URL = f"http://127.0.0.1:{PORT}/index.html"

VIEWPORTS = [
    ("01_en_desktop_1536x1024", 1536, 1024, "en", False),
    ("02_ar_desktop_1536x1024", 1536, 1024, "ar", False),
    ("03_en_tablet_768x1024",    768,  1024, "en", False),
    ("04_ar_tablet_768x1024",    768,  1024, "ar", False),
    ("05_en_mobile_375x812",      375,  812,  "en", True),
    ("06_ar_mobile_375x812",      375,  812,  "ar", True),
]

def main():
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
                page.goto(URL, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(1200)  # let fonts load
                if lang == "ar":
                    page.click("#ar")
                    page.wait_for_timeout(500)
                full_out = OUT_DIR / f"{name}_full.png"
                page.screenshot(path=str(full_out), full_page=True)
                vp_out = OUT_DIR / f"{name}_viewport.png"
                page.screenshot(path=str(vp_out), full_page=False)
                captured.append(name)
                print(f"  captured: {name} (full={full_out.stat().st_size}b, vp={vp_out.stat().st_size}b)", flush=True)
                context.close()
        finally:
            browser.close()
    print(f"\nTotal: {len(captured)} viewports x 2 = {len(captured)*2} files", flush=True)

if __name__ == "__main__":
    main()
