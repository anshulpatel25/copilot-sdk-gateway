"""Tests for Prometheus metrics: /metrics endpoint and metric recording."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from copilot_sdk_gateway.config import Settings
from copilot_sdk_gateway.main import create_app
from copilot_sdk_gateway.metrics import (
    completions_total,
    prompt_length_chars,
    response_length_chars,
)
from copilot_sdk_gateway.sdk.inference import CopilotInference


@pytest.fixture
def app():
    return create_app(settings=Settings())


@pytest.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# /metrics endpoint
# ---------------------------------------------------------------------------


async def test_metrics_endpoint_available(client):
    resp = await client.get("/metrics/")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]


async def test_metrics_endpoint_contains_completions_total(client):
    resp = await client.get("/metrics/")
    assert "completions_total" in resp.text


async def test_metrics_endpoint_contains_prompt_length_chars(client):
    resp = await client.get("/metrics/")
    assert "prompt_length_chars" in resp.text


async def test_metrics_endpoint_contains_response_length_chars(client):
    resp = await client.get("/metrics/")
    assert "response_length_chars" in resp.text


# ---------------------------------------------------------------------------
# completions_total counter
# ---------------------------------------------------------------------------


async def test_chat_increments_completions_total(client):
    before = completions_total.labels(model="gpt-4o", endpoint="/api/chat")._value.get()
    with patch.object(CopilotInference, "complete", new_callable=AsyncMock) as mock_c:
        mock_c.return_value = "Hello!"
        resp = await client.post(
            "/api/chat",
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Hi"}]},
        )
    assert resp.status_code == 200
    after = completions_total.labels(model="gpt-4o", endpoint="/api/chat")._value.get()
    assert after == before + 1


async def test_generate_increments_completions_total(client):
    before = completions_total.labels(
        model="gpt-4o", endpoint="/api/generate"
    )._value.get()
    with patch.object(CopilotInference, "complete", new_callable=AsyncMock) as mock_c:
        mock_c.return_value = "42"
        resp = await client.post(
            "/api/generate",
            json={"model": "gpt-4o", "prompt": "What is 6*7?"},
        )
    assert resp.status_code == 200
    after = completions_total.labels(
        model="gpt-4o", endpoint="/api/generate"
    )._value.get()
    assert after == before + 1


async def test_chat_error_does_not_increment_completions_total(client):
    before = completions_total.labels(model="gpt-4o", endpoint="/api/chat")._value.get()
    with patch.object(CopilotInference, "complete", new_callable=AsyncMock) as mock_c:
        mock_c.side_effect = RuntimeError("sdk failure")
        resp = await client.post(
            "/api/chat",
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Hi"}]},
        )
    assert resp.status_code == 500
    after = completions_total.labels(model="gpt-4o", endpoint="/api/chat")._value.get()
    assert after == before  # counter must NOT have been incremented


# ---------------------------------------------------------------------------
# prompt_length_chars and response_length_chars histograms
# ---------------------------------------------------------------------------


async def test_chat_observes_prompt_and_response_length(client):
    prompt_before = prompt_length_chars.labels(endpoint="/api/chat")._sum.get()
    response_before = response_length_chars.labels(endpoint="/api/chat")._sum.get()

    with patch.object(CopilotInference, "complete", new_callable=AsyncMock) as mock_c:
        mock_c.return_value = "Sure!"
        await client.post(
            "/api/chat",
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Hello"}]},
        )

    prompt_after = prompt_length_chars.labels(endpoint="/api/chat")._sum.get()
    response_after = response_length_chars.labels(endpoint="/api/chat")._sum.get()

    # Prompt "Hello" has 5 chars; response "Sure!" has 5 chars
    assert prompt_after == prompt_before + 5
    assert response_after == response_before + 5


async def test_generate_observes_prompt_and_response_length(client):
    prompt_before = prompt_length_chars.labels(endpoint="/api/generate")._sum.get()
    response_before = response_length_chars.labels(endpoint="/api/generate")._sum.get()

    with patch.object(CopilotInference, "complete", new_callable=AsyncMock) as mock_c:
        mock_c.return_value = "42"
        await client.post(
            "/api/generate",
            json={"model": "gpt-4o", "prompt": "What is 6*7?"},
        )

    prompt_after = prompt_length_chars.labels(endpoint="/api/generate")._sum.get()
    response_after = response_length_chars.labels(endpoint="/api/generate")._sum.get()

    # prompt "What is 6*7?" = 12 chars; response "42" = 2 chars
    assert prompt_after == prompt_before + 12
    assert response_after == response_before + 2
