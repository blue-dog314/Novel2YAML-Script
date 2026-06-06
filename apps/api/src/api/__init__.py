"""FastAPI application package for the novel-to-screenplay MVP."""

from __future__ import annotations

from .app import app, create_app

MODULE_NAME = "api"

__all__ = [
    "MODULE_NAME",
    "app",
    "create_app",
]
