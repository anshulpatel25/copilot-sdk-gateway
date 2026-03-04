# AGENTS.md — AI Agent Guidance for copilot-sdk-gateway

## Project Purpose

`copilot-sdk-gateway` is an **OpenAI-API-compatible HTTP proxy** written in Python.  
It translates Ollama wire-format requests into GitHub Copilot SDK calls, enabling any OpenAI-API-compatible client (Open WebUI, Continue, Aider, …) to use GitHub Copilot as its LLM backend.

---

## Repository Layout

```
copilot-sdk-gateway/
├── pyproject.toml                   ← single source of truth (uv + hatchling)
├── README.md
├── AGENTS.md                        ← this file
├── copilot_sdk_gateway/
│   ├── __init__.py
│   ├── main.py                      ← FastAPI app factory + uvicorn entry point
│   ├── config.py                    ← pydantic-settings (env-var config)
│   ├── metrics.py                   ← Prometheus business metrics (Counter + Histogram)
│   ├── models/
│   │   ├── __init__.py
│   │   └── ollama.py                ← Pydantic v2 request/response models
│   ├── sdk/
│   │   ├── __init__.py
│   │   └── inference.py             ← CopilotInference (SDK wrapper)
│   └── routers/
│       ├── __init__.py
│       ├── chat.py                  ← POST /api/chat
│       ├── generate.py              ← POST /api/generate
│       ├── models.py                ← GET /api/tags
│       └── version.py               ← GET /api/version
└── tests/
    ├── __init__.py
    ├── test_api.py                  ← FastAPI endpoint integration tests (mocked SDK)
    ├── test_chunks.py               ← Unit tests for split_into_chunks
    ├── test_inference.py            ← Unit tests for CopilotInference helpers
    └── test_metrics.py              ← Integration tests for /metrics endpoint
```

---

## Package Descriptions

| Module | Responsibility |
|---|---|
| `config.py` | `Settings` (pydantic-settings) + `get_settings()` cached factory |
| `metrics.py` | Prometheus business metrics (`completions_total`, `prompt_length_chars`, `response_length_chars`) |
| `models/ollama.py` | Pydantic v2 models for the Ollama wire format |
| `sdk/inference.py` | `CopilotInference`: wraps `github-copilot-sdk`; per-request client isolation |
| `routers/chat.py` | `POST /api/chat`; streaming helper `split_into_chunks`; records metrics on success |
| `routers/generate.py` | `POST /api/generate`; records metrics on success |
| `routers/models.py` | `GET /api/tags` |
| `routers/version.py` | `GET /api/version` |
| `main.py` | `create_app()` factory; dependency injection wiring; mounts PFI at `/metrics`; `main()` entry point |

---

## Coding Conventions

1. **Type hints everywhere** — all function signatures, return types, and variables must be annotated.
2. **async/await throughout** — all FastAPI handlers are `async def`; blocking SDK calls use `asyncio.get_event_loop().run_in_executor`.
3. **Pydantic v2** — use `model.model_dump(mode="json")` (not `.dict()`); no deprecated `json_encoders`.
4. **Per-request SDK isolation** — `CopilotInference.complete()` and `list_models()` each create a fresh `CopilotClient`, start it, use it, and stop it.  Never hold a shared client across requests.
5. **Dependency injection** — pass `CopilotInference` into routers via `app.dependency_overrides`; routers declare a `_get_inference()` placeholder.
6. **12-factor config** — all config from env vars via `Settings`; no hardcoded secrets.
7. **Logging** — `logging.getLogger(__name__)` per module; log to stdout; level from `LOG_LEVEL`.
8. **Error handling** — validation errors → 400; inference errors → 500; always wrap in `ErrorResponse`.
9. **Ruff** — linting is enforced (`UP`, `E`, `F`, `I` rule sets).  Run `uv run ruff check --fix` before committing.

---

## How to Add a New Endpoint

1. Create `copilot_sdk_gateway/routers/my_endpoint.py` with:
   - A `_get_inference()` placeholder dependency function.
   - An `APIRouter` and one or more route handlers.
2. Add any new request/response Pydantic models to `models/ollama.py`.
3. In `main.py → create_app()`:
   - Import the new router.
   - `app.include_router(my_endpoint.router)`
   - `app.dependency_overrides[my_endpoint._get_inference] = get_inference`
4. Write tests in `tests/test_api.py` (mock `CopilotInference` methods with `AsyncMock`).

---

## API Reference

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/version` | Returns `{"version":"0.1.0"}` |
| `GET` | `/api/tags` | Lists available Copilot models in Ollama format |
| `POST` | `/api/chat` | Multi-turn chat completion |
| `POST` | `/api/generate` | Single-turn text generation |
| `GET` | `/metrics` | Prometheus scrape endpoint (HTTP + business metrics) |

All streaming responses use `StreamingResponse` with `media_type="application/x-ndjson"`.

---

## Prometheus Metrics

Metrics are exposed at `GET /metrics` via [`prometheus-fastapi-instrumentator`](https://github.com/trallnag/prometheus-fastapi-instrumentator).

### Custom business metrics (defined in `metrics.py`)

| Metric | Type | Labels | Recorded when |
|---|---|---|---|
| `completions_total` | Counter | `model`, `endpoint` | Successful inference only |
| `prompt_length_chars` | Histogram | `endpoint` | Successful inference only |
| `response_length_chars` | Histogram | `endpoint` | Successful inference only |

### Instrumentator wiring (`main.py`)

```python
from prometheus_fastapi_instrumentator import Instrumentator

instrumentator = Instrumentator()
instrumentator.instrument(app).expose(app)
```

This registers the PFI middleware and adds a `GET /metrics` route automatically.  The standard HTTP metrics (request count, latency, sizes) are included out of the box.

### When adding a new endpoint that calls `inference.complete()`

After a successful `inference.complete()` call, record metrics:

```python
from copilot_sdk_gateway.metrics import (
    completions_total,
    prompt_length_chars,
    response_length_chars,
)

completions_total.labels(model=req.model, endpoint="/api/my_endpoint").inc()
prompt_length_chars.labels(endpoint="/api/my_endpoint").observe(len(prompt))
response_length_chars.labels(endpoint="/api/my_endpoint").observe(len(content))
```

Do **not** record metrics in error paths — only on successful completion.

---

## Build and Run Commands

```bash
# Install all dependencies (creates .venv)
uv sync

# Run the server
uv run python -m copilot_sdk_gateway.main

# Run tests
uv run pytest

# Lint (check only)
uv run ruff check copilot_sdk_gateway/ tests/

# Lint (auto-fix)
uv run ruff check --fix copilot_sdk_gateway/ tests/
```

---

## Environment Setup for Local Development

```bash
# Copy the example env file and fill in values
cp .env.example .env   # if provided, otherwise create manually

# Minimum config for local dev (CLI login):
export PORT=11434
export LOG_LEVEL=debug

# Or with a token:
export GITHUB_TOKEN=ghp_...
```

---

## Security Notes

- **Never commit secrets** — `GITHUB_TOKEN` and similar credentials must only be set via env vars or a `.env` file (which is in `.gitignore`).
- **No persistent client state** — per-request isolation prevents token or session leakage between concurrent callers.
- **Input validation** — all incoming JSON is validated by Pydantic before reaching business logic.
- **Error messages** — SDK exceptions are caught and returned as `ErrorResponse`; raw tracebacks are never exposed to clients.
