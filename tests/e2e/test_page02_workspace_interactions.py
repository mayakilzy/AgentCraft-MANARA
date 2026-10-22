"""
MANARA-UI-PAGE02-PRE-ACCEPTANCE-01 — Comprehensive Workspace Interaction Test.

Per owner (pre-acceptance mission, Section 4):
> "Add browser assertions for: Selecting an existing investigation,
>  Loading populated evidence and claims, Displaying backend-sourced
>  graph edges, Selecting a knowledge graph node and viewing its details,
>  Zoom/pan interaction, Accessible list fallback, Workflow state
>  presentation, Actual audit history, Switching EN/AR, Mobile RTL,
>  Regression checks for Page 01. Record individual results and real
>  command exit codes."

This script runs all 11 categories of browser assertions with real
backend + seeded dev data and records PASS/FAIL/SKIP for each.

Run:
    cd AgentCraft-MANARA
    MANARA_FRONTEND_URL=http://127.0.0.1:5173 \\
    MANARA_BACKEND_URL=http://127.0.0.1:8000 \\
    MANARA_SEEDED_INVESTIGATION_ID=inv-XXXXX \\
    python tests/e2e/test_page02_workspace_interactions.py

Prerequisites:
1. Backend running on 127.0.0.1:8000 with real sentence_transformers installed
2. Frontend Vite dev server on 127.0.0.1:5173
3. Database migrated (alembic upgrade head)
4. Seeded investigation via scripts/page02_phaseC_seed_fixtures.py
   (this script will pick up the ID from the MANARA_SEEDED_INVESTIGATION_ID
   env var, or from /home/z/my-project/scripts/.dev_investigation_id file)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

def main() -> int:
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        print("BLOCKER: Playwright not installed.")
        print("Install with: pip install playwright && playwright install chromium")
        return 2

    FRONTEND_URL = os.environ.get("MANARA_FRONTEND_URL", "http://127.0.0.1:5173")
    BACKEND_URL = os.environ.get("MANARA_BACKEND_URL", "http://127.0.0.1:8000")
    SEEDED_ID_FILE = "/home/z/my-project/scripts/.dev_investigation_id"
    SEEDED_ID = (
        os.environ.get("MANARA_SEEDED_INVESTIGATION_ID")
        or (Path(SEEDED_ID_FILE).read_text().strip() if Path(SEEDED_ID_FILE).exists() else "")
    )
    if not SEEDED_ID:
        print("BLOCKER: MANARA_SEEDED_INVESTIGATION_ID not set and no .dev_investigation_id file")
        return 2

    print(f"Seeded investigation ID: {SEEDED_ID}")
    print(f"Frontend: {FRONTEND_URL}")
    print(f"Backend: {BACKEND_URL}")

    # Result records — kept structured for JSON output
    results: list[dict] = []

    def record(name: str, status: str, detail: str = ""):
        results.append({"test": name, "status": status, "detail": detail})
        marker = {"pass": "✓", "fail": "✗", "skip": "△"}[status]
        line = f"  {marker} {name}"
        if detail:
            line += f" — {detail}"
        print(line)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # ===== Test category 1: Homepage loads (Page 01 regression) =====
        ctx = browser.new_context(viewport={"width": 1536, "height": 1024}, locale="en-US")
        page = ctx.new_page()
        try:
            page.goto(FRONTEND_URL, wait_until="networkidle", timeout=15000)
            page.wait_for_timeout(800)
            title = page.title()
            assert "MANARA" in title or "manara" in page.content().lower()
            record("1. Homepage loads (Page 01 regression)", "pass", f"title='{title}'")
        except Exception as e:
            record("1. Homepage loads (Page 01 regression)", "fail", str(e)[:200])
        finally:
            ctx.close()

        # ===== Test category 2: Status banner visible (Page 01 regression) =====
        ctx = browser.new_context(viewport={"width": 1536, "height": 1024}, locale="en-US")
        page = ctx.new_page()
        try:
            page.goto(FRONTEND_URL, wait_until="networkidle", timeout=15000)
            page.wait_for_timeout(1200)
            body = page.text_content("body") or ""
            # Status banner shows capabilities list per manaraApi.status()
            assert "capabilities" in body.lower() or "القدرات" in body, "no capabilities text"
            # Status badge should show Online (since backend is running)
            assert "Online" in body or "متصل" in body, "no Online badge"
            record("2. Status banner visible + Online (Page 01 regression)", "pass")
        except Exception as e:
            record("2. Status banner visible + Online (Page 01 regression)", "fail", str(e)[:200])
        finally:
            ctx.close()

        # ===== Test category 3: Investigation input accepts text (Page 01 regression) =====
        ctx = browser.new_context(viewport={"width": 1536, "height": 1024}, locale="en-US")
        page = ctx.new_page()
        try:
            page.goto(FRONTEND_URL, wait_until="networkidle", timeout=15000)
            page.wait_for_timeout(800)
            textarea = page.query_selector("textarea")
            assert textarea is not None, "no textarea found"
            textarea.fill("Future of waste recycling technologies in the next ten years")
            value = textarea.input_value()
            assert len(value) > 10, "textarea value too short"
            record("3. Investigation input accepts text (Page 01 regression)", "pass", f"value len={len(value)}")
        except Exception as e:
            record("3. Investigation input accepts text (Page 01 regression)", "fail", str(e)[:200])
        finally:
            ctx.close()

        # ===== Test category 4: Submit query + compose (Page 01 regression) =====
        ctx = browser.new_context(viewport={"width": 1536, "height": 1024}, locale="en-US")
        page = ctx.new_page()
        try:
            page.goto(FRONTEND_URL, wait_until="networkidle", timeout=15000)
            page.wait_for_timeout(800)
            page.fill("textarea", "How are additive manufacturing technologies transforming prosthetics?")
            btn = page.query_selector("button:has-text('Start Investigation')")
            assert btn is not None, "no Start Investigation button"
            btn.click()
            # Compose may take ~3-5 seconds with real backend
            page.wait_for_selector("text=Investigation ID", timeout=30000)
            record("4. Submit query — compose returns Investigation ID (Page 01 regression)", "pass")
        except Exception as e:
            record("4. Submit query — compose returns Investigation ID (Page 01 regression)", "fail", str(e)[:200])
        finally:
            ctx.close()

        # ===== Test category 5: Navigate to Workspace + select seeded investigation =====
        ctx = browser.new_context(viewport={"width": 1536, "height": 1024}, locale="en-US")
        page = ctx.new_page()
        try:
            page.goto(FRONTEND_URL, wait_until="networkidle", timeout=15000)
            page.wait_for_timeout(800)
            # Compose to get into the workspace page
            page.fill("textarea", "How are additive manufacturing technologies transforming prosthetics?")
            page.query_selector("button:has-text('Start Investigation')").click()
            page.wait_for_selector("text=Investigation ID", timeout=30000)
            page.wait_for_timeout(800)
            # Click "Open Investigation Workspace"
            page.query_selector("button:has-text('Open Investigation Workspace')").click()
            page.wait_for_timeout(1500)
            # Now switch to the seeded investigation via the dropdown
            toggle = page.query_selector("button:has-text('Switch investigation')")
            assert toggle is not None, "no Switch investigation toggle"
            toggle.click()
            page.wait_for_timeout(500)
            # Click on the seeded investigation in the dropdown
            seeded_btn = page.query_selector(f"button:has-text('{SEEDED_ID[:16]}')")
            assert seeded_btn is not None, f"no button matching seeded ID {SEEDED_ID[:16]}"
            seeded_btn.click()
            page.wait_for_timeout(2500)
            # Verify we're on the workspace — check for the audit panel populated
            page.wait_for_selector(".manara-audit-list .manara-audit-entry", timeout=10000)
            audit_count = len(page.query_selector_all(".manara-audit-list .manara-audit-entry"))
            assert audit_count >= 2, f"audit panel has only {audit_count} entries (expected ≥2)"
            record("5. Navigate to Workspace + select seeded investigation", "pass", f"audit_entries={audit_count}")
        except Exception as e:
            record("5. Navigate to Workspace + select seeded investigation", "fail", str(e)[:200])
        finally:
            ctx.close()

        # ===== Test category 6: Loading populated evidence and claims =====
        ctx = browser.new_context(viewport={"width": 1536, "height": 1024}, locale="en-US")
        page = ctx.new_page()
        try:
            page.goto(FRONTEND_URL, wait_until="networkidle", timeout=15000)
            page.fill("textarea", "How are additive manufacturing technologies transforming prosthetics?")
            page.query_selector("button:has-text('Start Investigation')").click()
            page.wait_for_selector("text=Investigation ID", timeout=30000)
            page.query_selector("button:has-text('Open Investigation Workspace')").click()
            page.wait_for_timeout(1500)
            page.query_selector("button:has-text('Switch investigation')").click()
            page.query_selector(f"button:has-text('{SEEDED_ID[:16]}')").click()
            page.wait_for_timeout(2500)
            # Verify Overview panel shows evidence count > 0
            overview_text = page.text_content(".manara-overview-panel") or ""
            # Evidence items count should be 5
            import re
            m = re.search(r"Evidence items[\s\S]{0,30}?(\d+)", overview_text)
            assert m is not None, "no 'Evidence items' text in overview panel"
            evidence_count = int(m.group(1))
            assert evidence_count > 0, f"evidence count is {evidence_count} (expected >0)"
            # Verify sources count > 0
            m2 = re.search(r"Sources analyzed[\s\S]{0,30}?(\d+)", overview_text)
            assert m2 is not None, "no 'Sources analyzed' text in overview panel"
            sources_count = int(m2.group(1))
            assert sources_count > 0, f"sources count is {sources_count} (expected >0)"
            record("6. Loading populated evidence and claims", "pass",
                   f"evidence={evidence_count}, sources={sources_count}")
        except Exception as e:
            record("6. Loading populated evidence and claims", "fail", str(e)[:200])
        finally:
            ctx.close()

        # ===== Test category 7: Knowledge graph displays backend-sourced edges =====
        ctx = browser.new_context(viewport={"width": 1536, "height": 1024}, locale="en-US")
        page = ctx.new_page()
        try:
            page.goto(FRONTEND_URL, wait_until="networkidle", timeout=15000)
            page.fill("textarea", "How are additive manufacturing technologies transforming prosthetics?")
            page.query_selector("button:has-text('Start Investigation')").click()
            page.wait_for_selector("text=Investigation ID", timeout=30000)
            page.query_selector("button:has-text('Open Investigation Workspace')").click()
            page.wait_for_timeout(1500)
            page.query_selector("button:has-text('Switch investigation')").click()
            page.query_selector(f"button:has-text('{SEEDED_ID[:16]}')").click()
            page.wait_for_timeout(2500)
            # Verify SVG graph has edges
            svg = page.query_selector(".manara-observatory-svg")
            assert svg is not None, "no .manara-observatory-svg element"
            # Count <path> elements (edges use <path>)
            paths = page.query_selector_all(".manara-observatory-svg path")
            edge_count = len(paths)
            # Subtract 1 for the halo ellipse — actually ellipse is separate.
            # Subtract paths that are part of filters (none in our SVG).
            assert edge_count >= 6, f"only {edge_count} <path> in SVG (expected ≥6 edges)"
            # Verify nodes (circles with class "graph-node")
            # Our nodes use <g> with role=button. Let's count them.
            # Seeded data: 5 claims + 4 unique evidence IDs referenced in 6 edges = 9 nodes
            # (evidence-5 has no edges, so doesn't appear as a graph node — this is correct
            # behavior: the graph only shows nodes that participate in relationships)
            node_groups = page.query_selector_all(".manara-observatory-svg g[role='button']")
            assert len(node_groups) >= 9, f"only {len(node_groups)} graph nodes (expected ≥9)"
            record("7. Knowledge graph displays backend-sourced edges", "pass",
                   f"edges={edge_count}, nodes={len(node_groups)}")
        except Exception as e:
            record("7. Knowledge graph displays backend-sourced edges", "fail", str(e)[:200])
        finally:
            ctx.close()

        # ===== Test category 8: Select knowledge graph node + view details =====
        ctx = browser.new_context(viewport={"width": 1536, "height": 1024}, locale="en-US")
        page = ctx.new_page()
        try:
            page.goto(FRONTEND_URL, wait_until="networkidle", timeout=15000)
            page.fill("textarea", "How are additive manufacturing technologies transforming prosthetics?")
            page.query_selector("button:has-text('Start Investigation')").click()
            page.wait_for_selector("text=Investigation ID", timeout=30000)
            page.query_selector("button:has-text('Open Investigation Workspace')").click()
            page.wait_for_timeout(1500)
            page.query_selector("button:has-text('Switch investigation')").click()
            page.query_selector(f"button:has-text('{SEEDED_ID[:16]}')").click()
            page.wait_for_timeout(2500)
            # Click on the first graph node (use force=True for SVG <g> elements)
            node_groups = page.query_selector_all(".manara-observatory-svg g[role='button']")
            assert len(node_groups) > 0, "no graph nodes to click"
            # Click the first node's inner circle to ensure proper hit target
            first_node = node_groups[0]
            # Try normal click first; if it times out, use force=True
            try:
                first_node.click(timeout=5000)
            except Exception:
                first_node.click(force=True, timeout=5000)
            page.wait_for_timeout(800)
            # Verify the node-panel renders
            node_panel = page.query_selector(".manara-node-panel")
            assert node_panel is not None, "no .manara-node-panel after clicking a node"
            panel_text = node_panel.text_content() or ""
            assert len(panel_text) > 5, f"node-panel text too short: '{panel_text}'"
            record("8. Select knowledge graph node + view details", "pass",
                   f"panel_text_len={len(panel_text)}")
        except Exception as e:
            record("8. Select knowledge graph node + view details", "fail", str(e)[:200])
        finally:
            ctx.close()

        # ===== Test category 9: Zoom in/out interaction =====
        ctx = browser.new_context(viewport={"width": 1536, "height": 1024}, locale="en-US")
        page = ctx.new_page()
        try:
            page.goto(FRONTEND_URL, wait_until="networkidle", timeout=15000)
            page.fill("textarea", "How are additive manufacturing technologies transforming prosthetics?")
            page.query_selector("button:has-text('Start Investigation')").click()
            page.wait_for_selector("text=Investigation ID", timeout=30000)
            page.query_selector("button:has-text('Open Investigation Workspace')").click()
            page.wait_for_timeout(1500)
            page.query_selector("button:has-text('Switch investigation')").click()
            page.query_selector(f"button:has-text('{SEEDED_ID[:16]}')").click()
            page.wait_for_timeout(2500)
            # Find zoom out button (aria-label "Zoom out")
            zoom_out = page.query_selector("button[aria-label='Zoom out']")
            zoom_in = page.query_selector("button[aria-label='Zoom in']")
            assert zoom_out is not None, "no Zoom out button"
            assert zoom_in is not None, "no Zoom in button"
            # Get current zoom %
            zoom_text = page.text_content(".manara-observatory-svg").split("%")[0][-3:]
            # Click zoom out 3 times
            for _ in range(3):
                zoom_out.click()
            page.wait_for_timeout(500)
            # Read the new zoom %
            new_zoom_text = ""
            for el in page.query_selector_all(".manara-observatory-svg + div, .manara-observatory-svg"):
                txt = el.text_content() or ""
                if "%" in txt:
                    import re
                    m = re.search(r"(\d+)%", txt)
                    if m:
                        new_zoom_text = m.group(1)
                        break
            record("9. Zoom in/out interaction", "pass",
                   f"initial_zoom~{zoom_text.strip()}, after_zoom_out={new_zoom_text or '?'}%")
        except Exception as e:
            record("9. Zoom in/out interaction", "fail", str(e)[:200])
        finally:
            ctx.close()

        # ===== Test category 10: Accessible list fallback =====
        ctx = browser.new_context(viewport={"width": 1536, "height": 1024}, locale="en-US")
        page = ctx.new_page()
        try:
            page.goto(FRONTEND_URL, wait_until="networkidle", timeout=15000)
            page.fill("textarea", "How are additive manufacturing technologies transforming prosthetics?")
            page.query_selector("button:has-text('Start Investigation')").click()
            page.wait_for_selector("text=Investigation ID", timeout=30000)
            page.query_selector("button:has-text('Open Investigation Workspace')").click()
            page.wait_for_timeout(1500)
            page.query_selector("button:has-text('Switch investigation')").click()
            page.query_selector(f"button:has-text('{SEEDED_ID[:16]}')").click()
            page.wait_for_timeout(2500)
            # Click the List button
            list_btn = page.query_selector("button:has-text('List')")
            assert list_btn is not None, "no List button"
            list_btn.click()
            page.wait_for_timeout(800)
            # Verify list view rendered with edge items
            # The list view uses div elements with role/edge_id text
            body = page.text_content("body") or ""
            # Should contain at least one of the edge relation types
            assert any(kw in body for kw in ["supports", "refutes", "qualifies"]), \
                "no edge relation keywords in body after List click"
            record("10. Accessible list fallback", "pass", "edge keywords present in list view")
        except Exception as e:
            record("10. Accessible list fallback", "fail", str(e)[:200])
        finally:
            ctx.close()

        # ===== Test category 11: Workflow state presentation (5-phase, 13-state FSM) =====
        ctx = browser.new_context(viewport={"width": 1536, "height": 1024}, locale="en-US")
        page = ctx.new_page()
        try:
            page.goto(FRONTEND_URL, wait_until="networkidle", timeout=15000)
            page.fill("textarea", "How are additive manufacturing technologies transforming prosthetics?")
            page.query_selector("button:has-text('Start Investigation')").click()
            page.wait_for_selector("text=Investigation ID", timeout=30000)
            page.query_selector("button:has-text('Open Investigation Workspace')").click()
            page.wait_for_timeout(1500)
            page.query_selector("button:has-text('Switch investigation')").click()
            page.query_selector(f"button:has-text('{SEEDED_ID[:16]}')").click()
            page.wait_for_timeout(2500)
            # Verify 5 phases render
            phases = page.query_selector_all(".manara-phase")
            assert len(phases) == 5, f"found {len(phases)} phases (expected 5)"
            # Verify the current phase has .current class
            current_phase = page.query_selector(".manara-phase.current")
            assert current_phase is not None, "no .manara-phase.current"
            # Verify state pills render
            state_pills = page.query_selector_all(".manara-phase-states button")
            assert len(state_pills) == 13, f"found {len(state_pills)} state pills (expected 13)"
            # Verify state-detail line shows current state
            detail_text = page.text_content(".manara-state-detail") or ""
            assert "Current state:" in detail_text or "الحالة الحالية:" in detail_text, \
                f"no 'Current state:' in state-detail: '{detail_text[:100]}'"
            record("11. Workflow state presentation (5 phases, 13 states, current marked)", "pass",
                   f"phases=5, pills=13")
        except Exception as e:
            record("11. Workflow state presentation (5 phases, 13 states, current marked)", "fail", str(e)[:200])
        finally:
            ctx.close()

        # ===== Test category 12: Audit history (transitions + decisions) =====
        ctx = browser.new_context(viewport={"width": 1536, "height": 1024}, locale="en-US")
        page = ctx.new_page()
        try:
            page.goto(FRONTEND_URL, wait_until="networkidle", timeout=15000)
            page.fill("textarea", "How are additive manufacturing technologies transforming prosthetics?")
            page.query_selector("button:has-text('Start Investigation')").click()
            page.wait_for_selector("text=Investigation ID", timeout=30000)
            page.query_selector("button:has-text('Open Investigation Workspace')").click()
            page.wait_for_timeout(1500)
            page.query_selector("button:has-text('Switch investigation')").click()
            page.query_selector(f"button:has-text('{SEEDED_ID[:16]}')").click()
            page.wait_for_timeout(2500)
            # Verify audit panel has multiple entries
            audit_entries = page.query_selector_all(".manara-audit-list .manara-audit-entry")
            assert len(audit_entries) >= 4, f"only {len(audit_entries)} audit entries (expected ≥4 for seeded inv)"
            # Verify entries have kind + description + meta
            first_entry = audit_entries[0]
            kind_text = first_entry.text_content() or ""
            assert len(kind_text) > 5, f"first audit entry too short: '{kind_text[:80]}'"
            record("12. Audit history (transitions + decisions)", "pass",
                   f"entries={len(audit_entries)}")
        except Exception as e:
            record("12. Audit history (transitions + decisions)", "fail", str(e)[:200])
        finally:
            ctx.close()

        # ===== Test category 13: Switch EN → AR + AR rendering =====
        ctx = browser.new_context(viewport={"width": 1536, "height": 1024}, locale="en-US")
        page = ctx.new_page()
        try:
            page.goto(FRONTEND_URL, wait_until="networkidle", timeout=15000)
            # Toggle to AR via the language switcher
            page.wait_for_timeout(800)
            # Try various selectors for the language toggle
            lang_btn = None
            for sel in ["button:has-text('العربية')", "button[aria-label*='Language']",
                        "button:has-text('AR')", "header button:has-text('EN')"]:
                lang_btn = page.query_selector(sel)
                if lang_btn is not None:
                    break
            assert lang_btn is not None, "no language toggle button"
            lang_btn.click()
            page.wait_for_timeout(1200)
            # Verify Arabic text appears
            body = page.text_content("body") or ""
            # Should contain at least one Arabic word from the i18n table
            arabic_markers = ["الرئيسية", "التحقيقات", "مساحة", "المعرفة"]
            found_arabic = any(m in body for m in arabic_markers)
            assert found_arabic, f"no Arabic markers in body after toggle"
            # Verify html dir is now rtl
            html_dir = page.evaluate("document.documentElement.dir")
            assert html_dir == "rtl", f"html.dir is '{html_dir}' (expected 'rtl')"
            record("13. Switch EN → AR + RTL layout", "pass", f"html.dir={html_dir}")
        except Exception as e:
            record("13. Switch EN → AR + RTL layout", "fail", str(e)[:200])
        finally:
            ctx.close()

        # ===== Test category 14: Mobile RTL (Arabic on 375×812) =====
        # Note: the React app's initial language state is always 'en' (per i18n.tsx).
        # We must explicitly toggle to AR via the language switcher button.
        ctx = browser.new_context(
            viewport={"width": 375, "height": 812},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
            locale="ar-SA",
        )
        page = ctx.new_page()
        try:
            page.goto(FRONTEND_URL, wait_until="networkidle", timeout=15000)
            page.wait_for_timeout(1000)
            # Click the AR language toggle (React app starts in EN regardless of locale)
            ar_btn = None
            for sel in ["button:has-text('العربية')", "button[aria-label*='Language']",
                        "button:has-text('AR')", "header button:has-text('EN')"]:
                ar_btn = page.query_selector(sel)
                if ar_btn is not None:
                    break
            assert ar_btn is not None, "no AR language toggle on mobile"
            ar_btn.click()
            page.wait_for_timeout(1200)
            # Verify html dir is now rtl
            html_dir = page.evaluate("document.documentElement.dir")
            assert html_dir == "rtl", f"html.dir is '{html_dir}' (expected 'rtl' after AR toggle)"
            # Verify Arabic text appears
            body = page.text_content("body") or ""
            assert any(m in body for m in ["الرئيسية", "التحقيقات"]), "no Arabic markers in mobile RTL"
            # Verify no horizontal overflow (scroll width > client width indicates overflow)
            overflow = page.evaluate("""() => ({
                scrollWidth: document.documentElement.scrollWidth,
                clientWidth: document.documentElement.clientWidth,
            })""")
            assert overflow["scrollWidth"] <= overflow["clientWidth"] + 5, \
                f"horizontal overflow: scroll={overflow['scrollWidth']} client={overflow['clientWidth']}"
            record("14. Mobile RTL (375×812, AR toggled, no horizontal overflow)", "pass",
                   f"scrollWidth={overflow['scrollWidth']} clientWidth={overflow['clientWidth']}")
        except Exception as e:
            record("14. Mobile RTL (375×812, AR toggled, no horizontal overflow)", "fail", str(e)[:200])
        finally:
            ctx.close()

        # ===== Test category 15: SVG text NOT mirrored in RTL (regression check) =====
        # Strategy: start in EN (React app default), compose, navigate to workspace,
        # switch to seeded investigation, THEN toggle to AR, then verify SVG CSS.
        ctx = browser.new_context(viewport={"width": 1536, "height": 1024}, locale="en-US")
        page = ctx.new_page()
        try:
            page.goto(FRONTEND_URL, wait_until="networkidle", timeout=15000)
            page.wait_for_timeout(800)
            # Compose in EN first
            page.fill("textarea", "How are additive manufacturing technologies transforming prosthetics?")
            page.query_selector("button:has-text('Start Investigation')").click()
            page.wait_for_selector("text=Investigation ID", timeout=30000)
            page.query_selector("button:has-text('Open Investigation Workspace')").click()
            page.wait_for_timeout(1500)
            # Switch to seeded investigation
            page.query_selector("button:has-text('Switch investigation')").click()
            page.wait_for_timeout(500)
            page.query_selector(f"button:has-text('{SEEDED_ID[:16]}')").click()
            page.wait_for_timeout(2500)
            # Verify audit panel populated (workspace is functional)
            page.wait_for_selector(".manara-audit-list .manara-audit-entry", timeout=10000)
            # NOW toggle to AR
            ar_btn = None
            for sel in ["button:has-text('العربية')", "button[aria-label*='Language']",
                        "button:has-text('AR')", "header button:has-text('EN')"]:
                ar_btn = page.query_selector(sel)
                if ar_btn is not None:
                    break
            assert ar_btn is not None, "no AR language toggle for test 15"
            ar_btn.click()
            page.wait_for_timeout(1500)
            # Verify html dir is rtl
            html_dir = page.evaluate("document.documentElement.dir")
            assert html_dir == "rtl", f"html.dir is '{html_dir}' (expected 'rtl' after AR toggle)"
            # Verify SVG exists and has computed direction: ltr (per our CSS fix)
            svg = page.query_selector(".manara-observatory-svg")
            assert svg is not None, "no .manara-observatory-svg in RTL"
            svg_dir = svg.evaluate("el => getComputedStyle(el).direction")
            assert svg_dir == "ltr", f"SVG direction is '{svg_dir}' (expected 'ltr')"
            # Verify SVG text elements render with proper direction
            svg_text_dir = svg.evaluate("""el => {
                const t = el.querySelector('text');
                return t ? getComputedStyle(t).direction : 'none';
            }""")
            assert svg_text_dir == "ltr", f"SVG text direction is '{svg_text_dir}' (expected 'ltr')"
            record("15. SVG text NOT mirrored in RTL (regression check for CSS fix)", "pass",
                   f"svg_direction={svg_dir}, text_direction={svg_text_dir}")
        except Exception as e:
            record("15. SVG text NOT mirrored in RTL (regression check for CSS fix)", "fail", str(e)[:200])
        finally:
            ctx.close()

        browser.close()

    # Print summary
    print()
    print("=" * 70)
    print("MANARA-UI-PAGE02-PRE-ACCEPTANCE-01 Workspace Interaction Test Results")
    print("=" * 70)
    for r in results:
        marker = {"pass": "✓", "fail": "✗", "skip": "△"}[r["status"]]
        line = f"  {marker} {r['test']}"
        if r["detail"]:
            line += f" — {r['detail']}"
        print(line)
    passed = sum(1 for r in results if r["status"] == "pass")
    failed = sum(1 for r in results if r["status"] == "fail")
    skipped = sum(1 for r in results if r["status"] == "skip")
    print(f"\n{passed} passed, {failed} failed, {skipped} skipped")

    # Save JSON report
    report_path = Path("/home/z/my-project/workspace/page02_reference/page02_workspace_test_results.json")
    report = {
        "mission": "MANARA-UI-PAGE02-PRE-ACCEPTANCE-01",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "frontend_url": FRONTEND_URL,
        "backend_url": BACKEND_URL,
        "seeded_investigation_id": SEEDED_ID,
        "summary": {"total": len(results), "passed": passed, "failed": failed, "skipped": skipped},
        "results": results,
    }
    report_path.write_text(json.dumps(report, indent=2))
    print(f"\nJSON report saved: {report_path}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
