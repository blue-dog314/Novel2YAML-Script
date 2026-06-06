"""In-memory storage for the local MVP API."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from generation import GenerationArtifacts
from shared_types import AdaptationConfig, PipelineError, ScreenplayDraftDocument, ValidationReport

JobStatus = Literal["running", "succeeded", "failed"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class StoredChapter:
    chapter_id: str
    order: int
    title: str
    text: str


@dataclass
class StoredProject:
    project_id: str
    title: str
    original_author: str
    language: str
    chapters: list[StoredChapter]
    chapters_confirmed: bool = False


@dataclass
class StoredJob:
    job_id: str
    project_id: str
    status: JobStatus
    screenplay_id: str | None = None
    error: PipelineError | None = None
    artifacts: GenerationArtifacts | None = None
    model: str = "fake-model"
    adaptation_config: AdaptationConfig | None = None
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)


@dataclass(frozen=True)
class StoredScreenplay:
    screenplay_id: str
    project_id: str
    yaml: str
    document: ScreenplayDraftDocument
    validation_report: ValidationReport
    artifacts: GenerationArtifacts


class InMemoryStore:
    def __init__(self) -> None:
        self._projects: dict[str, StoredProject] = {}
        self._jobs: dict[str, StoredJob] = {}
        self._screenplays: dict[str, StoredScreenplay] = {}

    def create_project(self, *, title: str, original_author: str, language: str, chapters: list[tuple[str, str]]) -> StoredProject:
        project_id = _new_id("proj")
        stored_chapters = [
            StoredChapter(chapter_id=f"ch-{index}", order=index, title=chapter_title, text=text)
            for index, (chapter_title, text) in enumerate(chapters, start=1)
        ]
        project = StoredProject(
            project_id=project_id,
            title=title,
            original_author=original_author,
            language=language,
            chapters=stored_chapters,
        )
        self._projects[project_id] = project
        return project

    def get_project(self, project_id: str) -> StoredProject | None:
        return self._projects.get(project_id)

    def confirm_chapters(self, project_id: str) -> StoredProject | None:
        project = self.get_project(project_id)
        if project is None:
            return None
        project.chapters_confirmed = True
        return project

    def create_job(
        self,
        *,
        project_id: str,
        model: str = "fake-model",
        adaptation_config: AdaptationConfig | None = None,
    ) -> StoredJob:
        job = StoredJob(
            job_id=_new_id("job"),
            project_id=project_id,
            status="running",
            model=model,
            adaptation_config=adaptation_config,
        )
        self._jobs[job.job_id] = job
        return job

    def complete_job(self, *, job_id: str, screenplay_id: str) -> StoredJob:
        job = self._jobs[job_id]
        job.status = "succeeded"
        job.screenplay_id = screenplay_id
        job.error = None
        job.updated_at = _now_iso()
        return job

    def fail_job(
        self,
        *,
        job_id: str,
        error: PipelineError,
        artifacts: GenerationArtifacts | None = None,
    ) -> StoredJob:
        job = self._jobs[job_id]
        job.status = "failed"
        job.error = error
        job.screenplay_id = None
        job.artifacts = artifacts
        job.updated_at = _now_iso()
        return job

    def start_retry(self, job_id: str) -> StoredJob | None:
        """Move a failed job back to ``running`` for a retry attempt.

        Keeps ``artifacts`` so the retry can resume from completed stages.
        Returns ``None`` when the job does not exist so the route can 404.
        """
        job = self._jobs.get(job_id)
        if job is None:
            return None
        job.status = "running"
        job.error = None
        job.screenplay_id = None
        job.updated_at = _now_iso()
        return job

    def get_job(self, job_id: str) -> StoredJob | None:
        return self._jobs.get(job_id)

    def create_screenplay(
        self,
        *,
        project_id: str,
        yaml: str,
        document: ScreenplayDraftDocument,
        validation_report: ValidationReport,
        artifacts: GenerationArtifacts,
    ) -> StoredScreenplay:
        screenplay = StoredScreenplay(
            screenplay_id=_new_id("sp"),
            project_id=project_id,
            yaml=yaml,
            document=document,
            validation_report=validation_report,
            artifacts=artifacts,
        )
        self._screenplays[screenplay.screenplay_id] = screenplay
        return screenplay

    def get_screenplay(self, screenplay_id: str) -> StoredScreenplay | None:
        return self._screenplays.get(screenplay_id)

    def delete_project(self, project_id: str) -> bool:
        """Delete a project together with its source text and derived artifacts.

        Removes the project (including its stored chapter text), every job spawned
        for it, and every generated screenplay. Returns ``False`` when the project
        does not exist so the route can return 404.
        """
        if project_id not in self._projects:
            return False
        del self._projects[project_id]
        self._jobs = {job_id: job for job_id, job in self._jobs.items() if job.project_id != project_id}
        self._screenplays = {
            screenplay_id: screenplay
            for screenplay_id, screenplay in self._screenplays.items()
            if screenplay.project_id != project_id
        }
        return True


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"
