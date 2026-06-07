"""Behavior tests for screenplay YAML exporters."""

from __future__ import annotations

from io import StringIO
from typing import Any

import pytest
from ruamel.yaml import YAML
from shared_types import (
    AdaptationConfig,
    Chapter,
    DialogueBlock,
    EmbeddedValidation,
    KeyEvent,
    Metadata,
    Scene,
    SceneKeyEventCoverage,
    Screenplay,
    ScreenplayDraftDocument,
)
from validators import validate_yaml_text

from exporters import MODULE_NAME, export_validated_yaml, export_yaml


EXPECTED_TOP_LEVEL_ORDER = [
    "metadata",
    "adaptation_config",
    "chapters",
    "characters",
    "locations",
    "screenplay",
    "timeline",
    "story_bible",
    "adaptation_changes",
    "validation",
    "revision_notes",
]


def _metadata(**overrides: Any) -> Metadata:
    data: dict[str, Any] = {
        "project_id": "proj-1",
        "title": "测试小说",
        "original_author": "作者",
        "schema_version": "0.1.0",
        "schema_doc_version": "0.1.0",
        "generator_version": "0.1.0",
        "prompt_version": "0.1.0",
        "generated_at": "2026-06-06T00:00:00+00:00",
        "language": "zh-CN",
        "source_chapter_count": 3,
        "model": "test-model",
    }
    data.update(overrides)
    return Metadata(**data)


def _chapter(order: int) -> Chapter:
    return Chapter(
        chapter_id=f"ch-{order}",
        order=order,
        title=f"第 {order} 章",
        summary="故事继续推进。",
        key_events=[KeyEvent(event_id=f"ev-{order}", text="关键事件。", status="adapted")],
    )


def _draft(*, screenplay: Screenplay | None = None) -> ScreenplayDraftDocument:
    scene = Scene(
        scene_id="sc-1",
        order=1,
        title="开场",
        source_chapters=["ch-1", "ch-2", "ch-3"],
        summary="Alice 问候。",
        content_blocks=[
            DialogueBlock(
                block_id="b-1",
                order=1,
                speaker="char-1",
                speaker_name="Alice",
                line="你好。",
            )
        ],
        key_event_coverage=[
            SceneKeyEventCoverage(key_event_id=f"ev-{order}", fidelity_status="faithful")
            for order in (1, 2, 3)
        ],
    )
    return ScreenplayDraftDocument(
        metadata=_metadata(),
        adaptation_config=AdaptationConfig(),
        chapters=[_chapter(1), _chapter(2), _chapter(3)],
        characters=[],
        locations=[],
        screenplay=screenplay or Screenplay(scenes=[scene]),
        adaptation_changes=[],
        validation=EmbeddedValidation(schema_version="0.1.0"),
        revision_notes=[],
    )


def _load_yaml(yaml_text: str) -> Any:
    return YAML(typ="safe").load(StringIO(yaml_text))


def test_module_name() -> None:
    assert MODULE_NAME == "exporters"


def test_export_yaml_produces_parseable_yaml() -> None:
    yaml_text = export_yaml(_draft())
    data = _load_yaml(yaml_text)
    assert isinstance(data, dict)
    assert data["metadata"]["project_id"] == "proj-1"


def test_export_yaml_keeps_unicode() -> None:
    yaml_text = export_yaml(_draft())
    assert "测试小说" in yaml_text
    assert "你好。" in yaml_text


def test_export_yaml_preserves_none_as_null() -> None:
    yaml_text = export_yaml(_draft())
    data = _load_yaml(yaml_text)
    assert "output_language" in data["adaptation_config"]
    assert data["adaptation_config"]["output_language"] is None
    assert "output_language: null" in yaml_text


def test_roundtrip_object_equivalence() -> None:
    original = _draft()
    yaml_text = export_yaml(original)
    document, report = validate_yaml_text(yaml_text)
    assert report.errors == []
    assert document is not None
    assert document.model_dump(mode="json") == original.model_dump(mode="json")


def test_export_validated_yaml_succeeds_for_valid_document() -> None:
    yaml_text, report = export_validated_yaml(_draft())
    assert yaml_text
    assert report.yaml_parse_passed is True
    assert report.schema_validation_passed is True
    assert report.reference_validation_passed is True
    assert report.coverage_validation_passed is True
    assert report.errors == []


def test_export_validated_yaml_raises_for_invalid_document() -> None:
    with pytest.raises(ValueError):
        export_validated_yaml(_draft(screenplay=Screenplay(scenes=[])))


def _draft_with_multiline_text() -> ScreenplayDraftDocument:
    scene = Scene(
        scene_id="sc-1",
        order=1,
        title="开场",
        source_chapters=["ch-1", "ch-2", "ch-3"],
        summary="Alice 问候。",
        content_blocks=[
            DialogueBlock(
                block_id="b-1",
                order=1,
                speaker="char-1",
                speaker_name="Alice",
                line="第一句。\n第二句。",
            )
        ],
    )
    return _draft(screenplay=Screenplay(scenes=[scene]))


def test_export_yaml_uses_literal_block_for_multiline_text() -> None:
    yaml_text = export_yaml(_draft_with_multiline_text())
    # The multi-line field must be a literal block scalar, not an escaped
    # single-line double-quoted string.
    assert "line: |-" in yaml_text
    assert "\\n" not in yaml_text
    assert "    第一句。" in yaml_text
    assert "    第二句。" in yaml_text
    # Round-trip preserves the exact text content.
    data = _load_yaml(yaml_text)
    block = data["screenplay"]["scenes"][0]["content_blocks"][0]
    assert block["line"] == "第一句。\n第二句。"


def test_export_yaml_keeps_single_line_text_as_plain_scalar() -> None:
    yaml_text = export_yaml(_draft())
    # Short single-line fields stay as ordinary scalars, never forced to blocks.
    assert "summary: 故事继续推进。" in yaml_text
    assert "summary: |" not in yaml_text
    assert "line: 你好。" in yaml_text


def test_export_validated_yaml_succeeds_with_multiline_text() -> None:
    yaml_text, report = export_validated_yaml(_draft_with_multiline_text())
    assert "line: |-" in yaml_text
    assert report.errors == []


def test_field_order_follows_contract() -> None:
    yaml_text = export_yaml(_draft())
    top_level_fields = [
        line.split(":", 1)[0]
        for line in yaml_text.splitlines()
        if line and not line.startswith(" ")
    ]
    assert top_level_fields == EXPECTED_TOP_LEVEL_ORDER
