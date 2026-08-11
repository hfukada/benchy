"""Service layer: fetch+cache+aggregate usage and cost data.

Past buckets are immutable and cached forever. The current bucket (the one
covering "now") is always re-fetched from the upstream API.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from .anthropic_client import COST_PATH, USAGE_PATH, AnthropicAdminClient
from .cache import BucketCache, filters_key
from .models import (
    Bucket,
    CostBucket,
    Dimension,
    UsageBucket,
)

log = logging.getLogger(__name__)


def _bucket_seconds(bucket: Bucket) -> int:
    return {"1m": 60, "1h": 3600, "1d": 86400}[bucket]


def _current_bucket_start(now: datetime, bucket: Bucket) -> datetime:
    secs = _bucket_seconds(bucket)
    epoch = int(now.timestamp())
    floored = epoch - (epoch % secs)
    return datetime.fromtimestamp(floored, tz=timezone.utc)


class UsageService:
    def __init__(self, client: AnthropicAdminClient, cache: BucketCache):
        self._client = client
        self._cache = cache

    async def fetch_usage(
        self,
        starting_at: datetime,
        ending_at: datetime,
        bucket: Bucket = "1d",
        group_by: list[Dimension] | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[UsageBucket]:
        filters = filters or {}
        cache_filters = {**filters, "group_by": sorted(group_by or [])}
        fkey = filters_key(cache_filters)

        now = datetime.now(timezone.utc)
        current_start = _current_bucket_start(now, bucket)
        cache_end = min(ending_at, current_start)

        cached_raw = await self._cache.get_range(
            USAGE_PATH, bucket, starting_at, cache_end, fkey
        )
        cached_starts = {row["starts_at"] for row in cached_raw}

        fresh: list[dict[str, Any]] = []
        live_fetch_needed = (
            ending_at > current_start
            or len(cached_raw) * _bucket_seconds(bucket)
            < (cache_end - starting_at).total_seconds()
        )
        if live_fetch_needed:
            async for b in self._client.iter_usage(
                starting_at=starting_at,
                ending_at=ending_at,
                bucket=bucket,
                group_by=group_by,
                models=filters.get("models"),
                workspace_ids=filters.get("workspace_ids"),
                api_key_ids=filters.get("api_key_ids"),
                service_tiers=filters.get("service_tiers"),
                context_window=filters.get("context_window"),
            ):
                fresh.append(b.model_dump(mode="json"))

            to_cache = [
                row for row in fresh
                if datetime.fromisoformat(row["ends_at"].replace("Z", "+00:00")) <= current_start
            ]
            if to_cache:
                await self._cache.put_buckets(USAGE_PATH, bucket, fkey, to_cache)

        # merge: cached + any fresh row not already in cache
        merged: dict[str, dict[str, Any]] = {row["starts_at"]: row for row in cached_raw}
        for row in fresh:
            if row["starts_at"] not in cached_starts:
                merged[row["starts_at"]] = row
            elif datetime.fromisoformat(
                row["ends_at"].replace("Z", "+00:00")
            ) > current_start:
                # current bucket: prefer fresh
                merged[row["starts_at"]] = row
        ordered = sorted(merged.values(), key=lambda r: r["starts_at"])
        return [UsageBucket.model_validate(r) for r in ordered]

    async def fetch_cost(
        self,
        starting_at: datetime,
        ending_at: datetime,
        group_by: list[str] | None = None,
        workspace_ids: list[str] | None = None,
    ) -> list[CostBucket]:
        # Cost is 1d only per Admin API. Cache same way.
        cache_filters = {"group_by": sorted(group_by or []), "workspace_ids": workspace_ids}
        fkey = filters_key(cache_filters)

        now = datetime.now(timezone.utc)
        current_start = _current_bucket_start(now, "1d")
        cache_end = min(ending_at, current_start)

        cached_raw = await self._cache.get_range(
            COST_PATH, "1d", starting_at, cache_end, fkey
        )
        cached_starts = {row["starts_at"] for row in cached_raw}

        fresh: list[dict[str, Any]] = []
        async for b in self._client.iter_cost(
            starting_at=starting_at,
            ending_at=ending_at,
            group_by=group_by,
            workspace_ids=workspace_ids,
        ):
            fresh.append(b.model_dump(mode="json"))

        to_cache = [
            row for row in fresh
            if datetime.fromisoformat(row["ends_at"].replace("Z", "+00:00")) <= current_start
        ]
        if to_cache:
            await self._cache.put_buckets(COST_PATH, "1d", fkey, to_cache)

        merged: dict[str, dict[str, Any]] = {row["starts_at"]: row for row in cached_raw}
        for row in fresh:
            if row["starts_at"] not in cached_starts or datetime.fromisoformat(
                row["ends_at"].replace("Z", "+00:00")
            ) > current_start:
                merged[row["starts_at"]] = row
        ordered = sorted(merged.values(), key=lambda r: r["starts_at"])
        return [CostBucket.model_validate(r) for r in ordered]


def parse_range(
    starting_at: str | None,
    ending_at: str | None,
    default_days: int = 30,
) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    end = (
        datetime.fromisoformat(ending_at.replace("Z", "+00:00"))
        if ending_at
        else now
    )
    start = (
        datetime.fromisoformat(starting_at.replace("Z", "+00:00"))
        if starting_at
        else end - timedelta(days=default_days)
    )
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return start, end
