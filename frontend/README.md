# MANARA Frontend (G00)

Vite + React + TypeScript shell for the G00 foundation. Connects to the FastAPI
backend at `http://localhost:8000` (proxied via Vite in dev).

## What's here

- `src/api/client.ts` — typed API client for the three G00 endpoints (`/status`,
  `/discovery`, `/contracts/schemas`).
- `src/components/StatusBanner.tsx` — renders `/status` (capabilities + not-implemented).
- `src/components/DiscoveryView.tsx` — renders the synthetic `/discovery` view.
- `src/styles.css` — minimal RTL-friendly dark theme.

## What's NOT here

No real investigation workflow, no forecasting UI, no tenant selector, no auth.
Those arrive in later missions per the roadmap.

## Dev

```bash
npm install
npm run dev          # http://localhost:5173
npm run typecheck    # tsc --noEmit
npm run build       # production build to dist/
```

The Vite dev server proxies `/status`, `/health`, `/discovery`, `/contracts`
to `http://localhost:8000` so you can run both processes concurrently.

To point the frontend at a different backend, set `VITE_API_BASE_URL` in a
`.env.local` file (never committed).
