from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("ANTHROPIC_ADMIN_API_KEY", "sk-ant-admin01-test")
    monkeypatch.setenv("ANTHROPIC_ORG_ID", "org_test")
    monkeypatch.setenv("ANTHROPIC_API_BASE", "https://api.anthropic.test")
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
        path = f.name
    monkeypatch.setenv("BENCHY_CACHE_DB", path)
    # bust the get_settings cache so the env above takes effect
    from app.config import get_settings
    get_settings.cache_clear()
    from app.deps import _cache_singleton
    _cache_singleton.cache_clear()
    yield
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
