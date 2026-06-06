"""Contract tests for the shared_types Pydantic models.

Covers: a minimal-but-legal draft document, the ``source_chapter_count >= 3``
guard, the ``ContentBlock`` discriminated union, the ``KeyEvent.status`` enum,
the internal ``mark_validated`` factory returning a ``ValidatedScreenplay``, and
the public-barrel boundary (``mark_validated`` must not leak from
``shared_types``).
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

import shared_types
from shared_types import (
    AdaptationConfig,
    Chapter,
    ChapterSummaryOutput,
    DialogueBlock,
    KeyEvent,
    KeyEventOutput,
    Metadata,
    ModelActionBlock,
    ModelDialogueBlock,
    PipelineError,
    Scene,
    SceneContentOutput,
    ScenePlanItem,
    ScenePlanOutput,
    Screenplay,
    ScreenplayDraftDocument,
    EmbeddedValidation,
    ValidatedScreenplay,
    ValidationReport,
)
from shared_types.internal import mark_validated


def _make_metadata(**overrides: Any) -> Metadata:
    """Build a valid ``Metadata`` instance, allowing field overrides."""
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


def _make_min_draft(**meta_overrides: Any) -> ScreenplayDraftDocument:
    """Return a minimal but valid ``ScreenplayDraftDocument``.

    ``characters``, ``locations``, ``adaptation_changes`` and ``revision_notes``
    are empty per P0a-lite-1; ``chapters`` carries three entries so the array
    length matches ``metadata.source_chapter_count`` (3), and ``screenplay``
    carries minimal content so the document is structurally non-empty.
    """
    chapters = [
        Chapter(
            chapter_id=f"ch-{i}",
            order=i,
            title=f"Chapter {i}",
            summary="The story unfolds.",
            key_events=[
                KeyEvent(event_id=f"ev-{i}", text="An event.", status="adapted")
            ],
        )
        for i in range(1, 4)
    ]
    block = DialogueBlock(
        block_id="b-1",
        order=1,
        speaker="char-1",
        speaker_name="Alice",
        line="Hello there.",
    )
    scene = Scene(
        scene_id="sc-1",
        order=1,
        title="Opening Scene",
        source_chapters=["ch-1", "ch-2", "ch-3"],
        summary="Alice greets.",
        content_blocks=[block],
    )
    return ScreenplayDraftDocument(
        metadata=_make_metadata(**meta_overrides),
        adaptation_config=AdaptationConfig(
            output_language="en",
            target_medium="series",
            adaptation_degree="faithful",
            narration_policy="minimal",
            tone="neutral",
            dialogue_style="natural",
        ),
        chapters=chapters,
        characters=[],
        locations=[],
        screenplay=Screenplay(scenes=[scene]),
        adaptation_changes=[],
        validation=EmbeddedValidation(schema_version="0.1.0"),
        revision_notes=[],
    )


def _passing_report(**overrides: Any) -> ValidationReport:
    data: dict[str, Any] = {
        "yaml_parse_passed": True,
        "schema_validation_passed": True,
        "reference_validation_passed": True,
        "coverage_validation_passed": True,
        "errors": [],
    }
    data.update(overrides)
    return ValidationReport(**data)


def test_minimal_legal_draft_constructs() -> None:
    draft = _make_min_draft()
    assert draft.metadata.source_chapter_count == 3
    assert draft.characters == []
    assert draft.locations == []
    assert draft.revision_notes == []
    assert draft.adaptation_changes == []
    assert draft.validation.passed is False
    assert draft.validation.validated_at is None
    assert len(draft.screenplay.scenes) == 1


def test_source_chapter_count_below_three_rejected() -> None:
    with pytest.raises(ValidationError):
        _make_metadata(source_chapter_count=2)


def test_document_with_low_chapter_count_rejected() -> None:
    with pytest.raises(ValidationError):
        _make_min_draft(source_chapter_count=1)


def test_dialogue_block_constructs_from_union_data() -> None:
    scene = Scene.model_validate(
        {
            "scene_id": "sc-1",
            "order": 1,
            "title": "T",
            "source_chapters": ["ch-1"],
            "summary": "s",
            "content_blocks": [
                {
                    "block_id": "b-1",
                    "order": 1,
                    "type": "dialogue",
                    "speaker": "char-1",
                    "speaker_name": "Alice",
                    "line": "Hi.",
                }
            ],
        }
    )
    block = scene.content_blocks[0]
    assert isinstance(block, DialogueBlock)
    assert block.speaker_name == "Alice"


def test_dialogue_block_missing_speaker_rejected() -> None:
    with pytest.raises(ValidationError):
        Scene.model_validate(
            {
                "scene_id": "sc-1",
                "order": 1,
                "title": "T",
                "source_chapters": ["ch-1"],
                "summary": "s",
                "content_blocks": [
                    {
                        "block_id": "b-1",
                        "order": 1,
                        "type": "dialogue",
                        "speaker_name": "Alice",
                        "line": "Hi.",
                    }
                ],
            }
        )


def test_content_block_illegal_type_rejected() -> None:
    with pytest.raises(ValidationError):
        Scene.model_validate(
            {
                "scene_id": "sc-1",
                "order": 1,
                "title": "T",
                "source_chapters": ["ch-1"],
                "summary": "s",
                "content_blocks": [
                    {"block_id": "b-1", "order": 1, "type": "foo", "text": "x"}
                ],
            }
        )


def test_key_event_illegal_status_rejected() -> None:
    # Route through ``model_validate`` so the deliberately-illegal status is a
    # runtime value (mypy would statically reject the literal otherwise); this
    # still exercises pydantic's enum enforcement.
    with pytest.raises(ValidationError):
        KeyEvent.model_validate(
            {"event_id": "ev-1", "text": "An event.", "status": "bogus"}
        )


def test_mark_validated_returns_validated_screenplay() -> None:
    draft = _make_min_draft()
    report = _passing_report()
    validated = mark_validated(draft, report)
    assert isinstance(validated, ValidatedScreenplay)
    assert validated.document.validation.passed is True
    assert validated.document.validation.validated_at is not None
    assert validated.document.validation.validated_at != ""
    assert validated.report is report


def test_mark_validated_coverage_none_is_pass() -> None:
    draft = _make_min_draft()
    validated = mark_validated(draft, _passing_report(coverage_validation_passed=None))
    assert isinstance(validated, ValidatedScreenplay)
    assert validated.document.validation.passed is True


def test_validated_screenplay_is_frozen() -> None:
    validated = mark_validated(_make_min_draft(), _passing_report())
    with pytest.raises(ValidationError):
        validated.document = _make_min_draft()


def test_mark_validated_rejects_failed_layer() -> None:
    draft = _make_min_draft()
    with pytest.raises(ValueError):
        mark_validated(draft, _passing_report(reference_validation_passed=False))


def test_mark_validated_rejects_nonempty_errors() -> None:
    draft = _make_min_draft()
    report = _passing_report(
        errors=[{"code": "E001", "message": "boom"}],
    )
    with pytest.raises(ValueError):
        mark_validated(draft, report)


def test_mark_validated_not_leaked_from_public_barrel() -> None:
    assert not hasattr(shared_types, "mark_validated")


# --- Fix 2: AdaptationConfig optional fields -------------------------------


def test_adaptation_config_all_optional() -> None:
    # Omitting all six previously-required knobs must succeed.
    config = AdaptationConfig()
    assert config.output_language is None
    assert config.target_medium is None
    assert config.adaptation_degree is None
    assert config.narration_policy is None
    assert config.tone is None
    assert config.dialogue_style is None
    assert config.episode_length_minutes is None
    assert config.max_scene_count is None


def test_draft_with_empty_adaptation_config_constructs() -> None:
    chapter = Chapter(
        chapter_id="ch-1",
        order=1,
        title="Chapter One",
        summary="The story opens.",
        key_events=[KeyEvent(event_id="ev-1", text="An event.", status="adapted")],
    )
    scene = Scene(
        scene_id="sc-1",
        order=1,
        title="Opening Scene",
        source_chapters=["ch-1"],
        summary="Alice greets.",
        content_blocks=[
            DialogueBlock(
                block_id="b-1",
                order=1,
                speaker="char-1",
                speaker_name="Alice",
                line="Hello there.",
            )
        ],
    )
    draft = ScreenplayDraftDocument(
        metadata=_make_metadata(),
        adaptation_config=AdaptationConfig(),
        chapters=[chapter],
        characters=[],
        locations=[],
        screenplay=Screenplay(scenes=[scene]),
        adaptation_changes=[],
        validation=EmbeddedValidation(schema_version="0.1.0"),
        revision_notes=[],
    )
    assert draft.adaptation_config.output_language is None


# --- Fix 3: ModelContentBlock discriminated union --------------------------


def test_model_dialogue_block_constructs_with_required_fields() -> None:
    block = ModelDialogueBlock(speaker_name="Alice", line="Hi.")
    assert block.type == "dialogue"
    assert block.speaker_name == "Alice"
    assert block.line == "Hi."


def test_model_action_block_constructs_with_text() -> None:
    block = ModelActionBlock(text="Rain falls.")
    assert block.type == "action"
    assert block.text == "Rain falls."


def test_scene_content_output_parses_union_blocks() -> None:
    out = SceneContentOutput.model_validate(
        {
            "scene_id": "sc-1",
            "content_blocks": [
                {"type": "action", "text": "Rain falls."},
                {"type": "dialogue", "speaker_name": "Alice", "line": "Hi."},
            ],
        }
    )
    assert isinstance(out.content_blocks[0], ModelActionBlock)
    assert isinstance(out.content_blocks[1], ModelDialogueBlock)


def test_model_dialogue_missing_speaker_and_line_rejected() -> None:
    with pytest.raises(ValidationError):
        SceneContentOutput.model_validate(
            {
                "scene_id": "sc-1",
                "content_blocks": [{"type": "dialogue"}],
            }
        )


def test_model_action_missing_text_rejected() -> None:
    with pytest.raises(ValidationError):
        SceneContentOutput.model_validate(
            {
                "scene_id": "sc-1",
                "content_blocks": [{"type": "action"}],
            }
        )


def test_model_content_block_illegal_type_rejected() -> None:
    with pytest.raises(ValidationError):
        SceneContentOutput.model_validate(
            {
                "scene_id": "sc-1",
                "content_blocks": [{"type": "bogus", "text": "x"}],
            }
        )


# --- Fix 2b: model_output required structural fields -----------------------


def test_chapter_summary_missing_key_events_rejected() -> None:
    with pytest.raises(ValidationError):
        ChapterSummaryOutput.model_validate(
            {"chapter_id": "ch-1", "title": "T", "summary": "s"}
        )


def test_scene_plan_item_missing_source_chapters_rejected() -> None:
    with pytest.raises(ValidationError):
        ScenePlanItem.model_validate({"title": "T", "summary": "s"})


def test_scene_plan_output_missing_scenes_rejected() -> None:
    with pytest.raises(ValidationError):
        ScenePlanOutput.model_validate({})


def test_scene_content_output_missing_content_blocks_rejected() -> None:
    with pytest.raises(ValidationError):
        SceneContentOutput.model_validate({"scene_id": "sc-1"})


def test_chapter_summary_optional_lists_default_when_omitted() -> None:
    out = ChapterSummaryOutput.model_validate(
        {
            "chapter_id": "ch-1",
            "title": "T",
            "summary": "s",
            "key_events": [],
        }
    )
    assert out.characters_mentioned == []
    assert out.locations_mentioned == []
    assert out.open_questions == []


def test_scene_content_output_optional_lists_default_when_omitted() -> None:
    out = SceneContentOutput.model_validate(
        {"scene_id": "sc-1", "content_blocks": []}
    )
    assert out.adaptation_notes == []
    assert out.quality_flags == []


# --- Fix 3: PipelineStage literal ------------------------------------------


def _pipeline_error_data(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "failed_stage": "validation",
        "error_type": "schema_validation_failed",
        "error_message": "boom",
        "retryable": False,
        "suggested_action": "fix it",
    }
    data.update(overrides)
    return data


def test_pipeline_error_accepts_legal_stage() -> None:
    err = PipelineError.model_validate(
        _pipeline_error_data(failed_stage="scene_planning")
    )
    assert err.failed_stage == "scene_planning"


def test_pipeline_error_rejects_illegal_stage() -> None:
    with pytest.raises(ValidationError):
        PipelineError.model_validate(_pipeline_error_data(failed_stage="bogus_stage"))


# --- Fix 5: model layer forbids backend-owned / unknown fields -------------


def test_model_dialogue_with_backend_owned_fields_rejected() -> None:
    # The model layer must never emit ``block_id``, ``order`` or ``speaker``;
    # extra="forbid" turns those into a hard ValidationError instead of a
    # silent drop.
    with pytest.raises(ValidationError):
        SceneContentOutput.model_validate(
            {
                "scene_id": "sc-1",
                "content_blocks": [
                    {
                        "type": "dialogue",
                        "speaker_name": "a",
                        "line": "b",
                        "block_id": "x",
                        "order": 1,
                        "speaker": "c",
                    }
                ],
            }
        )


def test_key_event_output_unknown_field_rejected() -> None:
    # ``status`` is a document-layer field; the model layer expresses weight as
    # ``importance``. Conflating the two must be rejected, not silently ignored.
    with pytest.raises(ValidationError):
        KeyEventOutput.model_validate(
            {"text": "t", "importance": "high", "status": "adapted"}
        )


def test_scene_content_output_legal_blocks_still_parse() -> None:
    # Forward regression: a clean dialogue + action payload (model-layer fields
    # only) must still validate and resolve to the correct subclasses.
    out = SceneContentOutput.model_validate(
        {
            "scene_id": "sc-1",
            "content_blocks": [
                {"type": "dialogue", "speaker_name": "a", "line": "b"},
                {"type": "action", "text": "t"},
            ],
        }
    )
    assert len(out.content_blocks) == 2
    assert isinstance(out.content_blocks[0], ModelDialogueBlock)
    assert isinstance(out.content_blocks[1], ModelActionBlock)


# --- Fix 6: document/report/error layers forbid unknown fields -------------


def test_metadata_unknown_field_rejected() -> None:
    with pytest.raises(ValidationError):
        _make_metadata(bogus="x")


def test_scene_unknown_field_rejected() -> None:
    with pytest.raises(ValidationError):
        Scene.model_validate(
            {
                "scene_id": "sc-1",
                "order": 1,
                "title": "T",
                "source_chapters": ["ch-1"],
                "summary": "s",
                "content_blocks": [],
                "bogus": "x",
            }
        )


def test_screenplay_draft_document_unknown_field_rejected() -> None:
    data = _make_min_draft().model_dump()
    data["bogus"] = "x"
    with pytest.raises(ValidationError):
        ScreenplayDraftDocument.model_validate(data)


def test_validation_report_unknown_field_rejected() -> None:
    with pytest.raises(ValidationError):
        ValidationReport.model_validate(
            {
                "yaml_parse_passed": True,
                "schema_validation_passed": True,
                "reference_validation_passed": True,
                "bogus": "x",
            }
        )


def test_pipeline_error_unknown_field_rejected() -> None:
    with pytest.raises(ValidationError):
        PipelineError.model_validate(
            {
                "failed_stage": "validation",
                "error_type": "schema_validation_failed",
                "error_message": "boom",
                "retryable": False,
                "suggested_action": "fix it",
                "bogus": "x",
            }
        )


