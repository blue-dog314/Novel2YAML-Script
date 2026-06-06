"""Input contracts owned by the generation orchestration layer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChapterInput:
    """A confirmed chapter handed to staged generation.

    Chapter parsing and user confirmation are intentionally outside this
    package; callers pass already-confirmed chapter IDs, titles, and source text.
    """

    chapter_id: str
    title: str
    text: str


__all__ = [
    "ChapterInput",
]
