# Page 02 Reference Validation — `MANARA-UI-PAGE02-SOURCE-INTEGRATION-01`

**Phase:** A — Reference Inspection
**Mission:** `MANARA-UI-PAGE02-SOURCE-INTEGRATION-01`
**Date:** 2026-10-22
**Investigator:** GLM (MANARA Dev)
**Source package:** `MANARA_PAGE_02_HTML_CSS_SOURCE_v1.zip` (immutable commit `697e711a9af2d502a5b21b8dfd33249679df0188` on `repo-info`)

---

## 1. Package Integrity Verification

| Check | Expected | Computed | Result |
|---|---|---|---|
| Git blob SHA | `39a7b95dbd1d011b8fecebefc399a2a609c2f476` | `39a7b95dbd1d011b8fecebefc399a2a609c2f476` | ✅ MATCH |
| File size | 4,704,445 bytes | 4,704,445 bytes | ✅ MATCH |
| ZIP integrity (entries) | 7 | 7 | ✅ MATCH |
| Internal layout | README.md, index.html, styles.css, script.js, assets/ (3 PNG) | README.md (4657B), index.html (11774B), styles.css (13845B), script.js (9588B), assets/approved-workspace.png (1667963B), assets/workspace-supporting-01.png (1635845B), assets/workspace-supporting-02.png (1802753B) | ✅ MATCH |

**Conclusion:** The package is intact, unmodified, and identical to the immutable documentation commit.

---

## 2. Reference File Inspection

### 2.1 `README.md`
The README explicitly declares:
- The package is a **supervisor-produced visual reference**, NOT yet owner-accepted.
- It is **not** the existing React app and does **not** provide real API data.
- The canonical binding master is `assets/approved-workspace.png`.
- Critical integration rules (9 items) are listed — key ones:
  1. Do not iframe or overlay live controls on a screenshot. Port DOM/SVG/CSS to React.
  2. Replace every sample record with **real supported data**, or an honest empty/loading/error state. All sample records are illustrative.
  3. The 13 real FSM states are grouped into five visual phases (Discovery, Build, Acquire, Synthesize, Deliver). Actual states and timestamps must come from the existing workflow API. Do not model transitions by clicking demo state pills.
  4. Graph must use real claim/evidence/source associations. Preserve Observatory visual appearance; use graph library only as implementation mechanism.
  5. Do not fabricate Edit Question, Pause, Share, Export.
  6. Source-provider cards are layout examples, not declarations of integration. Do not fabricate arXiv/PubMed/OpenAlex/Crossref source counts.
  7. Preserve the existing Page 01 shared shell; do not regress already-accepted shell.
  8. Render only what backend supports for audit/bitemporal. No arbitrary caps or fictitious percentages.
  9. Test viewports: 1536×1024 (EN + AR desktop), 768×1024 (tablet), 375×812 (mobile EN + AR).

The README also lists **Known reference differences from original screenshot** (5 items), all of which are intentional and documented:
- Original shows 7 process illustration stages; reference shows all 13 real states grouped in 5 phases per OPEN-01.
- Original has a cinematic globe-like celestial graph; reference uses editable CSS/SVG celestial flow.
- Original has counts/progress values; reference replaces with explicit sample labels.
- Icons here use local glyphs; GLM may substitute visually equivalent accessible icons.
- Original includes unsupported features; here they are omitted or described in README.

### 2.2 `index.html`
Standalone semantic layout, no build step required. Structure:
- App shell: grid `248px | minmax(0,1fr)` — sidebar + content-shell.
- Sidebar (light): brand tower (♜), nav with 9 items under 2 headings (KNOWLEDGE & ANALYSIS, FACTORY MANAGEMENT), sidebar-bottom (guide card + help).
- Content-shell: header (66px) + main.
- Header: mobile-menu, crumb (Investigations + case title), header-tools (surface-switch Studio/Observatory, lang button, helpicon).
- Main: demo-banner, investigation-strip, columns grid (2.52fr | 1fr):
  - Primary-col: question panel (h2 + Reference pill + h1 + p + 5 tags + workflow-heading + phases + state-detail), observatory (dark, SVG graph + 3 obs-cards + node-panel).
  - Secondary-col: overview panel (dl with 6 items), insights panel (5 insights).
- Sources panel (5 sources all marked "Connector not verified").
- Bottom-notes (Engineering handoff + Audit & bitemporal records).

### 2.3 `styles.css`
- CSS variables: `--paper:#f7f8f6` (Porcelain), `--navy:#092e40`, `--teal:#2c7380`, `--teal-dark:#07556a`, `--brass:#bb9362`, `--mist:#e8eff1`, `--line:#e1e9ed`, `--muted:#637589`.
- Typography: `--serif: 'Source Serif 4'`, `--sans: Inter`, `--arabic: 'IBM Plex Sans Arabic'`, `--mono: 'IBM Plex Mono'`.
- Observatory: `background: radial-gradient(ellipse at 80% 120%, #0d4660, #001c2c 65%, #001624)` — dark celestial surface.
- RTL rules: `[dir=rtl] body { font-family: var(--arabic) }`, plus brand/heading/observatory gradient adjustments.
- Responsive breakpoints: 1250px (sidebar narrower), 960px (single col), 740px (mobile drawer + sidebar slide-in), 440px (single-col source grid).
- Mobile sidebar: `transform: translateX(-110%)` (LTR) / `translateX(110%)` (RTL); `.sidebar.open` reveals it. This is the correct logical-property-aware approach (no `scaleX(-1)`).

### 2.4 `script.js`
- `stages`: 5 phases with their 13 FSM states:
  - Discovery: `received`, `scoped`, `coverage_checked` (3)
  - Build: `building_capabilities`, `mold_ready` (2)
  - Acquire: `acquiring`, `normalizing`, `evidencing` (3)
  - Synthesize: `forecasting_or_scenarios`, `drafting`, `verification` (3)
  - Deliver: `deliverable_ready`, `archived` (2)
  - **Total: 13 states** ✅ matches handoff's 13-state FSM requirement.
- `tr`: full EN→AR translation map for every `data-i18n` key.
- `graph()`: 7 illustrative nodes (Question, Needs, Coverage, Plan, Acquire, Evidence, Synthesis) with curved path edges and node selection → node-panel. **Explicitly illustrative** per README rule #4 — must be replaced with real claim/evidence/source associations in React.
- `setLang(value)`: toggles `lang`/`dir` on `<html>`, swaps text content for all `[data-i18n]` elements, re-renders stages and graph.
- Mobile drawer: `#menu` click → `.sidebar.open` + `#shade` shown.

---

## 3. Standalone HTML Rendering Verification

A local HTTP server was started (Python `http.server` on `127.0.0.1:8765`) and the reference was loaded with Playwright (Chromium, headless). Screenshots were captured at the following viewports (device_scale_factor=2 for retina-quality captures):

| # | Viewport | Lang | Files |
|---|---|---|---|
| 01 | 1536×1024 desktop | EN | `01_en_desktop_1536x1024_full.png`, `_viewport.png` |
| 02 | 1536×1024 desktop | AR | `02_ar_desktop_1536x1024_full.png`, `_viewport.png` |
| 03 | 768×1024 tablet | EN | `03_en_tablet_768x1024_full.png`, `_viewport.png` |
| 04 | 768×1024 tablet | AR | `04_ar_tablet_768x1024_full.png`, `_viewport.png` |
| 05 | 375×812 mobile | EN | `05_en_mobile_375x812_full.png`, `_viewport.png` |
| 06 | 375×812 mobile | AR | `06_ar_mobile_375x812_full.png`, `_viewport.png` |

All 12 screenshots saved to `workspace/page02_reference/screenshots/`. Visual inspection confirms:
- Layout renders without errors at all 6 viewports.
- No horizontal overflow at any viewport.
- Mobile drawer pattern activates correctly at ≤740px width.
- Arabic fonts load and render without tofu boxes.
- Graph SVG renders with curved edges, luminous nodes, and halo background.

---

## 4. VLM Comparison — Approved Image vs HTML Reference

**Comparison 1: Approved image vs EN desktop HTML reference.**

Shared layout regions (present in both): sidebar, header, research question panel, workflow stepper, observatory graph, key insights panel, source explorer, overview panel.

Material visual differences identified by VLM:

| # | Difference | Reference rationale | Classification |
|---|---|---|---|
| 1 | Original uses 7-step process; reference uses 5 phases with 13 sub-state pills | README "Known differences" #1; rule #3 (13 real FSM states in 5 visual phases per OPEN-01) | **INTENTIONAL — DO NOT REVERT** |
| 2 | Original has globe/constellation; reference uses editable CSS/SVG celestial flow | README "Known differences" #2 | **INTENTIONAL — preserve visual identity in React** |
| 3 | Original has counts/progress (e.g. "Coverage: 62%"); reference replaces with "No fictional completeness scores" | README rule #8 (no arbitrary caps or fictitious percentages); rule #2 (replace with real data or honest empty/loading/error state) | **INTENTIONAL — must surface real backend data, never invent** |
| 4 | Original shows active source statuses ("12 sources found"); reference shows "Connector not verified" | README rule #6 (do not fabricate source counts) | **INTENTIONAL — must surface real backend connection status** |
| 5 | Original has live-looking data ("Scientific Research v1.0", "~30-60 minutes"); reference uses "Visual reference", "Not available" | README rule #2 (replace with real data or honest state) | **INTENTIONAL — React port must surface real workflow data** |
| 6 | Reference adds top "DESIGN REFERENCE — SAMPLE DATA ONLY" banner | README rule #2 — illustrative marker; React port may keep similar disclosure when in dev mode but should NOT block the production layout | **INTENTIONAL — React port should remove banner when real data flows** |
| 7 | Reference adds bottom "Engineering handoff" + "Audit & bitemporal records" notes | README rule #8 — engineering reminder | **INTENTIONAL — React port should NOT render these as user-facing UI; they are dev-only guidance** |
| 8 | Reference adds state pills below each phase (e.g. `received`, `scoped`) | README rule #3 — required to surface all 13 FSM states | **INTENTIONAL — React port MUST preserve all 13 state pills wired to real workflow API** |

Overall fidelity: **Medium-High structural fidelity** — the macro-layout, color palette, typography, and component structure are correctly reproduced. Content fidelity is intentionally lower because the reference explicitly replaces fictitious data with honest sample markers; this is the correct behavior for a reference package.

**Comparison 2: Arabic RTL fidelity check (HTML reference AR desktop vs RTL best practices).**

| Aspect | Result |
|---|---|
| Layout correctly mirrored right-to-left | ✅ PASS |
| Sidebar on right, content flows RTL | ✅ PASS |
| Icons positioned correctly for RTL (left of Arabic labels) | ✅ PASS |
| Arabic text rendering in IBM Plex Sans Arabic | ✅ PASS (no tofu) |
| SVG knowledge graph nodes NOT mirrored | ✅ PASS |
| SVG text labels not distorted | ✅ PASS |
| No horizontal overflow | ✅ PASS |
| No `scaleX(-1)` flip artifacts on icons/images | ✅ PASS |

Overall RTL fidelity: **PASS — production-ready RTL compliance** via proper logical properties (`dir="rtl"`, `inset-inline-end`, `border-inline-start`).

---

## 5. Acceptable Divergences (Carry-Forward to React)

The following divergences from the approved image are **acceptable and must be preserved** in the React port:

1. **5-phase / 13-state stepper** instead of the original 7-step illustration. The 13 real FSM states are the source of truth.
2. **Editable SVG graph** instead of the cinematic globe. Preserves the visual identity (dark celestial surface, luminous curved edges, halo background, glowing nodes).
3. **No invented progress percentages or source counts.** All counts must come from real backend data or be omitted with honest empty states.
4. **Source cards show "Connector not verified"** instead of fake counts. React port must surface real backend connection status; if no connector exists, the honest "not verified" state is correct.
5. **Demo banner** ("DESIGN REFERENCE — SAMPLE DATA ONLY") will be **REMOVED** in the React port (replaced by the real loading/empty/error/populated state machine that the React component already implements).
6. **Bottom engineering/audit notes panels** will be **REMOVED** from user-facing UI in the React port (they are dev-only guidance in the reference).
7. **State pills below each phase** are **REQUIRED** in the React port, wired to the real workflow API's `current_state` field.
8. **RTL compliance via logical properties** (`dir`, `inset-inline-*`, `border-inline-*`) — must be preserved. NO `scaleX(-1)` on icons or images.

## 6. Carry-Forward Functional Constraints

The following constraints from the README and the inspection must be honored in the React port:

1. **No iframes, no screenshot overlays.** Port DOM/SVG/CSS directly into React components.
2. **Preserve the existing API integration** in `frontend/src/components/manara/InvestigationWorkspace.tsx` (614 lines): `manaraApiExt`, `api-client.ts`, all 13 FSM states, EN/AR i18n. Rebuild only the visual layer.
3. **Knowledge Graph must read real Node/Edge data** from the backend API contract — not the 7 illustrative nodes. Implement: pan, zoom, node selection, edge details, list fallback for accessibility.
4. **Honest state machine**: loading, empty, error, blocker, populated — all 5 must be distinct and triggered by real API responses.
5. **No fabricated actions** (Edit Question, Pause, Share, Export). If the backend contract does not support them, do not render them as enabled.
6. **No fabricated source-provider integration.** Show real connection status; never claim arXiv/PubMed/OpenAlex/Crossref counts that the backend does not provide.
7. **Audit history** must come from real audit APIs, newest-first. No invented entries.
8. **Do not regress Page 01.** The shared shell (sidebar, header, language switcher, i18n) is already accepted; preserve its visual decisions.
9. **Dev-isolated fixtures** for testing the populated state must: (a) be documented as synthetic, (b) honor real API contracts, (c) never leak to production, (d) never be presented as verified scientific findings.

## 7. Phase A Conclusion

Phase A is complete. The reference package is intact, the standalone HTML renders correctly at all required viewports, the Arabic RTL compliance is verified, and the VLM comparison confirms that all material differences from the approved image are explicitly documented in the README as intentional design decisions. The reference is a faithful, executable visual source ready to be ported to React.

**Next:** Phase B — diff the existing 614-line `InvestigationWorkspace.tsx` against the HTML reference, identify visual deltas, and rebuild the visual layer while preserving the API/FSM/i18n scaffolding.
