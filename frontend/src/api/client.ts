/**
 * MANARA API client — typed wrapper around the G00 + G01 backend surface.
 *
 * G00 endpoints: /status, /health, /discovery (synthetic), /contracts/schemas.
 * G01 endpoints: /registry/* (CRUD + search + promotions + evaluations + reindex).
 */

export interface StatusResponse {
  app: string;
  version: string;
  description: string;
  env: string;
  discovery_mode: "synthetic" | "live";
  timestamp_utc: string;
  build: Record<string, string>;
  capabilities: string[];
  not_implemented: string[];
  database_url_kind: string;
}

export interface SearchCapability {
  id: string;
  kind: "search-engine";
  schema_version: string;
  version: string;
  display_name: string;
  description_long: string;
  domains: string[];
  subdomains: string[];
  tags: string[];
  keywords_en: string[];
  keywords_ar: string[];
  synonyms: string[];
  positive_examples: string[];
  negative_examples: string[];
  connector_ids: string[];
  status: string;
  source_license: string;
  [k: string]: unknown;
}

export interface SyntheticDiscoveryView {
  label: "synthetic";
  data_origin: "hardcoded_in_process_example";
  generated_at: string;
  warning: string;
  capability: SearchCapability;
  notes: string[];
}

export interface RegistryListResponse {
  capabilities: SearchCapability[];
  total: number;
  filters: Record<string, unknown>;
}

export interface RegistrySearchStageTrace {
  stage: string;
  candidates_in: number;
  candidates_out: number;
  notes: string;
}

export interface RegistrySearchHit {
  capability_id: string;
  display_name: string;
  final_score: number;
  matched_by: string[];
  rejected_by_negative: string[];
  text_similarity: number;
  semantic_similarity: number;
  negative_penalty: number;
  capability: SearchCapability;
}

export interface RegistrySearchResponse {
  query: string;
  tenant_id: string;
  requested_top_k: number;
  stage_traces: RegistrySearchStageTrace[];
  hits: RegistrySearchHit[];
  gaps: string[];
  generated_at: string;
}

export interface PromoteResponse {
  capability_id: string;
  previous_status: string;
  new_status: string;
  decision: string;
  reviewer: string;
  rationale: string;
  decided_at: string;
}

export interface SeedResponse {
  seeded: string[];
  skipped: string[];
  total_created: number;
}

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "";

async function getJson<T>(path: string): Promise<T> {
  const url = API_BASE_URL ? `${API_BASE_URL}${path}` : path;
  const r = await fetch(url, { headers: { Accept: "application/json" } });
  if (!r.ok) {
    let detail: unknown;
    try {
      detail = await r.json();
    } catch {
      detail = await r.text();
    }
    throw new ManaraApiError(r.status, `GET ${path} failed`, detail);
  }
  return (await r.json()) as T;
}

async function postJson<T, B = unknown>(path: string, body?: B): Promise<T> {
  const url = API_BASE_URL ? `${API_BASE_URL}${path}` : path;
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!r.ok) {
    let detail: unknown;
    try {
      detail = await r.json();
    } catch {
      detail = await r.text();
    }
    throw new ManaraApiError(r.status, `POST ${path} failed`, detail);
  }
  return (await r.json()) as T;
}

async function patchJson<T, B = unknown>(path: string, body: B): Promise<T> {
  const url = API_BASE_URL ? `${API_BASE_URL}${path}` : path;
  const r = await fetch(url, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    let detail: unknown;
    try {
      detail = await r.json();
    } catch {
      detail = await r.text();
    }
    throw new ManaraApiError(r.status, `PATCH ${path} failed`, detail);
  }
  return (await r.json()) as T;
}

export class ManaraApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly detail?: unknown,
  ) {
    super(message);
    this.name = "ManaraApiError";
  }
}

export const manaraApi = {
  // G00
  status: () => getJson<StatusResponse>("/status"),
  discovery: () => getJson<SyntheticDiscoveryView>("/discovery"),

  // G01 — Registry
  listCapabilities: (params?: {
    domains?: string[];
    tags?: string[];
    statuses?: string[];
    limit?: number;
    offset?: number;
  }) => {
    const sp = new URLSearchParams();
    if (params?.domains) for (const d of params.domains) sp.append("domains", d);
    if (params?.tags) for (const t of params.tags) sp.append("tags", t);
    if (params?.statuses) for (const s of params.statuses) sp.append("statuses", s);
    if (params?.limit) sp.set("limit", String(params.limit));
    if (params?.offset) sp.set("offset", String(params.offset));
    const qs = sp.toString();
    return getJson<RegistryListResponse>(`/registry/capabilities${qs ? "?" + qs : ""}`);
  },

  getCapability: (id: string) =>
    getJson<SearchCapability>(`/registry/capabilities/${encodeURIComponent(id)}`),

  seedCapabilities: () => postJson<SeedResponse>("/registry/capabilities/seed"),

  search: (q: string, opts?: { top_k?: number; domains?: string[]; tags?: string[] }) => {
    const sp = new URLSearchParams();
    sp.set("q", q);
    if (opts?.top_k) sp.set("top_k", String(opts.top_k));
    if (opts?.domains) for (const d of opts.domains) sp.append("domains", d);
    if (opts?.tags) for (const t of opts.tags) sp.append("tags", t);
    return getJson<RegistrySearchResponse>(`/registry/search?${sp.toString()}`);
  },

  promote: (
    id: string,
    body: { reviewer: string; rationale: string; decision?: "approved" | "rejected" | "reverted" },
  ) =>
    patchJson<PromoteResponse>(`/registry/capabilities/${encodeURIComponent(id)}/promote`, body),

  reindex: (id: string) =>
    postJson<{ capability_id: string; embeddings_regenerated: number; model: string }>(
      `/registry/capabilities/${encodeURIComponent(id)}/reindex`,
    ),
} as const;
