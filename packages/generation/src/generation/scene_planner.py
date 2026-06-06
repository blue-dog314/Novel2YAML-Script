"""Scene-planning generation stage."""

from __future__ import annotations

from shared_types import ChapterSummaryOutput, ScenePlanOutput

from .llm import LLMClient
from .prompts import STAGE_SCENE_PLANNING, build_scene_plan_prompt
from .repair import complete_json_with_repair


def plan_scenes(
    chapter_summaries: list[ChapterSummaryOutput],
    llm: LLMClient,
) -> ScenePlanOutput:
    """Generate and validate a scene plan from chapter summaries."""
    system, user = build_scene_plan_prompt(chapter_summaries)
    return complete_json_with_repair(
        model_type=ScenePlanOutput,
        llm=llm,
        stage=STAGE_SCENE_PLANNING,
        system=system,
        user=user,
    )


__all__ = [
    "plan_scenes",
]
