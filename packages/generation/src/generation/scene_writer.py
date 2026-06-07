"""Scene-content generation stage."""

from __future__ import annotations

from shared_types import ModelActionBlock, ModelDialogueBlock, SceneContentOutput, ScenePlanItem

from .llm import LLMClient
from .prompts import STAGE_SCENE_CONTENT, build_scene_content_prompt
from .repair import complete_json_with_repair


def write_scene(
    scene_id: str,
    plan_item: ScenePlanItem,
    llm: LLMClient,
    relevant_key_events: list[tuple[str, str]] | None = None,
) -> SceneContentOutput:
    """Generate and validate model-owned content blocks for one scene."""
    system, user = build_scene_content_prompt(
        scene_id=scene_id,
        plan_item=plan_item,
        relevant_key_events=relevant_key_events,
    )
    content = complete_json_with_repair(
        model_type=SceneContentOutput,
        llm=llm,
        stage=STAGE_SCENE_CONTENT,
        system=system,
        user=user,
    )
    return _ensure_playable_content(content, plan_item)


def _ensure_playable_content(
    content: SceneContentOutput,
    plan_item: ScenePlanItem,
) -> SceneContentOutput:
    if any(isinstance(block, (ModelActionBlock, ModelDialogueBlock)) for block in content.content_blocks):
        return content
    fallback_text = (
        plan_item.summary
        or plan_item.dramatic_goal
        or plan_item.conflict
        or "角色在这一场中推动情节进入下一个可表演的戏剧节点。"
    )
    return content.model_copy(
        update={
            "content_blocks": [
                ModelActionBlock(text=fallback_text),
                *content.content_blocks,
            ],
            "quality_flags": [
                *content.quality_flags,
                "added_fallback_action_for_validation",
            ],
        },
    )


__all__ = [
    "write_scene",
]
