"""GitHub Copilot SDK inference wrapper with per-request client isolation."""

import logging
import re

from copilot import CopilotClient, PermissionHandler

from copilot_sdk_gateway.config import Settings
from copilot_sdk_gateway.models.ollama import Message

logger = logging.getLogger(__name__)


class CopilotInference:
    """Wraps the GitHub Copilot SDK to provide chat/generate/list_models."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def normalize_model(self, model: str) -> str:
        """Strip any ':tag' suffix (e.g. ':latest') from model IDs."""
        return re.sub(r":[^:]+$", "", model)

    def build_prompt_from_messages(self, messages: list[Message]) -> str:
        """
        Convert ordered [{role, content}] turns into a single prompt string.

        Single user message: pass through unchanged.
        Multiple turns: format as a labelled conversation history block.
        """
        if len(messages) == 1:
            return messages[0].content

        parts: list[str] = []
        for msg in messages:
            label = msg.role.capitalize()
            parts.append(f"{label}: {msg.content}")
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Client factory
    # ------------------------------------------------------------------

    def _build_client_options(self) -> dict:
        opts: dict = {"log_level": self._settings.log_level}
        if self._settings.github_token:
            opts["github_token"] = self._settings.github_token
        if self._settings.copilot_cli_url:
            opts["cli_url"] = self._settings.copilot_cli_url
        elif self._settings.copilot_cli_path:
            opts["cli_path"] = self._settings.copilot_cli_path
        return opts

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def complete(self, model: str, system_message: str, prompt: str) -> str:
        """
        Create a fresh SDK client + session per call (per-request isolation).
        Returns the assistant response text.
        """
        model = self.normalize_model(model)
        logger.debug("complete: model=%s prompt_len=%d", model, len(prompt))

        client = CopilotClient(self._build_client_options())
        try:
            await client.start()

            session_config: dict = {
                "model": model,
                "on_permission_request": PermissionHandler.approve_all,
            }
            if system_message:
                session_config["system_message"] = {
                    "mode": "replace",
                    "content": system_message,
                }

            session = await client.create_session(session_config)
            try:
                event = await session.send_and_wait(
                    {"prompt": prompt}, timeout=self._settings.inference_timeout
                )
                if event is None:
                    return ""
                return str(event.data.content)
            finally:
                await session.destroy()
        finally:
            await client.stop()

    async def list_models(self) -> list[str]:
        """Create a fresh SDK client, call list_models(), return model IDs."""
        client = CopilotClient(self._build_client_options())
        try:
            await client.start()
            models = await client.list_models()
            return [m.id for m in models]
        finally:
            await client.stop()
