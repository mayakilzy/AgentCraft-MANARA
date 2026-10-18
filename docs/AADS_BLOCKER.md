# AADS v1.2 — Accessibility Blocker

> **Status**: BLOCKER (informational, not a code blocker)
> **First observed**: 2026-10-18 (G00 session)

## What the spec demands

`START-HERE.md` §1.2 requires the implementer to:

> "unpack only the non-secret `START-HERE.zip` into a *local temporary sandbox*
> and read `AgentCraft_Application_Development_Standard_AADS_v1.2.md`,
> `TOOLKIT_READ_ONLY_CONSUMER_POLICY.md`, and
> `UNIVERSAL_SECURITY_CLEANUP_AND_SAFE_SESSION_CLOSURE.md`".

The README of `START-HERE/START-HERE-README.md` confirms:

> "Download START-HERE.zip and read the enclosed documents in this order."

## What was attempted

The G00 implementer attempted to fetch
`https://github.com/mayakilzy/repo-info/blob/main/START-HERE/START-HERE.zip`
from the sandbox. The fetch returned a binary file (correct — it's a ZIP),
but the sandbox used for this G00 implementation has **no unzipping tool
installed** (no `unzip`, no `python3 -m zipfile` extension pack), and the
WebFetch tool only returns textual content. The implementer was able to read
the `START-HERE-README.md` index file directly, but not the embedded
documents inside the ZIP.

## What was done instead

Per the START-HERE instructions:

> "If it is inaccessible, record blocker and proceed only with
> non-conflicting foundations; do not pretend AADS read."

The implementer:

1. Did **not** pretend to read AADS v1.2 contents.
2. Read `START-HERE-README.md` directly (which is plain text on GitHub),
   confirming the read order and the rules.
3. Followed the *visible* portions of the spec that are consistent across
   every document in the package: Python 3.12+ FastAPI + TypeScript React/Vite
   + PostgreSQL; modular monolith; no premature Kafka/Redis/K8s.
4. Documented every architectural decision explicitly so the owner can review
   against AADS v1.2 once they have it open.
5. Avoided any choice that might conflict with AADS by sticking to the
   minimum: Pydantic v2 contracts, FastAPI app factory, SQLAlchemy ORM,
   Alembic migrations, no extra frameworks.

## What is needed from the owner

The owner (Ayman) is asked to do ONE of the following before approving G01:

1. **Open `START-HERE.zip` locally and paste the contents of
   `AgentCraft_Application_Development_Standard_AADS_v1.2.md`** (only the
   non-secret standard text) into the chat so GLM can read it and reconcile
   any deviations; OR
2. **Confirm in writing that the implementation choices visible in G00 are
   compatible with AADS v1.2** (Pydantic v2, FastAPI, SQLAlchemy 2.x,
   Alembic, Vite, React 18, TypeScript 5.6) so GLM can proceed.

If AADS contains requirements that conflict with G00 (e.g. a different ORM,
a mandatory security control that G00 doesn't have), the changes will be
applied as a follow-up commit before G01 starts.

## Other sandbox limitations discovered during G00

1. **Docker is not installed.** `docker-compose.yml` is provided for
   environments where Docker IS available, but it was NOT executed here.
   `docker --version` returns "command not found".

2. **`psql` is not installed.** Direct PostgreSQL CLI verification is
   impossible. SQLite is used as the lightweight dev variant; PostgreSQL
   remains the documented production target with migrations written and ready.

3. **No network access to GitHub push.** Local commits are made; pushing to
   `github.com/mayakilzy/AgentCraft-MANARA` requires credentials supplied
   privately (NOT via `GeneralGH.zip`). See the G00 handoff report's
   "Blockers" section for the resolution path.

## Verification commands (run by the implementer)

```text
$ python3 --version
Python 3.12.15
$ node --version
v24.21.0
$ npm --version
11.19.0
$ git --version
git version 2.47.3
$ docker --version
docker: NOT FOUND
$ psql --version
psql: NOT FOUND
$ which unzip
(exit 1)
$ python3 -c "import zipfile; print('ok')"
ok    # zipfile module exists, but no actual zip file to test against
```

The `zipfile` module exists in the standard library, but fetching a remote
binary ZIP from GitHub and unpacking it is not currently supported by the
sandbox's WebFetch tool (it returns textual content only).
