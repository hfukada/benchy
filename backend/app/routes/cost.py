from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from ..deps import get_service
from ..derived import cost_timeseries_by
from ..models import BreakdownResponse, TimeseriesResponse
from ..service import UsageService, parse_range

router = APIRouter(prefix="/api/cost", tags=["cost"])


def _parse_list(v: str | None) -> list[str] | None:
    if not v:
        return None
    return [x for x in v.split(",") if x]


@router.get("/timeseries", response_model=TimeseriesResponse)
async def cost_timeseries_route(
    group_by: Annotated[str, Query(description="model|workspace_id|service_tier|cost_type|description|context_window|token_type")] = "model",
    starting_at: str | None = None,
    ending_at: str | None = None,
    workspace_ids: str | None = None,
    svc: UsageService = Depends(get_service),
) -> TimeseriesResponse:
    start, end = parse_range(starting_at, ending_at)
    buckets = await svc.fetch_cost(
        starting_at=start,
        ending_at=end,
        group_by=[group_by] if group_by else None,
        workspace_ids=_parse_list(workspace_ids),
    )
    raw = [b.model_dump(mode="json") for b in buckets]
    return cost_timeseries_by(raw, dimension=group_by)


@router.get("/breakdown", response_model=BreakdownResponse)
async def cost_breakdown_route(
    group_by: Annotated[str, Query()] = "model",
    starting_at: str | None = None,
    ending_at: str | None = None,
    workspace_ids: str | None = None,
    svc: UsageService = Depends(get_service),
) -> BreakdownResponse:
    from collections import defaultdict

    start, end = parse_range(starting_at, ending_at)
    buckets = await svc.fetch_cost(
        starting_at=start,
        ending_at=end,
        group_by=[group_by],
        workspace_ids=_parse_list(workspace_ids),
    )
    totals: dict[str, float] = defaultdict(float)
    for b in buckets:
        for r in b.results:
            k = getattr(r, group_by, None) if hasattr(r, group_by) else None
            key = str(k) if k is not None else "(none)"
            try:
                totals[key] += float(r.amount)
            except (TypeError, ValueError):
                continue
    from ..models import BreakdownRow

    rows = [BreakdownRow(key=k, value=v) for k, v in sorted(totals.items(), key=lambda kv: -kv[1])]
    return BreakdownResponse(group_by=group_by, rows=rows, total=sum(totals.values()))  # type: ignore[arg-type]
