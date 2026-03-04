"""Pydantic v2 models matching the Ollama wire format."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Tool definitions (used in ChatRequest.tools)
# ---------------------------------------------------------------------------


class ToolFunctionParameters(BaseModel):
    type: str = "object"
    properties: dict[str, Any] = {}
    required: list[str] = []


class ToolFunction(BaseModel):
    name: str
    description: str = ""
    parameters: ToolFunctionParameters = ToolFunctionParameters()


class Tool(BaseModel):
    type: str = "function"
    function: ToolFunction


# ---------------------------------------------------------------------------
# Tool calls (used in Message.tool_calls)
# ---------------------------------------------------------------------------


class ToolCallFunction(BaseModel):
    name: str
    arguments: dict[str, Any] = {}


class ToolCall(BaseModel):
    function: ToolCallFunction


# ---------------------------------------------------------------------------
# Messages and requests
# ---------------------------------------------------------------------------


class Message(BaseModel):
    role: str
    content: str = ""  # May be empty when tool_calls are present
    tool_calls: list[ToolCall] | None = None


class ChatRequest(BaseModel):
    model: str
    messages: list[Message]
    stream: bool = False
    tools: list[Tool] | None = None


class ChatResponse(BaseModel):
    model: str
    created_at: datetime
    message: Message
    done: bool
    done_reason: str = ""


class GenerateRequest(BaseModel):
    model: str
    prompt: str
    system: str = ""
    stream: bool = False


class GenerateResponse(BaseModel):
    model: str
    created_at: datetime
    response: str
    done: bool
    done_reason: str = ""


class ModelDetails(BaseModel):
    parent_model: str = ""
    format: str = ""
    family: str = ""
    families: list[str] = []
    parameter_size: str = ""
    quantization_level: str = ""


class Model(BaseModel):
    name: str
    model: str
    modified_at: datetime
    size: int = 0
    digest: str
    details: ModelDetails


class TagsResponse(BaseModel):
    models: list[Model]


class VersionResponse(BaseModel):
    version: str


class ErrorResponse(BaseModel):
    error: str
