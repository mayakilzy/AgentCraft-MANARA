"""Eight high-quality capability seed cards for the MANARA Registry (G01).

Per the owner decision:
- 8 cards covering the candidate catalog in 02_SEARCH/03_CATALOG_SEED.md
- Multilingual keywords (ar/en), synonyms, 15–30 positive examples for
  high-value cards, mandatory negative examples
- Each card is in ``candidate`` status (NOT approved) — promotion
  requires owner action per spec
- ``connector_ids`` left empty (real connectors arrive in G02)

Cards cover:
1. Academic publications (OpenAlex candidate)
2. Patent intelligence (EPO/Google Patents candidate)
3. Clinical trials (ClinicalTrials.gov candidate)
4. Energy/EV datasets (IEA/EIA candidate)
5. Agricultural statistics (FAOSTAT candidate)
6. Geopolitical events (GDELT candidate)
7. Waste/recycling statistics (OECD/Eurostat candidate)
8. Technology/code activity (GitHub metadata candidate)

The prosthetics acceptance test should retrieve:
- search.academic-publications (medical + engineering research)
- search.patent-intelligence (neural interface patents)
- search.clinical-trials (prosthetic trials)
- search.github-activity (robotics code activity)

…when the user queries "future of intelligent prosthetics" — even though
NONE of these cards literally contains the word "prosthetics" in their
display_name. This is the cross-domain semantic match the MiniLM model
enables, and it's the real acceptance test for G01.
"""

from __future__ import annotations

from manara.contracts import CapabilityGraph, SearchCapability
from manara.lifecycle import FoundryState

# ─────────────────────────────────────────────────────────────────────────────
# Card 1: Academic Publications
# ─────────────────────────────────────────────────────────────────────────────


def card_academic_publications() -> SearchCapability:
    return SearchCapability(
        id="search.academic-publications",
        version="0.1.0",
        display_name="Academic Publications Search",
        description_long=(
            "Logical search capability over scholarly publication metadata: "
            "works, authors, citations, abstracts, affiliations, and citation "
            "networks. Covers multidisciplinary literature from OpenAlex, "
            "Crossref, arXiv, and Semantic Scholar. Use for evidence-led "
            "literature review, citation chaining, author networks, and "
            "research-trend analysis across any discipline."
        ),
        author="manara-g01-seed",
        domains=["academic", "research", "science"],
        subdomains=[
            "literature", "citations", "authors", "affiliations",
            "open-access", "preprints",
        ],
        tags=[
            "publications", "papers", "citations", "doi", "openalex",
            "crossref", "arxiv", "semantic-scholar", "bibliometrics",
        ],
        keywords_en=[
            "publication", "paper", "article", "journal", "preprint",
            "citation", "author", "affiliation", "doi", "open access",
            "bibliometric", "research trend", "h-index", "citation network",
            "literature review", "systematic review", "meta-analysis",
        ],
        keywords_ar=[
            "منشور", "بحث علمي", "مقالة", "مجلة", "استشهاد", "مؤلف",
            "انتماء", "مراجعة أدبية", "اتجاه البحث", "الببليومتريا",
        ],
        synonyms=[
            "scholarly article", "research paper", "academic work",
            "peer-reviewed article", "scientific publication",
        ],
        task_intents=[
            "literature-review", "citation-chaining", "trend-analysis",
            "author-network", "affiliation-mapping", "evidence-synthesis",
        ],
        positive_examples=[
            "Find papers about sodium-ion battery manufacturing published 2020-2025",
            "Trace citation networks around a breakthrough neural interface paper",
            "Compare author productivity in precision agriculture 2018-2024",
            "Map affiliations publishing on desalination membranes",
            "Identify highly-cited preprints in solid-state battery chemistry",
            "Build a systematic review of clinical trial recruitment methods",
            "Compare open-access rates across robotics journals",
            "Find retractions in prosthetics and implant literature",
            "Trace the diffusion of a method across disciplines via citations",
            "Identify emerging research fronts in battery recycling",
            "Find co-authorship networks in Middle East AI research",
            "Track citation velocity of preprints vs. published versions",
            "Compare bibliometric productivity across universities in a region",
            "Identify interdisciplinary bridges between robotics and neuroscience",
            "Find review articles on a specific disease mechanism",
            "Locate preprints that have not yet been peer-reviewed",
            "Trace a research group's output over a decade",
            "Find papers that cite a specific foundational work",
            "Compare meta-analyses on the same clinical question",
            "Identify under-cited high-quality work in a niche",
            "Map the diffusion of CRISPR techniques across fields",
            "Find peer-reviewed evidence on a recently announced technology",
            "Trace funding acknowledgement patterns in a research area",
            "Identify journals that published retractions in a domain",
            "Find open-access versions of paywalled papers",
            "Build an evidence map for a public health question",
            "Find research-translation papers (lab to industry)",
            "Identify reproducibility studies in a field",
            "Trace the geographic distribution of authors on a topic",
            "Find citation-dense reviews suitable as starting points",
        ],
        negative_examples=[
            "Treat a preprint as peer-reviewed evidence without verification",
            "Assume citation count equals scientific quality",
            "Use author affiliation as proof of conflict of interest without disclosure check",
            "Conclude efficacy from a single in-vitro study",
            "Infer causal relationships from correlational studies",
            "Assume all listed authors contributed equally",
            "Treat a retracted paper's findings as still valid",
        ],
        coverage_geographies=["global"],
        languages=["en", "ar", "fr", "es", "zh", "de", "ja", "ko", "ru"],
        search_purposes=[
            "discovery", "evidence-synthesis", "trend-analysis",
            "citation-network", "literature-review",
        ],
        data_types=[
            "academic-publications", "citations", "authors",
            "affiliations", "abstracts",
        ],
        temporal_coverage={"earliest": "1665", "latest": "present"},
        freshness_policy="daily",
        forecast_relevance="medium",
        output_schema={"$ref": "normalized-publication-evidence-v1"},
        quality_contract={
            "requires": ["doi", "publication_date", "author_list", "venue"],
            "prefers": ["abstract", "citations", "open_access_url"],
        },
        connector_ids=[],
        source_license="review-required",
        data_reuse_rights="cache",
        commercial_rights="commercial-with-attribution",
        personal_data_policy="review-required",
        status=FoundryState.CANDIDATE,
        owner_tenant="tenant_demo",
        graph=CapabilityGraph(uses_connector=[], complements=[], specializes=[], replaces=[], conflicts_with=[]),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Card 2: Patent Intelligence
# ─────────────────────────────────────────────────────────────────────────────


def card_patent_intelligence() -> SearchCapability:
    return SearchCapability(
        id="search.patent-intelligence",
        version="0.1.0",
        display_name="Patent Intelligence Search",
        description_long=(
            "Logical search capability over patent family metadata: filing "
            "dates, assignees, classifications (IPC/CPC), claims, and patent "
            "families. Surfaces early signals of technological direction "
            "across batteries, medicine, agriculture, robotics, construction, "
            "and other engineering domains. A patent filing is evidence of an "
            "inventive step being claimed — NOT proof of efficacy, "
            "regulatory clearance, or commercial availability."
        ),
        author="manara-g01-seed",
        domains=["industry", "batteries", "medicine", "agriculture", "robotics", "construction"],
        subdomains=[
            "patent-families", "ipc-classification", "assignees",
            "claims", "filings", "prior-art",
        ],
        tags=[
            "patents", "patent-family", "ip-intelligence", "early-indicator",
            "innovation-trajectory", "filing-trends",
        ],
        keywords_en=[
            "patent", "patent family", "innovation trajectory", "assignee",
            "filing date", "ipc", "cpc", "prior art", "claim", "inventor",
            "patent landscape", "freedom-to-operate", "patent-pending",
            "granted patent", "patent application", "priority date",
        ],
        keywords_ar=[
            "براءات", "براءة اختراع", "اتجاه الابتكار", "صاحب البراءة",
            "تاريخ الإيداع", "التصنيف الدولي", "المطالبات", "المخترع",
        ],
        synonyms=[
            "ip intelligence", "patent analytics", "patent search",
            "invention disclosure", "patent family mapping",
        ],
        task_intents=[
            "technology-signals", "historical-trend", "assignee-comparison",
            "patent-landscape", "freedom-to-operate", "prior-art-search",
        ],
        positive_examples=[
            "Identify patent families about sodium-ion battery manufacturing",
            "Compare neural prosthetics patent activity by year and assignee",
            "Trace desalination membrane innovations across assignees",
            "Find filings related to precision irrigation robots",
            "Compare construction material inventions in two countries",
            "Map patent landscape for solid-state electrolytes",
            "Identify assignees dominating a specific IPC subclass",
            "Trace priority chains across jurisdictions (USPTO, EPO, WIPO)",
            "Find patent families citing a specific foundational patent",
            "Compare filing velocity before/after a regulatory change",
            "Identify emerging assignees in a new technology area",
            "Track geographic filing strategy of a multinational",
            "Find patents with claims referencing a specific material",
            "Build a patent landscape for a technology niche",
            "Identify lapsed patents in a public-domain candidate search",
            "Compare patent family sizes across competitors",
            "Find recently granted patents in a narrow CPC subclass",
            "Trace continuations and divisionals of a base filing",
            "Identify invention hot-spots by assignee country",
            "Map patent thickets in a contested technology area",
            "Find filings by academic institutions in a domain",
            "Compare patenting strategies: product vs. process claims",
            "Identify early signals of pivot in a company's R&D direction",
            "Find patents citing non-prior literature (scientific references)",
            "Map cross-licensing networks via co-assignees",
            "Track university-industry co-assigned inventions",
            "Find filings referencing standard-essential patents",
            "Identify patent applications withdrawn before grant",
            "Map citation networks between patent families",
            "Find recently published applications in a specific IPC",
        ],
        negative_examples=[
            "Prove a medical implant is safe based only on patent filing",
            "Declare patented prototype commercially shipped",
            "Measure independent inventions by raw application count without grouping families",
            "Infer regulatory approval from patent grant",
            "Treat applicant name as confirmed manufacturer",
            "Assume a granted patent is currently in force (maintenance status unchecked)",
            "Conclude market availability from patent coverage",
        ],
        coverage_geographies=["global"],
        languages=["en", "ar", "de", "fr", "ja", "zh", "ko"],
        search_purposes=[
            "discovery", "technology-signals", "historical-trend",
            "assignee-comparison", "patent-landscape",
        ],
        data_types=["patent-metadata", "patent-family", "ipc-classification", "claims"],
        temporal_coverage={"earliest": "1790", "latest": "present"},
        freshness_policy="weekly",
        forecast_relevance="high",
        output_schema={"$ref": "normalized-patent-evidence-v1"},
        quality_contract={
            "requires": ["filing_date", "assignee", "ipc_or_cpc", "family_id"],
            "prefers": ["claims_text", "priority_date", "grant_date"],
        },
        connector_ids=[],
        source_license="review-required",
        data_reuse_rights="cache",
        commercial_rights="commercial-with-attribution",
        personal_data_policy="review-required",
        status=FoundryState.CANDIDATE,
        owner_tenant="tenant_demo",
        graph=CapabilityGraph(uses_connector=[], complements=["search.academic-publications"], specializes=[], replaces=[], conflicts_with=[]),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Card 3: Clinical Trials
# ─────────────────────────────────────────────────────────────────────────────


def card_clinical_trials() -> SearchCapability:
    return SearchCapability(
        id="search.clinical-trials",
        version="0.1.0",
        display_name="Clinical Trials Registry Search",
        description_long=(
            "Logical search capability over clinical trial registrations: "
            "phases, enrollment status, interventions, sponsors, outcome "
            "measures, and results postings. Surfaces the regulatory and "
            "evidentiary backbone behind medical and biomedical claims. "
            "A trial registration is evidence a trial was planned — NOT "
            "proof of efficacy, safety, or regulatory approval."
        ),
        author="manara-g01-seed",
        domains=["medicine", "health", "biomedical", "regulatory"],
        subdomains=[
            "trial-registration", "phases", "interventions", "sponsors",
            "outcomes", "regulatory-pathways",
        ],
        tags=[
            "clinical-trials", "clinicaltrials-gov", "regulatory",
            "phase-1", "phase-2", "phase-3", "phase-4", "interventional",
            "observational", "adverse-events",
        ],
        keywords_en=[
            "clinical trial", "trial registration", "phase", "enrollment",
            "intervention", "placebo", "randomized", "blinded", "primary endpoint",
            "secondary endpoint", "adverse event", "safety", "efficacy",
            "regulatory submission", "investigational new drug", "IND",
            "biomarker", "comparator",
        ],
        keywords_ar=[
            "تجربة سريرية", "تسجيل التجارب", "المرحلة", "التجنيد",
            "التدخل", "الغفل", "النقطة النهائية", "الحدث الضار", "السلامة",
        ],
        synonyms=[
            "clinical study", "interventional study", "registry trial",
            "CT.gov", "EudraCT", "ISRCTN",
        ],
        task_intents=[
            "regulatory-pathway-analysis", "evidence-synthesis",
            "safety-signal-monitoring", "trial-completion-tracking",
        ],
        positive_examples=[
            "Find interventional trials on neural interface prosthetics",
            "Compare phase-3 enrollment sizes for sodium-glucose cotransporter inhibitors",
            "Identify sponsors of pediatric oncology trials in a region",
            "Trace completion rates of trials registered 2018-2022",
            "Find trials posting results within 1 year of completion",
            "Map geographic distribution of trial sites for a disease",
            "Identify trials terminated early and the cited reasons",
            "Find trials using a specific biomarker as primary endpoint",
            "Compare intervention arms across trials of the same drug class",
            "Identify adaptive-design trials in a therapeutic area",
            "Find trials with delayed results posting (>1 year overdue)",
            "Trace Investigational New Drug applications to subsequent trials",
            "Find trials of pediatric medical devices",
            "Map sponsorship patterns: industry vs. academic vs. government",
            "Identify trials enrolling in multiple jurisdictions",
            "Find trials with adaptive or basket designs",
            "Compare registered primary endpoints vs. published results",
            "Identify trials of gene therapies in a specific indication",
            "Find first-in-human trials of a novel device class",
            "Trace historical trends in trial registration for a disease",
            "Find trials using real-world-evidence comparators",
            "Identify trials with biomarker-stratified enrollment",
            "Map trial networks in a specific therapeutic area",
            "Find trials of repurposed drugs",
            "Identify trials terminated for futility vs. safety",
            "Find trials with published protocols",
            "Trace trial registration before and after a regulatory change",
            "Find trials enrolling pediatric populations",
            "Identify trials with adaptive sample-size re-estimation",
            "Map trials sponsored by patient advocacy groups",
        ],
        negative_examples=[
            "Conclude efficacy from a phase-1 safety trial",
            "Treat trial registration as proof the intervention works",
            "Infer regulatory approval from trial completion",
            "Assume published results match the registered primary endpoint",
            "Use early-phase trial results as definitive evidence",
            "Conclude safety from a small single-arm trial",
            "Treat observational trial results as interventional evidence",
        ],
        coverage_geographies=["global"],
        languages=["en", "ar", "es", "fr", "zh", "ja", "de"],
        search_purposes=[
            "regulatory-evidence", "safety-monitoring", "trial-completion",
            "evidence-synthesis",
        ],
        data_types=[
            "trial-registration", "trial-results", "phases",
            "interventions", "sponsors", "outcomes",
        ],
        temporal_coverage={"earliest": "1999", "latest": "present"},
        freshness_policy="daily",
        forecast_relevance="medium",
        output_schema={"$ref": "normalized-clinical-trial-evidence-v1"},
        quality_contract={
            "requires": ["nct_id", "phase", "enrollment_status", "intervention"],
            "prefers": ["primary_endpoint", "results_posted", "sponsor"],
        },
        connector_ids=[],
        source_license="review-required",
        data_reuse_rights="cache",
        commercial_rights="commercial-with-attribution",
        personal_data_policy="strict-no-patient-data",
        status=FoundryState.CANDIDATE,
        owner_tenant="tenant_demo",
        graph=CapabilityGraph(uses_connector=[], complements=["search.academic-publications"], specializes=[], replaces=[], conflicts_with=[]),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Card 4: Energy & EV Datasets
# ─────────────────────────────────────────────────────────────────────────────


def card_energy_ev_datasets() -> SearchCapability:
    return SearchCapability(
        id="search.energy-ev-datasets",
        version="0.1.0",
        display_name="Energy & EV Datasets Search",
        description_long=(
            "Logical search capability over energy and electric-vehicle "
            "datasets: battery pack and cell costs, manufacturing capacity, "
            "charging infrastructure, electricity generation mix, and supply "
            "chain flows. Distinguishes lab benchmarks from commercial-scale "
            "metrics. Per the MANARA spec: cell-level metrics must NOT be "
            "confused with pack-level metrics."
        ),
        author="manara-g01-seed",
        domains=["energy", "automotive", "manufacturing", "supply-chain"],
        subdomains=[
            "battery-cost", "ev-sales", "charging-infrastructure",
            "electricity-generation", "critical-minerals", "manufacturing-capacity",
        ],
        tags=[
            "iea", "eia", "battery-cost", "ev-adoption",
            "charging-stations", "lithium", "cobalt", "nickel",
            "grid-mix", "capacity-factor",
        ],
        keywords_en=[
            "battery cost per kwh", "ev sales", "charging infrastructure",
            "lithium price", "cobalt supply", "nickel demand",
            "grid emission factor", "capacity factor", "levelized cost",
            "lcoe", "cell vs pack", "energy density", "cathode chemistry",
            "supply chain", "critical minerals",
        ],
        keywords_ar=[
            "تكلفة البطارية", "مبيعات السيارات الكهربائية",
            "شبكة الشحن", "الليثيوم", "الكوبالت", "النيكل",
            "عامل السعة", "كثافة الطاقة",
        ],
        synonyms=[
            "EV market data", "battery market intelligence",
            "energy transition datasets", "clean energy statistics",
        ],
        task_intents=[
            "market-forecast", "supply-chain-analysis",
            "policy-impact-assessment", "cost-trajectory-analysis",
        ],
        positive_examples=[
            "Track pack-level Li-ion cost per kWh from 2015 to 2024",
            "Compare cell-level vs. pack-level costs across chemistries",
            "Identify countries leading in EV charging infrastructure deployment",
            "Map cobalt supply concentration by country of origin",
            "Trace grid emission factor changes in a region over a decade",
            "Find LCOE benchmarks for utility-scale solar 2020-2024",
            "Compare EV adoption rates across jurisdictions",
            "Identify critical mineral supply risks for a battery chemistry",
            "Track manufacturing capacity announcements vs. operational capacity",
            "Find public datasets on residential EV charging patterns",
            "Map regional concentration of cathode production",
            "Compare lab-scale vs. commercial-scale battery performance",
            "Identify grid bottlenecks in high-EV-adoption regions",
            "Trace historical lithium price volatility",
            "Find capacity-factor data for offshore wind farms",
            "Compare announced vs. operational gigafactory capacity",
            "Map nickel supply chains by origin and processing country",
            "Find EV battery second-life applications datasets",
            "Identify V2G (vehicle-to-grid) pilot programmes",
            "Trace critical mineral recycling rates by jurisdiction",
            "Find public datasets on grid flexibility and storage",
            "Compare battery degradation curves across chemistries",
            "Identify announced cathode chemistry transitions",
            "Map EV incentive policy changes and adoption responses",
            "Find datasets on fast-charging deployment",
            "Trace solid-state battery pilot announcements",
            "Identify grid-scale storage installations by chemistry",
            "Compare LCOE across regions for the same technology",
            "Find public data on consumer EV charging behavior",
        ],
        negative_examples=[
            "Confuse cell-level cost with pack-level cost",
            "Treat a lab benchmark as a commercial-scale metric",
            "Infer grid emission factor from generation capacity alone",
            "Assume announced capacity equals operational capacity",
            "Conclude supply security from current production concentration",
            "Treat a one-off pilot as scaled commercial availability",
            "Infer EV adoption from charging infrastructure alone",
        ],
        coverage_geographies=["global"],
        languages=["en", "ar", "zh", "de", "ja", "fr"],
        search_purposes=[
            "market-forecast", "supply-chain-analysis",
            "policy-impact", "cost-trajectory",
        ],
        data_types=[
            "time-series", "supply-chain-flows", "cost-benchmarks",
            "capacity-data", "adoption-metrics",
        ],
        temporal_coverage={"earliest": "1990", "latest": "present"},
        freshness_policy="monthly",
        forecast_relevance="high",
        output_schema={"$ref": "normalized-energy-evidence-v1"},
        quality_contract={
            "requires": ["value", "unit", "region", "year"],
            "prefers": ["methodology", "source_url", "revision_date"],
        },
        connector_ids=[],
        source_license="review-required",
        data_reuse_rights="cache",
        commercial_rights="non-commercial",
        personal_data_policy="review-required",
        status=FoundryState.CANDIDATE,
        owner_tenant="tenant_demo",
        graph=CapabilityGraph(uses_connector=[], complements=["search.academic-publications", "search.patent-intelligence"], specializes=[], replaces=[], conflicts_with=[]),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Card 5: Agricultural Statistics
# ─────────────────────────────────────────────────────────────────────────────


def card_agricultural_statistics() -> SearchCapability:
    return SearchCapability(
        id="search.agricultural-statistics",
        version="0.1.0",
        display_name="Agricultural Statistics Search",
        description_long=(
            "Logical search capability over agricultural datasets: crop "
            "production, yields, land use, climate-agriculture indicators, "
            "irrigation, fertilizer consumption, and food trade flows. "
            "Bridges agronomic data (FAOSTAT), climate data (NASA POWER, "
            "Copernicus), and trade data (UN Comtrade). Distinguishes "
            "causal effects from correlations."
        ),
        author="manara-g01-seed",
        domains=["agriculture", "food", "climate", "trade"],
        subdomains=[
            "crop-production", "yields", "land-use", "irrigation",
            "fertilizer", "food-trade", "climate-agriculture",
        ],
        tags=[
            "faostat", "nasa-power", "copernicus", "crop-yield",
            "irrigation", "fertilizer", "food-security", "agri-trade",
        ],
        keywords_en=[
            "crop yield", "agricultural production", "irrigated area",
            "fertilizer consumption", "food trade", "arable land",
            "harvested area", "crop calendar", "growing season",
            "drought index", "NDVI",
        ],
        keywords_ar=[
            "إنتاج المحاصيل", "محصول الزراعة", "مساحة الأراضي المروية",
            "استهلاك الأسمدة", "تجارة الغذاء", "الأراضي الصالحة للزراعة",
        ],
        synonyms=[
            "agri-statistics", "food and agriculture data",
            "crop metrics", "agronomic data",
        ],
        task_intents=[
            "trend-analysis", "food-security-assessment",
            "yield-forecast", "trade-flow-analysis",
        ],
        positive_examples=[
            "Track wheat yield trends in North Africa 2000-2024",
            "Compare irrigated vs. rainfed area for a crop across countries",
            "Map fertilizer consumption intensity by region",
            "Identify countries with declining arable land per capita",
            "Trace food trade flows for a commodity during a crisis",
            "Find NDVI time series for a specific region",
            "Compare crop calendars across climate zones",
            "Identify drought-impact signals in yield data",
            "Track adoption of drip irrigation by country",
            "Map crop diversification patterns over a decade",
            "Find Copernicus NDVI anomalies for a region",
            "Compare cereal yield growth rates across continents",
            "Identify food-import-dependent countries",
            "Trace historical shifts in cropping patterns",
            "Find NASA POWER climate-agriculture indicators",
            "Map yield gaps between regions with similar climate",
            "Identify regions with rapid irrigation expansion",
            "Track fertilizer price and consumption decoupling",
            "Find regions with persistent yield stagnation",
            "Compare cropping intensity across irrigation regimes",
            "Identify under-reported crops in national statistics",
            "Map trade-network changes after a policy shock",
            "Find regions where climate trends align with yield shifts",
            "Trace historical land-use change trajectories",
            "Compare organic vs. conventional yield statistics",
            "Identify climate-driven yield volatility hotspots",
            "Find smallholder yield benchmarks in a region",
            "Map regional concentration of staple crop production",
            "Trace soil degradation signals in long-term yield series",
        ],
        negative_examples=[
            "Infer causation from correlation between climate and yield",
            "Compare yields across regions without controlling for irrigation",
            "Treat a single year's anomaly as a trend",
            "Assume national statistics reflect smallholder reality",
            "Confuse harvested area with planted area",
            "Infer food security from production alone (ignoring trade)",
        ],
        coverage_geographies=["global"],
        languages=["en", "ar", "fr", "es", "zh"],
        search_purposes=[
            "trend-analysis", "food-security",
            "yield-forecast", "trade-flow-analysis",
        ],
        data_types=[
            "time-series", "spatial-data", "trade-flows",
            "land-use-metrics", "yield-data",
        ],
        temporal_coverage={"earliest": "1961", "latest": "present"},
        freshness_policy="annual",
        forecast_relevance="high",
        output_schema={"$ref": "normalized-agricultural-evidence-v1"},
        quality_contract={
            "requires": ["value", "unit", "country_or_region", "year"],
            "prefers": ["methodology", "source_url", "revision_history"],
        },
        connector_ids=[],
        source_license="review-required",
        data_reuse_rights="cache",
        commercial_rights="commercial-with-attribution",
        personal_data_policy="review-required",
        status=FoundryState.CANDIDATE,
        owner_tenant="tenant_demo",
        graph=CapabilityGraph(uses_connector=[], complements=["search.energy-ev-datasets"], specializes=[], replaces=[], conflicts_with=[]),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Card 6: Geopolitical Events
# ─────────────────────────────────────────────────────────────────────────────


def card_geopolitical_events() -> SearchCapability:
    return SearchCapability(
        id="search.geopolitical-events",
        version="0.1.0",
        display_name="Geopolitical Events Search",
        description_long=(
            "Logical search capability over event-data feeds: GDELT, ACLED "
            "(where licensed), and curated geopolitical event datasets. "
            "Surfaces event counts, actor attribution, and source "
            "corroboration. NEVER infers causation or invented probabilities; "
            "every event is paired with its source for verification. "
            "Competing narratives are preserved."
        ),
        author="manara-g01-seed",
        domains=["geopolitics", "events", "media", "conflict"],
        subdomains=[
            "event-data", "actor-attribution", "source-corroboration",
            "competing-narratives", "conflict-tracking",
        ],
        tags=[
            "gdelt", "acled", "event-data", "actor-attribution",
            "source-corroboration", "competing-narratives",
        ],
        keywords_en=[
            "geopolitical event", "actor attribution", "event count",
            "source corroboration", "competing narrative", "conflict event",
            "protest event", "diplomatic event", "trade dispute",
            "sanctions event",
        ],
        keywords_ar=[
            "حدث جيوسياسي", "الحدث", "نسبة الفاعل", "مصدر موثق",
            "روايات متنافسة", "صراع", "احتجاج",
        ],
        synonyms=[
            "political event data", "conflict tracking",
            "news event extraction",
        ],
        task_intents=[
            "event-tracking", "narrative-comparison",
            "conflict-monitoring", "diplomatic-trend-analysis",
        ],
        positive_examples=[
            "Track event counts for a region over time",
            "Compare competing narratives around a specific event",
            "Find events attributed to a specific actor",
            "Identify corroboration patterns across sources",
            "Trace diplomatic event trends between two countries",
            "Map event-data coverage gaps for a region",
            "Identify spikes in protest events in a period",
            "Compare GDELT and ACLED coverage for a conflict",
            "Find events with high source-disagreement",
            "Trace sanctions imposition events",
            "Identify trade dispute event patterns",
            "Map cross-border event attribution",
            "Find events with delayed source corroboration",
            "Compare event tone across sources",
            "Identify under-reported event types",
            "Trace event-actor network centrality",
            "Find events with multiple actor attributions",
            "Compare event data revisions over time",
            "Identify event bursts around policy changes",
            "Map geographic clustering of events",
            "Find events with conflicting casualty counts",
            "Trace narrative shifts in coverage of an issue",
            "Identify recurring event patterns",
            "Find events with rapid corroboration",
            "Map event propagation across sources",
            "Identify source-specific event coverage biases",
            "Trace regional escalation patterns",
            "Find events with uncorroborated claims",
            "Map actor co-occurrence in event data",
            "Identify events with no actor attribution",
        ],
        negative_examples=[
            "Infer causation from event correlation",
            "Treat event count as proof of ground truth",
            "Invent probabilities for future events",
            "Treat single-source events as fully corroborated",
            "Conclude actor intent from event attribution alone",
            "Compare event counts across datasets without normalization",
            "Treat protest event count as direct public opinion measure",
        ],
        coverage_geographies=["global"],
        languages=["en", "ar", "fr", "es", "zh", "ru"],
        search_purposes=[
            "event-tracking", "narrative-comparison",
            "conflict-monitoring", "trend-analysis",
        ],
        data_types=[
            "event-data", "actor-attribution", "source-metadata",
            "tone-scores", "geocoded-events",
        ],
        temporal_coverage={"earliest": "1979", "latest": "present"},
        freshness_policy="daily",
        forecast_relevance="low",
        output_schema={"$ref": "normalized-event-evidence-v1"},
        quality_contract={
            "requires": ["event_date", "source_url", "actor_attribution"],
            "prefers": ["geocode", "tone_score", "corroboration_count"],
        },
        connector_ids=[],
        source_license="review-required",
        data_reuse_rights="cache",
        commercial_rights="non-commercial",
        personal_data_policy="strict-no-PII",
        status=FoundryState.CANDIDATE,
        owner_tenant="tenant_demo",
        graph=CapabilityGraph(uses_connector=[], complements=[], specializes=[], replaces=[], conflicts_with=[]),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Card 7: Waste & Recycling Statistics
# ─────────────────────────────────────────────────────────────────────────────


def card_waste_recycling_statistics() -> SearchCapability:
    return SearchCapability(
        id="search.waste-recycling-statistics",
        version="0.1.0",
        display_name="Waste & Recycling Statistics Search",
        description_long=(
            "Logical search capability over waste and recycling datasets: "
            "OECD, Eurostat, UNEP, and national statistical agencies. "
            "Surfaces waste generation, processing rates, material recovery, "
            "and policy indicators. Critical: compares only series with the "
            "same denominator, geography, and measurement definition."
        ),
        author="manara-g01-seed",
        domains=["waste", "recycling", "environment", "policy"],
        subdomains=[
            "waste-generation", "material-recovery", "processing-rates",
            "policy-indicators", "circular-economy",
        ],
        tags=[
            "oecd", "eurostat", "unep", "waste-statistics",
            "recycling-rate", "material-recovery", "circular-economy",
        ],
        keywords_en=[
            "municipal waste", "recycling rate", "material recovery",
            "waste generation", "e-waste", "plastic waste",
            "circular economy", "landfill diversion", "incineration rate",
            "composting rate",
        ],
        keywords_ar=[
            "النفايات البلدية", "معدل إعادة التدوير", "استرجاع المواد",
            "توليد النفايات", "النفايات الإلكترونية", "الاقتصاد الدائري",
        ],
        synonyms=[
            "waste management statistics", "circular economy data",
            "material flow analysis",
        ],
        task_intents=[
            "trend-analysis", "policy-impact-assessment",
            "cross-country-comparison", "indicator-tracking",
        ],
        positive_examples=[
            "Compare municipal waste generation per capita across OECD countries",
            "Track recycling rate trends in the EU 2010-2024",
            "Find e-waste collection rates by country",
            "Map plastic waste trade flows post-2018 policy changes",
            "Identify countries with stagnating recycling rates",
            "Compare landfill diversion rates across regions",
            "Trace material recovery rate changes after policy interventions",
            "Find UNEP indicators for circular economy progress",
            "Map incineration capacity deployment by country",
            "Compare composting rates in regions with similar climate",
            "Identify countries with rising e-waste generation",
            "Trace hazardous waste trends in a region",
            "Find construction-and-demolition waste recovery rates",
            "Map organic waste composting infrastructure",
            "Compare packaging waste recycling rates across jurisdictions",
            "Identify policy-driven inflection points in waste trends",
            "Find textile waste generation trends",
            "Trace battery collection rates for recycling",
            "Map waste-to-energy capacity deployment",
            "Compare recycling rate methodologies across datasets",
            "Identify under-reported waste streams in national statistics",
            "Find food waste generation estimates",
            "Trace trade flows of recycled materials",
            "Map informal-sector waste recovery in developing countries",
            "Compare extended producer responsibility schemes",
            "Find deposit-return-system performance indicators",
            "Trace single-use-plastics policy impacts on waste streams",
            "Map regional disparities in waste infrastructure",
            "Identify circular-economy indicator frameworks",
        ],
        negative_examples=[
            "Compare recycling rates across countries without checking methodology",
            "Treat tonnage as proof of material recovery (quality unknown)",
            "Infer policy impact from correlation alone",
            "Compare rates across different waste-stream definitions",
            "Assume reported rates equal actual recovery rates",
            "Confuse collection rate with recycling rate",
        ],
        coverage_geographies=["global", "eu", "oecd"],
        languages=["en", "ar", "fr", "de", "es"],
        search_purposes=[
            "trend-analysis", "policy-impact",
            "cross-country-comparison", "indicator-tracking",
        ],
        data_types=[
            "time-series", "policy-indicators", "material-flows",
            "capacity-data", "trade-flows",
        ],
        temporal_coverage={"earliest": "1990", "latest": "present"},
        freshness_policy="annual",
        forecast_relevance="medium",
        output_schema={"$ref": "normalized-waste-evidence-v1"},
        quality_contract={
            "requires": ["value", "unit", "country_or_region", "year", "methodology"],
            "prefers": ["source_url", "revision_history"],
        },
        connector_ids=[],
        source_license="review-required",
        data_reuse_rights="cache",
        commercial_rights="non-commercial",
        personal_data_policy="review-required",
        status=FoundryState.CANDIDATE,
        owner_tenant="tenant_demo",
        graph=CapabilityGraph(uses_connector=[], complements=["search.energy-ev-datasets"], specializes=[], replaces=[], conflicts_with=[]),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Card 8: GitHub Activity / Code Intelligence
# ─────────────────────────────────────────────────────────────────────────────


def card_github_activity() -> SearchCapability:
    return SearchCapability(
        id="search.github-activity",
        version="0.1.0",
        display_name="GitHub Activity & Code Intelligence Search",
        description_long=(
            "Logical search capability over public GitHub repository "
            "metadata: activity signals, releases, license types, language "
            "distribution, and model release metadata (Hugging Face public). "
            "Useful for technology-adoption signals, open-source momentum, "
            "and code-license reconnaissance. Activity signals are evidence "
            "of community engagement — NOT proof of production readiness, "
            "safety, or commercial viability."
        ),
        author="manara-g01-seed",
        domains=["technology", "open-source", "ai", "software"],
        subdomains=[
            "repository-activity", "release-tracking", "license-analysis",
            "language-distribution", "model-releases",
        ],
        tags=[
            "github", "open-source", "repository-activity", "releases",
            "huggingface", "model-cards", "license-intelligence",
        ],
        keywords_en=[
            "repository stars", "release velocity", "open source momentum",
            "license type", "language distribution", "forks",
            "commits per week", "open issues", "closed PRs",
            "model release", "model card",
        ],
        keywords_ar=[
            "مستودع", "نشاط المستودع", "إصدارات", "ترخيص مفتوح المصدر",
            "توزيع اللغات",
        ],
        synonyms=[
            "code activity signals", "OSS intelligence",
            "repository metadata", "developer activity",
        ],
        task_intents=[
            "technology-adoption-tracking", "license-reconnaissance",
            "release-monitoring", "momentum-analysis",
        ],
        positive_examples=[
            "Identify repositories with rising star velocity in robotics",
            "Track release cadence of a popular ML framework",
            "Map license distribution in a code ecosystem",
            "Find repositories with sustained contributor growth",
            "Compare activity levels across competing libraries",
            "Identify open-source alternatives to a commercial product",
            "Trace language distribution shifts in a domain",
            "Find recently released model cards in a niche",
            "Map fork velocity as a momentum indicator",
            "Identify repositories with healthy issue-closure rates",
            "Track open-source momentum in battery modeling tools",
            "Find license-permissive repos for a specific task",
            "Compare commit frequency across similar projects",
            "Identify abandoned vs. actively maintained projects",
            "Trace release tags and changelogs of a library",
            "Find emerging repositories in a new technology area",
            "Map repository interdependencies via dependency graphs",
            "Identify projects transitioning to governance models",
            "Track sponsor funding patterns in OSS",
            "Find repositories with high test-coverage signals",
            "Compare PR review latency across projects",
            "Identify security-advisory activity in a dependency tree",
            "Trace contributor geographic distribution",
            "Find repositories with active maintainer response",
            "Map license compatibility for a stack",
            "Identify repositories being deprecated or archived",
            "Track Hugging Face model release trends",
            "Find code with permissive commercial-use licenses",
            "Identify robotically-trending repositories in a domain",
        ],
        negative_examples=[
            "Treat star count as proof of production readiness",
            "Infer software safety from activity alone",
            "Assume open-source equals commercially usable (license check required)",
            "Conclude commercial viability from community momentum",
            "Treat a model card as proof of model safety",
            "Infer code quality from commit frequency",
            "Treat sponsorship as proof of long-term maintenance",
        ],
        coverage_geographies=["global"],
        languages=["en", "ar", "zh", "ja", "es", "fr", "de", "ru"],
        search_purposes=[
            "technology-adoption", "license-reconnaissance",
            "momentum-analysis", "release-monitoring",
        ],
        data_types=[
            "repository-metadata", "release-events", "license-metadata",
            "contributor-activity", "language-stats",
        ],
        temporal_coverage={"earliest": "2008", "latest": "present"},
        freshness_policy="daily",
        forecast_relevance="low",
        output_schema={"$ref": "normalized-github-activity-evidence-v1"},
        quality_contract={
            "requires": ["repo_url", "license", "last_commit_at"],
            "prefers": ["stars", "open_issues_count", "release_tag"],
        },
        connector_ids=[],
        source_license="review-required",
        data_reuse_rights="cache",
        commercial_rights="commercial-with-attribution",
        personal_data_policy="review-required",
        status=FoundryState.CANDIDATE,
        owner_tenant="tenant_demo",
        graph=CapabilityGraph(uses_connector=[], complements=["search.academic-publications"], specializes=[], replaces=[], conflicts_with=[]),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Registry of all seed cards
# ─────────────────────────────────────────────────────────────────────────────


SEED_CAPABILITIES: list[SearchCapability] = [
    card_academic_publications(),
    card_patent_intelligence(),
    card_clinical_trials(),
    card_energy_ev_datasets(),
    card_agricultural_statistics(),
    card_geopolitical_events(),
    card_waste_recycling_statistics(),
    card_github_activity(),
]


# Domain → expected-card mapping used by the prosthetics acceptance test
# (intentionally NOT a hard mapping the search uses; this is for tests only)
DOMAIN_SIGNAL_MAP: dict[str, list[str]] = {
    "academic": ["search.academic-publications"],
    "patents": ["search.patent-intelligence"],
    "medicine": ["search.clinical-trials", "search.academic-publications"],
    "energy": ["search.energy-ev-datasets"],
    "agriculture": ["search.agricultural-statistics"],
    "events": ["search.geopolitical-events"],
    "waste": ["search.waste-recycling-statistics"],
    "code": ["search.github-activity"],
}


__all__ = [
    "SEED_CAPABILITIES",
    "DOMAIN_SIGNAL_MAP",
    "card_academic_publications",
    "card_agricultural_statistics",
    "card_clinical_trials",
    "card_energy_ev_datasets",
    "card_github_activity",
    "card_geopolitical_events",
    "card_patent_intelligence",
    "card_waste_recycling_statistics",
]
