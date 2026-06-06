"""Project endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ..deps import get_store
from ..models import (
    ChapterSummaryResponse,
    ChaptersResponse,
    ConfirmChaptersResponse,
    GenerationNoticeResponse,
    ProjectCreateRequest,
    ProjectResponse,
)
from ..store import InMemoryStore, StoredProject

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    request: ProjectCreateRequest,
    store: InMemoryStore = Depends(get_store),
) -> ProjectResponse:
    if request.rights_confirmed is not True:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must confirm adaptation/use rights before uploading source text.",
        )
    project = store.create_project(
        title=request.title,
        original_author=request.original_author,
        language=request.language,
        chapters=[(chapter.title, chapter.text) for chapter in request.chapters],
    )
    return _project_response(project)


@router.get("/{project_id}/chapters", response_model=ChaptersResponse)
def get_chapters(
    project_id: str,
    store: InMemoryStore = Depends(get_store),
) -> ChaptersResponse:
    project = _get_project_or_404(store, project_id)
    return ChaptersResponse(
        project_id=project.project_id,
        chapters=[
            ChapterSummaryResponse(
                chapter_id=chapter.chapter_id,
                order=chapter.order,
                title=chapter.title,
                char_count=len(chapter.text),
                confirmed=project.chapters_confirmed,
            )
            for chapter in project.chapters
        ],
    )


@router.post("/{project_id}/chapters/confirm", response_model=ConfirmChaptersResponse)
def confirm_chapters(
    project_id: str,
    store: InMemoryStore = Depends(get_store),
) -> ConfirmChaptersResponse:
    project = store.confirm_chapters(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return ConfirmChaptersResponse(
        project_id=project.project_id,
        chapters_confirmed=project.chapters_confirmed,
        chapter_count=len(project.chapters),
    )


@router.get("/{project_id}/generation-notice", response_model=GenerationNoticeResponse)
def get_generation_notice(
    project_id: str,
    store: InMemoryStore = Depends(get_store),
) -> GenerationNoticeResponse:
    project = _get_project_or_404(store, project_id)
    total_char_count = sum(len(chapter.text) for chapter in project.chapters)
    estimated_scene_count = max(1, min(len(project.chapters) * 2, 24))
    risk_notice = [
        "Generation sends chapter text to the configured LLM provider.",
        "Source text is treated as untrusted data, but model output can still require author review.",
        "Large chapters can increase latency and provider cost.",
    ]
    if len(project.chapters) < 3:
        risk_notice.append("At least three confirmed chapters are required before generation can succeed.")
    if not project.chapters_confirmed:
        risk_notice.append("Confirm chapters before starting generation.")
    return GenerationNoticeResponse(
        project_id=project.project_id,
        chapter_count=len(project.chapters),
        total_char_count=total_char_count,
        estimated_scene_count=estimated_scene_count,
        cost_notice=(
            "Cost depends on provider pricing, chapter length, retry count, and the number "
            "of generated scenes; this local MVP does not estimate currency cost."
        ),
        risk_notice=risk_notice,
    )


def _get_project_or_404(store: InMemoryStore, project_id: str) -> StoredProject:
    project = store.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return project


def _project_response(project: StoredProject) -> ProjectResponse:
    return ProjectResponse(
        project_id=project.project_id,
        title=project.title,
        original_author=project.original_author,
        language=project.language,
        chapter_count=len(project.chapters),
        chapters_confirmed=project.chapters_confirmed,
    )
