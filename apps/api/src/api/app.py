"""FastAPI application factory for the local MVP API."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .routes.jobs import router as jobs_router
from .routes.projects import router as projects_router
from .routes.screenplays import router as screenplays_router
from .store import InMemoryStore

_STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app() -> FastAPI:
    """Create the unauthenticated local MVP API app.

    This P0a-lite-1 API keeps all state in memory and is intended for local demo
    use only. Source text is accepted only through the rights-confirmed upload
    gate and is never returned by chapter-list endpoints.
    """
    api_app = FastAPI(title="Novel to Screenplay MVP API")
    api_app.state.store = InMemoryStore()

    api_app.include_router(projects_router)
    api_app.include_router(screenplays_router)
    api_app.include_router(jobs_router)

    # Serve the local author workbench (a no-build single-page UI) from the same
    # origin under /app, so it shares cookies/origin with the API and needs no
    # CORS. API routes live under /projects, /screenplays, /jobs and never
    # collide with this mount.
    api_app.mount(
        "/app",
        StaticFiles(directory=_STATIC_DIR, html=True),
        name="workbench",
    )
    return api_app


app = create_app()
