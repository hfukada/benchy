export function fmtTokens(n: number): string {
  if (n >= 1e9) return `${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(2)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  return String(n);
}

export function fmtUsd(n: number): string {
  return n.toLocaleString(undefined, {
    style: "currency",
    currency: "USD",
  });
}

export function fmtPct(ratio: number): string {
  return `${(ratio * 100).toFixed(1)}%`;
}

export function fmtDay(iso: string): string {
  // Show YYYY-MM-DD from an ISO timestamp.
  return iso.slice(0, 10);
}

// Stable-ish palette for series keys. Index by position in a keys array.
const PALETTE = [
  "#6366f1",
  "#10b981",
  "#f59e0b",
  "#ef4444",
  "#06b6d4",
  "#8b5cf6",
  "#ec4899",
  "#84cc16",
  "#f97316",
  "#14b8a6",
];

export function colorAt(i: number): string {
  return PALETTE[i % PALETTE.length];
}
