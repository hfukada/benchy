from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest
import respx

from app.anthropic_client import AnthropicAdminClient
from app.config import get_settings


@pytest.mark.asyncio
@respx.mock
async def test_iter_usage_follows_pagination():
    settings = get_settings()
    base = settings.anthropic_api_base
    page1 = {
        "data": [
            {
                "starts_at": "2026-01-01T00:00:00Z",
                "ends_at":   "2026-01-02T00:00:00Z",
                "results": [
                    {"model": "claude-opus-4-7", "uncached_input_tokens": 10,
                     "output_tokens": 5}
                ],
            }
        ],
        "has_more": True,
        "next_page": "cursor-abc",
    }
    page2 = {
        "data": [
            {
                "starts_at": "2026-01-02T00:00:00Z",
                "ends_at":   "2026-01-03T00:00:00Z",
                "results": [
                    {"model": "claude-opus-4-7", "output_tokens": 7}
                ],
            }
        ],
        "has_more": False,
        "next_page": None,
    }
    route = respx.get(f"{base}/v1/organizations/usage_report/messages")
    route.side_effect = [
        httpx.Response(200, json=page1),
        httpx.Response(200, json=page2),
    ]

    client = AnthropicAdminClient(settings)
    try:
        out = []
        async for b in client.iter_usage(
            starting_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ending_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
        ):
            out.append(b)
    finally:
        await client.aclose()

    assert len(out) == 2
    assert route.call_count == 2
    # second call carried the next_page cursor
    second_request = route.calls[1].request
    assert "page=cursor-abc" in str(second_request.url)


@pytest.mark.asyncio
@respx.mock
async def test_retries_on_429(monkeypatch):
    # patch asyncio.sleep so retry doesn't slow tests
    import asyncio
    async def _no_sleep(_):
        return None
    monkeypatch.setattr(asyncio, "sleep", _no_sleep)

    settings = get_settings()
    base = settings.anthropic_api_base
    payload = {"data": [], "has_more": False, "next_page": None}
    route = respx.get(f"{base}/v1/organizations/usage_report/messages")
    route.side_effect = [
        httpx.Response(429, headers={"retry-after": "0"}, text="slow down"),
        httpx.Response(200, json=payload),
    ]
    client = AnthropicAdminClient(settings)
    try:
        async for _ in client.iter_usage(
            starting_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ending_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        ):
            pass
    finally:
        await client.aclose()
    assert route.call_count == 2
