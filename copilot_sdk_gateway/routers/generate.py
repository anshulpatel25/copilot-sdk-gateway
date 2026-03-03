"""POST /api/generate router — single-turn text generation."""

import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from copilot_sdk_gateway.copilot.inference import CopilotInference
from copilot_sdk_gateway.models.ollama import ErrorResponse, GenerateRequest, GenerateResponse
from copilot_sdk_gateway.routers.chat import split_into_chunks

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_inference() -> CopilotInference:
    raise RuntimeError("inference dependency not configured")  # pragma: no cover


@router.post("/api/generate")
async def generate(
    req: GenerateRequest,
    inference: CopilotInference = Depends(_get_inference),
):
    if not req.model:
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(error="model is required").model_dump(),
        )
    if not req.prompt:
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(error="prompt is required").model_dump(),
        )

    try:
        content = await inference.complete(req.model, req.system, req.prompt)
    except Exception as exc:
        logger.error("inference error: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(error=str(exc)).model_dump(),
        ) from exc

    now = datetime.now(tz=UTC)

    if not req.stream:
        return GenerateResponse(
            model=req.model,
            created_at=now,
            response=content,
            done=True,
            done_reason="stop",
        )

    # Streaming: emit word-level NDJSON chunks
    chunks = split_into_chunks(content)

    async def stream_chunks():
        for chunk in chunks:
            resp = GenerateResponse(
                model=req.model,
                created_at=datetime.now(tz=UTC),
                response=chunk,
                done=False,
            )
            yield json.dumps(resp.model_dump(mode="json")) + "\n"
        sentinel = GenerateResponse(
            model=req.model,
            created_at=datetime.now(tz=UTC),
            response="",
            done=True,
            done_reason="stop",
        )
        yield json.dumps(sentinel.model_dump(mode="json")) + "\n"

    return StreamingResponse(stream_chunks(), media_type="application/x-ndjson")
