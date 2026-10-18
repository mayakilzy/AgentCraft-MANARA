# Dependencies & Licenses

> **MANARA G00 · dependency inventory**

All dependencies are listed in `backend/pyproject.toml` (Python) and
`frontend/package.json` (TypeScript). Each is open-source and compatible with
a closed/commercial downstream license (the owner has not yet selected the
final license; see `LICENSE`).

## Backend (Python ≥ 3.12)

| Package              | Version     | License       | Purpose                                   |
|----------------------|-------------|---------------|-------------------------------------------|
| fastapi              | ≥0.115,<0.117| MIT           | Web framework                            |
| uvicorn[standard]    | ≥0.32,<0.36 | BSD-3-Clause  | ASGI server                               |
| pydantic             | ≥2.9,<3     | MIT           | Typed contract schemas + validation        |
| pydantic-settings    | ≥2.5,<3     | MIT           | Settings via env vars                     |
| email-validator      | ≥2.2,<3     | CC0-1.0       | Email validation (Pydantic `HttpUrl` etc.) |
| SQLAlchemy           | ≥2.0.36,<3  | MIT           | ORM + database abstraction                 |
| alembic              | ≥1.14,<2    | MIT           | Schema migrations                          |
| httpx                | ≥0.27,<0.29 | BSD-3-Clause  | HTTP client (tests + future connectors)    |
| python-multipart     | ≥0.0.12,<0.1| MIT           | Form parsing (FastAPI dep)                 |
| psycopg[binary]      | ≥3.2,<4     | LGPL-2.1+     | PostgreSQL driver (optional `[postgres]`)  |

### Dev dependencies

| Package              | Version     | License       | Purpose                                   |
|----------------------|-------------|---------------|-------------------------------------------|
| ruff                 | ≥0.7,<0.9   | MIT           | Lint + format                             |
| mypy                 | ≥1.13,<2    | MIT           | Static type checker                        |
| pytest               | ≥8.3,<9     | MIT           | Test runner                                |
| pytest-asyncio       | ≥0.24,<0.27 | MIT           | Async test support                         |
| pytest-cov           | ≥5.0,<7     | MIT           | Coverage plugin                             |
| coverage             | ≥7.6,<8     | Apache-2.0    | Coverage core                              |

## Frontend (Node ≥ 20)

| Package              | Version     | License       | Purpose                                   |
|----------------------|-------------|---------------|-------------------------------------------|
| react                | ^18.3.1     | MIT           | UI framework                               |
| react-dom            | ^18.3.1     | MIT           | React DOM renderer                         |
| @vitejs/plugin-react | ^4.3.3      | MIT           | Vite React plugin                          |
| vite                 | ^5.4.10     | BSD-3-Clause  | Build tool / dev server                     |
| typescript           | ^5.6.3      | Apache-2.0    | Type checker / compiler                    |
| @types/react         | ^18.3.12    | MIT           | React type stubs                           |
| @types/react-dom     | ^18.3.1     | MIT           | ReactDOM type stubs                        |

## License compatibility notes

- **LGPL (psycopg)**: Linked dynamically; compatible with closed/commercial
  applications as long as psycopg itself is not modified. We do not modify it.
- **BSD-3-Clause / Apache-2.0 / MIT**: All permissive; no copyleft concerns.
- **CC0-1.0 (email-validator)**: Public domain; no concerns.

## SBOM

A Software Bill of Materials can be generated with:

```bash
# Backend
cd backend && pip install pip-audit && pip-audit -r <(pip freeze) -f json -o sbom-backend.json

# Frontend
cd frontend && npm install -g @cyclonedx/cyclonedx-cli && cyclonedx-npm --output-file sbom-frontend.json
```

This is **not** run as part of G00; it is documented as a follow-up step for
the owner to execute before any production deployment review.
