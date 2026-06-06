"""Scene-content generation stage."""

from __future__ import annotations

from shared_types import SceneContentOutput, ScenePlanItem

from .llm import LLMClient
from .prompts import STAGE_SCENE_CONTENT, build_scene_content_prompt
from .repair import complete_json_with_repair


def write_scene(
    scene_id: str,
    plan_item: ScenePlanItem,
    llm: LLMClient,
) -> SceneContentOutput:
    """Generate and validate model-owned content blocks for one scene."""
    system, user = build_scene_content_prompt(scene_id=scene_id, plan_item=plan_item)
    return complete_json_with_repair(
        model_type=SceneContentOutput,
        llm=llm,
        stage=STAGE_SCENE_CONTENT,
        system=system,
        user=user,
    )


__all__ = [
    "write_scene",
]
