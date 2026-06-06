"""Typed container for completed staged-generation intermediate outputs."""

from __future__ import annotations

from dataclasses import dataclass

from shared_types import ChapterSummaryOutput, SceneContentOutput, ScenePlanOutput


@dataclass(frozen=True)
class GenerationArtifacts:
    """Completed intermediate outputs from the staged generation pipeline.

    Each field represents a stage that has fully completed. A non-``None``
    value means that whole stage finished and its output is reusable for a
    resume. ``scene_contents`` is only populated once every planned scene has
    been written; a partially written scene set is not cached (stays ``None``).
    """

    chapter_summaries: list[ChapterSummaryOutput] | None = None
    scene_plan: ScenePlanOutput | None = None
    scene_contents: list[SceneContentOutput] | None = None


__all__ = [
    "GenerationArtifacts",
]
