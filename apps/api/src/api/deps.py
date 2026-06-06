"""FastAPI dependency providers."""

from __future__ import annotations

from os import environ
from typing import cast

from fastapi import Request
from generation import FakeLLMClient, LLMClient, OpenAICompatibleLLMClient

from .store import InMemoryStore


def get_store(request: Request) -> InMemoryStore:
    return cast(InMemoryStore, request.app.state.store)


def get_llm_client(request: Request) -> LLMClient:
    llm_client = getattr(request.app.state, "llm_client", None)
    if llm_client is None:
        provider = environ.get("NOVEL_TO_SCREENPLAY_LLM_PROVIDER", "fake").strip().casefold()
        if provider == "fake":
            llm_client = FakeLLMClient()
        elif provider in {"openai", "openai-compatible"}:
            llm_client = OpenAICompatibleLLMClient.from_env()
        else:
            raise RuntimeError(f"Unsupported LLM provider {provider!r}.")
        request.app.state.llm_client = llm_client
    return cast(LLMClient, llm_client)
