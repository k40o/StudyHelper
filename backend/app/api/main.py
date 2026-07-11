"""FastAPI application factory.

Serves the JSON API under /api and, in production, the built React app at /.
CORS is open in dev so the Vite dev server (and your iPad) can call it.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .container import Container
from .routes import router

logging.basicConfig(level=logging.INFO)

# backend/app/api/main.py -> project root. Overridable for containers where the
# built frontend lives at a different path.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_DIST = Path(os.environ.get("STUDYGAME_FRONTEND_DIST", PROJECT_ROOT / "frontend" / "dist"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    container = Container()
    app.state.container = container
    container.start()
    try:
        yield
    finally:
        container.stop()


def create_app() -> FastAPI:
    app = FastAPI(title="StudyGame API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # dev-friendly; tighten for real deployment
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    @app.get("/healthz")
    def healthz() -> dict:
        """Unauthenticated liveness probe — used by the Electron shell to know
        when the bundled backend is ready, and by cloud host health checks."""
        return {"status": "ok"}

    # Serve the built frontend if it exists (single-server mode for iPad).
    if FRONTEND_DIST.exists():
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")

    return app


app = create_app()
