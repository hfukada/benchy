from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone

import pytest

from app.cache import BucketCache, filters_key


def test_filters_key_stable():
    a = filters_key({"models": ["b", "a"], "workspace_ids": ["w1"]})
    b = filters_key({"workspace_ids": ["w1"], "models": ["a", "b"]})
    assert a == b


def test_filters_key_drops_empty():
    assert filters_key({"models": None, "x": []}) == filters_key({})


@pytest.mark.asyncio
async def test_cache_roundtrip():
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
        path = f.name
    try:
        cache = BucketCache(path)
        fk = filters_key({"models": ["a"]})
        await cache.put_buckets("/usage", "1d", fk, [
            {
                "starts_at": "2026-01-01T00:00:00+00:00",
                "ends_at":   "2026-01-02T00:00:00+00:00",
                "results": [],
            },
            {
                "starts_at": "2026-01-02T00:00:00+00:00",
                "ends_at":   "2026-01-03T00:00:00+00:00",
                "results": [{"model": "a", "output_tokens": 5}],
            },
        ])
        rows = await cache.get_range(
            "/usage", "1d", fk_start := datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 1, 3, tzinfo=timezone.utc), fk,
        )
        assert len(rows) == 2
        assert rows[1]["results"][0]["model"] == "a"

        # different filters_key isolates rows
        rows2 = await cache.get_range(
            "/usage", "1d", fk_start, datetime(2026, 1, 3, tzinfo=timezone.utc),
            filters_key({"models": ["b"]}),
        )
        assert rows2 == []
    finally:
        os.unlink(path)
