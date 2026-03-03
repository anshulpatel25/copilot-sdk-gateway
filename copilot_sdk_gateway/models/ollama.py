"""Pydantic v2 models matching the Ollama wire format."""

from datetime import datetime

from pydantic import BaseModel


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str
    messages: list[Message]
    stream: bool = False


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
