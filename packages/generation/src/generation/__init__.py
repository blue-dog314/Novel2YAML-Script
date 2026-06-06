"""Generation helpers and staged screenplay orchestration."""

from __future__ import annotations

from .artifacts import GenerationArtifacts
from .assembly import assemble_screenplay
from .inputs import ChapterInput
from .llm import FakeLLMClient, LLMClient, OpenAICompatibleLLMClient
from .orchestrator import (
    PipelineFailure,
    generate_screenplay,
    generate_screenplay_with_artifacts,
)

MODULE_NAME = "generation"

__all__ = [
    "MODULE_NAME",
    "ChapterInput",
    "FakeLLMClient",
    "GenerationArtifacts",
    "LLMClient",
    "OpenAICompatibleLLMClient",
    "PipelineFailure",
    "assemble_screenplay",
    "generate_screenplay",
    "generate_screenplay_with_artifacts",
]
