/**
 * MANARA API client — typed wrapper around the G00 backend surface.
 *
 * All endpoints the backend actually exposes are listed here. Anything not
 * in this file is NOT implemented (matches the G00 honesty contract).
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
  tags: string[];
  keywords_en: string[];
  keywords_ar: string[];
  positive_examples: string[];
  negative_examples: string[];
  connector_ids: string[];
  status: string;
  source_license: string;
}

export interface SyntheticDiscoveryView {
  label: "synthetic";
  data_origin: "hardcoded_in_process_example";
  generated_at: string;
  warning: string;
  capability: SearchCapability;
  notes: string[];
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
  status: () => getJson<StatusResponse>("/status"),
  discovery: () => getJson<SyntheticDiscoveryView>("/discovery"),
} as const;
