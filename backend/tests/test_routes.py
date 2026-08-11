from __future__ import annotations

import httpx
import pytest
import respx
from starlette.testclient import TestClient


@pytest.fixture
def client():
    from app.config import get_settings
    from app.main import create_app
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as c:
        yield c


def _base():
    from app.config import get_settings
    return get_settings().anthropic_api_base


@respx.mock
def test_summary_route(client):
    base = _base()
    respx.get(f"{base}/v1/organizations/usage_report/messages").mock(
        return_value=httpx.Response(200, json={
            "data": [{
                "starts_at": "2026-01-01T00:00:00Z",
                "ends_at":   "2026-01-02T00:00:00Z",
                "results": [
                    {"model": "claude-opus-4-7",
                     "uncached_input_tokens": 100,
                     "cache_read_input_tokens": 900,
                     "cache_creation_input_tokens": 0,
                     "output_tokens": 50},
                ],
            }],
            "has_more": False, "next_page": None,
        })
    )
    respx.get(f"{base}/v1/organizations/cost_report").mock(
        return_value=httpx.Response(200, json={
            "data": [{
                "starts_at": "2026-01-01T00:00:00Z",
                "ends_at":   "2026-01-02T00:00:00Z",
                "results": [{"amount": "2.50", "model": "claude-opus-4-7"}],
            }],
            "has_more": False, "next_page": None,
        })
    )

    r = client.get(
        "/api/summary",
        params={"starting_at": "2026-01-01T00:00:00Z", "ending_at": "2026-01-02T00:00:00Z"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total_output_tokens"] == 50
    assert body["total_input_tokens"] == 100
    assert body["total_cache_read_tokens"] == 900
    assert body["total_cost_usd"] == 2.5
    assert body["cache_hit_ratio"] == 0.9
    assert body["top_model"] == "claude-opus-4-7"


@respx.mock
def test_usage_timeseries_groups_by_model(client):
    base = _base()
    respx.get(f"{base}/v1/organizations/usage_report/messages").mock(
        return_value=httpx.Response(200, json={
            "data": [{
                "starts_at": "2026-01-01T00:00:00Z",
                "ends_at":   "2026-01-02T00:00:00Z",
                "results": [
                    {"model": "claude-opus-4-7", "output_tokens": 100},
                    {"model": "claude-sonnet-4-6", "output_tokens": 50},
                ],
            }],
            "has_more": False, "next_page": None,
        })
    )
    r = client.get(
        "/api/usage/timeseries",
        params={
            "starting_at": "2026-01-01T00:00:00Z",
            "ending_at":   "2026-01-02T00:00:00Z",
            "metric": "output_tokens",
            "group_by": "model",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["keys"] == ["claude-opus-4-7", "claude-sonnet-4-6"]
    assert body["series"][0]["values"] == {"claude-opus-4-7": 100, "claude-sonnet-4-6": 50}


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


@respx.mock
def test_unknown_metric_400(client):
    r = client.get(
        "/api/usage/timeseries",
        params={"metric": "bogus"},
    )
    assert r.status_code == 400
