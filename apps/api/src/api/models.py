"""Request and response models for the local MVP API."""

from __future__ import annotations

from pydantic import BaseModel, Field
from shared_types import AdaptationConfig, PipelineError, ScreenplayDraftDocument, ValidationReport

from .store import JobStatus


class ChapterUpload(BaseModel):
    title: str
    text: str


class ProjectCreateRequest(BaseModel):
    title: str
    original_author: str
    language: str = "zh"
    rights_confirmed: bool = False
    chapters: list[ChapterUpload] = Field(default_factory=list)


class ProjectResponse(BaseModel):
    project_id: str
    title: str
    original_author: str
    language: str
    chapter_count: int
    chapters_confirmed: bool


class ChapterSummaryResponse(BaseModel):
    chapter_id: str
    order: int
    title: str
    char_count: int
    confirmed: bool


class ChaptersResponse(BaseModel):
    project_id: str
    chapters: list[ChapterSummaryResponse]


class ConfirmChaptersResponse(BaseModel):
    project_id: str
    chapters_confirmed: bool
    chapter_count: int


class GenerateRequest(BaseModel):
    project_id: str
    model: str = "fake-model"
    adaptation_config: AdaptationConfig | None = None


class ValidateYamlRequest(BaseModel):
    yaml: str


class SchemaDocResponse(BaseModel):
    schema_filename: str
    schema_doc: str


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    project_id: str
    screenplay_id: str | None = None
    error: PipelineError | None = None


class ArtifactsResponse(BaseModel):
    screenplay_id: str
    yaml: str
    document: ScreenplayDraftDocument
    validation_report: ValidationReport
