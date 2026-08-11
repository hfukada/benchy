"""Pydantic models for API responses.

These mirror the Anthropic Admin API shapes for the bits we use, plus our own
aggregate/derived shapes that the frontend consumes.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Bucket = Literal["1m", "1h", "1d"]
Dimension = Literal["model", "workspace_id", "api_key_id", "service_tier", "context_window"]


class UsageResult(BaseModel):
    """One row of a usage_report/messages response."""

    uncached_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    output_tokens: int = 0
    server_tool_use_tokens: int = 0

    model: str | None = None
    workspace_id: str | None = None
    api_key_id: str | None = None
    service_tier: str | None = None
    context_window: str | None = None


class UsageBucket(BaseModel):
    starts_at: datetime
    ends_at: datetime
    results: list[UsageResult] = Field(default_factory=list)


class UsageResponse(BaseModel):
    data: list[UsageBucket] = Field(default_factory=list)
    has_more: bool = False
    next_page: str | None = None


class CostResult(BaseModel):
    amount: str  # decimal as string
    currency: str = "USD"
    workspace_id: str | None = None
    description: str | None = None
    cost_type: str | None = None
    context_window: str | None = None
    model: str | None = None
    service_tier: str | None = None
    token_type: str | None = None


class CostBucket(BaseModel):
    starts_at: datetime
    ends_at: datetime
    results: list[CostResult] = Field(default_factory=list)


class CostResponse(BaseModel):
    data: list[CostBucket] = Field(default_factory=list)
    has_more: bool = False
    next_page: str | None = None


# ---- Frontend-facing shapes ----


class TimeseriesPoint(BaseModel):
    t: datetime
    # arbitrary dimension keys -> value
    values: dict[str, float] = Field(default_factory=dict)


class TimeseriesResponse(BaseModel):
    bucket: Bucket
    group_by: Dimension | None = None
    series: list[TimeseriesPoint]
    # union of all dimension keys present in series, ordered by total descending
    keys: list[str]


class BreakdownRow(BaseModel):
    key: str
    value: float


class BreakdownResponse(BaseModel):
    group_by: Dimension
    rows: list[BreakdownRow]
    total: float


class SummaryResponse(BaseModel):
    total_input_tokens: int
    total_output_tokens: int
    total_cache_read_tokens: int
    total_cache_creation_tokens: int
    total_cost_usd: float
    cache_hit_ratio: float  # cache_read / (input + cache_read + cache_creation)
    cache_savings_usd: float  # cost we'd have paid if cache_reads were uncached input
    top_model: str | None
    period_start: datetime
    period_end: datetime
    prev_period_cost_usd: float | None = None
    prev_period_tokens: int | None = None


class CacheEfficiencyPoint(BaseModel):
    t: datetime
    model: str
    cache_hit_ratio: float
    cache_read_tokens: int
    cache_creation_tokens: int
    uncached_input_tokens: int


class CacheEfficiencyResponse(BaseModel):
    bucket: Bucket
    points: list[CacheEfficiencyPoint]


class DimensionsResponse(BaseModel):
    models: list[str]
    workspaces: list[str]
    api_keys: list[str]
    service_tiers: list[str]
