import { useMemo, useState } from "react";

import type { Range } from "./api";
import { CacheEfficiency } from "./components/CacheEfficiency";
import { ModelMix } from "./components/ModelMix";
import { SummaryCards } from "./components/SummaryCards";

function daysAgoISO(days: number): string {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - days);
  return d.toISOString().slice(0, 10);
}

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

// The date inputs give us YYYY-MM-DD; the backend accepts RFC3339, so we widen
// to full-day UTC bounds.
function toRange(start: string, end: string): Range {
  return {
    starting_at: `${start}T00:00:00Z`,
    ending_at: `${end}T00:00:00Z`,
  };
}

export default function App() {
  const [start, setStart] = useState(daysAgoISO(30));
  const [end, setEnd] = useState(todayISO());

  const range = useMemo(() => toRange(start, end), [start, end]);

  return (
    <div className="app">
      <div className="header">
        <div>
          <h1>benchy</h1>
          <div className="sub">Claude usage &amp; cost — alternative dashboard</div>
        </div>
        <div className="range">
          <label htmlFor="start">from</label>
          <input
            id="start"
            type="date"
            value={start}
            max={end}
            onChange={(e) => setStart(e.target.value)}
          />
          <label htmlFor="end">to</label>
          <input
            id="end"
            type="date"
            value={end}
            min={start}
            onChange={(e) => setEnd(e.target.value)}
          />
        </div>
      </div>

      <SummaryCards range={range} />
      <ModelMix range={range} />
      <CacheEfficiency range={range} />
    </div>
  );
}
