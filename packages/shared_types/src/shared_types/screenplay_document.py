"""Second-layer contract: the backend-owned screenplay document.

This is the normalized domain/YAML structure the backend owns. Unlike the
model-output DTOs it carries stable IDs, ``order`` values, and document-level
enums. Reference: SKILL.md sections 6 and 7.

``ScreenplayDraftDocument`` is the single document model. The "validated" state
is expressed structurally by ``shared_types.validated.ValidatedScreenplay``,
which wraps a document together with its ``ValidationReport``.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

from ._config import FORBID_EXTRA_CONFIG

KeyEventStatus = Literal[
    "adapted",
    "partially_adapted",
    "merged",
    "omitted",
    "pending_review",
]

# How faithfully a scene covers a source key event. Defined independently from
# the identical Literal in ``model_output`` so the two contract layers stay
# decoupled (the document layer must not import the model layer).
KeyEventFidelityStatus = Literal["faithful", "adapted", "partial", "omitted"]

AdaptationChangeType = Literal[
    "merged",
    "omitted",
    "added",
    "reordered",
    "compressed",
    "expanded",
    "changed_pov",
]


# --- content blocks: discriminated union on ``type`` -----------------------


class ActionBlock(BaseModel):
    """An action / stage-direction block."""

    model_config = FORBID_EXTRA_CONFIG

    block_id: str
    order: int
    type: Literal["action"] = "action"
    text: str


class DialogueBlock(BaseModel):
    """A line of dialogue. Carries both speaker id and display name."""

    model_config = FORBID_EXTRA_CONFIG

    block_id: str
    order: int
    type: Literal["dialogue"] = "dialogue"
    speaker: str
    speaker_name: str
    line: str
    emotion: str | None = None
    action_hint: str | None = None


class VoiceOverBlock(BaseModel):
    """A voice-over block."""

    model_config = FORBID_EXTRA_CONFIG

    block_id: str
    order: int
    type: Literal["voice_over"] = "voice_over"
    text: str


class NoteBlock(BaseModel):
    """An author/production note block."""

    model_config = FORBID_EXTRA_CONFIG

    block_id: str
    order: int
    type: Literal["note"] = "note"
    text: str


ContentBlock = Annotated[
    Union[ActionBlock, DialogueBlock, VoiceOverBlock, NoteBlock],
    Field(discriminator="type"),
]


# --- chapters --------------------------------------------------------------


class KeyEvent(BaseModel):
    """A key event in the document layer. Uses ``status`` (not ``importance``)."""

    model_config = FORBID_EXTRA_CONFIG

    event_id: str
    text: str
    status: KeyEventStatus


class Chapter(BaseModel):
    """A parsed, confirmed chapter with its summary and key events."""

    model_config = FORBID_EXTRA_CONFIG

    chapter_id: str
    order: int
    title: str
    summary: str
    key_events: list[KeyEvent] = []


# --- characters / locations (minimal in P0a-lite-1) ------------------------


class Character(BaseModel):
    """A character. Minimal in P0a-lite-1; the table may be empty."""

    model_config = FORBID_EXTRA_CONFIG

    character_id: str
    name: str


class Location(BaseModel):
    """A location. Minimal in P0a-lite-1; the table may be empty."""

    model_config = FORBID_EXTRA_CONFIG

    location_id: str
    name: str


# --- screenplay ------------------------------------------------------------


class SceneKeyEventCoverage(BaseModel):
    """A backend-owned record that a scene covers a source key event.

    Assembled from the model's ``CoveredKeyEvent`` claims after the backend
    verifies that ``key_event_id`` is a real event of one of the scene's source
    chapters and (when given) resolves the model's block index to a real
    ``block_id``. Unverifiable claims are dropped during assembly.
    """

    model_config = FORBID_EXTRA_CONFIG

    key_event_id: str
    fidelity_status: KeyEventFidelityStatus
    covered_by_block_id: str | None = None
    notes: str | None = None


class Scene(BaseModel):
    """A single scene with ordered content blocks."""

    model_config = FORBID_EXTRA_CONFIG

    scene_id: str
    order: int
    title: str
    source_chapters: list[str] = []
    summary: str
    content_blocks: list[ContentBlock] = []
    key_event_coverage: list[SceneKeyEventCoverage] = []
    location_id: str | None = None
    location_name: str | None = None
    time: str | None = None
    characters: list[str] = []
    scene_type: str | None = None
    estimated_duration_seconds: int | None = None
    dramatic_goal: str | None = None
    conflict: str | None = None
    adaptation_notes: list[str] = []
    quality_flags: list[str] = []


class Screenplay(BaseModel):
    """The screenplay body: an ordered list of scenes."""

    model_config = FORBID_EXTRA_CONFIG

    scenes: list[Scene] = []


# --- timeline (P0a) --------------------------------------------------------


class TimelineEntry(BaseModel):
    """A single story-timeline entry.

    Backend-owned: the backend derives the timeline deterministically from
    chapter key events (it owns ``entry_id`` and the ``related_scenes`` link).
    ``time`` is optional free text since P0a does not yet model absolute time.
    ``source_chapters`` records provenance; ``related_scenes`` lists the scenes
    that cover those chapters and is validated against known scene ids.
    """

    model_config = FORBID_EXTRA_CONFIG

    entry_id: str
    description: str
    time: str | None = None
    source_chapters: list[str] = []
    related_scenes: list[str] = []


# --- story bible (P0a) -----------------------------------------------------


class CharacterProfile(BaseModel):
    """Story-bible profile: a character and the scenes they appear in.

    Backend-derived from the assembled characters table and scene references;
    no new LLM stage. ``scene_ids`` lists scenes whose ``characters`` include
    this character id, in scene order.
    """

    model_config = FORBID_EXTRA_CONFIG

    character_id: str
    name: str
    scene_ids: list[str] = []


class LocationProfile(BaseModel):
    """Story-bible profile: a location and the scenes set there."""

    model_config = FORBID_EXTRA_CONFIG

    location_id: str
    name: str
    scene_ids: list[str] = []


class StoryBible(BaseModel):
    """Backend-derived overview aggregating characters and locations across scenes.

    Minimal P0a aggregation: it is computed deterministically from the
    characters/locations tables and the scenes that reference them. It owns no
    new data the model produced.
    """

    model_config = FORBID_EXTRA_CONFIG

    characters: list[CharacterProfile] = []
    locations: list[LocationProfile] = []


# --- adaptation changes ----------------------------------------------------


class AdaptationChange(BaseModel):
    """An explicit record of a meaningful adaptation change."""

    model_config = FORBID_EXTRA_CONFIG

    change_id: str
    type: AdaptationChangeType
    source_chapters: list[str] = []
    affected_scenes: list[str] = []
    description: str
    reason: str


# --- metadata / config / embedded validation / revision notes --------------


class Metadata(BaseModel):
    """Document metadata. ``source_chapter_count`` must be an int >= 3."""

    model_config = FORBID_EXTRA_CONFIG

    project_id: str
    title: str
    original_author: str
    schema_version: str
    schema_doc_version: str
    generator_version: str
    prompt_version: str
    generated_at: str
    language: str
    source_chapter_count: int = Field(ge=3)
    model: str


class AdaptationConfig(BaseModel):
    """User-chosen adaptation configuration.

    All fields are optional. SKILL.md section 4 lists these as adaptation
    *config* options; a legal document need not fill every one. This matches the
    TS contract, where the same knobs are optional.
    """

    model_config = FORBID_EXTRA_CONFIG

    output_language: str | None = None
    target_medium: str | None = None
    episode_length_minutes: int | None = None
    adaptation_degree: str | None = None
    narration_policy: str | None = None
    tone: str | None = None
    dialogue_style: str | None = None
    max_scene_count: int | None = None


class EmbeddedValidation(BaseModel):
    """The ``validation`` block embedded in the document.

    In the draft state ``passed`` is ``False`` and ``validated_at`` is ``None``;
    ``mark_validated`` rewrites these when branding a validated document.
    """

    model_config = FORBID_EXTRA_CONFIG

    schema_version: str
    validated_at: str | None = None
    passed: bool = False


class RevisionNote(BaseModel):
    """A minimal revision note. May be empty in P0a-lite-1."""

    model_config = FORBID_EXTRA_CONFIG

    note_id: str
    text: str


# --- top-level documents ---------------------------------------------------


class ScreenplayDraftDocument(BaseModel):
    """The backend-normalized screenplay document, not yet validated.

    Field order matches SKILL.md section 6. P0a-lite-1 allows empty
    ``characters``, ``locations``, ``adaptation_changes``, and
    ``revision_notes`` arrays, but the fields must always be present. Structural
    checks (e.g. non-empty scenes, valid references) are the validators layer's
    responsibility, not enforced here.
    """

    model_config = FORBID_EXTRA_CONFIG

    metadata: Metadata
    adaptation_config: AdaptationConfig
    chapters: list[Chapter] = []
    characters: list[Character] = []
    locations: list[Location] = []
    screenplay: Screenplay
    timeline: list[TimelineEntry] = []
    story_bible: StoryBible = StoryBible()
    adaptation_changes: list[AdaptationChange] = []
    validation: EmbeddedValidation
    revision_notes: list[RevisionNote] = []

