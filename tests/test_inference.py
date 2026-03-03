"""Unit tests for CopilotInference helpers (no SDK calls required)."""

import pytest

from copilot_sdk_gateway.config import Settings
from copilot_sdk_gateway.copilot.inference import CopilotInference
from copilot_sdk_gateway.models.ollama import Message


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
