"""First-layer contract: ModelOutput DTOs.

These are the minimal structures the LLM is allowed to emit. They intentionally
do *not* carry backend-owned data such as stable IDs, ``order`` values, or
document-level ``status`` enums. The backend assigns those during normalization
when it assembles the second-layer :mod:`screenplay_document` structures.

Reference: SKILL.md section 10 (model output contracts).
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field

from ._config import FORBID_EXTRA_CONFIG

# All model-output DTOs reject unknown keys. Per SKILL.md section 10 the model
# layer must never emit backend-owned fields (e.g. ``block_id``, ``order``,
# ``speaker``); forbidding extras turns a silent drop into a hard
# ``ValidationError``, reinforcing the field whitelist (SKILL.md sections 5/12).

# The model expresses event weight as ``importance``. The document layer instead
# tracks adaptation ``status``; the two must not be conflated.
KeyEventImportance = Literal["high", "medium", "low"]

# Block ``type`` is shared between the model layer and the document layer.
ContentBlockType = Literal["action", "dialogue", "voice_over", "note"]

# How faithfully a scene covers a source key event. Defined here for the model
# layer; the document layer defines an identical Literal independently so the
# two contract layers stay decoupled.
KeyEventFidelityStatus = Literal["faithful", "adapted", "partial", "omitted"]


class KeyEventOutput(BaseModel):
    """A single key event as produced by chapter-summary generation."""

    model_config = FORBID_EXTRA_CONFIG

    text: str
    importance: KeyEventImportance


class ChapterSummaryOutput(BaseModel):
    """Structured output for one chapter's summary stage."""

    model_config = FORBID_EXTRA_CONFIG

    chapter_id: str
    title: str
    summary: str
    key_events: list[KeyEventOutput]
    characters_mentioned: list[str] = []
    locations_mentioned: list[str] = []
    open_questions: list[str] = []


class ScenePlanItem(BaseModel):
    """A single planned scene before any content is written."""

    model_config = FORBID_EXTRA_CONFIG

    title: str
    source_chapters: list[str]
    location_name: str | None = None
    time: str | None = None
    characters: list[str] = []
    dramatic_goal: str | None = None
    conflict: str | None = None
    summary: str


class ScenePlanOutput(BaseModel):
    """Structured output for the scene-planning stage."""

    model_config = FORBID_EXTRA_CONFIG

    scenes: list[ScenePlanItem]


class ModelActionBlock(BaseModel):
    """Model-layer action block. Requires ``text``."""

    model_config = FORBID_EXTRA_CONFIG

    type: Literal["action"] = "action"
    text: str


class ModelDialogueBlock(BaseModel):
    """Model-layer dialogue block.

    The model references speakers only by ``speaker_name`` (no character id) and
    never assigns ``block_id`` or ``order``. ``speaker_name`` and ``line`` are
    required per SKILL.md section 10.
    """

    model_config = FORBID_EXTRA_CONFIG

    type: Literal["dialogue"] = "dialogue"
    speaker_name: str
    line: str
    emotion: str | None = None
    action_hint: str | None = None


class ModelVoiceOverBlock(BaseModel):
    """Model-layer voice-over block. Requires ``text``."""

    model_config = FORBID_EXTRA_CONFIG

    type: Literal["voice_over"] = "voice_over"
    text: str


class ModelNoteBlock(BaseModel):
    """Model-layer note block. Requires ``text``."""

    model_config = FORBID_EXTRA_CONFIG

    type: Literal["note"] = "note"
    text: str


# Discriminated union on ``type``, mirroring the document layer's ContentBlock
# while keeping model-layer semantics (no speaker id, no block_id/order).
ModelContentBlock = Annotated[
    Union[
        ModelActionBlock,
        ModelDialogueBlock,
        ModelVoiceOverBlock,
        ModelNoteBlock,
    ],
    Field(discriminator="type"),
]


class CoveredKeyEvent(BaseModel):
    """A model-reported claim that a scene covers a source key event.

    The model references the backend-computed ``key_event_id`` (it never mints
    ids) and points at the block that covers the event by 1-based
    ``covered_by_block_index`` into ``content_blocks`` -- the model layer has no
    ``block_id`` (the backend assigns those during assembly). The backend treats
    these claims as untrusted and re-verifies every reference before keeping it.
    """

    model_config = FORBID_EXTRA_CONFIG

    key_event_id: str
    fidelity_status: KeyEventFidelityStatus
    covered_by_block_index: int | None = None
    notes: str | None = None


class SceneContentOutput(BaseModel):
    """Structured output for the scene-content generation stage."""

    model_config = FORBID_EXTRA_CONFIG

    scene_id: str
    content_blocks: list[ModelContentBlock]
    covered_key_events: list[CoveredKeyEvent] = []
    adaptation_notes: list[str] = []
    quality_flags: list[str] = []


class RepairOutput(BaseModel):
    """Structured output for a repair attempt.

    Repair fixes structure only; ``result`` carries the corrected structured
    payload when ``fixed`` is true.
    """

    model_config = FORBID_EXTRA_CONFIG

    fixed: bool
    reason: str
    result: dict[str, Any] | None = None
