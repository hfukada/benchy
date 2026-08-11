import { fetchSummary, type Range } from "../api";
import { fmtPct, fmtTokens, fmtUsd } from "../format";
import { useAsync } from "../useAsync";

function Delta({ now, prev }: { now: number; prev: number | null }) {
  if (prev == null || prev === 0) return null;
  const change = (now - prev) / prev;
  const up = change >= 0;
  return (
    <div className={`delta ${up ? "up" : "down"}`}>
      {up ? "▲" : "▼"} {fmtPct(Math.abs(change))} vs prev
    </div>
  );
}

export function SummaryCards({ range }: { range: Range }) {
  const { data, loading, error } = useAsync(() => fetchSummary(range), [
    range.starting_at,
    range.ending_at,
  ]);

  if (error) return <div className="state error">Failed to load summary: {error}</div>;
  if (loading || !data) return <div className="state">Loading summary…</div>;

  const totalTokens =
    data.total_input_tokens +
    data.total_output_tokens +
    data.total_cache_read_tokens +
    data.total_cache_creation_tokens;

  return (
    <div className="cards">
      <div className="card">
        <div className="label">Total cost</div>
        <div className="value">{fmtUsd(data.total_cost_usd)}</div>
        <Delta now={data.total_cost_usd} prev={data.prev_period_cost_usd} />
      </div>
      <div className="card">
        <div className="label">Total tokens</div>
        <div className="value">{fmtTokens(totalTokens)}</div>
        <Delta now={totalTokens} prev={data.prev_period_tokens} />
      </div>
      <div className="card">
        <div className="label">Input tokens</div>
        <div className="value">{fmtTokens(data.total_input_tokens)}</div>
      </div>
      <div className="card">
        <div className="label">Output tokens</div>
        <div className="value">{fmtTokens(data.total_output_tokens)}</div>
      </div>
      <div className="card">
        <div className="label">Cache hit ratio</div>
        <div className="value">{fmtPct(data.cache_hit_ratio)}</div>
      </div>
      <div className="card">
        <div className="label">Top model</div>
        <div className="value" style={{ fontSize: 16 }}>
          {data.top_model ?? "—"}
        </div>
      </div>
    </div>
  );
}
