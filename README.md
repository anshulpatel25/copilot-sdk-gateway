# copilot-sdk-gateway

An **OpenAI-API-compatible HTTP proxy** that forwards inference requests to the GitHub Copilot backend via the [GitHub Copilot Python SDK](https://github.com/github/copilot-sdk).

## Architecture

```
OpenAI-API-compatible client  (e.g. Open WebUI, Continue, Aider)
        │
        ▼  HTTP  (Ollama wire format, port 11434)
copilot-sdk-gateway
        │
        ▼  github-copilot-sdk (Python)
  Copilot CLI  (spawned per request)
        │
        ▼
  GitHub Copilot / LLM backend
```

Key design decisions:

- **Per-request isolation** — every HTTP request creates its own `CopilotClient` + session.  No shared mutable state between concurrent calls.
- **Streaming emulation** — `session.send_and_wait()` fetches the full response; it is then split into word-level chunks and delivered as NDJSON.
- **Model ID normalisation** — any `:tag` suffix (e.g. `:latest`) is stripped before forwarding to the SDK.
- **12-factor config** — all configuration from environment variables; no hardcoded secrets.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.12+ | |
| [`uv`](https://docs.astral.sh/uv/) | Project / dependency manager |
| [Copilot CLI](https://docs.github.com/en/copilot/how-tos/set-up/install-copilot-cli) | `copilot` must be on `PATH` (or set `COPILOT_CLI_PATH`) |
| GitHub Copilot subscription | Required for non-BYOK usage |

---

## Quick Start

```bash
# 1. Clone and enter the repo
git clone https://github.com/anshulpatel25/copilot-sdk-gateway
cd copilot-sdk-gateway

# 2. Install dependencies (creates .venv automatically)
uv sync

# 3. Configure (optional — sensible defaults for local dev)
export GITHUB_TOKEN="ghp_..."   # or rely on `copilot auth login`

# 4. Run the gateway
uv run python -m copilot_sdk_gateway.main
# → Listening on http://0.0.0.0:11434
```

Point any OpenAI-API-compatible client at `http://localhost:11434`.

---

## Configuration Reference

All settings are read from environment variables (and optionally from a `.env` file).

| Variable | Default | Description |
|---|---|---|
| `PORT` | `11434` | TCP port to listen on |
| `GITHUB_TOKEN` | `""` | GitHub personal access token; empty = fall back to `copilot auth login` |
| `COPILOT_CLI_PATH` | `""` | Absolute path to the `copilot` binary; empty = locate on `PATH` |
| `COPILOT_CLI_URL` | `""` | Connect to an already-running CLI server (`host:port`); when set, `COPILOT_CLI_PATH` is ignored |
| `LOG_LEVEL` | `error` | Logging verbosity (`debug`, `info`, `warning`, `error`) |
| `INFERENCE_TIMEOUT` | `300.0` | Seconds to wait for the Copilot session to become idle before raising a `TimeoutError`; increase for slow or long-running models |

---

## API Reference

### `GET /api/version`

Returns the gateway version.

```bash
curl http://localhost:11434/api/version
# {"version":"0.1.0"}
```

---

### `GET /api/tags`

Lists available Copilot models in Ollama `tags` format.

```bash
curl http://localhost:11434/api/tags
```

```json
{
  "models": [
    {
      "name": "gpt-4o:latest",
      "model": "gpt-4o:latest",
      "modified_at": "2025-01-01T00:00:00Z",
      "size": 0,
      "digest": "",
      "details": {}
    }
  ]
}
```

---

### `POST /api/chat`

Multi-turn chat completion.

```bash
curl http://localhost:11434/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user",   "content": "What is the capital of France?"}
    ]
  }'
```

**Streaming:**

```bash
curl http://localhost:11434/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "Count to five."}],
    "stream": true
  }'
```

---

### `POST /api/generate`

Single-turn text generation.

```bash
curl http://localhost:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4o", "prompt": "Why is the sky blue?"}'
```

**Streaming:**

```bash
curl http://localhost:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4o", "prompt": "Write a haiku.", "stream": true}'
```

---

## Observability / Metrics

The gateway exposes a Prometheus scrape endpoint at **`GET /metrics`** (powered by
[`prometheus-fastapi-instrumentator`](https://github.com/trallnag/prometheus-fastapi-instrumentator)).

### Available metrics

#### Standard HTTP metrics (provided automatically by the instrumentator)

| Metric | Type | Description |
|---|---|---|
| `http_requests_total` | Counter | Total HTTP requests by `handler`, `status`, `method` |
| `http_request_size_bytes` | Summary | Incoming request content-length by `handler` |
| `http_response_size_bytes` | Summary | Outgoing response content-length by `handler` |
| `http_request_duration_seconds` | Histogram | Request latency by `handler` and `method` |
| `http_request_duration_highr_seconds` | Histogram | High-resolution latency (no labels) |

#### Custom business metrics

| Metric | Type | Labels | Description |
|---|---|---|---|
| `completions_total` | Counter | `model`, `endpoint` | Successful inference completions |
| `prompt_length_chars` | Histogram | `endpoint` | Prompt length in characters |
| `response_length_chars` | Histogram | `endpoint` | Response length in characters |

Metrics are recorded **only on successful completions** — errors do not increment any counter or histogram.

### Scraping with Prometheus

Add a scrape job to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: copilot-sdk-gateway
    static_configs:
      - targets: ["localhost:11434"]
    metrics_path: /metrics
```

### Example queries (PromQL)

```promql
# Completion rate per model over the last 5 minutes
rate(completions_total[5m])

# 95th-percentile response length per endpoint
histogram_quantile(0.95, sum by (le, endpoint) (rate(response_length_chars_bucket[5m])))

# Average prompt length per endpoint
rate(prompt_length_chars_sum[5m]) / rate(prompt_length_chars_count[5m])

# HTTP error rate (5xx) per handler
sum by (handler) (rate(http_requests_total{status="5xx"}[5m]))
```

### Verifying locally

```bash
curl http://localhost:11434/metrics
```

You should see output like:

```
# HELP completions_total Total number of successful completions
# TYPE completions_total counter
completions_total{endpoint="/api/chat",model="gpt-4o"} 3.0
# HELP prompt_length_chars Length of prompt in characters
# TYPE prompt_length_chars histogram
prompt_length_chars_bucket{endpoint="/api/chat",le="0.005"} 0.0
...
```

---

## Development Setup

```bash
# Install all dependencies (including dev)
uv sync

# Run tests
uv run pytest

# Lint
uv run ruff check copilot_sdk_gateway/ tests/

# Auto-fix lint issues
uv run ruff check --fix copilot_sdk_gateway/ tests/

# Start the server in development mode (auto-reload)
uv run uvicorn copilot_sdk_gateway.main:create_app \
    --factory --reload --port 11434
```

---

## License

MIT — see [LICENSE](LICENSE).
