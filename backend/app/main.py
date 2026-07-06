"""FastAPI app factory and router mounting."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.config import Settings, get_settings
from app.decks.router import router as decks_router
from app.spa import SPAStaticFiles
from app.storage import Storage

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    """Give the `app.*` loggers their own stderr handler at INFO.

    Without this, uvicorn doesn't route our application loggers, so INFO-level
    generation/upload logs stay invisible and failures surface only as bare tracebacks.
    """
    app_logger = logging.getLogger("app")
    if app_logger.handlers:  # idempotent — safe if create_app runs more than once
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    app_logger.addHandler(handler)
    app_logger.setLevel(logging.INFO)
    # Leave propagate=True: uvicorn adds no root handler (so no double-logging), and pytest's
    # caplog captures via root propagation. Setting it False silently breaks log-assertion tests.


def create_app(settings: Settings | None = None) -> FastAPI:
    _configure_logging()
    settings = settings or get_settings()
    app = FastAPI(title="Smart Flashcards API")
    app.state.settings = settings
    app.state.storage = Storage(settings.data_dir)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router)
    app.include_router(decks_router)

    @app.get("/api/health", tags=["ops"])
    def health() -> dict[str, str]:
        """Unauthenticated liveness probe for the hosting platform."""
        return {"status": "ok"}

    # Production: serve the built frontend from the same origin (docs/DEPLOY.md).
    # Mounted last so every /api route above takes precedence.
    if settings.static_dir is not None:
        if settings.static_dir.is_dir():
            app.mount("/", SPAStaticFiles(directory=settings.static_dir, html=True), name="spa")
        else:
            logger.warning(
                "STATIC_DIR %s does not exist — SPA serving disabled", settings.static_dir
            )
    return app


app = create_app()
