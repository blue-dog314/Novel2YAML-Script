"""Behavior tests for deterministic screenplay assembly."""

from __future__ import annotations

from typing import Any

import pytest
from exporters import export_validated_yaml
from shared_types import (
    Character,
    ChapterSummaryOutput,
    DialogueBlock,
    KeyEventOutput,
    ModelActionBlock,
    ModelDialogueBlock,
    ModelNoteBlock,
    SceneContentOutput,
    ScenePlanItem,
    ScenePlanOutput,
)
from validators import validate_document

from generation import MODULE_NAME, assemble_screenplay


FIXED_NOW = "2026-06-06T00:00:00+00:00"


def _chapter_summary(order: int) -> ChapterSummaryOutput:
    return ChapterSummaryOutput(
        chapter_id=f"ch-{order}",
        title=f"第 {order} 章",
        summary="章节摘要。",
        key_events=[KeyEventOutput(text=f"事件 {order}", importance="high")],
    )


def _scene_plan_item(*source_chapters: str, title: str = "开场") -> ScenePlanItem:
    return ScenePlanItem(
        title=title,
        source_chapters=list(source_chapters),
        location_name="庭院",
        time="夜晚",
        characters=["Alice"],
        dramatic_goal="建立冲突",
        conflict="秘密被发现",
        summary="Alice 遇到阻碍。",
    )


def _scene_plan() -> ScenePlanOutput:
    return ScenePlanOutput(
        scenes=[
            _scene_plan_item("ch-1", "ch-2", title="第一场"),
            _scene_plan_item("ch-3", title="第二场"),
        ]
    )


def _scene_content(scene_id: str, speaker_name: str = "Alice") -> SceneContentOutput:
    return SceneContentOutput(
        scene_id=scene_id,
        content_blocks=[
            ModelActionBlock(text="Alice 推门而入。"),
            ModelDialogueBlock(
                speaker_name=speaker_name,
                line="你好。",
                emotion="平静",
                action_hint="点头",
            ),
        ],
        adaptation_notes=["保留关键冲突。"],
        quality_flags=["needs_review"],
    )


def _kwargs(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "chapter_summaries": [_chapter_summary(1), _chapter_summary(2), _chapter_summary(3)],
        "scene_plan": _scene_plan(),
        "scene_contents": [_scene_content("sc-001"), _scene_content("sc-002")],
        "project_id": "proj-1",
        "title": "测试小说",
        "original_author": "作者",
        "language": "zh-CN",
        "model": "test-model",
    }
    data.update(overrides)
    return data


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("generation.assembly._now_iso", lambda: FIXED_NOW)


def test_module_name() -> None:
    assert MODULE_NAME == "generation"


def test_deterministic_output() -> None:
    first = assemble_screenplay(**_kwargs())
    second = assemble_screenplay(**_kwargs())
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_sequential_ids_zero_padded() -> None:
    document = assemble_screenplay(**_kwargs())
    assert [scene.scene_id for scene in document.screenplay.scenes] == ["sc-001", "sc-002"]
    assert [block.block_id for block in document.screenplay.scenes[0].content_blocks] == [
        "sc-001-blk-001",
        "sc-001-blk-002",
    ]


def test_orders_monotonic_from_one() -> None:
    document = assemble_screenplay(**_kwargs())
    assert [chapter.order for chapter in document.chapters] == [1, 2, 3]
    assert [scene.order for scene in document.screenplay.scenes] == [1, 2]
    assert [block.order for block in document.screenplay.scenes[0].content_blocks] == [1, 2]


def test_importance_dropped_status_pending_review() -> None:
    document = assemble_screenplay(**_kwargs())
    assert document.chapters[0].key_events[0].status == "pending_review"
    assert "importance" not in document.chapters[0].key_events[0].model_dump(mode="json")


def test_chapter_id_preserved() -> None:
    document = assemble_screenplay(**_kwargs())
    assert [chapter.chapter_id for chapter in document.chapters] == ["ch-1", "ch-2", "ch-3"]


def test_speaker_slug_english() -> None:
    document = assemble_screenplay(**_kwargs(scene_contents=[_scene_content("sc-001", "Alice Smith"), _scene_content("sc-002")]))
    dialogue = document.screenplay.scenes[0].content_blocks[1]
    assert getattr(dialogue, "speaker") == "char-alice-smith"


def test_speaker_slug_chinese() -> None:
    document = assemble_screenplay(**_kwargs(scene_contents=[_scene_content("sc-001", "林黛玉"), _scene_content("sc-002")]))
    dialogue = document.screenplay.scenes[0].content_blocks[1]
    assert getattr(dialogue, "speaker") == "char-林黛玉"


def test_speaker_slug_empty_fallback() -> None:
    document = assemble_screenplay(**_kwargs(scene_contents=[_scene_content("sc-001", "!!!"), _scene_content("sc-002")]))
    dialogue = document.screenplay.scenes[0].content_blocks[1]
    assert getattr(dialogue, "speaker") == "char-unnamed-1"


def test_same_speaker_reuses_id() -> None:
    document = assemble_screenplay(**_kwargs(scene_contents=[_scene_content("sc-001", "Alice"), _scene_content("sc-002", " alice ")]))
    first = document.screenplay.scenes[0].content_blocks[1]
    second = document.screenplay.scenes[1].content_blocks[1]
    assert getattr(first, "speaker") == getattr(second, "speaker") == "char-alice"


def test_assembled_document_passes_validators() -> None:
    report = validate_document(assemble_screenplay(**_kwargs()))
    assert report.yaml_parse_passed is True
    assert report.schema_validation_passed is True
    assert report.reference_validation_passed is True
    assert report.coverage_validation_passed is True
    assert report.errors == []


def test_assembled_document_export_roundtrip() -> None:
    yaml_text, report = export_validated_yaml(assemble_screenplay(**_kwargs()))
    assert yaml_text
    assert report.errors == []


def test_unknown_scene_content_id_raises() -> None:
    with pytest.raises(ValueError, match="unknown scene_id"):
        assemble_screenplay(**_kwargs(scene_contents=[_scene_content("sc-001"), _scene_content("sc-999")]))


def test_missing_scene_content_raises() -> None:
    with pytest.raises(ValueError, match="missing scene content"):
        assemble_screenplay(**_kwargs(scene_contents=[_scene_content("sc-001")]))


def test_duplicate_scene_content_raises() -> None:
    with pytest.raises(ValueError, match="duplicate scene content"):
        assemble_screenplay(**_kwargs(scene_contents=[_scene_content("sc-001"), _scene_content("sc-001")]))


def test_character_table_populated_with_backend_ids() -> None:
    document = assemble_screenplay(**_kwargs())
    assert document.characters == [Character(character_id="char-alice", name="Alice")]
    # Locations remain empty until G2b populates them.
    assert document.locations == []


def test_scene_and_dialogue_reference_character_ids() -> None:
    document = assemble_screenplay(**_kwargs())
    scene = document.screenplay.scenes[0]
    # scene.characters carries backend ids, not raw names.
    assert scene.characters == ["char-alice"]
    dialogue = scene.content_blocks[1]
    assert isinstance(dialogue, DialogueBlock)
    assert dialogue.speaker == "char-alice"
    assert dialogue.speaker_name == "Alice"


def test_character_ids_are_unique_and_deduplicated() -> None:
    # "Alice" appears in chapter mentions, scene characters, and dialogue;
    # it must collapse to a single character entry.
    document = assemble_screenplay(
        **_kwargs(
            chapter_summaries=[
                _chapter_summary(1),
                _chapter_summary(2),
                ChapterSummaryOutput(
                    chapter_id="ch-3",
                    title="第 3 章",
                    summary="章节摘要。",
                    key_events=[KeyEventOutput(text="事件 3", importance="high")],
                    characters_mentioned=["Alice", "Bob"],
                ),
            ]
        )
    )
    ids = [character.character_id for character in document.characters]
    assert ids == ["char-alice", "char-bob"]
    assert len(ids) == len(set(ids))


def test_validation_block_is_draft_state() -> None:
    document = assemble_screenplay(**_kwargs())
    assert document.validation.passed is False
    assert document.validation.validated_at is None


def test_note_block_assembles_as_note() -> None:
    content = SceneContentOutput(
        scene_id="sc-001",
        content_blocks=[ModelNoteBlock(text="制作提示。"), ModelActionBlock(text="Alice 停下。")],
    )
    document = assemble_screenplay(**_kwargs(scene_contents=[content, _scene_content("sc-002")]))
    assert document.screenplay.scenes[0].content_blocks[0].type == "note"
