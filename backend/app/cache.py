"""SQLite cache for raw Admin API responses.

Past usage/cost buckets are immutable. We cache each fully-closed bucket
forever, keyed by (endpoint, bucket_starts_at, bucket_width, group_by_key,
filters_key). The current open bucket is never cached.

This is intentionally simple — the cache stores serialized bucket rows, and
the route layer reassembles them. We do not try to be a full query engine.
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS bucket_cache (
    endpoint        TEXT NOT NULL,
    bucket_width    TEXT NOT NULL,
    starts_at       TEXT NOT NULL,
    ends_at         TEXT NOT NULL,
    filters_key     TEXT NOT NULL,
    payload         TEXT NOT NULL,
    fetched_at      TEXT NOT NULL,
    PRIMARY KEY (endpoint, bucket_width, starts_at, filters_key)
);
CREATE INDEX IF NOT EXISTS bucket_cache_range
    ON bucket_cache (endpoint, bucket_width, filters_key, starts_at);
"""


def filters_key(d: dict[str, Any]) -> str:
    """Stable, order-independent key for a filter dict."""
    normalized = {k: sorted(v) if isinstance(v, list) else v for k, v in sorted(d.items()) if v}
    return json.dumps(normalized, separators=(",", ":"), sort_keys=True)


class BucketCache:
    def __init__(self, path: str):
        self._path = path
        self._initialized = False

    async def _conn(self) -> aiosqlite.Connection:
        conn = await aiosqlite.connect(self._path)
        await conn.execute("PRAGMA journal_mode=WAL")
        if not self._initialized:
            await conn.executescript(SCHEMA)
            await conn.commit()
            self._initialized = True
        return conn

    async def get_range(
        self,
        endpoint: str,
        bucket_width: str,
        starts_at: datetime,
        ends_at: datetime,
        filters_k: str,
    ) -> list[dict[str, Any]]:
        conn = await self._conn()
        try:
            cur = await conn.execute(
                """
                SELECT payload FROM bucket_cache
                WHERE endpoint = ?
                  AND bucket_width = ?
                  AND filters_key = ?
                  AND starts_at >= ?
                  AND starts_at < ?
                ORDER BY starts_at ASC
                """,
                (endpoint, bucket_width, filters_k, starts_at.isoformat(), ends_at.isoformat()),
            )
            rows = await cur.fetchall()
        finally:
            await conn.close()
        return [json.loads(r[0]) for r in rows]

    async def put_buckets(
        self,
        endpoint: str,
        bucket_width: str,
        filters_k: str,
        buckets: Iterable[dict[str, Any]],
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        conn = await self._conn()
        try:
            await conn.executemany(
                """
                INSERT OR REPLACE INTO bucket_cache
                    (endpoint, bucket_width, starts_at, ends_at, filters_key, payload, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        endpoint,
                        bucket_width,
                        b["starts_at"],
                        b["ends_at"],
                        filters_k,
                        json.dumps(b, separators=(",", ":")),
                        now,
                    )
                    for b in buckets
                ],
            )
            await conn.commit()
        finally:
            await conn.close()

    async def clear(self) -> None:
        conn = await self._conn()
        try:
            await conn.execute("DELETE FROM bucket_cache")
            await conn.commit()
        finally:
            await conn.close()
