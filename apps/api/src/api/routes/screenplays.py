"""Screenplay generation and artifact endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from exporters import export_validated_yaml
from generation import ChapterInput, LLMClient, PipelineFailure, generate_screenplay

from ..deps import get_llm_client, get_store
from ..models import ArtifactsResponse, GenerateRequest, JobResponse
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

    job = store.create_job(project_id=project.project_id)
    chapters = [
        ChapterInput(chapter_id=chapter.chapter_id, title=chapter.title, text=chapter.text)
        for chapter in project.chapters
    ]
    try:
        document = generate_screenplay(
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
        failed_job = store.fail_job(job_id=job.job_id, error=exc.error)
        return JobResponse.model_validate(failed_job, from_attributes=True)

    screenplay = store.create_screenplay(
        project_id=project.project_id,
        yaml=yaml_text,
        document=document,
        validation_report=validation_report,
    )
    completed_job = store.complete_job(job_id=job.job_id, screenplay_id=screenplay.screenplay_id)
    return JobResponse.model_validate(completed_job, from_attributes=True)


@router.get("/screenplays/{screenplay_id}/artifacts", response_model=ArtifactsResponse)
def get_artifacts(
    screenplay_id: str,
    store: InMemoryStore = Depends(get_store),
) -> ArtifactsResponse:
    screenplay = store.get_screenplay(screenplay_id)
    if screenplay is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screenplay not found.")
    return ArtifactsResponse.model_validate(screenplay, from_attributes=True)
