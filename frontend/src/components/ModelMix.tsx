import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { fetchModelMix, type Range } from "../api";
import { colorAt, fmtDay, fmtTokens } from "../format";
import { useAsync } from "../useAsync";

export function ModelMix({ range }: { range: Range }) {
  const { data, loading, error } = useAsync(() => fetchModelMix(range), [
    range.starting_at,
    range.ending_at,
  ]);

  return (
    <div className="panel">
      <h2>Model mix over time</h2>
      <p className="desc">Output tokens by model, stacked, per day.</p>
      {error ? (
        <div className="state error">Failed to load: {error}</div>
      ) : loading || !data ? (
        <div className="state">Loading…</div>
      ) : data.series.length === 0 ? (
        <div className="state">No usage in this range.</div>
      ) : (
        <ResponsiveContainer width="100%" height={320}>
          <AreaChart
            data={data.series.map((p) => ({ t: fmtDay(p.t), ...p.values }))}
            margin={{ top: 8, right: 12, bottom: 0, left: 4 }}
          >
            <CartesianGrid stroke="#232a3a" vertical={false} />
            <XAxis dataKey="t" stroke="#8b93a7" fontSize={12} />
            <YAxis
              stroke="#8b93a7"
              fontSize={12}
              tickFormatter={(v: number) => fmtTokens(v)}
            />
            <Tooltip
              contentStyle={{
                background: "#1b2130",
                border: "1px solid #232a3a",
                borderRadius: 8,
                color: "#e6e9ef",
              }}
              formatter={(v: number) => fmtTokens(v)}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            {data.keys.map((k, i) => (
              <Area
                key={k}
                type="monotone"
                dataKey={k}
                stackId="1"
                stroke={colorAt(i)}
                fill={colorAt(i)}
                fillOpacity={0.5}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
