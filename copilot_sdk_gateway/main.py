"""Entry point: creates FastAPI app, registers routes, handles lifecycle."""

import logging

import uvicorn
from fastapi import FastAPI

from copilot_sdk_gateway.config import Settings, get_settings
from copilot_sdk_gateway.routers import chat, generate, models, version
from copilot_sdk_gateway.sdk.inference import CopilotInference


def _configure_logging(log_level: str) -> None:
    level = getattr(logging, log_level.upper(), logging.ERROR)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory — creates and configures the FastAPI app."""
    if settings is None:
        settings = get_settings()

    _configure_logging(settings.log_level)

    inference = CopilotInference(settings)

    app = FastAPI(title="copilot-sdk-gateway", version="0.1.0")

    # Wire the inference dependency into each router
    def get_inference() -> CopilotInference:
        return inference

    app.include_router(version.router)
    app.include_router(
        models.router,
        dependencies=[],
    )
    app.include_router(
        chat.router,
        dependencies=[],
    )
    app.include_router(
        generate.router,
        dependencies=[],
    )

    # Override dependency providers
    app.dependency_overrides[models._get_inference] = get_inference
    app.dependency_overrides[chat._get_inference] = get_inference
    app.dependency_overrides[generate._get_inference] = get_inference

    logger = logging.getLogger(__name__)
    logger.info("copilot-sdk-gateway started on port %d", settings.port)

    return app


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "copilot_sdk_gateway.main:create_app",
        factory=True,
        host="0.0.0.0",
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
