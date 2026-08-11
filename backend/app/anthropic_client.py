"""Thin async client for the Anthropic Admin Usage & Cost APIs.

Docs: https://docs.anthropic.com/en/api/admin-api/usage-cost

We expose two endpoints:

- GET /v1/organizations/usage_report/messages
- GET /v1/organizations/cost_report

Both are bucketed timeseries. They paginate via `next_page`. We follow the
cursor until exhausted.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

import httpx

from .config import Settings
from .models import (
    Bucket,
    CostBucket,
    CostResponse,
    Dimension,
    UsageBucket,
    UsageResponse,
)

log = logging.getLogger(__name__)

USAGE_PATH = "/v1/organizations/usage_report/messages"
COST_PATH = "/v1/organizations/cost_report"


class AnthropicAdminError(RuntimeError):
    def __init__(self, status: int, body: str):
        super().__init__(f"Anthropic Admin API {status}: {body}")
        self.status = status
        self.body = body


class AnthropicAdminClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self._settings = settings
        self._client = client or httpx.AsyncClient(
            base_url=settings.anthropic_api_base,
            headers={
                "x-api-key": settings.anthropic_admin_api_key,
                "anthropic-version": "2023-06-01",
            },
            timeout=30.0,
        )
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> "AnthropicAdminClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()

    # ---- HTTP plumbing ----

    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        """GET with 429/5xx retry. Honors Retry-After when present."""
        attempt = 0
        while True:
            attempt += 1
            resp = await self._client.get(path, params=params)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < 5:
                retry_after = float(resp.headers.get("retry-after", "0") or 0)
                delay = retry_after if retry_after > 0 else min(2 ** attempt, 30)
                log.warning(
                    "Anthropic Admin API %s on %s; retry %d in %.1fs",
                    resp.status_code, path, attempt, delay,
                )
                await asyncio.sleep(delay)
                continue
            raise AnthropicAdminError(resp.status_code, resp.text)

    @staticmethod
    def _iso_z(dt: datetime) -> str:
        # Admin API expects RFC3339; force UTC trailing Z.
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    # ---- Public API ----

    async def iter_usage(
        self,
        starting_at: datetime,
        ending_at: datetime,
        bucket: Bucket = "1d",
        group_by: list[Dimension] | None = None,
        models: list[str] | None = None,
        workspace_ids: list[str] | None = None,
        api_key_ids: list[str] | None = None,
        service_tiers: list[str] | None = None,
        context_window: list[str] | None = None,
    ) -> AsyncIterator[UsageBucket]:
        """Yield each usage time bucket, following pagination."""
        params: dict[str, Any] = {
            "starting_at": self._iso_z(starting_at),
            "ending_at": self._iso_z(ending_at),
            "bucket_width": bucket,
            "limit": 7,  # max allowed for 1d is 31; keep small to test pagination paths
        }
        if group_by:
            params["group_by[]"] = list(group_by)
        if models:
            params["models[]"] = list(models)
        if workspace_ids:
            params["workspace_ids[]"] = list(workspace_ids)
        if api_key_ids:
            params["api_key_ids[]"] = list(api_key_ids)
        if service_tiers:
            params["service_tiers[]"] = list(service_tiers)
        if context_window:
            params["context_window[]"] = list(context_window)

        async for bucket_row in self._iter_paginated(USAGE_PATH, params, UsageResponse):
            yield bucket_row

    async def iter_cost(
        self,
        starting_at: datetime,
        ending_at: datetime,
        group_by: list[str] | None = None,
        workspace_ids: list[str] | None = None,
    ) -> AsyncIterator[CostBucket]:
        params: dict[str, Any] = {
            "starting_at": self._iso_z(starting_at),
            "ending_at": self._iso_z(ending_at),
            "limit": 31,
        }
        if group_by:
            params["group_by[]"] = list(group_by)
        if workspace_ids:
            params["workspace_ids[]"] = list(workspace_ids)

        async for bucket_row in self._iter_paginated(COST_PATH, params, CostResponse):
            yield bucket_row

    async def _iter_paginated(
        self,
        path: str,
        params: dict[str, Any],
        response_cls: type,
    ) -> AsyncIterator[Any]:
        current_params = dict(params)
        while True:
            raw = await self._get(path, current_params)
            parsed = response_cls.model_validate(raw)
            for row in parsed.data:
                yield row
            if not parsed.has_more or not parsed.next_page:
                return
            current_params = dict(params)
            current_params["page"] = parsed.next_page
