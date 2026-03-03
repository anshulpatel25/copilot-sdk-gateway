"""GET /api/version router."""

from fastapi import APIRouter

from copilot_sdk_gateway.models.ollama import VersionResponse

router = APIRouter()


@router.get("/api/version", response_model=VersionResponse)
async def get_version() -> VersionResponse:
    return VersionResponse(version="0.1.0")
