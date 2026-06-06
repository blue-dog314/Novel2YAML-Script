"""Behavior tests for deterministic screenplay validators."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError
from shared_types import (
    AdaptationChange,
    AdaptationConfig,
    Chapter,
    DialogueBlock,
    EmbeddedValidation,
    KeyEvent,
    Metadata,
    NoteBlock,
    Scene,
    Screenplay,
    ScreenplayDraftDocument,
    TimelineEntry,
    ValidatedScreenplay,
)

from validators import (
    MODULE_NAME,
    validate_and_mark,
    validate_document,
    validate_yaml_text,
)


def _metadata(**overrides: Any) -> Metadata:
    data: dict[str, Any] = {
        "project_id": "proj-1",
        "title": "A Test Novel",
        "original_author": "Author Name",
        "schema_version": "0.1.0",
        "schema_doc_version": "0.1.0",
        "generator_version": "0.1.0",
        "prompt_version": "0.1.0",
        "generated_at": "2026-06-06T00:00:00+00:00",
        "language": "en",
        "source_chapter_count": 3,
        "model": "test-model",
    }
    data.update(overrides)
    return Metadata(**data)


def _chapter(order: int) -> Chapter:
    return Chapter(
        chapter_id=f"ch-{order}",
        order=order,
        title=f"Chapter {order}",
        summary="The story unfolds.",
        key_events=[KeyEvent(event_id=f"ev-{order}", text="An event.", status="adapted")],
    )


def _block(order: int = 1, block_id: str = "b-1", speaker: str = "char-1") -> DialogueBlock:
    return DialogueBlock(
        block_id=block_id,
        order=order,
        speaker=speaker,
        speaker_name="Alice",
        line="Hello there.",
    )


def _draft(**overrides: Any) -> ScreenplayDraftDocument:
    scene = Scene(
        scene_id="sc-1",
        order=1,
        title="Opening Scene",
        source_chapters=["ch-1", "ch-2", "ch-3"],
        summary="Alice greets.",
        content_blocks=[_block()],
    )
    data: dict[str, Any] = {
        "metadata": _metadata(),
        "adaptation_config": AdaptationConfig(),
        "chapters": [_chapter(1), _chapter(2), _chapter(3)],
        "characters": [],
        "locations": [],
        "screenplay": Screenplay(scenes=[scene]),
        "adaptation_changes": [],
        "validation": EmbeddedValidation(schema_version="0.1.0"),
        "revision_notes": [],
    }
    data.update(overrides)
    return ScreenplayDraftDocument(**data)


def test_module_name() -> None:
    assert MODULE_NAME == "validators"


def test_valid_document_passes_all_layers() -> None:
    report = validate_document(_draft())
    assert report.yaml_parse_passed is True
    assert report.schema_validation_passed is True
    assert report.reference_validation_passed is True
    assert report.coverage_validation_passed is True
    assert report.errors == []


def test_validate_and_mark_returns_validated_screenplay() -> None:
    validated = validate_and_mark(_draft())
    assert isinstance(validated, ValidatedScreenplay)
    assert validated.document.validation.passed is True
    assert validated.report.coverage_validation_passed is True


def test_yaml_text_schema_error_reports_schema_failure() -> None:
    _, report = validate_yaml_text("metadata:\n  source_chapter_count: 2\n")
    assert report.yaml_parse_passed is True
    assert report.schema_validation_passed is False
    assert report.reference_validation_passed is False
    assert report.coverage_validation_passed is False
    assert any(error.code == "SCHEMA_VALIDATION_FAILED" for error in report.errors)


def test_yaml_text_illegal_control_character_reports_syntax_failure() -> None:
    _, report = validate_yaml_text("metadata: bad\x00text")
    assert report.yaml_parse_passed is False
    assert report.schema_validation_passed is False
    assert report.coverage_validation_passed is False
    assert report.errors[0].code == "ILLEGAL_CONTROL_CHARACTER"


def test_unknown_source_chapter_fails_reference_validation() -> None:
    scene = Scene(
        scene_id="sc-1",
        order=1,
        title="Opening Scene",
        source_chapters=["ch-1", "missing"],
        summary="Alice greets.",
        content_blocks=[_block()],
    )
    report = validate_document(_draft(screenplay=Screenplay(scenes=[scene])))
    assert report.reference_validation_passed is False
    assert any(error.code == "UNKNOWN_SOURCE_CHAPTER" for error in report.errors)


def test_duplicate_block_order_fails_reference_validation() -> None:
    scene = Scene(
        scene_id="sc-1",
        order=1,
        title="Opening Scene",
        source_chapters=["ch-1", "ch-2", "ch-3"],
        summary="Alice greets.",
        content_blocks=[_block(order=1, block_id="b-1"), _block(order=1, block_id="b-2")],
    )
    report = validate_document(_draft(screenplay=Screenplay(scenes=[scene])))
    assert report.reference_validation_passed is False
    assert any(error.code == "DUPLICATE_BLOCK_ORDER" for error in report.errors)


def test_duplicate_scene_order_fails_reference_validation() -> None:
    scenes = [
        Scene(
            scene_id="sc-1",
            order=1,
            title="Opening Scene",
            source_chapters=["ch-1", "ch-2"],
            summary="Alice greets.",
            content_blocks=[_block(block_id="b-1")],
        ),
        Scene(
            scene_id="sc-2",
            order=1,
            title="Second Scene",
            source_chapters=["ch-3"],
            summary="Alice leaves.",
            content_blocks=[_block(block_id="b-2")],
        ),
    ]
    report = validate_document(_draft(screenplay=Screenplay(scenes=scenes)))
    assert report.reference_validation_passed is False
    assert any(error.code == "DUPLICATE_SCENE_ORDER" for error in report.errors)


def test_duplicate_chapter_order_fails_reference_validation() -> None:
    chapters = [_chapter(1), _chapter(2), _chapter(3)]
    chapters[1] = Chapter(
        chapter_id="ch-2",
        order=1,
        title="Chapter 2",
        summary="The story continues.",
        key_events=[KeyEvent(event_id="ev-2", text="An event.", status="adapted")],
    )
    report = validate_document(_draft(chapters=chapters))
    assert report.reference_validation_passed is False
    assert any(error.code == "DUPLICATE_CHAPTER_ORDER" for error in report.errors)


def test_empty_screenplay_fails_coverage_validation() -> None:
    report = validate_document(_draft(screenplay=Screenplay(scenes=[])))
    assert report.reference_validation_passed is True
    assert report.coverage_validation_passed is False
    assert any(error.code == "SCREENPLAY_EMPTY" for error in report.errors)


def test_empty_scene_content_blocks_fails_coverage_validation() -> None:
    scene = Scene(
        scene_id="sc-1",
        order=1,
        title="Opening Scene",
        source_chapters=["ch-1", "ch-2", "ch-3"],
        summary="Alice greets.",
        content_blocks=[],
    )
    report = validate_document(_draft(screenplay=Screenplay(scenes=[scene])))
    assert report.coverage_validation_passed is False
    assert any(error.code == "SCENE_CONTENT_BLOCKS_EMPTY" for error in report.errors)


def test_scene_with_only_note_block_fails_coverage_validation() -> None:
    scene = Scene(
        scene_id="sc-1",
        order=1,
        title="Opening Scene",
        source_chapters=["ch-1", "ch-2", "ch-3"],
        summary="Alice greets.",
        content_blocks=[NoteBlock(block_id="b-1", order=1, text="A production note.")],
    )
    report = validate_document(_draft(screenplay=Screenplay(scenes=[scene])))
    assert report.coverage_validation_passed is False
    assert any(error.code == "SCENE_MISSING_ACTION_OR_DIALOGUE" for error in report.errors)


def test_uncovered_chapter_fails_coverage_validation() -> None:
    scene = Scene(
        scene_id="sc-1",
        order=1,
        title="Opening Scene",
        source_chapters=["ch-1", "ch-2"],
        summary="Alice greets.",
        content_blocks=[_block()],
    )
    report = validate_document(_draft(screenplay=Screenplay(scenes=[scene])))
    assert report.coverage_validation_passed is False
    assert any(error.code == "CHAPTER_NOT_COVERED" for error in report.errors)


def test_source_chapter_count_mismatch_fails_reference_validation() -> None:
    metadata = _metadata(source_chapter_count=4)
    report = validate_document(_draft(metadata=metadata))
    assert report.reference_validation_passed is False
    assert any(error.code == "SOURCE_CHAPTER_COUNT_MISMATCH" for error in report.errors)


def test_adaptation_change_unknown_references_fail_reference_validation() -> None:
    report = validate_document(
        _draft(
            adaptation_changes=[
                AdaptationChange(
                    change_id="chg-1",
                    type="compressed",
                    source_chapters=["missing"],
                    affected_scenes=["missing-scene"],
                    description="Condensed a missing chapter.",
                    reason="Invalid test fixture.",
                )
            ]
        )
    )

    assert report.reference_validation_passed is False
    assert any(error.code == "UNKNOWN_ADAPTATION_CHANGE_SOURCE_CHAPTER" for error in report.errors)
    assert any(error.code == "UNKNOWN_ADAPTATION_CHANGE_SCENE" for error in report.errors)


def test_non_added_adaptation_change_requires_source_chapters() -> None:
    report = validate_document(
        _draft(
            adaptation_changes=[
                AdaptationChange(
                    change_id="chg-1",
                    type="compressed",
                    source_chapters=[],
                    affected_scenes=["sc-1"],
                    description="Condensed material.",
                    reason="Pacing.",
                )
            ]
        )
    )

    assert report.reference_validation_passed is False
    assert any(error.code == "ADAPTATION_CHANGE_SOURCE_CHAPTERS_EMPTY" for error in report.errors)


def test_empty_key_events_fail_coverage_validation() -> None:
    chapters = [_chapter(1), _chapter(2), _chapter(3)]
    chapters[1] = Chapter(
        chapter_id="ch-2",
        order=2,
        title="Chapter 2",
        summary="The story continues.",
        key_events=[],
    )

    report = validate_document(_draft(chapters=chapters))

    assert report.coverage_validation_passed is False
    assert any(error.code == "CHAPTER_KEY_EVENTS_EMPTY" for error in report.errors)


def test_omitted_chapter_requires_omitted_or_merged_key_events() -> None:
    chapters = [_chapter(1), _chapter(2), _chapter(3)]
    scene = Scene(
        scene_id="sc-1",
        order=1,
        title="Opening Scene",
        source_chapters=["ch-1", "ch-2"],
        summary="Alice greets.",
        content_blocks=[_block()],
    )

    report = validate_document(
        _draft(
            chapters=chapters,
            screenplay=Screenplay(scenes=[scene]),
            adaptation_changes=[
                AdaptationChange(
                    change_id="chg-1",
                    type="omitted",
                    source_chapters=["ch-3"],
                    affected_scenes=[],
                    description="Chapter 3 is omitted.",
                    reason="Scope control.",
                )
            ],
        )
    )

    assert report.coverage_validation_passed is False
    assert any(error.code == "OMITTED_CHAPTER_HAS_ACTIVE_KEY_EVENTS" for error in report.errors)


def test_omitted_chapter_with_omitted_key_events_passes_coverage() -> None:
    chapters = [_chapter(1), _chapter(2), _chapter(3)]
    chapters[2] = Chapter(
        chapter_id="ch-3",
        order=3,
        title="Chapter 3",
        summary="The story continues.",
        key_events=[KeyEvent(event_id="ev-3", text="An event.", status="omitted")],
    )
    scene = Scene(
        scene_id="sc-1",
        order=1,
        title="Opening Scene",
        source_chapters=["ch-1", "ch-2"],
        summary="Alice greets.",
        content_blocks=[_block()],
    )

    report = validate_document(
        _draft(
            chapters=chapters,
            screenplay=Screenplay(scenes=[scene]),
            adaptation_changes=[
                AdaptationChange(
                    change_id="chg-1",
                    type="omitted",
                    source_chapters=["ch-3"],
                    affected_scenes=[],
                    description="Chapter 3 is omitted.",
                    reason="Scope control.",
                )
            ],
        )
    )

    assert report.reference_validation_passed is True
    assert report.coverage_validation_passed is True


def test_character_refs_checked_only_when_character_table_populated() -> None:
    scene = Scene(
        scene_id="sc-1",
        order=1,
        title="Opening Scene",
        source_chapters=["ch-1", "ch-2", "ch-3"],
        summary="Alice greets.",
        content_blocks=[_block(speaker="missing")],
    )
    report = validate_document(_draft(screenplay=Screenplay(scenes=[scene])))
    assert report.reference_validation_passed is True


def test_validate_and_mark_rejects_failed_coverage() -> None:
    with pytest.raises(ValueError):
        validate_and_mark(_draft(screenplay=Screenplay(scenes=[])))


def test_shared_types_still_rejects_invalid_metadata() -> None:
    with pytest.raises(ValidationError):
        _metadata(source_chapter_count=2)


def test_valid_timeline_passes_reference_validation() -> None:
    timeline = [
        TimelineEntry(
            entry_id="ch-1-tl-001",
            description="An event.",
            source_chapters=["ch-1"],
            related_scenes=["sc-1"],
        ),
        TimelineEntry(
            entry_id="ch-2-tl-001",
            description="Another event.",
            source_chapters=["ch-2", "ch-3"],
            related_scenes=["sc-1"],
        ),
    ]
    report = validate_document(_draft(timeline=timeline))
    assert report.reference_validation_passed is True
    assert report.errors == []


def test_unknown_timeline_source_chapter_fails_reference_validation() -> None:
    timeline = [
        TimelineEntry(
            entry_id="tl-1",
            description="An event.",
            source_chapters=["missing"],
            related_scenes=["sc-1"],
        )
    ]
    report = validate_document(_draft(timeline=timeline))
    assert report.reference_validation_passed is False
    assert any(error.code == "UNKNOWN_TIMELINE_SOURCE_CHAPTER" for error in report.errors)


def test_unknown_timeline_scene_fails_reference_validation() -> None:
    timeline = [
        TimelineEntry(
            entry_id="tl-1",
            description="An event.",
            source_chapters=["ch-1"],
            related_scenes=["missing-scene"],
        )
    ]
    report = validate_document(_draft(timeline=timeline))
    assert report.reference_validation_passed is False
    assert any(error.code == "UNKNOWN_TIMELINE_SCENE" for error in report.errors)


def test_duplicate_timeline_entry_id_fails_reference_validation() -> None:
    timeline = [
        TimelineEntry(
            entry_id="tl-1",
            description="An event.",
            source_chapters=["ch-1"],
            related_scenes=["sc-1"],
        ),
        TimelineEntry(
            entry_id="tl-1",
            description="Another event.",
            source_chapters=["ch-2"],
            related_scenes=["sc-1"],
        ),
    ]
    report = validate_document(_draft(timeline=timeline))
    assert report.reference_validation_passed is False
    assert any(error.code == "DUPLICATE_TIMELINE_ENTRY_ID" for error in report.errors)
