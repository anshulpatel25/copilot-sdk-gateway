"""GET /api/tags router — list available Copilot models in Ollama format."""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException

from copilot_sdk_gateway.models.ollama import Model, ModelDetails, TagsResponse
from copilot_sdk_gateway.sdk.inference import CopilotInference

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_inference() -> CopilotInference:
    """Dependency placeholder; overridden by the app factory."""
    raise RuntimeError("inference dependency not configured")  # pragma: no cover


@router.get("/api/tags", response_model=TagsResponse)
async def list_models(
    inference: CopilotInference = Depends(_get_inference),
) -> TagsResponse:
    try:
        model_ids = await inference.list_models()
    except Exception as exc:
        logger.error("list_models failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    now = datetime.now(tz=UTC)
    models = []
    for mid in model_ids:
        # Append ':latest' if the model ID has no tag
        name = mid if ":" in mid else f"{mid}:latest"
        models.append(
            Model(
                name=name,
                model=name,
                modified_at=now,
                size=0,
                digest="",
                details=ModelDetails(),
            )
        )
    return TagsResponse(models=models)
