"""Tests for scene-level partial regeneration."""

from __future__ import annotations

import json
from typing import Any

import pytest

from generation import (
    ChapterInput,
    FakeLLMClient,
    GenerationArtifacts,
    PipelineFailure,
    generate_screenplay_with_artifacts,
    regenerate_scene,
)

FIXED_NOW = "2026-06-06T00:00:00+00:00"


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("generation.assembly._now_iso", lambda: FIXED_NOW)


def _chapters() -> list[ChapterInput]:
    return [
        ChapterInput(
            chapter_id=f"ch-{index}",
            title=f"Chapter {index}",
            text=f"Source text for chapter {index}.",
        )
        for index in range(1, 4)
    ]


def _two_scene_plan() -> str:
    chapter_ids = ["ch-1", "ch-2", "ch-3"]
    return json.dumps(
        {
            "scenes": [
                {
                    "title": f"Scene {n}",
                    "source_chapters": chapter_ids,
                    "location_name": "Main location",
                    "time": "Day",
                    "characters": ["Alice"],
                    "dramatic_goal": "Advance the drama.",
                    "conflict": "Rising pressure.",
                    "summary": f"Scene {n} summary.",
                }
                for n in (1, 2)
            ]
        },
        sort_keys=True,
    )


def _scene_content(scene_id: str, text: str) -> str:
    return json.dumps(
        {
            "scene_id": scene_id,
            "content_blocks": [{"type": "action", "text": text}],
            "adaptation_notes": [],
            "quality_flags": [],
        },
        sort_keys=True,
    )


def _seed() -> tuple[Any, GenerationArtifacts]:
    llm = FakeLLMClient(responses={"scene_planning": [_two_scene_plan()]})
    return generate_screenplay_with_artifacts(
        chapters=_chapters(),
        project_id="proj-1",
        title="Test Novel",
        original_author="Author Name",
        language="en",
        model="fake-model",
        llm=llm,
    )


def _regenerate(
    artifacts: GenerationArtifacts,
    scene_id: str,
    llm: FakeLLMClient,
) -> tuple[Any, GenerationArtifacts]:
    return regenerate_scene(
        artifacts=artifacts,
        scene_id=scene_id,
        project_id="proj-1",
        title="Test Novel",
        original_author="Author Name",
        language="en",
        model="fake-model",
        llm=llm,
    )


def _action_texts(scene: Any) -> list[str]:
    return [block.text for block in scene.content_blocks if block.type == "action"]


def test_regenerate_rewrites_only_target_scene() -> None:
    document, artifacts = _seed()
    original_scene_two = document.screenplay.scenes[1]

    llm = FakeLLMClient(
        responses={"scene_content_generation": [_scene_content("sc-001", "Rewritten opening.")]}
    )
    new_document, new_artifacts = _regenerate(artifacts, "sc-001", llm)

    # Only the scene-content stage is touched; no re-summarizing/replanning.
    assert [call.stage for call in llm.calls] == ["scene_content_generation"]

    scenes = new_document.screenplay.scenes
    assert len(scenes) == len(document.screenplay.scenes) == 2

    # Target scene rewritten with the new content.
    assert scenes[0].scene_id == "sc-001"
    assert scenes[0].order == 1
    assert "Rewritten opening." in _action_texts(scenes[0])

    # Non-target scene unchanged (scene_id, order, and content).
    assert scenes[1].scene_id == original_scene_two.scene_id
    assert scenes[1].order == original_scene_two.order
    assert _action_texts(scenes[1]) == _action_texts(original_scene_two)

    # Returned artifacts: same length, only the target slot replaced.
    assert artifacts.scene_contents is not None
    assert new_artifacts.scene_contents is not None
    assert len(new_artifacts.scene_contents) == 2
    rewritten_block = new_artifacts.scene_contents[0].content_blocks[0]
    assert rewritten_block.type == "action"
    assert rewritten_block.text == "Rewritten opening."
    assert new_artifacts.scene_contents[1] is artifacts.scene_contents[1]
    assert new_artifacts.scene_plan is artifacts.scene_plan
    assert new_artifacts.chapter_summaries is artifacts.chapter_summaries


def test_regenerate_out_of_range_scene_id_fails() -> None:
    _, artifacts = _seed()

    with pytest.raises(PipelineFailure) as exc_info:
        _regenerate(artifacts, "sc-999", FakeLLMClient())

    error = exc_info.value.error
    assert error.retryable is False
    assert error.error_type == "model_output_invalid"
    assert error.failed_stage == "scene_content_generation"
    assert "sc-999" in error.error_message


def test_regenerate_malformed_scene_id_fails() -> None:
    _, artifacts = _seed()

    with pytest.raises(PipelineFailure) as exc_info:
        _regenerate(artifacts, "bad", FakeLLMClient())

    error = exc_info.value.error
    assert error.retryable is False
    assert error.error_type == "model_output_invalid"
    assert "bad" in error.error_message


def test_regenerate_requires_completed_artifacts() -> None:
    _, artifacts = _seed()
    incomplete = GenerationArtifacts(
        chapter_summaries=artifacts.chapter_summaries,
        scene_plan=artifacts.scene_plan,
        scene_contents=None,
    )

    with pytest.raises(PipelineFailure) as exc_info:
        _regenerate(incomplete, "sc-001", FakeLLMClient())

    error = exc_info.value.error
    assert error.retryable is False
    assert error.failed_stage == "scene_content_generation"
