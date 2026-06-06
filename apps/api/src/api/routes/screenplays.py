"""Screenplay generation and artifact endpoints."""

from __future__ import annotations

from importlib.resources import files

import screenplay_schema
from fastapi import APIRouter, Depends, HTTPException, status
from exporters import export_validated_yaml
from generation import (
    ChapterInput,
    LLMClient,
    PipelineFailure,
    generate_screenplay_with_artifacts,
    regenerate_scene,
)
from shared_types import ValidationReport
from validators import validate_yaml_text

from ..deps import get_llm_client, get_store
from ..models import (
    ArtifactsResponse,
    GenerateRequest,
    JobResponse,
    SceneRegenerateRequest,
    SchemaDocResponse,
    ValidateYamlRequest,
)
from ..store import InMemoryStore

router = APIRouter(tags=["screenplays"])


@router.post("/screenplays/generate", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def generate(
    request: GenerateRequest,
    store: InMemoryStore = Depends(get_store),
    llm: LLMClient = Depends(get_llm_client),
) -> JobResponse:
    project = store.get_project(request.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    if not project.chapters_confirmed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Project chapters are not confirmed.")

    job = store.create_job(
        project_id=project.project_id,
        model=request.model,
        adaptation_config=request.adaptation_config,
    )
    chapters = [
        ChapterInput(chapter_id=chapter.chapter_id, title=chapter.title, text=chapter.text)
        for chapter in project.chapters
    ]
    try:
        document, artifacts = generate_screenplay_with_artifacts(
            chapters=chapters,
            project_id=project.project_id,
            title=project.title,
            original_author=project.original_author,
            language=project.language,
            model=request.model,
            llm=llm,
            adaptation_config=request.adaptation_config,
        )
        yaml_text, validation_report = export_validated_yaml(document)
    except PipelineFailure as exc:
        failed_job = store.fail_job(job_id=job.job_id, error=exc.error, artifacts=exc.artifacts)
        return JobResponse.model_validate(failed_job, from_attributes=True)

    screenplay = store.create_screenplay(
        project_id=project.project_id,
        yaml=yaml_text,
        document=document,
        validation_report=validation_report,
        artifacts=artifacts,
    )
    completed_job = store.complete_job(job_id=job.job_id, screenplay_id=screenplay.screenplay_id)
    return JobResponse.model_validate(completed_job, from_attributes=True)


@router.post("/screenplays/validate-yaml", response_model=ValidationReport)
def validate_yaml(request: ValidateYamlRequest) -> ValidationReport:
    """Validate author-edited screenplay YAML without storing it."""
    _, report = validate_yaml_text(request.yaml)
    return report


@router.post(
    "/screenplays/{screenplay_id}/scenes/regenerate",
    response_model=ArtifactsResponse,
    status_code=status.HTTP_201_CREATED,
)
def regenerate_scene_endpoint(
    screenplay_id: str,
    request: SceneRegenerateRequest,
    store: InMemoryStore = Depends(get_store),
    llm: LLMClient = Depends(get_llm_client),
) -> ArtifactsResponse:
    """Regenerate a single scene, producing a new screenplay that keeps the old one.

    ``StoredScreenplay`` is frozen and the product keeps iteration history, so a
    successful regeneration is stored under a fresh ``screenplay_id`` rather than
    mutating the source screenplay in place.
    """
    screenplay = store.get_screenplay(screenplay_id)
    if screenplay is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screenplay not found.")

    project = store.get_project(screenplay.project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project for this screenplay not found.",
        )

    try:
        new_document, new_artifacts = regenerate_scene(
            artifacts=screenplay.artifacts,
            scene_id=request.scene_id,
            project_id=project.project_id,
            title=project.title,
            original_author=project.original_author,
            language=project.language,
            model=screenplay.document.metadata.model,
            llm=llm,
            adaptation_config=screenplay.document.adaptation_config,
        )
    except PipelineFailure as exc:
        if (
            exc.error.failed_stage == "scene_content_generation"
            and exc.error.retryable is False
            and "Unknown scene_id" in exc.error.error_message
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=exc.error.error_message,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.error.error_message,
        ) from exc

    yaml_text, validation_report = export_validated_yaml(new_document)
    new_screenplay = store.create_screenplay(
        project_id=project.project_id,
        yaml=yaml_text,
        document=new_document,
        validation_report=validation_report,
        artifacts=new_artifacts,
    )
    return ArtifactsResponse.model_validate(new_screenplay, from_attributes=True)


@router.get("/screenplays/{screenplay_id}/artifacts", response_model=ArtifactsResponse)
def get_artifacts(
    screenplay_id: str,
    store: InMemoryStore = Depends(get_store),
) -> ArtifactsResponse:
    screenplay = store.get_screenplay(screenplay_id)
    if screenplay is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screenplay not found.")
    return ArtifactsResponse.model_validate(screenplay, from_attributes=True)


@router.get("/screenplays/{screenplay_id}/validation-report", response_model=ValidationReport)
def get_validation_report(
    screenplay_id: str,
    store: InMemoryStore = Depends(get_store),
) -> ValidationReport:
    screenplay = store.get_screenplay(screenplay_id)
    if screenplay is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screenplay not found.")
    return screenplay.validation_report


@router.get("/screenplays/{screenplay_id}/schema-doc", response_model=SchemaDocResponse)
def get_schema_doc(
    screenplay_id: str,
    store: InMemoryStore = Depends(get_store),
) -> SchemaDocResponse:
    screenplay = store.get_screenplay(screenplay_id)
    if screenplay is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screenplay not found.")
    schema_doc = files(screenplay_schema).joinpath(screenplay_schema.SCHEMA_DOC_FILENAME).read_text(encoding="utf-8")
    return SchemaDocResponse(
        schema_filename=screenplay_schema.SCHEMA_DOC_FILENAME,
        schema_doc=schema_doc,
    )
