from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends

from ..deps import get_service
from ..derived import cache_hit_ratio, cost_total, totals
from ..models import SummaryResponse
from ..service import UsageService, parse_range

router = APIRouter(prefix="/api/summary", tags=["summary"])


@router.get("", response_model=SummaryResponse)
async def summary_route(
    starting_at: str | None = None,
    ending_at: str | None = None,
    svc: UsageService = Depends(get_service),
) -> SummaryResponse:
    start, end = parse_range(starting_at, ending_at)
    span = end - start
    prev_start = start - span
    prev_end = start

    usage_buckets = await svc.fetch_usage(start, end, bucket="1d", group_by=["model"])
    prev_buckets = await svc.fetch_usage(prev_start, prev_end, bucket="1d", group_by=["model"])

    cost_buckets = await svc.fetch_cost(start, end)
    prev_cost = await svc.fetch_cost(prev_start, prev_end)

    all_results = [r for b in usage_buckets for r in b.results]
    prev_results = [r for b in prev_buckets for r in b.results]

    t = totals(all_results)
    cost_total_now = cost_total([b.model_dump(mode="json") for b in cost_buckets])
    cost_total_prev = cost_total([b.model_dump(mode="json") for b in prev_cost])

    prev_tokens = sum(
        r.uncached_input_tokens + r.cache_creation_input_tokens
        + r.cache_read_input_tokens + r.output_tokens
        for r in prev_results
    )

    return SummaryResponse(
        total_input_tokens=t["uncached_input"],
        total_output_tokens=t["output"],
        total_cache_read_tokens=t["cache_read"],
        total_cache_creation_tokens=t["cache_creation"],
        total_cost_usd=cost_total_now,
        cache_hit_ratio=cache_hit_ratio(all_results),
        cache_savings_usd=0.0,  # requires per-model pricing table; left as 0 for now
        top_model=t["top_model"],  # type: ignore[arg-type]
        period_start=start,
        period_end=end,
        prev_period_cost_usd=cost_total_prev,
        prev_period_tokens=prev_tokens,
    )
