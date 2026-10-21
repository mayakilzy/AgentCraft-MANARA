/* ============================================================
   MANARA API client — typed wrapper around the Manara backend.

   In development (Vite dev server), the Vite proxy forwards
   /status and /mold-factory/* to the real backend at
   http://localhost:8000 (configurable via VITE_API_TARGET).

   When the backend is unreachable, the client falls back to
   deterministic development fixtures so the UI can be visually
   tested. Every response carries `_source: 'live' | 'fixture'`
   so the UI can label fixture data honestly.

   In production, set VITE_API_BASE to the backend URL.
   ============================================================ */

export type CoverageLevel = 'NONE' | 'CATALOG' | 'OPERATIONAL' | 'VERIFIED';
export type DeliverableType = 'research_deliverable' | 'coverage_blocker_report';

export interface DetectedNeed {
  need: string;
  label_en: string;
  label_ar: string;
  relevance: number;
}

export interface CoverageEntry {
  need: string;
  need_label: string;
  selected_capability_id: string | null;
  coverage_level: CoverageLevel;
  connector_ids: string[];
  selection_reasoning: string;
  operational_gap_recorded: boolean;
}

export interface GapEntry {
  need: string;
  need_label: string;
  foundry_resolution: string;
  resolution_notes: string;
  catalog_capability_id: string | null;
  coverage_level: CoverageLevel;
}

export interface ComposeResponse {
  query: string;
  investigation_id: string;
  mold_recipe_id: string;
  is_unknown_domain: boolean;
  detection_reasoning: string;
  detected_needs: DetectedNeed[];
  coverage: CoverageEntry[];
  gaps: GapEntry[];
  is_complete: boolean;
  is_catalog_complete: boolean;
  deliverable_type: DeliverableType;
  composition_notes: string;
  composed_at: string;
  /** Added by the client — never trust the backend for this flag */
  _source: 'live' | 'fixture';
}

export interface StatusResponse {
  app: string;
  version: string;
  description: string;
  env: string;
  discovery_mode: 'synthetic' | 'live';
  timestamp_utc: string;
  capabilities: string[];
  not_implemented: string[];
  database_url_kind: string;
  /** Added by the client — never trust the backend for this flag */
  _source: 'live' | 'fixture';
}

export class ManaraApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly detail?: unknown,
  ) {
    super(message);
    this.name = 'ManaraApiError';
  }
}

// In Vite, use import.meta.env instead of process.env
const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) || '';

/* ============================================================
   Deterministic development fixtures
   Used when the backend is unreachable. The same query always
   yields the same composition, so the UI can be visually tested.
   ============================================================ */

function hashQuery(query: string): number {
  let h = 0;
  for (let i = 0; i < query.length; i++) {
    h = ((h << 5) - h + query.charCodeAt(i)) | 0;
  }
  return Math.abs(h);
}

function fixtureStatus(): StatusResponse {
  return {
    app: 'MANARA',
    version: '0.1.0',
    description: 'Adaptive Intelligence Factory (development fixture)',
    env: 'development',
    discovery_mode: 'synthetic',
    timestamp_utc: new Date().toISOString(),
    capabilities: [
      'registry:capability_crud',
      'registry:hybrid_search',
      'foundry:openalex_connector',
      'memory:evidence_ingestion',
      'mold_factory:mold_architect',
      'agents:ephemeral_runtime',
      'foresight:baseline_forecaster',
      'publishing:quality_gate',
    ],
    not_implemented: [
      'multi_tenant_authn',
      'live_llm_execution',
      'live_search_verified',
    ],
    database_url_kind: 'sqlite',
    _source: 'fixture',
  };
}

function fixtureCompose(query: string): ComposeResponse {
  const h = hashQuery(query);
  const isComplete = h % 3 === 0; // ~33% chance of complete
  const isBlocker = !isComplete && h % 2 === 0; // ~33% blocker, ~33% partial

  const needs = [
    { need: 'scientific_literature', label_en: 'Scientific Literature', label_ar: 'الأدبيات العلمية', relevance: 0.95 },
    { need: 'patent_intelligence', label_en: 'Patent Intelligence', label_ar: 'ذكاء براءات الاختراع', relevance: 0.72 },
    { need: 'clinical_evidence', label_en: 'Clinical Evidence', label_ar: 'الأدلة السريرية', relevance: 0.68 },
    { need: 'technology_signals', label_en: 'Technology Signals', label_ar: 'إشارات التقنية', relevance: 0.55 },
  ].slice(0, 2 + (h % 3)); // 2-4 needs

  const coverageLevels: CoverageLevel[] = ['VERIFIED', 'OPERATIONAL', 'CATALOG', 'NONE'];
  const coverage = needs.map((n, i) => ({
    need: n.need,
    need_label: n.label_en,
    selected_capability_id: i === 0 ? 'search.academic-publications' : null,
    coverage_level: coverageLevels[(h + i) % 4],
    connector_ids: i === 0 ? ['openalex-v1'] : [],
    selection_reasoning: i === 0
      ? 'OpenAlex connector provides operational access to academic publications.'
      : 'No approved connector available for this capability.',
    operational_gap_recorded: i > 0,
  }));

  const gaps = coverage
    .filter((c) => c.coverage_level === 'NONE' || c.coverage_level === 'CATALOG')
    .map((c) => ({
      need: c.need,
      need_label: c.need_label,
      foundry_resolution: c.coverage_level === 'CATALOG' ? 'foundry_no_candidate' : 'no_capability',
      resolution_notes: c.coverage_level === 'CATALOG'
        ? 'A capability card exists but no approved connector is registered.'
        : 'No capability card matches this research need.',
      catalog_capability_id: c.coverage_level === 'CATALOG' ? c.selected_capability_id : null,
      coverage_level: c.coverage_level,
    }));

  const isCatalogComplete = coverage.every((c) => c.coverage_level !== 'NONE');

  return {
    query,
    investigation_id: `inv-fixture-${h.toString(36).padStart(8, '0')}`,
    mold_recipe_id: `mold-fixture-${h.toString(36).padStart(8, '0')}`,
    is_unknown_domain: h % 5 === 0,
    detection_reasoning: 'No existing reusable mold matched this query. A new temporary mold was composed.',
    detected_needs: needs,
    coverage,
    gaps,
    is_complete: isComplete,
    is_catalog_complete: isCatalogComplete,
    deliverable_type: isComplete ? 'research_deliverable' : 'coverage_blocker_report',
    composition_notes: `Composed temporary mold with ${needs.length} need(s), ${coverage.length} coverage entr(ies), ${gaps.length} gap(s).`,
    composed_at: new Date().toISOString(),
    _source: 'fixture',
  };
}

/* ============================================================
   API methods
   ============================================================ */

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API_BASE}${url}`, {
    ...init,
    headers: { Accept: 'application/json', ...(init?.headers || {}) },
  });
  if (!r.ok) {
    let detail: unknown;
    try {
      detail = await r.json();
    } catch {
      detail = await r.text();
    }
    throw new ManaraApiError(r.status, `Request to ${url} failed`, detail);
  }
  return (await r.json()) as T;
}

export const manaraApi = {
  async status(): Promise<StatusResponse> {
    try {
      const r = await fetchJson<StatusResponse>('/status');
      return { ...r, _source: 'live' as const };
    } catch {
      return fixtureStatus();
    }
  },

  async compose(query: string): Promise<ComposeResponse> {
    try {
      const r = await fetchJson<ComposeResponse>('/mold-factory/compose', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
      });
      return { ...r, _source: 'live' as const };
    } catch {
      // Backend unreachable — return deterministic fixture
      return fixtureCompose(query);
    }
  },
} as const;
