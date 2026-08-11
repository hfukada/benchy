from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from ..deps import get_service
from ..derived import (
    cache_efficiency_points,
    usage_breakdown,
    usage_timeseries,
)
from ..models import (
    BreakdownResponse,
    Bucket,
    CacheEfficiencyResponse,
    Dimension,
    TimeseriesResponse,
)
from ..service import UsageService, parse_range

router = APIRouter(prefix="/api/usage", tags=["usage"])

VALID_METRICS = {
    "input_tokens",
    "all_input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_creation_tokens",
    "total_tokens",
}


def _parse_list(v: str | None) -> list[str] | None:
    if not v:
        return None
    return [x for x in v.split(",") if x]


@router.get("/timeseries", response_model=TimeseriesResponse)
async def usage_timeseries_route(
    bucket: Annotated[Bucket, Query()] = "1d",
    metric: Annotated[str, Query()] = "total_tokens",
    group_by: Annotated[Dimension | None, Query()] = None,
    starting_at: str | None = None,
    ending_at: str | None = None,
    models: Annotated[str | None, Query(description="comma-separated")] = None,
    workspace_ids: Annotated[str | None, Query(description="comma-separated")] = None,
    api_key_ids: Annotated[str | None, Query(description="comma-separated")] = None,
    service_tiers: Annotated[str | None, Query(description="comma-separated")] = None,
    svc: UsageService = Depends(get_service),
) -> TimeseriesResponse:
    if metric not in VALID_METRICS:
        from fastapi import HTTPException
        raise HTTPException(400, f"metric must be one of {sorted(VALID_METRICS)}")
    start, end = parse_range(starting_at, ending_at)
    buckets = await svc.fetch_usage(
        starting_at=start,
        ending_at=end,
        bucket=bucket,
        group_by=[group_by] if group_by else None,
        filters={
            "models": _parse_list(models),
            "workspace_ids": _parse_list(workspace_ids),
            "api_key_ids": _parse_list(api_key_ids),
            "service_tiers": _parse_list(service_tiers),
        },
    )
    return usage_timeseries(buckets, bucket, metric, group_by)  # type: ignore[arg-type]


@router.get("/breakdown", response_model=BreakdownResponse)
async def usage_breakdown_route(
    group_by: Annotated[Dimension, Query()] = "model",
    metric: Annotated[str, Query()] = "total_tokens",
    starting_at: str | None = None,
    ending_at: str | None = None,
    models: str | None = None,
    workspace_ids: str | None = None,
    api_key_ids: str | None = None,
    service_tiers: str | None = None,
    svc: UsageService = Depends(get_service),
) -> BreakdownResponse:
    if metric not in VALID_METRICS:
        from fastapi import HTTPException
        raise HTTPException(400, f"metric must be one of {sorted(VALID_METRICS)}")
    start, end = parse_range(starting_at, ending_at)
    buckets = await svc.fetch_usage(
        starting_at=start,
        ending_at=end,
        bucket="1d",
        group_by=[group_by],
        filters={
            "models": _parse_list(models),
            "workspace_ids": _parse_list(workspace_ids),
            "api_key_ids": _parse_list(api_key_ids),
            "service_tiers": _parse_list(service_tiers),
        },
    )
    return usage_breakdown(buckets, metric, group_by)  # type: ignore[arg-type]


@router.get("/cache_efficiency", response_model=CacheEfficiencyResponse)
async def cache_efficiency_route(
    bucket: Annotated[Bucket, Query()] = "1d",
    starting_at: str | None = None,
    ending_at: str | None = None,
    models: str | None = None,
    workspace_ids: str | None = None,
    svc: UsageService = Depends(get_service),
) -> CacheEfficiencyResponse:
    start, end = parse_range(starting_at, ending_at)
    buckets = await svc.fetch_usage(
        starting_at=start,
        ending_at=end,
        bucket=bucket,
        group_by=["model"],
        filters={
            "models": _parse_list(models),
            "workspace_ids": _parse_list(workspace_ids),
        },
    )
    return CacheEfficiencyResponse(bucket=bucket, points=cache_efficiency_points(buckets))
