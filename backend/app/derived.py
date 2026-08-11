"""Pure functions that compute the 'alternative' metrics from raw usage rows.

Kept pure so they are trivial to unit test.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime
from typing import Literal

from .models import (
    BreakdownResponse,
    BreakdownRow,
    CacheEfficiencyPoint,
    Dimension,
    TimeseriesPoint,
    TimeseriesResponse,
    UsageBucket,
    UsageResult,
)

UsageMetric = Literal[
    "input_tokens",       # uncached_input_tokens only
    "all_input_tokens",   # uncached + cache_read + cache_creation
    "output_tokens",
    "cache_read_tokens",
    "cache_creation_tokens",
    "total_tokens",
]


def _result_value(r: UsageResult, metric: UsageMetric) -> int:
    if metric == "input_tokens":
        return r.uncached_input_tokens
    if metric == "all_input_tokens":
        return r.uncached_input_tokens + r.cache_read_input_tokens + r.cache_creation_input_tokens
    if metric == "output_tokens":
        return r.output_tokens
    if metric == "cache_read_tokens":
        return r.cache_read_input_tokens
    if metric == "cache_creation_tokens":
        return r.cache_creation_input_tokens
    if metric == "total_tokens":
        return (
            r.uncached_input_tokens
            + r.cache_read_input_tokens
            + r.cache_creation_input_tokens
            + r.output_tokens
        )
    raise ValueError(f"unknown metric: {metric}")


def _dim_key(r: UsageResult, dim: Dimension | None) -> str:
    if dim is None:
        return "value"
    val = getattr(r, dim, None)
    return str(val) if val is not None else "(none)"


def usage_timeseries(
    buckets: Iterable[UsageBucket],
    bucket_width: str,
    metric: UsageMetric,
    group_by: Dimension | None,
) -> TimeseriesResponse:
    series: list[TimeseriesPoint] = []
    key_totals: dict[str, float] = defaultdict(float)

    for b in buckets:
        values: dict[str, float] = defaultdict(float)
        for r in b.results:
            k = _dim_key(r, group_by)
            v = _result_value(r, metric)
            values[k] += v
            key_totals[k] += v
        series.append(TimeseriesPoint(t=b.starts_at, values=dict(values)))

    keys = [k for k, _ in sorted(key_totals.items(), key=lambda kv: -kv[1])]
    return TimeseriesResponse(
        bucket=bucket_width,  # type: ignore[arg-type]
        group_by=group_by,
        series=series,
        keys=keys,
    )


def usage_breakdown(
    buckets: Iterable[UsageBucket],
    metric: UsageMetric,
    group_by: Dimension,
) -> BreakdownResponse:
    totals: dict[str, float] = defaultdict(float)
    for b in buckets:
        for r in b.results:
            totals[_dim_key(r, group_by)] += _result_value(r, metric)
    rows = [BreakdownRow(key=k, value=v) for k, v in sorted(totals.items(), key=lambda kv: -kv[1])]
    return BreakdownResponse(group_by=group_by, rows=rows, total=sum(totals.values()))


def cache_hit_ratio(results: Iterable[UsageResult]) -> float:
    cache_read = 0
    denom = 0
    for r in results:
        cache_read += r.cache_read_input_tokens
        denom += (
            r.uncached_input_tokens
            + r.cache_read_input_tokens
            + r.cache_creation_input_tokens
        )
    return (cache_read / denom) if denom else 0.0


def cache_efficiency_points(
    buckets: Iterable[UsageBucket],
) -> list[CacheEfficiencyPoint]:
    """Per (bucket, model) cache hit ratio."""
    points: list[CacheEfficiencyPoint] = []
    for b in buckets:
        per_model: dict[str, list[UsageResult]] = defaultdict(list)
        for r in b.results:
            per_model[r.model or "(unknown)"].append(r)
        for model, rows in per_model.items():
            cr = sum(r.cache_read_input_tokens for r in rows)
            cc = sum(r.cache_creation_input_tokens for r in rows)
            ui = sum(r.uncached_input_tokens for r in rows)
            denom = cr + cc + ui
            ratio = (cr / denom) if denom else 0.0
            points.append(
                CacheEfficiencyPoint(
                    t=b.starts_at,
                    model=model,
                    cache_hit_ratio=ratio,
                    cache_read_tokens=cr,
                    cache_creation_tokens=cc,
                    uncached_input_tokens=ui,
                )
            )
    return points


def totals(results: Iterable[UsageResult]) -> dict[str, int]:
    ui = cc = cr = ot = 0
    per_model: dict[str, int] = defaultdict(int)
    for r in results:
        ui += r.uncached_input_tokens
        cc += r.cache_creation_input_tokens
        cr += r.cache_read_input_tokens
        ot += r.output_tokens
        if r.model:
            per_model[r.model] += (
                r.uncached_input_tokens
                + r.cache_creation_input_tokens
                + r.cache_read_input_tokens
                + r.output_tokens
            )
    top_model = max(per_model.items(), key=lambda kv: kv[1])[0] if per_model else None
    return {
        "uncached_input": ui,
        "cache_creation": cc,
        "cache_read": cr,
        "output": ot,
        "top_model": top_model,  # type: ignore[dict-item]
    }


def cache_savings_usd(
    results: Iterable[UsageResult],
    cache_read_unit_cost: dict[str, float],
    input_unit_cost: dict[str, float],
) -> float:
    """Dollars saved by cache reads vs uncached input at list price, per model.

    cache_read_unit_cost / input_unit_cost are $/token, keyed by model.
    """
    saved = 0.0
    for r in results:
        if not r.model:
            continue
        in_cost = input_unit_cost.get(r.model, 0.0)
        cr_cost = cache_read_unit_cost.get(r.model, 0.0)
        # what we paid for cache reads vs what we'd have paid uncached
        saved += r.cache_read_input_tokens * (in_cost - cr_cost)
    return max(saved, 0.0)


def cost_total(cost_data: list[dict]) -> float:
    """Sum 'amount' across cost buckets."""
    total = 0.0
    for b in cost_data:
        for r in b.get("results", []):
            try:
                total += float(r.get("amount", "0"))
            except (TypeError, ValueError):
                continue
    return total


def cost_timeseries_by(
    cost_data: list[dict],
    dimension: str,
) -> TimeseriesResponse:
    series: list[TimeseriesPoint] = []
    key_totals: dict[str, float] = defaultdict(float)
    for b in cost_data:
        values: dict[str, float] = defaultdict(float)
        for r in b.get("results", []):
            k = str(r.get(dimension) or "(none)")
            try:
                amt = float(r.get("amount", "0"))
            except (TypeError, ValueError):
                amt = 0.0
            values[k] += amt
            key_totals[k] += amt
        starts_at = b["starts_at"]
        t = datetime.fromisoformat(starts_at.replace("Z", "+00:00")) if isinstance(
            starts_at, str
        ) else starts_at
        series.append(TimeseriesPoint(t=t, values=dict(values)))
    keys = [k for k, _ in sorted(key_totals.items(), key=lambda kv: -kv[1])]
    return TimeseriesResponse(
        bucket="1d",
        group_by=None,
        series=series,
        keys=keys,
    )
