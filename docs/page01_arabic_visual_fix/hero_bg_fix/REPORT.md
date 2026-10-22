# REPORT — MANARA-UI-PAGE01-ARABIC-HERO-BACKGROUND-FIX-01

**Mission:** MANARA-UI-PAGE01-ARABIC-HERO-BACKGROUND-FIX-01
**Status:** COMPLETED
**Date:** 2026-10-22
**Branch:** work/MANARA-UI-PAGE01-ARABIC-VISUAL-FIX-01 (same branch as the prior Arabic visual fix)

## Problem

After the Tajawal font + RTL visual fixes, the Arabic version of Page 01 still had a visual overlap: the lighthouse artwork was positioned on the RIGHT side (same side as the Arabic text), causing the title, description, and compose box to sit on top of the lighthouse artwork.

## Root Cause

The RTL CSS rule for `.manara-hero-art` had a bug:

```css
/* PRIOR (buggy) */
[dir="rtl"] .manara-hero-art {
  inset-inline-end: auto;     /* CLEARS the default left positioning */
  inset-inline-start: 0;      /* RTL: right: 0 — puts artwork on the RIGHT */
  ...
}
```

The comment in the code said "The artwork's position is mirrored via inset-inline-end (which automatically becomes 'left' in RTL)" — but the code CONTRADICTED the comment by clearing `inset-inline-end` and setting `inset-inline-start: 0` (which in RTL = `right: 0`, placing the artwork on the right side, same side as the text).

## Fix

Changed the RTL rule to put the artwork on the LEFT:

```css
/* FIXED */
[dir="rtl"] .manara-hero-art {
  inset-inline-end: 0;        /* RTL: left: 0 — artwork on the LEFT */
  inset-inline-start: auto;   /* Clear the right edge */
  mask-image: linear-gradient(270deg, transparent 0%, #000 27%);
  -webkit-mask-image: linear-gradient(270deg, transparent 0%, #000 27%);
}
```

The mask (`270deg` = right-to-left gradient) makes the RIGHT portion of the artwork transparent (faded out near the text) while keeping the LEFT portion fully visible. The lighthouse image itself is NOT flipped (no `scaleX(-1)`) per owner directive.

## Verification

### VLM Arabic desktop (after fix):
1. ✅ Lighthouse artwork is on the LEFT side
2. ✅ Arabic hero title on the RIGHT, no overlap with artwork
3. ✅ Arabic description on the RIGHT, no overlap
4. ✅ Compose box on the RIGHT/center, no overlap
5. ✅ Lighthouse artwork still visible and beautiful
6. ✅ Smooth fade from artwork to text side (no harsh edge)

VLM verdict: "The RTL fix was successful. The layout correctly mirrors the design for Arabic readers."

### VLM English regression check:
1. ✅ Lighthouse artwork on the RIGHT (unchanged)
2. ✅ Hero title on the LEFT, clear of artwork
3. ✅ No visual regressions

### Quality gates:
- TypeScript: PASS (0 errors)
- ESLint: PASS (0 errors)
- Build: PASS (49 KB CSS, 284 KB JS)
- Vitest: 23/23 PASS

## Files Changed

- `frontend/src/styles.css` — single rule fix: `[dir="rtl"] .manara-hero-art` position corrected

**No other files modified.** No English version changes. Tajawal font retained.

## Stop Condition

✅ Arabic fixed (artwork moved to left, text clear on right)
✅ English unchanged
🛑 STOP — awaiting owner review
