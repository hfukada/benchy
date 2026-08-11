// Typed client for the benchy backend. Shapes mirror backend/app/models.py.

export interface SummaryResponse {
  total_input_tokens: number;
  total_output_tokens: number;
  total_cache_read_tokens: number;
  total_cache_creation_tokens: number;
  total_cost_usd: number;
  cache_hit_ratio: number;
  cache_savings_usd: number;
  top_model: string | null;
  period_start: string;
  period_end: string;
  prev_period_cost_usd: number | null;
  prev_period_tokens: number | null;
}

export interface TimeseriesPoint {
  t: string;
  values: Record<string, number>;
}

export interface TimeseriesResponse {
  bucket: string;
  group_by: string | null;
  series: TimeseriesPoint[];
  // dimension keys present across the series, ordered by total descending
  keys: string[];
}

export interface CacheEfficiencyPoint {
  t: string;
  model: string;
  cache_hit_ratio: number;
  cache_read_tokens: number;
  cache_creation_tokens: number;
  uncached_input_tokens: number;
}

export interface CacheEfficiencyResponse {
  bucket: string;
  points: CacheEfficiencyPoint[];
}

export interface Range {
  starting_at: string;
  ending_at: string;
}

function qs(params: Record<string, string | undefined>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") sp.set(k, v);
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

async function getJSON<T>(path: string): Promise<T> {
  const resp = await fetch(path);
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      if (body && typeof body.detail === "string") detail = body.detail;
    } catch {
      // non-JSON error body; keep statusText
    }
    throw new Error(`${resp.status}: ${detail}`);
  }
  return resp.json() as Promise<T>;
}

export function fetchSummary(r: Range): Promise<SummaryResponse> {
  return getJSON<SummaryResponse>(`/api/summary${qs({ ...r })}`);
}

export function fetchModelMix(r: Range): Promise<TimeseriesResponse> {
  return getJSON<TimeseriesResponse>(
    `/api/usage/timeseries${qs({ ...r, metric: "output_tokens", group_by: "model" })}`,
  );
}

export function fetchCacheEfficiency(r: Range): Promise<CacheEfficiencyResponse> {
  return getJSON<CacheEfficiencyResponse>(
    `/api/usage/cache_efficiency${qs({ ...r, bucket: "1d" })}`,
  );
}
