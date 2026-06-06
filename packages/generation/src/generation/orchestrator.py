"""Staged generation orchestrator."""

from __future__ import annotations

from typing import NoReturn

from exporters import export_validated_yaml
from shared_types import (
    AdaptationConfig,
    PipelineError,
    PipelineErrorType,
    PipelineStage,
    ScreenplayDraftDocument,
    ValidationReport,
)
from validators import validate_document

from .assembly import assemble_screenplay
from .chapter_summary import summarize_chapters
from .inputs import ChapterInput
from .llm import LLMClient
from .repair import ModelOutputInvalid
from .scene_planner import plan_scenes
from .scene_writer import write_scene


class PipelineFailure(Exception):
    """Exception wrapper carrying the public PipelineError contract."""

    def __init__(self, error: PipelineError) -> None:
        self.error = error
        super().__init__(error.error_message)


def generate_screenplay(
    *,
    chapters: list[ChapterInput],
    project_id: str,
    title: str,
    original_author: str,
    language: str,
    model: str,
    llm: LLMClient,
    adaptation_config: AdaptationConfig | None = None,
) -> ScreenplayDraftDocument:
    """Run staged generation through assembly, validation, export, and re-parse."""
    completed_artifacts: list[str] = []
    if len(chapters) < 3:
        _raise_pipeline_failure(
            failed_stage="chapter_parsing",
            error_type="chapter_count_insufficient",
            error_message="At least three confirmed chapters are required.",
            retryable=False,
            completed_artifacts=completed_artifacts,
            suggested_action="Provide three or more confirmed chapters before generation.",
        )

    try:
        chapter_summaries = summarize_chapters(chapters, llm)
    except ModelOutputInvalid as exc:
        _raise_model_output_failure(exc, completed_artifacts)
    except Exception as exc:
        _raise_unexpected_stage_failure("summarizing", exc, completed_artifacts)
    completed_artifacts.append("chapter_summaries")

    try:
        scene_plan = plan_scenes(chapter_summaries, llm)
    except ModelOutputInvalid as exc:
        _raise_model_output_failure(exc, completed_artifacts)
    except Exception as exc:
        _raise_unexpected_stage_failure("scene_planning", exc, completed_artifacts)
    completed_artifacts.append("scene_plan")

    scene_contents = []
    for index, plan_item in enumerate(scene_plan.scenes, start=1):
        try:
            scene_contents.append(write_scene(_scene_id(index), plan_item, llm))
        except ModelOutputInvalid as exc:
            _raise_model_output_failure(exc, completed_artifacts)
        except Exception as exc:
            _raise_unexpected_stage_failure(
                "scene_content_generation",
                exc,
                completed_artifacts,
            )
    completed_artifacts.append("scene_contents")

    try:
        document = assemble_screenplay(
            chapter_summaries=chapter_summaries,
            scene_plan=scene_plan,
            scene_contents=scene_contents,
            project_id=project_id,
            title=title,
            original_author=original_author,
            language=language,
            model=model,
            adaptation_config=adaptation_config,
        )
    except Exception as exc:
        _raise_pipeline_failure(
            failed_stage="assembly",
            error_type="model_output_invalid",
            error_message=f"Assembly failed: {exc}",
            retryable=True,
            completed_artifacts=completed_artifacts,
            suggested_action="Regenerate the model outputs and try assembly again.",
        )
    completed_artifacts.append("screenplay_draft")

    report = validate_document(document)
    if not _report_passed(report):
        _raise_pipeline_failure(
            failed_stage="validation",
            error_type=_validation_error_type(report),
            error_message=_validation_error_message(report),
            retryable=True,
            completed_artifacts=completed_artifacts,
            suggested_action="Regenerate or repair the staged outputs before export.",
        )
    completed_artifacts.append("validation_report")

    try:
        export_validated_yaml(document)
    except Exception as exc:
        _raise_pipeline_failure(
            failed_stage="revalidation",
            error_type="schema_validation_failed",
            error_message=f"Exported YAML failed revalidation: {exc}",
            retryable=False,
            completed_artifacts=completed_artifacts,
            suggested_action="Inspect exporter and schema compatibility before retrying.",
        )
    completed_artifacts.append("screenplay_yaml")

    return document


def _scene_id(index: int) -> str:
    return f"sc-{index:03d}"


def _report_passed(report: ValidationReport) -> bool:
    return (
        report.yaml_parse_passed
        and report.schema_validation_passed
        and report.reference_validation_passed
        and report.coverage_validation_passed is True
        and not report.errors
    )


def _validation_error_type(report: ValidationReport) -> PipelineErrorType:
    if not report.schema_validation_passed:
        return "schema_validation_failed"
    if not report.reference_validation_passed:
        return "reference_validation_failed"
    if report.coverage_validation_passed is not True:
        return "coverage_validation_failed"
    return "schema_validation_failed"


def _validation_error_message(report: ValidationReport) -> str:
    if not report.errors:
        return "Validation failed without detailed issues."
    issue_summaries = [
        f"{issue.code}: {issue.message}"
        for issue in report.errors[:3]
    ]
    return "; ".join(issue_summaries)


def _raise_model_output_failure(
    exc: ModelOutputInvalid,
    completed_artifacts: list[str],
) -> NoReturn:
    _raise_pipeline_failure(
        failed_stage=exc.stage,
        error_type=exc.error_type,
        error_message=exc.error_message,
        retryable=True,
        completed_artifacts=completed_artifacts,
        suggested_action="Regenerate the failed stage output; automatic repair has already been tried once.",
    )


def _raise_unexpected_stage_failure(
    failed_stage: PipelineStage,
    exc: Exception,
    completed_artifacts: list[str],
) -> NoReturn:
    _raise_pipeline_failure(
        failed_stage=failed_stage,
        error_type="model_output_invalid",
        error_message=f"{failed_stage} failed: {exc}",
        retryable=True,
        completed_artifacts=completed_artifacts,
        suggested_action="Retry the failed generation stage with fresh model output.",
    )


def _raise_pipeline_failure(
    *,
    failed_stage: PipelineStage,
    error_type: PipelineErrorType,
    error_message: str,
    retryable: bool,
    completed_artifacts: list[str],
    suggested_action: str,
) -> NoReturn:
    raise PipelineFailure(
        PipelineError(
            failed_stage=failed_stage,
            error_type=error_type,
            error_message=error_message,
            retryable=retryable,
            completed_artifacts=list(completed_artifacts),
            suggested_action=suggested_action,
        )
    )


__all__ = [
    "ChapterInput",
    "PipelineFailure",
    "generate_screenplay",
]
