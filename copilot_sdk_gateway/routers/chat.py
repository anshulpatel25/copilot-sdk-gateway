"""POST /api/chat router — multi-turn chat completion."""

import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from copilot_sdk_gateway.metrics import (
    completions_total,
    prompt_length_chars,
    response_length_chars,
)
from copilot_sdk_gateway.models.ollama import (
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    Message,
    ToolCall,
    ToolCallFunction,
)
from copilot_sdk_gateway.sdk.inference import CopilotInference

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_inference() -> CopilotInference:
    raise RuntimeError("inference dependency not configured")  # pragma: no cover


def split_into_chunks(content: str) -> list[str]:
    """Split content on whitespace; append a trailing space to all but the last chunk."""
    words = content.split()
    if not words:
        return []
    return [w + " " for w in words[:-1]] + [words[-1]]


def _split_messages(messages: list[Message]) -> tuple[str, list[Message]]:
    """Separate system messages from conversation turns."""
    system_parts: list[str] = []
    conversation: list[Message] = []
    for msg in messages:
        if msg.role == "system":
            system_parts.append(msg.content)
        else:
            conversation.append(msg)
    return "\n".join(system_parts), conversation


def _build_tool_calls(raw: list[dict]) -> list[ToolCall]:
    """Convert raw SDK tool-call dicts into Ollama :class:`ToolCall` objects."""
    result: list[ToolCall] = []
    for item in raw:
        fn = item.get("function", {})
        result.append(
            ToolCall(
                function=ToolCallFunction(
                    name=fn.get("name", ""),
                    arguments=fn.get("arguments", {}),
                )
            )
        )
    return result


@router.post("/api/chat")
async def chat(
    req: ChatRequest,
    inference: CopilotInference = Depends(_get_inference),
):
    if not req.model:
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(error="model is required").model_dump(),
        )
    if not req.messages:
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(error="messages must not be empty").model_dump(),
        )

    system_message, conversation = _split_messages(req.messages)

    if not conversation:
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error="at least one non-system message is required"
            ).model_dump(),
        )

    prompt = inference.build_prompt_from_messages(conversation)

    try:
        result = await inference.complete(req.model, system_message, prompt, tools=req.tools)
    except Exception as exc:
        logger.error("inference error: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(error=str(exc)).model_dump(),
        ) from exc

    content = result.content
    tool_calls = _build_tool_calls(result.tool_calls) if result.tool_calls else None

    completions_total.labels(model=req.model, endpoint="/api/chat").inc()
    prompt_length_chars.labels(endpoint="/api/chat").observe(len(prompt))
    response_length_chars.labels(endpoint="/api/chat").observe(len(content))

    now = datetime.now(tz=UTC)

    if not req.stream:
        return ChatResponse(
            model=req.model,
            created_at=now,
            message=Message(role="assistant", content=content, tool_calls=tool_calls),
            done=True,
            done_reason="stop",
        )

    # Streaming: emit word-level NDJSON chunks
    chunks = split_into_chunks(content)

    async def stream_chunks():
        # If the response contains tool calls, emit a single chunk with them
        if tool_calls:
            resp = ChatResponse(
                model=req.model,
                created_at=datetime.now(tz=UTC),
                message=Message(role="assistant", content=content, tool_calls=tool_calls),
                done=True,
                done_reason="stop",
            )
            yield json.dumps(resp.model_dump(mode="json")) + "\n"
            return

        for chunk in chunks:
            resp = ChatResponse(
                model=req.model,
                created_at=datetime.now(tz=UTC),
                message=Message(role="assistant", content=chunk),
                done=False,
            )
            yield json.dumps(resp.model_dump(mode="json")) + "\n"
        sentinel = ChatResponse(
            model=req.model,
            created_at=datetime.now(tz=UTC),
            message=Message(role="assistant", content=""),
            done=True,
            done_reason="stop",
        )
        yield json.dumps(sentinel.model_dump(mode="json")) + "\n"

    return StreamingResponse(stream_chunks(), media_type="application/x-ndjson")
