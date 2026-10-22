# MANARA Dev Scripts

Reusable, non-sensitive testing scripts persisted to the work branch
for future dev sessions. These scripts exercise the real backend API
contracts — no stubs, no synthetic DBs.

## Scripts

### `page02_phaseA_capture_reference.py`
Renders the standalone HTML reference at 6 viewports and captures
Playwright screenshots. Used in Phase A of the source integration to
verify the reference renders correctly before porting to React.

Prerequisites: Page 02 source package extracted locally.
Run: `python3 scripts/dev/page02_phaseA_capture_reference.py`

### `page02_phaseC_seed_fixtures.py`
Seeds a dev-isolated SQLite database with a synthetic investigation
containing 5 evidence + 5 claims + 6 edges + 11 decisions + 4
workflow transitions, via REAL API contracts (POST /mold-factory/compose,
POST /memory/evidence, POST /memory/claims/{id}/support, PATCH verdict).

All fixture data is documented as synthetic dev data, NOT real research
findings. Honors real API contracts. Never leaks to production (uses
tenant_demo, which is the dev-only tenant ID).

Prerequisites:
- Backend running on 127.0.0.1:8000 with real sentence_transformers
- Database migrated (alembic upgrade head)

Run: `python3 scripts/dev/page02_phaseC_seed_fixtures.py`

### `page02_phaseD_capture_react.py`
Captures React screenshots at 6 viewports (EN/AR × desktop/tablet/mobile)
with live backend + seeded dev data. Switches to the seeded investigation
via the workspace's investigation selector dropdown. Verifies audit panel
populates and evidence count > 0 before capturing.

Prerequisites:
- Backend running on 127.0.0.1:8000
- Vite dev server on 127.0.0.1:5173
- Seeded investigation (run page02_phaseC_seed_fixtures.py first)

Run: `python3 scripts/dev/page02_phaseD_capture_react.py`

## NOT Persisted (Intentionally)

- `backend/manara_dev.db` — synthetic dev DB, NOT production code
- `scripts/stubs/sentence_transformers/` — Python stub for missing torch
  dependency, NOT for production use. Real `sentence_transformers` +
  `torch CPU` should be installed via `uv pip install torch --index-url
  https://download.pytorch.org/whl/cpu sentence-transformers` (~187 MB).
- `/home/z/my-project/.secrets/GH_TOKEN` — never committed
