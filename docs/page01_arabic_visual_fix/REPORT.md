# REPORT — `MANARA-UI-PAGE01-ARABIC-VISUAL-FIX-01`

**Mission:** `MANARA-UI-PAGE01-ARABIC-VISUAL-FIX-01`
**Status:** COMPLETED
**Date:** 2026-10-22
**Investigator:** GLM (MANARA Dev)
**Branch:** `work/MANARA-UI-PAGE01-ARABIC-VISUAL-FIX-01` (branched from `work/MANARA-UI-PAGE02-SOURCE-INTEGRATION-01` at `9618549`)

---

## 1. Mission Scope (Per Owner Brief)

Fix the Arabic (RTL) visual distortions in Page 01 (Home page) so that the Arabic version:
1. Visually matches the approved design as closely as possible
2. Is parallel in quality to the preliminarily-accepted English version
3. Uses **Tajawal** as the primary Arabic display font

Forbidden:
- Modifying the English version (unless shared technical reason)
- Redesigning the page from scratch
- Adding new elements
- Using any Arabic font other than Tajawal
- Text-only fixes (real visual fixes required)

---

## 2. What Was Fixed

### 2.1 Arabic Font: IBM Plex Sans Arabic → Tajawal

**Files changed:**
- `frontend/index.html` — Google Fonts URL updated to load `Tajawal:wght@400;500;700;800` (removed `IBM+Plex+Sans+Arabic`)
- `frontend/src/styles.css` — CSS variable `--font-ibm-arabic` now resolves to `"Tajawal", "IBM Plex Sans Arabic", system-ui, sans-serif` (Tajawal primary, IBM Plex fallback). Added new `--font-arabic` alias pointing to the same stack.

**Where Tajawal is applied (in `[dir="rtl"]` context only):**
- Body text (`[dir="rtl"] body, .font-ui, .font-sans`)
- Headings (`h1`–`h6`)
- Hero title (`.manara-hero-title`)
- Hero description (`.manara-hero-description`)
- Hero accent (`.manara-hero-accent`)
- Eyebrow text (`.manara-eyebrow`)
- Section titles (`.manara-section-title h2`, `.manara-section-title p`)
- Step card titles + descriptions (`.manara-step h3`, `.manara-step p`)
- Mountain CTA card (`.manara-mountain-card h2`, `.manara-mountain-card p`)
- Mountain CTA button (`.manara-mountain-cta`)
- Capabilities section header + cards (`.manara-capabilities > h2`, `.manara-cap-grid b/small`)
- Question hint (`.manara-question-hint`)
- Learn more link (`.manara-learn-more`)
- Below-hero section (`.manara-below`)

**Font weights:**
- Headings: `font-weight: 700` (Tajawal's strongest weight for clear, bold Arabic titles)
- Body: `font-weight: 400` (regular weight for comfortable reading)
- Labels/chips: `font-weight: 500–600` (medium for balanced, non-crowded chips)

### 2.2 Fix #1: Hero Title Sizing (Arabic)

**Problem:** Arabic hero title used `clamp(38px, 4.1vw, 69px)` from the English CSS. Tajawal glyphs are wider than Source Serif 4, causing text collision and overlap with the lighthouse artwork.

**Fix:**
- Reduced Arabic font-size: `clamp(30px, 3.2vw, 52px)`
- Increased line-height: `1.18` (Arabic needs more vertical space for tall glyphs)
- Letter-spacing: `0` (negative letter-spacing is harmful for Arabic glyph shaping)
- Added `max-width: 600px` to prevent text from overflowing into the hero art area
- Responsive breakpoints: `clamp(28px, 3.5vw, 42px)` at ≤1180px, `clamp(26px, 7vw, 38px)` at ≤780px

### 2.3 Fix #2: Hero Text/Background Overlap

**Problem:** Arabic hero copy (`max-width: 700px`) was wide enough to overlap with the lighthouse artwork positioned on the left side (in RTL).

**Fix:**
- Reduced Arabic hero copy `max-width` to `580px` (≤1180px: `500px`, ≤780px: `100%`)
- Added `position: relative; z-index: 2` to keep text above the artwork
- Added `text-align: right` for natural Arabic reading flow

### 2.4 Fix #3: Input Box RTL

**Problem:** Arabic textarea wasn't properly right-aligned; char counter and submit button weren't flowing naturally in RTL.

**Fix:**
- Added explicit `text-align: right` on `.manara-question-input` in RTL
- Adjusted padding: `padding-right: 16px; padding-left: 8px`
- Ensured `.manara-question-actions` and `.manara-question-submit` use `flex-direction: row` (which naturally reverses in RTL)
- Used CSS `order` to ensure the submit button's text + arrow icon flow correctly (text on right, arrow on left = "forward" in Arabic)

### 2.5 Fix #4: Chips Strip RTL

**Problem:** Chips weren't properly arranged right-to-left; risk of text compression.

**Fix:**
- Added explicit `flex-direction: row` + `justify-content: flex-start` + `text-align: right`
- Each chip: `text-align: right`, `direction: rtl`, `white-space: nowrap`, `overflow: hidden`, `text-overflow: ellipsis`, `max-width: 220px` (prevents compression)

### 2.6 Fix #5: "How MANARA Works" Step Cards

**Problem:** Icons were on the left side (LTR-style) instead of the right (RTL leading edge); text wasn't right-aligned.

**Fix:**
- Added explicit `flex-direction: row` for `.manara-step` in RTL (children naturally reverse in RTL flex row)
- Added `text-align: right` for `.manara-step h3` and `.manara-step p`
- Applied Tajawal font + `font-weight: 700` for headings, `400` for body

### 2.7 Fix #6: Capability Cards

**Problem:** Icons on the left, text not right-aligned.

**Fix:**
- Added `align-items: flex-end` + `text-align: right` for `.manara-cap-grid > div` in RTL
- Added `text-align: right` for `.manara-cap-grid b` and `.manara-cap-grid small`
- Applied Tajawal font

### 2.8 Fix #7: Bottom Dark CTA (Mountain) Card

**Problem:** Default positioning was LTR-oriented; text alignment wasn't right for Arabic.

**Fix:**
- Applied Tajawal font + `font-weight: 700` for the heading
- Reduced heading font-size to `20px` (from `22px`) to prevent line-break issues with wider Arabic glyphs
- Added `text-align: right` for the description
- CTA button: switched from `inset-inline-start: 22px` to `inset-inline-end: 22px` for RTL (so the button sits on the right side = start of reading direction)

### 2.9 Fix #8: Arabic Sidebar

**Problem:** Sidebar nav items didn't render text in Tajawal; alignment felt "off" for Arabic.

**Fix:**
- Tajawal is now applied via the global `[dir="rtl"] body` rule (sidebar inherits this)
- The existing `flex items-center gap-3` on nav items + the `[dir="rtl"]` document direction naturally reverses children: nav icon on right, text in middle, lock badge on left
- No additional CSS rules needed beyond the global Tajawal application

### 2.10 Fix #9: Top Bar / Header

**Problem:** Search bar magnifying glass icon was on the left in RTL (should be on the right = leading edge of reading direction). Language switcher layout looked LTR-pasted-into-RTL.

**Fix:**
- Added `manara-header-search` class to the search bar element in `Header.tsx`
- Added CSS rule: `[dir="rtl"] .manara-header-search { flex-direction: row-reverse; }` — this ensures the search icon appears on the right in RTL
- The language switcher component (`LanguageSwitcher.tsx`) was already using `inset-inline-*` logical properties, so no change needed

### 2.11 Other Arabic Visual Fixes

- **Hero accent** (`<em>` tag for "تكتشف"): Removed italic (italic doesn't apply to Arabic; removed via `font-style: normal`), set `font-weight: 700`
- **Eyebrow text**: Removed wide letter-spacing (`letter-spacing: 0`) — Arabic doesn't use the spacing aesthetic of uppercase English
- **Hero description**: Reduced font-size to `14px` (from `16px`) because Tajawal glyphs are wider; increased line-height to `1.6` for comfortable reading

---

## 3. Was the English Version Affected?

**No.** All visual fixes are scoped under `[dir="rtl"]` selectors in CSS. The English (`[dir="ltr"]`) version uses the existing Source Serif 4 + Inter fonts and the existing layout — completely unchanged.

**Verification:** VLM check on the English desktop screenshot confirmed:
> "1. Unchanged? Yes, the page appears visually identical to a standard English version. 2. Hero Font? Yes, 'What do you want to discover today?' is rendered in Source Serif 4 (serif). 3. Layout Direction? Yes, strictly LTR. 4. Regressions? None detected."

The only change to a non-RTL-scoped file was:
- `index.html` — Google Fonts URL updated (removed IBM Plex Sans Arabic, added Tajawal). This change affects font LOADING only; the English version never used IBM Plex Sans Arabic (it uses Source Serif 4 + Inter), so removing IBM Plex Sans Arabic from the URL doesn't affect English rendering.

**VLM English verification: PASS — no regressions detected.**

---

## 4. VLM Verification of Arabic Fixes

VLM check on the Arabic desktop screenshot (after fix) confirmed all 10 verification points:

| # | Check | Status |
|---|---|---|
| 1 | Hero title sized appropriately (not oversized, no overlap) | ✅ PASS |
| 2 | Text not colliding with lighthouse artwork | ✅ PASS |
| 3 | Input box properly RTL (text right-aligned, submit button on left) | ✅ PASS |
| 4 | Chips arranged right-to-left | ✅ PASS |
| 5 | Step cards: icon on right, text on left, arrow pointing left (forward in RTL) | ✅ PASS |
| 6 | Capability cards: icons on right, text right-aligned | ✅ PASS |
| 7 | Bottom CTA card properly RTL | ✅ PASS |
| 8 | Sidebar properly RTL (sidebar on right, icons on right) | ✅ PASS |
| 9 | Header search bar: search icon on the right | ✅ PASS |
| 10 | Arabic font appears to be Tajawal (geometric, open counters, rounded terminals) — distinct from IBM Plex Sans Arabic | ✅ PASS |

**Overall VLM verdict:** "The layout successfully implements a high-quality, standard RTL (Right-to-Left) interface suitable for Arabic users."

---

## 5. Test Results

| Test | Result |
|---|---|
| TypeScript (`tsc --noEmit`) | ✅ PASS (0 errors) |
| ESLint (`InvestigationWorkspace.tsx`, `Hero.tsx`, `Header.tsx`) | ✅ PASS (0 errors) |
| Vite production build | ✅ PASS (49.00 KB CSS, 284.72 KB JS) |
| Vitest (frontend unit tests) | ✅ 23/23 PASS |
| E2E Journey Test (`test_investigation_journey.py`) | ✅ 7/7 PASS (with warm model) |
| VLM Arabic desktop verification | ✅ 10/10 checks PASS |
| VLM English (regression check) | ✅ No regressions |

**Note on E2E timing:** The first compose call after backend restart takes ~15 seconds (model loading). The E2E test's 30s timeout is sufficient when the model is warm. The test was verified to pass 7/7 after warming up the model with 2 curl calls.

---

## 6. Files Changed

| File | Change |
|---|---|
| `frontend/index.html` | Google Fonts URL: removed `IBM+Plex+Sans+Arabic`, added `Tajawal:wght@400;500;700;800` |
| `frontend/src/styles.css` | Updated `--font-ibm-arabic` variable to Tajawal primary; added `--font-arabic` alias; added ~230 lines of `[dir="rtl"]` scoped visual fixes for Hero, Input, Chips, Step cards, Capability cards, Mountain CTA, Header search bar |
| `frontend/src/components/manara/Header.tsx` | Added `manara-header-search` class to the search bar element (for RTL flex-direction targeting) |

**No other files modified.** No backend code changes. No i18n.tsx changes. No App.tsx changes.

---

## 7. Screenshots Captured

**Before** (baseline, with IBM Plex Sans Arabic):
- `before/01_ar_desktop_before_full.png` (1536×1024)
- `before/02_ar_mobile_before_full.png` (375×812)
- `before/vlm_analysis.json` (VLM analysis of issues)

**After** (with Tajawal + visual fixes):
- `after/01_ar_desktop_after_full.png` (1536×1024)
- `after/02_ar_mobile_after_full.png` (375×812)
- `after/03_en_desktop_unchanged_full.png` (1536×1024, English regression check)
- `after/vlm_after_ar.json` (VLM verification of fixes)
- `after/vlm_en_unchanged.json` (VLM English regression check)

---

## 8. Stop Condition

Per owner's brief: "توقف بعد إصلاح Page 01 Arabic only ولا تنتقل إلى صفحة أخرى قبل اعتمادنا."

**🛑 STOP.** Page 01 Arabic visual fixes are complete. Awaiting owner's review and approval before:
- Merging to `main`
- Starting any other page work (including Page 03 / Memory Explorer)

The English version is unchanged. The Arabic version now uses Tajawal and has all 9 visual issues fixed per VLM verification.

☕❤️🗼🤝
