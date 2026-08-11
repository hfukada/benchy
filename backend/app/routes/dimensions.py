from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends

from ..deps import get_service
from ..models import DimensionsResponse
from ..service import UsageService, parse_range

router = APIRouter(prefix="/api/dimensions", tags=["dimensions"])


@router.get("", response_model=DimensionsResponse)
async def dimensions_route(
    starting_at: str | None = None,
    ending_at: str | None = None,
    svc: UsageService = Depends(get_service),
) -> DimensionsResponse:
    start, end = parse_range(starting_at, ending_at, default_days=30)
    buckets = await svc.fetch_usage(
        starting_at=start,
        ending_at=end,
        bucket="1d",
        group_by=["model", "workspace_id", "api_key_id", "service_tier"],
    )
    models: set[str] = set()
    workspaces: set[str] = set()
    api_keys: set[str] = set()
    tiers: set[str] = set()
    for b in buckets:
        for r in b.results:
            if r.model:
                models.add(r.model)
            if r.workspace_id:
                workspaces.add(r.workspace_id)
            if r.api_key_id:
                api_keys.add(r.api_key_id)
            if r.service_tier:
                tiers.add(r.service_tier)
    return DimensionsResponse(
        models=sorted(models),
        workspaces=sorted(workspaces),
        api_keys=sorted(api_keys),
        service_tiers=sorted(tiers),
    )
