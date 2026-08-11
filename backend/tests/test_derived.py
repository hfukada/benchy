from __future__ import annotations

from datetime import datetime, timezone

from app.derived import (
    cache_efficiency_points,
    cache_hit_ratio,
    cache_savings_usd,
    cost_timeseries_by,
    cost_total,
    totals,
    usage_breakdown,
    usage_timeseries,
)
from app.models import UsageBucket, UsageResult


def _ub(t: str, results: list[dict]) -> UsageBucket:
    return UsageBucket(
        starts_at=datetime.fromisoformat(t).replace(tzinfo=timezone.utc),
        ends_at=datetime.fromisoformat(t).replace(tzinfo=timezone.utc),
        results=[UsageResult(**r) for r in results],
    )


def test_cache_hit_ratio_basic():
    rs = [
        UsageResult(uncached_input_tokens=100, cache_read_input_tokens=900, cache_creation_input_tokens=0),
    ]
    assert cache_hit_ratio(rs) == 0.9


def test_cache_hit_ratio_no_inputs():
    assert cache_hit_ratio([UsageResult(output_tokens=10)]) == 0.0


def test_usage_timeseries_groups_and_orders_keys():
    buckets = [
        _ub("2026-01-01T00:00:00", [
            {"model": "claude-opus-4-7", "output_tokens": 100},
            {"model": "claude-sonnet-4-6", "output_tokens": 50},
        ]),
        _ub("2026-01-02T00:00:00", [
            {"model": "claude-opus-4-7", "output_tokens": 200},
            {"model": "claude-sonnet-4-6", "output_tokens": 25},
        ]),
    ]
    out = usage_timeseries(buckets, "1d", "output_tokens", "model")
    assert out.keys == ["claude-opus-4-7", "claude-sonnet-4-6"]
    assert out.series[0].values == {"claude-opus-4-7": 100, "claude-sonnet-4-6": 50}
    assert out.series[1].values == {"claude-opus-4-7": 200, "claude-sonnet-4-6": 25}


def test_usage_breakdown_sums_across_buckets():
    buckets = [
        _ub("2026-01-01T00:00:00", [
            {"model": "a", "output_tokens": 1},
            {"model": "b", "output_tokens": 2},
        ]),
        _ub("2026-01-02T00:00:00", [
            {"model": "a", "output_tokens": 10},
        ]),
    ]
    out = usage_breakdown(buckets, "output_tokens", "model")
    assert out.total == 13
    assert [(r.key, r.value) for r in out.rows] == [("a", 11), ("b", 2)]


def test_cache_efficiency_per_bucket_per_model():
    buckets = [
        _ub("2026-01-01T00:00:00", [
            {"model": "a", "uncached_input_tokens": 100, "cache_read_input_tokens": 300, "cache_creation_input_tokens": 100},
        ]),
    ]
    points = cache_efficiency_points(buckets)
    assert len(points) == 1
    assert points[0].model == "a"
    assert points[0].cache_hit_ratio == 0.6  # 300 / 500


def test_totals_picks_top_model():
    rs = [
        UsageResult(model="a", output_tokens=100),
        UsageResult(model="b", output_tokens=200),
        UsageResult(model="b", uncached_input_tokens=50),
    ]
    t = totals(rs)
    assert t["top_model"] == "b"
    assert t["output"] == 300


def test_cache_savings_clamped_to_zero():
    rs = [UsageResult(model="a", cache_read_input_tokens=1000)]
    # if cache_read costs MORE than input (impossible but be safe), don't go negative
    saved = cache_savings_usd(
        rs,
        cache_read_unit_cost={"a": 0.0000030},
        input_unit_cost={"a": 0.0000030},
    )
    assert saved == 0.0


def test_cost_total_and_timeseries():
    data = [
        {
            "starts_at": "2026-01-01T00:00:00Z",
            "ends_at": "2026-01-02T00:00:00Z",
            "results": [
                {"amount": "1.50", "model": "a"},
                {"amount": "0.50", "model": "b"},
            ],
        },
        {
            "starts_at": "2026-01-02T00:00:00Z",
            "ends_at": "2026-01-03T00:00:00Z",
            "results": [
                {"amount": "2.00", "model": "a"},
            ],
        },
    ]
    assert cost_total(data) == 4.0
    ts = cost_timeseries_by(data, "model")
    assert ts.keys == ["a", "b"]
    assert ts.series[0].values == {"a": 1.5, "b": 0.5}
    assert ts.series[1].values == {"a": 2.0}
