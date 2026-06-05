"""Pipeline error contract.

Reference: SKILL.md section 9 (failure handling rules).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from ._config import FORBID_EXTRA_CONFIG

# Pipeline stage identifiers, in snake_case, aligned with the staged generation
# flow in SKILL.md (section "Use staged generation", steps 1-10).
PipelineStage = Literal[
    "chapter_parsing",
    "chapter_confirmation",
    "summarizing",
    "key_event_extraction",
    "scene_planning",
    "scene_content_generation",
    "assembly",
    "validation",
    "export",
    "revalidation",
]

PipelineErrorType = Literal[
    "chapter_parse_failed",
    "chapter_count_insufficient",
    "model_output_invalid",
    "schema_validation_failed",
    "reference_validation_failed",
    "coverage_validation_failed",
    "content_quality_warning",
]


class PipelineError(BaseModel):
    """A user-readable, structured error returned when a stage fails."""

    model_config = FORBID_EXTRA_CONFIG

    failed_stage: PipelineStage
    error_type: PipelineErrorType
    error_message: str
    retryable: bool
    completed_artifacts: list[str] = []
    suggested_action: str
