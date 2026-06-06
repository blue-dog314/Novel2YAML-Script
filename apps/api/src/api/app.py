"""FastAPI application factory for the local MVP API."""

from __future__ import annotations

from fastapi import FastAPI

from .routes.jobs import router as jobs_router
from .routes.projects import router as projects_router
from .routes.screenplays import router as screenplays_router
from .store import InMemoryStore


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
    return api_app


app = create_app()
