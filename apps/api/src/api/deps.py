"""FastAPI dependency providers."""

from __future__ import annotations

from typing import cast

from fastapi import Request
from generation import FakeLLMClient, LLMClient

from .store import InMemoryStore


def get_store(request: Request) -> InMemoryStore:
    return cast(InMemoryStore, request.app.state.store)


def get_llm_client(request: Request) -> LLMClient:
    llm_client = getattr(request.app.state, "llm_client", None)
    if llm_client is None:
        llm_client = FakeLLMClient()
        request.app.state.llm_client = llm_client
    return cast(LLMClient, llm_client)
