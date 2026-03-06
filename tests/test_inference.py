"""Unit tests for CopilotInference helpers (no SDK calls required)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from copilot_sdk_gateway.config import Settings
from copilot_sdk_gateway.models.ollama import Message
from copilot_sdk_gateway.sdk.inference import CopilotInference


@pytest.fixture
def inference() -> CopilotInference:
    return CopilotInference(Settings())


class TestNormalizeModel:
    def test_strips_latest(self, inference):
        assert inference.normalize_model("gpt-4:latest") == "gpt-4"

    def test_strips_arbitrary_tag(self, inference):
        assert inference.normalize_model("claude-3:v2") == "claude-3"

    def test_no_tag_unchanged(self, inference):
        assert inference.normalize_model("gpt-4") == "gpt-4"

    def test_empty_string(self, inference):
        assert inference.normalize_model("") == ""


class TestBuildPromptFromMessages:
    def test_single_user_message_passthrough(self, inference):
        msgs = [Message(role="user", content="Hello")]
        assert inference.build_prompt_from_messages(msgs) == "Hello"

    def test_multiple_turns_labelled(self, inference):
        msgs = [
            Message(role="user", content="Hi"),
            Message(role="assistant", content="Hello!"),
            Message(role="user", content="How are you?"),
        ]
        result = inference.build_prompt_from_messages(msgs)
        assert result == "User: Hi\nAssistant: Hello!\nUser: How are you?"

    def test_single_assistant_message_passthrough(self, inference):
        msgs = [Message(role="assistant", content="Sure")]
        assert inference.build_prompt_from_messages(msgs) == "Sure"


class TestInferenceTimeout:
    def test_default_inference_timeout(self):
        settings = Settings()
        assert settings.inference_timeout == 300.0

    def test_custom_inference_timeout(self):
        settings = Settings(inference_timeout=120.0)
        assert settings.inference_timeout == 120.0

    async def test_complete_passes_timeout_to_send_and_wait(self):
        settings = Settings(inference_timeout=120.0)
        inference = CopilotInference(settings)

        mock_event = MagicMock()
        mock_event.data.content = "response text"

        mock_session = AsyncMock()
        mock_session.send_and_wait = AsyncMock(return_value=mock_event)
        mock_session.destroy = AsyncMock()

        mock_client = AsyncMock()
        mock_client.start = AsyncMock()
        mock_client.stop = AsyncMock()
        mock_client.create_session = AsyncMock(return_value=mock_session)

        with patch("copilot_sdk_gateway.sdk.inference.CopilotClient", return_value=mock_client):
            result = await inference.complete("gpt-4o", "", "Hello")

        assert result == "response text"
        mock_session.send_and_wait.assert_awaited_once_with(
            {"prompt": "Hello"}, timeout=120.0
        )
