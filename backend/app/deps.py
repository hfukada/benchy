"""FastAPI dependencies."""
from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache

from fastapi import Depends

from .anthropic_client import AnthropicAdminClient
from .cache import BucketCache
from .config import Settings, get_settings
from .service import UsageService


@lru_cache
def _cache_singleton(path: str) -> BucketCache:
    return BucketCache(path)


def get_cache(settings: Settings = Depends(get_settings)) -> BucketCache:
    return _cache_singleton(settings.cache_db)


async def get_client(
    settings: Settings = Depends(get_settings),
) -> AsyncIterator[AnthropicAdminClient]:
    client = AnthropicAdminClient(settings)
    try:
        yield client
    finally:
        await client.aclose()


async def get_service(
    client: AnthropicAdminClient = Depends(get_client),
    cache: BucketCache = Depends(get_cache),
) -> UsageService:
    return UsageService(client, cache)
