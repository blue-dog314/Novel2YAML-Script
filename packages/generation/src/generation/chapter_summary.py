"""Chapter-summary generation stage."""

from __future__ import annotations

from shared_types import ChapterSummaryOutput

from .inputs import ChapterInput
from .llm import LLMClient
from .prompts import STAGE_SUMMARIZING, build_chapter_summary_prompt
from .repair import complete_json_with_repair


def summarize_chapters(
    chapters: list[ChapterInput],
    llm: LLMClient,
) -> list[ChapterSummaryOutput]:
    """Generate one validated ChapterSummaryOutput for each chapter."""
    return [_summarize_chapter(chapter, llm) for chapter in chapters]


def _summarize_chapter(
    chapter: ChapterInput,
    llm: LLMClient,
) -> ChapterSummaryOutput:
    system, user = build_chapter_summary_prompt(chapter)
    return complete_json_with_repair(
        model_type=ChapterSummaryOutput,
        llm=llm,
        stage=STAGE_SUMMARIZING,
        system=system,
        user=user,
    )


__all__ = [
    "summarize_chapters",
]
