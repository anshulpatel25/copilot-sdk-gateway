# copilot-sdk-gateway

An **Ollama-compatible HTTP proxy** that forwards inference requests to the GitHub Copilot backend via the [GitHub Copilot Python SDK](https://github.com/github/copilot-sdk).

## Architecture

```
Ollama-compatible client  (e.g. Open WebUI, Continue, Aider)
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

Point any Ollama-compatible client at `http://localhost:11434`.

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

## Running as a systemd Service

```ini
# /etc/systemd/system/copilot-sdk-gateway.service
[Unit]
Description=copilot-sdk-gateway
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/opt/copilot-sdk-gateway
Environment=GITHUB_TOKEN=ghp_...
Environment=PORT=11434
ExecStart=/opt/copilot-sdk-gateway/.venv/bin/copilot-sdk-gateway
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable --now copilot-sdk-gateway
```

---

## License

MIT — see [LICENSE](LICENSE).
