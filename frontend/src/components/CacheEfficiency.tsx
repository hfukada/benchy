import {
  CartesianGrid,
  Line,
  LineChart,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { fetchCacheEfficiency, type Range } from "../api";
import { colorAt, fmtDay, fmtPct } from "../format";
import { useAsync } from "../useAsync";

export function CacheEfficiency({ range }: { range: Range }) {
  const { data, loading, error } = useAsync(() => fetchCacheEfficiency(range), [
    range.starting_at,
    range.ending_at,
  ]);

  // Pivot flat (t, model, ratio) points into one row per day with a column
  // per model, so each model becomes its own line.
  const { rows, models } = (() => {
    if (!data) return { rows: [] as Record<string, number | string>[], models: [] as string[] };
    const byDay = new Map<string, Record<string, number | string>>();
    const modelSet = new Set<string>();
    for (const p of data.points) {
      const day = fmtDay(p.t);
      modelSet.add(p.model);
      const row = byDay.get(day) ?? { t: day };
      row[p.model] = p.cache_hit_ratio;
      byDay.set(day, row);
    }
    const sortedRows = [...byDay.values()].sort((a, b) =>
      String(a.t).localeCompare(String(b.t)),
    );
    return { rows: sortedRows, models: [...modelSet].sort() };
  })();

  return (
    <div className="panel">
      <h2>Cache efficiency</h2>
      <p className="desc">
        Cache hit ratio = cache_read / (uncached + cache_read + cache_creation), per model per day.
      </p>
      {error ? (
        <div className="state error">Failed to load: {error}</div>
      ) : loading || !data ? (
        <div className="state">Loading…</div>
      ) : rows.length === 0 ? (
        <div className="state">No usage in this range.</div>
      ) : (
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
            <CartesianGrid stroke="#232a3a" vertical={false} />
            <XAxis dataKey="t" stroke="#8b93a7" fontSize={12} />
            <YAxis
              stroke="#8b93a7"
              fontSize={12}
              domain={[0, 1]}
              tickFormatter={(v: number) => fmtPct(v)}
            />
            <Tooltip
              contentStyle={{
                background: "#1b2130",
                border: "1px solid #232a3a",
                borderRadius: 8,
                color: "#e6e9ef",
              }}
              formatter={(v: number) => fmtPct(v)}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            {models.map((m, i) => (
              <Line
                key={m}
                type="monotone"
                dataKey={m}
                stroke={colorAt(i)}
                dot={false}
                strokeWidth={2}
                connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
