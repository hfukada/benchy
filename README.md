# benchy

An alternative dashboard for Claude usage and cost metrics, pulled from the
Anthropic Admin API.

The official console shows totals and a couple of charts. benchy adds:

- **Cache efficiency** view — cache hit ratio, cache savings in dollars,
  cache_read vs cache_creation vs raw input.
- **Model mix over time** — stacked share by model, not just totals.
- **Input:output ratio** — proxy for prompt-heavy vs generation-heavy workloads.
- **Effective $/M output tokens** — cost / output, per model, over time.
- Drilldowns by **workspace**, **API key**, and **service tier**.

## Stack

- Backend: FastAPI, httpx, aiosqlite, pydantic-settings.
- Frontend: Vite + React + TypeScript, TanStack Query, Recharts, Tailwind, Zustand.
- Cache: local SQLite. Past usage buckets are immutable, so they are cached
  forever; only the current open bucket is re-fetched.

## Setup

```bash
cp .env.example .env
# fill in ANTHROPIC_ADMIN_API_KEY and ANTHROPIC_ORG_ID

make install   # uv sync + npm install
make dev       # runs backend (:8000) and frontend (:5173)
```

Open http://127.0.0.1:5173.

## Layout

```
backend/    FastAPI app, Admin API client, cache, derived metrics
frontend/   React dashboard
```

## Tests

```bash
make test
```

Backend tests use `respx` to mock the Anthropic API — they do not hit the
network.
