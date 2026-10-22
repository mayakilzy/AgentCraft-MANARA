"""MANARA-UI-PAGE01-ARABIC-COMPOSE-FIX-01 — regression tests.

Verifies that the MoldArchitect generates valid ASCII mold identifiers
for research queries in any language (Arabic, Turkish, CJK, mixed).

Before this fix, Arabic queries failed HTTP 422 because the mold ID
contained non-ASCII characters (e.g. ``mold.قارن-...``) which violated
the ``^mold\\.[a-z0-9][a-z0-9-]{1,80}$`` pattern.

The fix: ``MoldArchitect._derive_domain`` now sanitizes non-ASCII tokens
to a deterministic 8-char hex slug (``q{hash8}``) via SHA-256.
"""
from __future__ import annotations

import os

os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", "/home/z/my-project/.models")
os.environ.setdefault("HF_HOME", "/home/z/my-project/.models/hf_cache")

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from manara.app import create_app
from manara.config import reload_settings
from manara.db.session import get_engine, init_db, reset_engine
from manara.mold_factory.architect import MoldArchitect

MOLD_ID_PATTERN = r"^mold\.[a-z0-9][a-z0-9-]{1,80}$"


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests for the slug helper
# ─────────────────────────────────────────────────────────────────────────────


class TestAsciiSlug:
    def test_ascii_token_preserved_verbatim(self):
        """English/Turkish-ASCII tokens pass through unchanged (backwards compat)."""
        assert MoldArchitect._ascii_slug("compare") == "compare"
        assert MoldArchitect._ascii_slug("robotik") == "robotik"
        assert MoldArchitect._ascii_slug("recycling") == "recycling"
        assert MoldArchitect._ascii_slug("data-2026") == "data-2026"

    def test_arabic_token_becomes_deterministic_ascii_slug(self):
        """Arabic tokens get a deterministic q{hash8} slug."""
        s1 = MoldArchitect._ascii_slug("قارن")
        s2 = MoldArchitect._ascii_slug("قارن")
        assert s1 == s2, "same input must produce same slug (idempotency)"
        assert s1.startswith("q"), "non-ASCII slug must start with 'q' marker"
        assert len(s1) == 9, "expected q + 8 hex chars"
        assert re.fullmatch(r"[a-z0-9][a-z0-9-]*", s1), "slug must be pattern-safe"

    def test_different_arabic_tokens_produce_different_slugs(self):
        """Different non-ASCII tokens must produce different slugs (no collisions)."""
        s1 = MoldArchitect._ascii_slug("قارن")
        s2 = MoldArchitect._ascii_slug("مستقبل")
        assert s1 != s2, "different tokens must produce different slugs"

    def test_cjk_token_handled(self):
        """CJK characters get a deterministic slug."""
        s = MoldArchitect._ascii_slug("比較")
        assert s.startswith("q")
        assert re.fullmatch(r"[a-z0-9][a-z0-9-]*", s)

    def test_turkish_dotted_i_handled(self):
        """Turkish dotted-i (İ) is non-ASCII; gets a slug."""
        s = MoldArchitect._ascii_slug("İstanıbul")
        assert s.startswith("q")
        assert re.fullmatch(r"[a-z0-9][a-z0-9-]*", s)


class TestDeriveDomain:
    def test_english_query_preserves_token(self):
        """English queries continue to produce verbatim lowercase tokens."""
        d = MoldArchitect._derive_domain(
            "Compare clinical outcomes of robotic versus manual prosthetic alignment"
        )
        assert d == "compare"

    def test_arabic_query_produces_ascii_slug(self):
        """Arabic queries produce ASCII-safe slugs (the bug fix)."""
        d = MoldArchitect._derive_domain(
            "قارن النتائج السريرية للمحاذاة التعاضدية الآلية مقابل اليدوية"
        )
        assert re.fullmatch(r"[a-z0-9][a-z0-9-]*", d), \
            f"Arabic-derived domain must be ASCII-safe, got {d!r}"

    def test_arabic_query_idempotent(self):
        """Same Arabic query → same domain slug (deterministic)."""
        q = "قارن النتائج السريرية للمحاذاة التعاضدية الآلية مقابل اليدوية"
        d1 = MoldArchitect._derive_domain(q)
        d2 = MoldArchitect._derive_domain(q)
        assert d1 == d2

    def test_different_arabic_queries_differ(self):
        """Different Arabic queries produce different slugs."""
        d1 = MoldArchitect._derive_domain("قارن النتائج السريرية")
        d2 = MoldArchitect._derive_domain("ما هو مستقبل الذكاء الاصطناعي")
        assert d1 != d2

    def test_mixed_ar_en_uses_first_eligible_token(self):
        """Mixed queries use the first non-stopword token (could be EN or AR)."""
        # First token "Compare" is ASCII → preserved verbatim
        d = MoldArchitect._derive_domain("Compare قارن the clinical outcomes")
        assert d == "compare"
        # First token "قارن" is non-ASCII → slug
        d = MoldArchitect._derive_domain("قارن compare the clinical outcomes")
        assert d.startswith("q") or re.fullmatch(r"[a-z0-9][a-z0-9-]*", d)

    def test_all_stopwords_falls_back_to_custom(self):
        """All-stopword queries fall back to 'custom' (preserved behavior)."""
        d = MoldArchitect._derive_domain("the and for with from about into")
        assert d == "custom"


# ─────────────────────────────────────────────────────────────────────────────
# Integration tests via FastAPI TestClient
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    """Isolated TestClient with file-backed SQLite for Arabic compose tests."""
    db_path = tmp_path_factory.mktemp("arabic_compose") / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["MANARA_ENV"] = "development"
    os.environ["MANARA_DISCOVERY_MODE"] = "synthetic"
    os.environ["MANARA_SINGLE_TENANT_DEMO"] = "true"
    reload_settings()
    reset_engine()
    init_db()
    app = create_app()
    with TestClient(app) as c:
        yield c


class TestArabicComposeEndToEnd:
    """End-to-end: Arabic research question → real compose → valid identifiers."""

    def test_arabic_compose_returns_200(self, client):
        """The bug: Arabic queries used to return HTTP 422. Now must return 200."""
        r = client.post(
            "/mold-factory/compose",
            json={
                "query": (
                    "قارن النتائج السريرية للمحاذاة التعاضدية الآلية مقابل اليدوية "
                    "للمرضى الذين تزيد أعمارهم عن 60 عاماً المصابين بالفصال العظمي"
                )
            },
        )
        assert r.status_code == 200, f"Arabic compose must succeed, got {r.status_code}: {r.text[:300]}"

    def test_arabic_compose_returns_valid_mold_id(self, client):
        """The mold_id must match the canonical pattern."""
        r = client.post(
            "/mold-factory/compose",
            json={"query": "قارن النتائج السريرية للمحاذاة التعاضدية"},
        )
        assert r.status_code == 200
        body = r.json()
        mold_id = body["mold_recipe_id"]
        assert re.match(MOLD_ID_PATTERN, mold_id), \
            f"mold_id {mold_id!r} does not match pattern {MOLD_ID_PATTERN}"

    def test_arabic_compose_returns_valid_investigation_id(self, client):
        """The investigation_id must be present and non-empty."""
        r = client.post(
            "/mold-factory/compose",
            json={"query": "قارن النتائج السريرية"},
        )
        assert r.status_code == 200
        body = r.json()
        inv_id = body["investigation_id"]
        assert inv_id and inv_id.startswith("inv-"), \
            f"investigation_id {inv_id!r} invalid"

    def test_arabic_query_preserved_verbatim(self, client):
        """The original Arabic query must be preserved in the response.query field."""
        ar_query = "قارن النتائج السريرية للمحاذاة التعاضدية الآلية مقابل اليدوية"
        r = client.post("/mold-factory/compose", json={"query": ar_query})
        assert r.status_code == 200
        body = r.json()
        assert body["query"] == ar_query, \
            f"Arabic query not preserved verbatim: got {body['query']!r}"

    def test_arabic_investigation_retrievable(self, client):
        """The AR investigation must be retrievable via GET /investigations/{id}."""
        r = client.post(
            "/mold-factory/compose",
            json={"query": "قارن النتائج السريرية للمحاذاة التعاضدية"},
        )
        assert r.status_code == 200
        inv_id = r.json()["investigation_id"]

        # Retrieve via list
        r = client.get("/mold-factory/investigations")
        assert r.status_code == 200
        inv_list = r.json()
        assert any(i["id"] == inv_id for i in inv_list), \
            f"AR investigation {inv_id} not found in list"

        # Retrieve via detail
        r = client.get(f"/mold-factory/investigations/{inv_id}")
        assert r.status_code == 200
        inv = r.json()
        assert inv["id"] == inv_id
        assert "قارن" in inv["topic"], f"AR topic not preserved: {inv['topic']!r}"

    def test_arabic_investigation_workflow_initializable(self, client):
        """Workflow can be initialized for an AR investigation."""
        r = client.post(
            "/mold-factory/compose",
            json={"query": "قارن النتائج السريرية للمحاذاة التعاضدية"},
        )
        inv_id = r.json()["investigation_id"]

        r = client.post(f"/mold-factory/investigations/{inv_id}/workflow")
        assert r.status_code == 201, f"workflow init failed: {r.status_code} {r.text[:200]}"
        assert r.json()["state"] == "received"

    def test_arabic_mold_retrievable(self, client):
        """The AR mold must be retrievable via GET /mold-factory/molds/{id}."""
        r = client.post(
            "/mold-factory/compose",
            json={"query": "قارن النتائج السريرية للمحاذاة التعاضدية"},
        )
        mold_id = r.json()["mold_recipe_id"]

        r = client.get(f"/mold-factory/molds/{mold_id}")
        assert r.status_code == 200
        assert r.json()["id"] == mold_id

    def test_repeated_identical_arabic_query_distinct_investigations(self, client):
        """Same AR query twice → different investigation_ids (random suffix) but
        same domain slug (deterministic hash)."""
        q = "قارن النتائج السريرية للمحذاة التعاضدية الآلية مقابل اليدوية"
        r1 = client.post("/mold-factory/compose", json={"query": q})
        r2 = client.post("/mold-factory/compose", json={"query": q})
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["investigation_id"] != r2.json()["investigation_id"], \
            "different investigations expected"
        # Both mold IDs should share the same domain slug prefix
        m1 = r1.json()["mold_recipe_id"]
        m2 = r2.json()["mold_recipe_id"]
        # Extract the domain part: mold.{domain}-{ts}-{rand}
        d1 = m1.split("-", 2)[0]  # "mold.qa3fb23a1"
        d2 = m2.split("-", 2)[0]
        assert d1 == d2, f"same AR query should produce same domain slug: {d1} vs {d2}"


class TestOtherLanguagesCompose:
    """Compose must work for Turkish, mixed, and other Unicode inputs."""

    def test_turkish_compose(self, client):
        r = client.post(
            "/mold-factory/compose",
            json={
                "query": (
                    "Robotik ile manuel protez hizalamasının klinik sonuçlarını "
                    "60 yaş üstü osteoartrit hastalarında karşılaştır"
                )
            },
        )
        assert r.status_code == 200, f"Turkish compose failed: {r.status_code}"
        assert re.match(MOLD_ID_PATTERN, r.json()["mold_recipe_id"])

    def test_mixed_ar_en_compose(self, client):
        r = client.post(
            "/mold-factory/compose",
            json={"query": "Compare قارن the clinical outcomes النتائج السريرية"},
        )
        assert r.status_code == 200
        assert re.match(MOLD_ID_PATTERN, r.json()["mold_recipe_id"])

    def test_cjk_compose(self, client):
        r = client.post(
            "/mold-factory/compose",
            json={"query": "比較機器人輔助與手動義肢對位在60歲以上骨關節炎患者中的臨床結果"},
        )
        assert r.status_code == 200, f"CJK compose failed: {r.status_code}"
        assert re.match(MOLD_ID_PATTERN, r.json()["mold_recipe_id"])


class TestEnglishBackwardsCompat:
    """English queries must continue to work exactly as before."""

    def test_english_compose_unchanged(self, client):
        """English query produces 'mold.compare-...' as before (no slug hashing)."""
        r = client.post(
            "/mold-factory/compose",
            json={
                "query": (
                    "Compare clinical outcomes of robotic versus manual prosthetic "
                    "alignment in patients aged 60+ with osteoarthritis"
                )
            },
        )
        assert r.status_code == 200
        mold_id = r.json()["mold_recipe_id"]
        assert mold_id.startswith("mold.compare-"), \
            f"English mold ID should start with 'mold.compare-', got {mold_id!r}"
