"""Chapter-summary generation stage."""

from __future__ import annotations

from shared_types import ChapterSummaryOutput, KeyEventOutput

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
    summary = complete_json_with_repair(
        model_type=ChapterSummaryOutput,
        llm=llm,
        stage=STAGE_SUMMARIZING,
        system=system,
        user=user,
    )
    return _ensure_key_events(summary)


def _ensure_key_events(summary: ChapterSummaryOutput) -> ChapterSummaryOutput:
    if summary.key_events:
        return summary
    fallback_text = summary.summary.strip() or f"{summary.title} 的核心事件需要作者复核。"
    return summary.model_copy(
        update={
            "key_events": [
                KeyEventOutput(text=fallback_text, importance="medium"),
            ],
        },
    )


__all__ = [
    "summarize_chapters",
]
