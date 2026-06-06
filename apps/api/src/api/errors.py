"""HTTP error mapping helpers."""

from __future__ import annotations

from shared_types import PipelineError


def pipeline_error_status(error: PipelineError) -> int:
    if error.error_type == "chapter_count_insufficient":
        return 400
    if error.error_type in {"schema_validation_failed", "reference_validation_failed", "coverage_validation_failed"}:
        return 422
    if error.error_type == "model_output_invalid":
        return 502
    return 400
