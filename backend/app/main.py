from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import cost, dimensions, summary, usage

logging.basicConfig(level=logging.INFO)


def create_app() -> FastAPI:
    from .config import get_settings
    settings = get_settings()

    app = FastAPI(title="benchy", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    app.include_router(usage.router)
    app.include_router(cost.router)
    app.include_router(summary.router)
    app.include_router(dimensions.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


# Only create the module-level app when the API key is present.
# Tests import this module and call create_app() directly after patching env.
if os.environ.get("ANTHROPIC_ADMIN_API_KEY"):
    app = create_app()
