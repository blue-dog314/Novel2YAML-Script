"""Generation helpers and staged screenplay orchestration."""

from __future__ import annotations

from .assembly import assemble_screenplay
from .inputs import ChapterInput
from .llm import FakeLLMClient, LLMClient, OpenAICompatibleLLMClient
from .orchestrator import PipelineFailure, generate_screenplay

MODULE_NAME = "generation"

__all__ = [
    "MODULE_NAME",
    "ChapterInput",
    "FakeLLMClient",
    "LLMClient",
    "OpenAICompatibleLLMClient",
    "PipelineFailure",
    "assemble_screenplay",
    "generate_screenplay",
]
