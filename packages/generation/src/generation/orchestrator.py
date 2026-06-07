"""Staged generation orchestrator."""

from __future__ import annotations

import re
from typing import NoReturn

from exporters import export_validated_yaml
from shared_types import (
    AdaptationConfig,
    ChapterSummaryOutput,
    PipelineError,
    PipelineErrorType,
    PipelineStage,
    SceneContentOutput,
    ScenePlanOutput,
    ScreenplayDraftDocument,
    ValidationReport,
)
from validators import validate_document

from .artifacts import GenerationArtifacts
from .assembly import assemble_screenplay, build_scene_key_events
from .chapter_summary import summarize_chapters
from .inputs import ChapterInput
from .llm import LLMClient
from .repair import ModelOutputInvalid
from .scene_planner import plan_scenes
from .scene_writer import write_scene


class PipelineFailure(Exception):
    """Exception wrapper carrying the public PipelineError contract."""

    def __init__(
        self,
        error: PipelineError,
        artifacts: GenerationArtifacts | None = None,
    ) -> None:
        self.error = error
        self.artifacts = artifacts
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
    resume_from: GenerationArtifacts | None = None,
) -> ScreenplayDraftDocument:
    """Run staged generation and return the validated draft document."""
    document, _ = generate_screenplay_with_artifacts(
        chapters=chapters,
        project_id=project_id,
        title=title,
        original_author=original_author,
        language=language,
        model=model,
        llm=llm,
        adaptation_config=adaptation_config,
        resume_from=resume_from,
    )
    return document


def generate_screenplay_with_artifacts(
    *,
    chapters: list[ChapterInput],
    project_id: str,
    title: str,
    original_author: str,
    language: str,
    model: str,
    llm: LLMClient,
    adaptation_config: AdaptationConfig | None = None,
    resume_from: GenerationArtifacts | None = None,
) -> tuple[ScreenplayDraftDocument, GenerationArtifacts]:
    """Run staged generation, returning the document and completed artifacts.

    Stages whose output is already present in ``resume_from`` are skipped and
    do not call the LLM. Deterministic, cheap steps (assembly, validation, and
    export revalidation) always run.
    """
    if len(chapters) < 3:
        _raise_pipeline_failure(
            failed_stage="chapter_parsing",
            error_type="chapter_count_insufficient",
            error_message="At least three confirmed chapters are required.",
            retryable=False,
            artifacts=GenerationArtifacts(),
            suggested_action="Provide three or more confirmed chapters before generation.",
        )

    if resume_from is not None and resume_from.chapter_summaries is not None:
        chapter_summaries = resume_from.chapter_summaries
    else:
        try:
            chapter_summaries = summarize_chapters(chapters, llm)
        except ModelOutputInvalid as exc:
            _raise_model_output_failure(exc, GenerationArtifacts())
        except Exception as exc:
            _raise_unexpected_stage_failure("summarizing", exc, GenerationArtifacts())

    if resume_from is not None and resume_from.scene_plan is not None:
        scene_plan = resume_from.scene_plan
    else:
        try:
            scene_plan = plan_scenes(chapter_summaries, llm)
        except ModelOutputInvalid as exc:
            _raise_model_output_failure(
                exc,
                GenerationArtifacts(chapter_summaries=chapter_summaries),
            )
        except Exception as exc:
            _raise_unexpected_stage_failure(
                "scene_planning",
                exc,
                GenerationArtifacts(chapter_summaries=chapter_summaries),
            )

    if resume_from is not None and resume_from.scene_contents is not None:
        scene_contents = resume_from.scene_contents
    else:
        scene_contents = []
        for index, plan_item in enumerate(scene_plan.scenes, start=1):
            partial = GenerationArtifacts(
                chapter_summaries=chapter_summaries,
                scene_plan=scene_plan,
            )
            try:
                relevant_key_events = build_scene_key_events(
                    chapter_summaries, plan_item.source_chapters
                )
                scene_contents.append(
                    write_scene(_scene_id(index), plan_item, llm, relevant_key_events)
                )
            except ModelOutputInvalid as exc:
                _raise_model_output_failure(exc, partial)
            except Exception as exc:
                _raise_unexpected_stage_failure(
                    "scene_content_generation",
                    exc,
                    partial,
                )

    artifacts = GenerationArtifacts(
        chapter_summaries=chapter_summaries,
        scene_plan=scene_plan,
        scene_contents=scene_contents,
    )

    document = _assemble_validate_export(
        chapter_summaries=chapter_summaries,
        scene_plan=scene_plan,
        scene_contents=scene_contents,
        project_id=project_id,
        title=title,
        original_author=original_author,
        language=language,
        model=model,
        adaptation_config=adaptation_config,
        artifacts=artifacts,
    )

    return document, artifacts


def regenerate_scene(
    *,
    artifacts: GenerationArtifacts,
    scene_id: str,
    project_id: str,
    title: str,
    original_author: str,
    language: str,
    model: str,
    llm: LLMClient,
    adaptation_config: AdaptationConfig | None = None,
) -> tuple[ScreenplayDraftDocument, GenerationArtifacts]:
    """Regenerate one scene's content and deterministically reassemble the doc.

    Given completed artifacts from a prior successful generation and a target
    ``scene_id``, only that scene's content blocks are rewritten via the LLM.
    Every other stage output (chapter summaries, scene plan, and the remaining
    scene contents) is reused as-is, then the whole document is reassembled,
    validated, and revalidated through the shared deterministic path.
    """
    if artifacts.scene_plan is None or artifacts.scene_contents is None:
        _raise_pipeline_failure(
            failed_stage="scene_content_generation",
            error_type="model_output_invalid",
            error_message=(
                "Cannot regenerate a scene without a completed scene plan and "
                "scene contents."
            ),
            retryable=False,
            artifacts=artifacts,
            suggested_action="Run a full generation first to produce reusable artifacts.",
        )

    scene_plan = artifacts.scene_plan
    scene_contents = artifacts.scene_contents

    if re.fullmatch(r"sc-\d{3}", scene_id) is None:
        _raise_unknown_scene_id(scene_id, artifacts)
    pos = int(scene_id[3:]) - 1
    if pos < 0 or pos >= len(scene_plan.scenes):
        _raise_unknown_scene_id(scene_id, artifacts)

    try:
        plan_item = scene_plan.scenes[pos]
        relevant_key_events = build_scene_key_events(
            artifacts.chapter_summaries or [], plan_item.source_chapters
        )
        new_content = write_scene(scene_id, plan_item, llm, relevant_key_events)
    except ModelOutputInvalid as exc:
        _raise_model_output_failure(exc, artifacts)
    except Exception as exc:
        _raise_unexpected_stage_failure("scene_content_generation", exc, artifacts)

    new_scene_contents = list(scene_contents)
    new_scene_contents[pos] = new_content

    new_artifacts = GenerationArtifacts(
        chapter_summaries=artifacts.chapter_summaries,
        scene_plan=scene_plan,
        scene_contents=new_scene_contents,
    )

    document = _assemble_validate_export(
        chapter_summaries=artifacts.chapter_summaries or [],
        scene_plan=scene_plan,
        scene_contents=new_scene_contents,
        project_id=project_id,
        title=title,
        original_author=original_author,
        language=language,
        model=model,
        adaptation_config=adaptation_config,
        artifacts=new_artifacts,
    )

    return document, new_artifacts


def _assemble_validate_export(
    *,
    chapter_summaries: list[ChapterSummaryOutput],
    scene_plan: ScenePlanOutput,
    scene_contents: list[SceneContentOutput],
    project_id: str,
    title: str,
    original_author: str,
    language: str,
    model: str,
    adaptation_config: AdaptationConfig | None,
    artifacts: GenerationArtifacts,
) -> ScreenplayDraftDocument:
    """Deterministically assemble, validate, and revalidate a draft document.

    Shared by the full-generation and single-scene-regeneration paths so both
    emit identical ``failed_stage``/``error_type`` mappings on failure.
    """
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
            artifacts=artifacts,
            suggested_action="Regenerate the model outputs and try assembly again.",
        )

    report = validate_document(document)
    if not _report_passed(report):
        _raise_pipeline_failure(
            failed_stage="validation",
            error_type=_validation_error_type(report),
            error_message=_validation_error_message(report),
            retryable=True,
            artifacts=artifacts,
            extra_labels=["screenplay_draft"],
            suggested_action="Regenerate or repair the staged outputs before export.",
        )

    try:
        export_validated_yaml(document)
    except Exception as exc:
        _raise_pipeline_failure(
            failed_stage="revalidation",
            error_type="schema_validation_failed",
            error_message=f"Exported YAML failed revalidation: {exc}",
            retryable=False,
            artifacts=artifacts,
            extra_labels=["screenplay_draft", "validation_report"],
            suggested_action="Inspect exporter and schema compatibility before retrying.",
        )

    return document


def _raise_unknown_scene_id(
    scene_id: str,
    artifacts: GenerationArtifacts,
) -> NoReturn:
    _raise_pipeline_failure(
        failed_stage="scene_content_generation",
        error_type="model_output_invalid",
        error_message=f"Unknown scene_id {scene_id!r}.",
        retryable=False,
        artifacts=artifacts,
        suggested_action="Use a scene_id of the form 'sc-NNN' that exists in the scene plan.",
    )


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


def _labels(artifacts: GenerationArtifacts) -> list[str]:
    """Derive the public completed-artifact labels from the typed container.

    Mirrors the historical append order: a stage label is present only when
    that stage fully completed (its artifact field is non-``None``). The
    ``scene_contents`` label therefore appears only when every scene was
    written, matching the prior behaviour.
    """
    labels: list[str] = []
    if artifacts.chapter_summaries is not None:
        labels.append("chapter_summaries")
    if artifacts.scene_plan is not None:
        labels.append("scene_plan")
    if artifacts.scene_contents is not None:
        labels.append("scene_contents")
    return labels


def _raise_model_output_failure(
    exc: ModelOutputInvalid,
    artifacts: GenerationArtifacts,
) -> NoReturn:
    _raise_pipeline_failure(
        failed_stage=exc.stage,
        error_type=exc.error_type,
        error_message=exc.error_message,
        retryable=True,
        artifacts=artifacts,
        suggested_action="Regenerate the failed stage output; automatic repair has already been tried once.",
    )


def _raise_unexpected_stage_failure(
    failed_stage: PipelineStage,
    exc: Exception,
    artifacts: GenerationArtifacts,
) -> NoReturn:
    _raise_pipeline_failure(
        failed_stage=failed_stage,
        error_type="model_output_invalid",
        error_message=f"{failed_stage} failed: {exc}",
        retryable=True,
        artifacts=artifacts,
        suggested_action="Retry the failed generation stage with fresh model output.",
    )


def _raise_pipeline_failure(
    *,
    failed_stage: PipelineStage,
    error_type: PipelineErrorType,
    error_message: str,
    retryable: bool,
    artifacts: GenerationArtifacts,
    suggested_action: str,
    extra_labels: list[str] | None = None,
) -> NoReturn:
    completed_artifacts = _labels(artifacts)
    if extra_labels:
        completed_artifacts.extend(extra_labels)
    raise PipelineFailure(
        PipelineError(
            failed_stage=failed_stage,
            error_type=error_type,
            error_message=error_message,
            retryable=retryable,
            completed_artifacts=completed_artifacts,
            suggested_action=suggested_action,
        ),
        artifacts,
    )


__all__ = [
    "ChapterInput",
    "GenerationArtifacts",
    "PipelineFailure",
    "generate_screenplay",
    "generate_screenplay_with_artifacts",
    "regenerate_scene",
]
