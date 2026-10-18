"""Investigation Decomposer — splits a research question into research needs.

The core insight from the owner's G01 review:

> "The system retrieved patent-intelligence correctly, but it also returned
> agriculture and energy engines, while academic-publications and clinical-
> trials were missing — despite being essential."

The original G01 search pipeline returned engines ranked by overall
semantic similarity to the query. This works for *single-need* queries
("find me patents") but fails for *multi-need* investigation questions
("study the future of intelligent prosthetics") because:

1. The query implicitly demands MULTIPLE kinds of evidence (literature,
   patents, trials, code activity).
2. Pure similarity cannot distinguish "this engine matches a small part
   of the query" from "this engine matches the whole query intent".
3. False positives emerge when an engine's general vocabulary ("research",
   "trends") overlaps with the query's vocabulary but its actual
   scope is unrelated (e.g. agricultural-statistics matching
   "research" in a prosthetics query).

The InvestigationDecomposer addresses this by:

1. Decomposing the query into a set of RESEARCH NEEDS — each need is an
   archetype like "scientific_literature" or "clinical_evidence".
2. Scoring each need's relevance to the query (using both keyword
   signals and a small set of probe embeddings).
3. Returning the prioritized list of detected needs, so the search
   pipeline can pick ONE engine per need (Multi-Capability Coverage).

This is NOT an LLM call. The decomposer uses:
* Keyword/pattern matching (multilingual ar/en)
* Probe embeddings — pre-computed embeddings of canonical need descriptions
* Compositional rules (e.g. "if clinical_evidence detected, also consider
  scientific_literature")

Probe embeddings are computed once at startup and cached on the Embedder
singleton. The decomposer is therefore cheap and deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from manara.registry.embeddings import Embedder, Vector

# ─────────────────────────────────────────────────────────────────────────────
# Research need archetypes
# ─────────────────────────────────────────────────────────────────────────────

ResearchNeedKind = Literal[
    "scientific_literature",
    "patent_intelligence",
    "clinical_evidence",
    "technology_signals",
    "market_data",
    "policy_indicators",
    "event_tracking",
    "environmental_data",
]


@dataclass
class ResearchNeedArchetype:
    """A canonical research need archetype."""

    id: ResearchNeedKind
    label_en: str
    label_ar: str
    keywords_en: list[str]
    keywords_ar: list[str]
    probe_text: str
    companion_needs: list[ResearchNeedKind] = field(default_factory=list)


ARCHETYPES: list[ResearchNeedArchetype] = [
    ResearchNeedArchetype(
        id="scientific_literature",
        label_en="Scientific literature & citations",
        label_ar="الأبحاث العلمية والاستشهادات",
        keywords_en=[
            "research", "study", "studies", "paper", "papers", "publication",
            "literature", "review", "meta-analysis", "evidence", "findings",
            "journal", "preprint", "citation", "doi", "academic",
            "systematic review", "peer-reviewed", "scholarly", "author",
            "future", "trends", "trajectory", "advances", "progress",
            "state of the art", "horizon", "outlook", "forecast",
        ],
        keywords_ar=[
            "بحث", "دراسة", "أبحاث", "منشور", "مقال", "أدبيات", "مراجعة",
            "استشهاد", "مجلة", "علمي", "الباحث", "المراجعة المنهجية",
            "مستقبل", "اتجاهات", "تطور", "آفاق",
        ],
        probe_text=(
            "Find peer-reviewed scientific publications, literature reviews, "
            "citations, and academic research findings about this topic. "
            "Include systematic reviews, meta-analyses, preprints, author "
            "networks, and studies about future trends and advances."
        ),
        companion_needs=[],
    ),
    ResearchNeedArchetype(
        id="patent_intelligence",
        label_en="Patent intelligence & IP trends",
        label_ar="براءات الاختراع واتجاهات الملكية الفكرية",
        keywords_en=[
            "patent", "patents", "innovation", "invention", "filing",
            "assignee", "ipc", "cpc", "intellectual property", "prior art",
            "patent family", "patent landscape", "patent-pending",
            "future", "trajectory", "advances", "technology",
        ],
        keywords_ar=[
            "براءة", "براءات", "اختراع", "ابتكار", "ملكية فكرية", "إيداع",
            "صاحب البراءة", "تاريخ الإيداع", "مستقبل", "تطور",
        ],
        probe_text=(
            "Identify patent families, assignees, filing trends, and IP "
            "landscape signals related to this topic. Use patents as early "
            "indicators of innovation direction and future technological "
            "trajectories — not as proof of efficacy."
        ),
        companion_needs=["technology_signals"],
    ),
    ResearchNeedArchetype(
        id="clinical_evidence",
        label_en="Clinical evidence & regulatory pathways",
        label_ar="الأدلة السريرية والمسارات التنظيمية",
        keywords_en=[
            "clinical", "trial", "trials", "phase", "efficacy", "safety",
            "medical", "health", "patient", "treatment", "therapy",
            "regulatory", "approval", "fda", "ema", "intervention",
            "implant", "device", "drug", "prosthetic", "prosthetics",
            "neural", "interface", "bionic", "biomedical", "engineering",
            "neuroprosthetic", "brain-computer", "exoskeleton", "robotics",
        ],
        keywords_ar=[
            "سريري", "تجربة سريرية", "مرحلة", "فعالية", "سلامة", "طبي",
            "علاج", "تنظيمي", "اعتماد", "تدخل", "زرعة", "دواء",
            "صناعي", "أطراف صناعية", "واجهة عصبية", "هندسة طبية",
        ],
        probe_text=(
            "Find clinical trials, regulatory submissions, intervention "
            "studies, and approval records for medical treatments, devices, "
            "prosthetics, neural interfaces, and drugs related to this "
            "topic. Distinguish trial registration from efficacy evidence."
        ),
        companion_needs=["scientific_literature"],
    ),
    ResearchNeedArchetype(
        id="technology_signals",
        label_en="Technology signals & code activity",
        label_ar="إشارات التقنية ونشاط الكود",
        keywords_en=[
            "technology", "software", "code", "github", "repository",
            "open-source", "model", "release", "implementation",
            "framework", "library", "developer", "ai", "ml",
            "intelligent", "smart", "robotics", "automation",
        ],
        keywords_ar=[
            "تقنية", "برمجيات", "كود", "مستودع", "مفتوح المصدر", "نموذج",
            "إصدار", "إطار عمل", "مطور", "ذكي", "روبوتات", "أتمتة",
        ],
        probe_text=(
            "Identify technology adoption signals: GitHub repository "
            "activity, open-source momentum, model releases, AI/ML tooling, "
            "robotics implementations, and developer engagement related to "
            "this topic."
        ),
        companion_needs=[],
    ),
    ResearchNeedArchetype(
        id="market_data",
        label_en="Market data, costs & supply chains",
        label_ar="بيانات السوق والتكاليف وسلاسل الإمداد",
        keywords_en=[
            "market", "cost", "price", "sales", "adoption", "supply",
            "demand", "production", "capacity", "manufacturer", "vendor",
            "commercial", "industry", "kpi", "revenue", "forecast",
            "kwh", "per unit", "economics", "scaling",
        ],
        keywords_ar=[
            "سوق", "سعر", "تكلفة", "مبيعات", "اعتماد", "إمداد", "طلب",
            "إنتاج", "طاقة", "مصنع", "تجاري", "صناعة",
        ],
        probe_text=(
            "Find market data, cost benchmarks (e.g. cost per kWh, per "
            "unit), sales/adoption metrics, supply-chain flows, and "
            "manufacturing capacity related to this topic."
        ),
        companion_needs=["policy_indicators"],
    ),
    ResearchNeedArchetype(
        id="policy_indicators",
        label_en="Policy indicators & regulation",
        label_ar="مؤشرات السياسات والتنظيم",
        keywords_en=[
            "policy", "regulation", "regulatory", "government", "law",
            "standard", "compliance", "directive", "framework", "public",
            "national", "international",
        ],
        keywords_ar=[
            "سياسة", "تنظيم", "حكومي", "قانون", "معيار", "امتثال", "توجيه",
            "إطار", "عام", "وطني", "دولي",
        ],
        probe_text=(
            "Identify government policy, regulatory frameworks, compliance "
            "standards, and public-sector indicators relevant to this topic."
        ),
        companion_needs=[],
    ),
    ResearchNeedArchetype(
        id="event_tracking",
        label_en="Event tracking & narrative corroboration",
        label_ar="تتبع الأحداث والتحقق من الروايات",
        keywords_en=[
            "event", "events", "news", "geopolitical", "conflict", "actor",
            "narrative", "diplomatic", "sanctions", "protest", "crisis",
            "announcement", "statement",
        ],
        keywords_ar=[
            "حدث", "أحداث", "أخبار", "جيوسياسي", "صراع", "فاعل", "رواية",
            "دبلوماسي", "عقوبات", "احتجاج", "أزمة", "إعلان", "تصريح",
        ],
        probe_text=(
            "Track geopolitical events, conflict incidents, diplomatic "
            "moves, and competing narratives around this topic. Use "
            "multiple sources for corroboration; never invent probabilities."
        ),
        companion_needs=[],
    ),
    ResearchNeedArchetype(
        id="environmental_data",
        label_en="Environmental, agricultural & climate data",
        label_ar="البيانات البيئية والزراعية والمناخية",
        keywords_en=[
            "environment", "environmental", "climate", "agriculture",
            "crop", "yield", "waste", "recycling", "weather", "land",
            "water", "emission", "pollution", "biodiversity",
        ],
        keywords_ar=[
            "بيئة", "بيئي", "مناخ", "زراعة", "محصول", "إنتاج", "نفايات",
            "تدوير", "طقس", "أرض", "ماء", "انبعاث", "تلوث", "تنوع حيوي",
        ],
        probe_text=(
            "Find environmental, agricultural, climate, and waste/recycling "
            "statistics related to this topic. Distinguish causal effects "
            "from correlations."
        ),
        companion_needs=["policy_indicators"],
    ),
]


ARCHETYPE_BY_ID: dict[str, ResearchNeedArchetype] = {a.id: a for a in ARCHETYPES}


# ─────────────────────────────────────────────────────────────────────────────
# Need → capability-id mapping
# ─────────────────────────────────────────────────────────────────────────────

# Maps a ResearchNeedKind to the seed capability IDs that can satisfy it.
# Multiple capabilities can satisfy the same need (e.g. patent_intelligence
# is satisfied by search.patent-intelligence, but technology_signals is
# satisfied by BOTH search.github-activity and search.patent-intelligence).
# The Multi-Capability Coverage search picks the BEST match per need.

NEED_TO_CAPABILITIES: dict[ResearchNeedKind, list[str]] = {
    "scientific_literature": ["search.academic-publications"],
    "patent_intelligence": ["search.patent-intelligence"],
    "clinical_evidence": ["search.clinical-trials"],
    "technology_signals": ["search.github-activity", "search.patent-intelligence"],
    "market_data": ["search.energy-ev-datasets"],
    "policy_indicators": [
        "search.waste-recycling-statistics",
        "search.agricultural-statistics",
        "search.energy-ev-datasets",
    ],
    "event_tracking": ["search.geopolitical-events"],
    "environmental_data": [
        "search.agricultural-statistics",
        "search.waste-recycling-statistics",
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# Decomposition result
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class DetectedNeed:
    """A single detected research need in a query."""

    need: ResearchNeedKind
    label_en: str
    label_ar: str
    relevance: float
    keyword_signal: float
    semantic_signal: float
    companion_needs: list[ResearchNeedKind]


@dataclass
class DecompositionResult:
    """The full output of decomposing a query into research needs."""

    query: str
    detected_needs: list[DetectedNeed]
    implicit_needs: list[DetectedNeed]
    rejected_needs: list[DetectedNeed]


# ─────────────────────────────────────────────────────────────────────────────
# Decomposer
# ─────────────────────────────────────────────────────────────────────────────


KEYWORD_WEIGHT = 0.55
SEMANTIC_WEIGHT = 0.45
DETECTION_THRESHOLD = 0.15
PROBE_ONLY_THRESHOLD = 0.25

_PROBE_CACHE: dict[str, Vector] = {}


def _probe_embedding(archetype: ResearchNeedArchetype, embedder: Embedder) -> Vector:
    if archetype.id not in _PROBE_CACHE:
        _PROBE_CACHE[archetype.id] = embedder.encode_one(archetype.probe_text)
    return _PROBE_CACHE[archetype.id]


def _tokenize(text: str) -> set[str]:
    import re

    return {t for t in re.findall(r"\w+", text.lower(), flags=re.UNICODE) if len(t) >= 2}


def _keyword_signal(query_tokens: set[str], archetype: ResearchNeedArchetype) -> float:
    if not query_tokens:
        return 0.0
    en_tokens = {kw.lower() for kw in archetype.keywords_en}
    ar_tokens = set(archetype.keywords_ar)
    all_kw = en_tokens | ar_tokens
    if not all_kw:
        return 0.0
    overlap = query_tokens & all_kw
    if not overlap:
        return 0.0
    import math

    return min(1.0, math.log2(1 + len(overlap)) / math.log2(1 + len(all_kw)))


def decompose_query(
    query: str,
    *,
    embedder: Embedder,
    detection_threshold: float = DETECTION_THRESHOLD,
) -> DecompositionResult:
    """Decompose a natural-language query into research needs.

    Returns a :class:`DecompositionResult` with three lists:
    * ``detected_needs`` — needs that passed the threshold directly.
    * ``implicit_needs`` — needs added via companion rules (e.g. clinical
      evidence implies scientific literature). These have a relevance
      capped at 0.5 so they don't override a directly-detected need.
    * ``rejected_needs`` — needs considered but below threshold.

    The decomposition is deterministic given the same query and embedder.
    """
    query_tokens = _tokenize(query)
    query_vec = embedder.encode_one(query)
    q_norm = query_vec / (np.linalg.norm(query_vec) + 1e-12)

    scored: list[DetectedNeed] = []
    for archetype in ARCHETYPES:
        kw_signal = _keyword_signal(query_tokens, archetype)
        probe = _probe_embedding(archetype, embedder)
        p_norm = probe / (np.linalg.norm(probe) + 1e-12)
        sem_signal = float(q_norm @ p_norm)

        relevance = KEYWORD_WEIGHT * kw_signal + SEMANTIC_WEIGHT * sem_signal
        if sem_signal >= PROBE_ONLY_THRESHOLD:
            relevance = max(relevance, sem_signal * 0.85)

        scored.append(DetectedNeed(
            need=archetype.id,
            label_en=archetype.label_en,
            label_ar=archetype.label_ar,
            relevance=round(relevance, 4),
            keyword_signal=round(kw_signal, 4),
            semantic_signal=round(sem_signal, 4),
            companion_needs=list(archetype.companion_needs),
        ))

    detected = [s for s in scored if s.relevance >= detection_threshold]
    rejected = [s for s in scored if s.relevance < detection_threshold]

    detected_ids = {d.need for d in detected}
    implicit: list[DetectedNeed] = []
    implicit_ids: set[str] = set()
    for d in detected:
        for comp in d.companion_needs:
            if comp in detected_ids or comp in implicit_ids:
                continue
            comp_archetype = ARCHETYPE_BY_ID.get(comp)
            if comp_archetype is None:
                continue
            implicit.append(DetectedNeed(
                need=comp_archetype.id,
                label_en=comp_archetype.label_en,
                label_ar=comp_archetype.label_ar,
                relevance=0.5,
                keyword_signal=0.0,
                semantic_signal=0.0,
                companion_needs=[],
            ))
            implicit_ids.add(comp)

    detected.sort(key=lambda d: d.relevance, reverse=True)

    return DecompositionResult(
        query=query,
        detected_needs=detected,
        implicit_needs=implicit,
        rejected_needs=rejected,
    )


def reset_probe_cache() -> None:
    """Clear the probe-embedding cache (used by tests)."""
    _PROBE_CACHE.clear()


__all__ = [
    "ARCHETYPES",
    "ARCHETYPE_BY_ID",
    "DETECTION_THRESHOLD",
    "KEYWORD_WEIGHT",
    "NEED_TO_CAPABILITIES",
    "PROBE_ONLY_THRESHOLD",
    "SEMANTIC_WEIGHT",
    "DecompositionResult",
    "DetectedNeed",
    "ResearchNeedArchetype",
    "ResearchNeedKind",
    "decompose_query",
    "reset_probe_cache",
]
