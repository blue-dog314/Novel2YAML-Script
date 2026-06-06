"""Job endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from exporters import export_validated_yaml
from generation import ChapterInput, LLMClient, PipelineFailure, generate_screenplay_with_artifacts

from ..deps import get_llm_client, get_store
from ..models import JobResponse
from ..store import InMemoryStore

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str, store: InMemoryStore = Depends(get_store)) -> JobResponse:
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return JobResponse.model_validate(job, from_attributes=True)


@router.post("/{job_id}/retry", response_model=JobResponse)
def retry_job(
    job_id: str,
    store: InMemoryStore = Depends(get_store),
    llm: LLMClient = Depends(get_llm_client),
) -> JobResponse:
    """Resume a failed job from its last completed stage.

    Reuses the cached intermediate artifacts so stages that already succeeded
    are not re-run. Only failed, retryable jobs are eligible.
    """
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    if job.status != "failed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only failed jobs can be retried.",
        )
    if job.error is not None and job.error.retryable is False:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=job.error.suggested_action)

    project = store.get_project(job.project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project no longer exists; cannot retry job.",
        )

    resume_from = job.artifacts
    store.start_retry(job_id)
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
            model=job.model,
            llm=llm,
            adaptation_config=job.adaptation_config,
            resume_from=resume_from,
        )
        yaml_text, validation_report = export_validated_yaml(document)
    except PipelineFailure as exc:
        failed_job = store.fail_job(job_id=job_id, error=exc.error, artifacts=exc.artifacts)
        return JobResponse.model_validate(failed_job, from_attributes=True)

    screenplay = store.create_screenplay(
        project_id=project.project_id,
        yaml=yaml_text,
        document=document,
        validation_report=validation_report,
        artifacts=artifacts,
    )
    completed_job = store.complete_job(job_id=job_id, screenplay_id=screenplay.screenplay_id)
    return JobResponse.model_validate(completed_job, from_attributes=True)
