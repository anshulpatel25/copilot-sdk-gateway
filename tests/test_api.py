"""Integration tests for FastAPI endpoints using HTTPX test client.

The Copilot SDK's `CopilotInference.complete` and `list_models` methods
are mocked so no real SDK/CLI is needed.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from copilot_sdk_gateway.config import Settings
from copilot_sdk_gateway.copilot.inference import CopilotInference
from copilot_sdk_gateway.main import create_app


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
# /api/version
# ---------------------------------------------------------------------------


async def test_version(client):
    resp = await client.get("/api/version")
    assert resp.status_code == 200
    assert resp.json() == {"version": "0.1.0"}


# ---------------------------------------------------------------------------
# /api/tags
# ---------------------------------------------------------------------------


async def test_list_models(client):
    with patch.object(CopilotInference, "list_models", new_callable=AsyncMock) as mock_lm:
        mock_lm.return_value = ["gpt-4o", "claude-sonnet-4-5"]
        resp = await client.get("/api/tags")

    assert resp.status_code == 200
    data = resp.json()
    names = [m["name"] for m in data["models"]]
    assert "gpt-4o:latest" in names
    assert "claude-sonnet-4-5:latest" in names


async def test_list_models_preserves_existing_tag(client):
    with patch.object(CopilotInference, "list_models", new_callable=AsyncMock) as mock_lm:
        mock_lm.return_value = ["gpt-4o:preview"]
        resp = await client.get("/api/tags")

    assert resp.status_code == 200
    names = [m["name"] for m in resp.json()["models"]]
    assert "gpt-4o:preview" in names


# ---------------------------------------------------------------------------
# /api/chat
# ---------------------------------------------------------------------------


async def test_chat_non_streaming(client):
    with patch.object(CopilotInference, "complete", new_callable=AsyncMock) as mock_c:
        mock_c.return_value = "Hello there!"
        resp = await client.post(
            "/api/chat",
            json={
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": "Hi"}],
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["done"] is True
    assert data["message"]["content"] == "Hello there!"
    assert data["message"]["role"] == "assistant"


async def test_chat_streaming(client):
    with patch.object(CopilotInference, "complete", new_callable=AsyncMock) as mock_c:
        mock_c.return_value = "hello world"
        resp = await client.post(
            "/api/chat",
            json={
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": "Hi"}],
                "stream": True,
            },
        )

    assert resp.status_code == 200
    lines = [line for line in resp.text.strip().split("\n") if line]
    objects = [json.loads(line) for line in lines]
    # Non-sentinel chunks
    non_done = [o for o in objects if not o["done"]]
    assert len(non_done) == 2  # "hello " and "world"
    assert non_done[0]["message"]["content"] == "hello "
    assert non_done[1]["message"]["content"] == "world"
    # Sentinel
    sentinel = objects[-1]
    assert sentinel["done"] is True
    assert sentinel["done_reason"] == "stop"


async def test_chat_missing_model(client):
    resp = await client.post(
        "/api/chat",
        json={"model": "", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 400


async def test_chat_empty_messages(client):
    resp = await client.post(
        "/api/chat",
        json={"model": "gpt-4o", "messages": []},
    )
    assert resp.status_code == 400


async def test_chat_only_system_messages(client):
    resp = await client.post(
        "/api/chat",
        json={
            "model": "gpt-4o",
            "messages": [{"role": "system", "content": "You are helpful."}],
        },
    )
    assert resp.status_code == 400


async def test_chat_with_system_message(client):
    with patch.object(CopilotInference, "complete", new_callable=AsyncMock) as mock_c:
        mock_c.return_value = "Sure!"
        resp = await client.post(
            "/api/chat",
            json={
                "model": "gpt-4o",
                "messages": [
                    {"role": "system", "content": "Be brief."},
                    {"role": "user", "content": "Hello"},
                ],
            },
        )
    assert resp.status_code == 200
    # Verify system message was passed through
    call_args = mock_c.call_args
    assert call_args[0][1] == "Be brief."  # system_message arg


# ---------------------------------------------------------------------------
# /api/generate
# ---------------------------------------------------------------------------


async def test_generate_non_streaming(client):
    with patch.object(CopilotInference, "complete", new_callable=AsyncMock) as mock_c:
        mock_c.return_value = "42"
        resp = await client.post(
            "/api/generate",
            json={"model": "gpt-4o", "prompt": "What is 6*7?"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["response"] == "42"
    assert data["done"] is True


async def test_generate_streaming(client):
    with patch.object(CopilotInference, "complete", new_callable=AsyncMock) as mock_c:
        mock_c.return_value = "forty two"
        resp = await client.post(
            "/api/generate",
            json={"model": "gpt-4o", "prompt": "6*7?", "stream": True},
        )

    assert resp.status_code == 200
    lines = [line for line in resp.text.strip().split("\n") if line]
    objects = [json.loads(line) for line in lines]
    sentinel = objects[-1]
    assert sentinel["done"] is True
    assert sentinel["done_reason"] == "stop"


async def test_generate_missing_prompt(client):
    resp = await client.post(
        "/api/generate",
        json={"model": "gpt-4o", "prompt": ""},
    )
    assert resp.status_code == 400


async def test_generate_with_system(client):
    with patch.object(CopilotInference, "complete", new_callable=AsyncMock) as mock_c:
        mock_c.return_value = "OK"
        resp = await client.post(
            "/api/generate",
            json={"model": "gpt-4o", "prompt": "Hello", "system": "Be concise."},
        )
    assert resp.status_code == 200
    call_args = mock_c.call_args
    assert call_args[0][1] == "Be concise."
