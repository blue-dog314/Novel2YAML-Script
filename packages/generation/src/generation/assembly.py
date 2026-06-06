"""Deterministic DTO-to-document assembly for screenplay drafts."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from shared_types import (
    SCREENPLAY_GENERATOR_VERSION,
    SCREENPLAY_PROMPT_VERSION,
    SCREENPLAY_SCHEMA_DOC_VERSION,
    SCREENPLAY_SCHEMA_VERSION,
    ActionBlock,
    AdaptationConfig,
    Chapter,
    Character,
    CharacterProfile,
    ChapterSummaryOutput,
    DialogueBlock,
    EmbeddedValidation,
    KeyEvent,
    Location,
    LocationProfile,
    Metadata,
    ModelActionBlock,
    ModelDialogueBlock,
    ModelNoteBlock,
    ModelVoiceOverBlock,
    NoteBlock,
    Scene,
    SceneContentOutput,
    ScenePlanOutput,
    Screenplay,
    ScreenplayDraftDocument,
    StoryBible,
    TimelineEntry,
    VoiceOverBlock,
)

_SLUG_SEPARATOR_RE = re.compile(r"-+")


class _CharacterRegistry:
    """Backend-owned character id/name registry.

    The model layer only emits character *names* (dialogue ``speaker_name``,
    scene ``characters``, chapter ``characters_mentioned``). The backend owns id
    assignment, mapping each distinct name (casefolded) to a stable ``char-<slug>``
    id while preserving the first-seen display name. This keeps ID ownership in
    the backend per CLAUDE.md and lets the reference validator activate.
    """

    def __init__(self) -> None:
        self._by_key: dict[str, tuple[str, str]] = {}
        self._unnamed_counter = 0

    def register(self, name: str) -> str:
        key = name.strip().casefold()
        existing = self._by_key.get(key)
        if existing is not None:
            return existing[0]
        core = _slug_core(name)
        if not core:
            self._unnamed_counter += 1
            core = f"unnamed-{self._unnamed_counter}"
        character_id = f"char-{core}"
        self._by_key[key] = (character_id, name.strip())
        return character_id

    def characters(self) -> list[Character]:
        return [
            Character(character_id=character_id, name=display_name)
            for character_id, display_name in self._by_key.values()
        ]


class _LocationRegistry:
    """Backend-owned location id/name registry.

    The model layer only emits location *names* (chapter ``locations_mentioned``,
    scene-plan ``location_name``). The backend owns id assignment, mapping each
    distinct name (casefolded) to a stable ``loc-<slug>`` id while preserving the
    first-seen display name. This keeps ID ownership in the backend per CLAUDE.md
    and lets the reference validator activate.
    """

    def __init__(self) -> None:
        self._by_key: dict[str, tuple[str, str]] = {}
        self._unnamed_counter = 0

    def register(self, name: str) -> str:
        key = name.strip().casefold()
        existing = self._by_key.get(key)
        if existing is not None:
            return existing[0]
        core = _slug_core(name)
        if not core:
            self._unnamed_counter += 1
            core = f"unnamed-{self._unnamed_counter}"
        location_id = f"loc-{core}"
        self._by_key[key] = (location_id, name.strip())
        return location_id

    def locations(self) -> list[Location]:
        return [
            Location(location_id=location_id, name=display_name)
            for location_id, display_name in self._by_key.values()
        ]


def assemble_screenplay(
    *,
    chapter_summaries: list[ChapterSummaryOutput],
    scene_plan: ScenePlanOutput,
    scene_contents: list[SceneContentOutput],
    project_id: str,
    title: str,
    original_author: str,
    language: str,
    model: str,
    adaptation_config: AdaptationConfig | None = None,
) -> ScreenplayDraftDocument:
    """Assemble model-output DTOs into a backend-owned screenplay draft."""
    scene_ids = [_seq_id("sc", index) for index, _ in enumerate(scene_plan.scenes, start=1)]
    content_by_scene_id = _index_scene_contents(scene_contents, scene_ids)
    chapters = _assemble_chapters(chapter_summaries)
    character_registry = _CharacterRegistry()
    location_registry = _LocationRegistry()
    # Register chapter-mentioned characters first so ids follow chapter order,
    # then scene/dialogue names get registered during scene assembly below.
    for summary in chapter_summaries:
        for name in summary.characters_mentioned:
            character_registry.register(name)
        for location_name in summary.locations_mentioned:
            location_registry.register(location_name)
    scenes = _assemble_scenes(
        scene_plan,
        scene_ids,
        content_by_scene_id,
        character_registry,
        location_registry,
    )
    timeline = _assemble_timeline(chapter_summaries, scenes)
    characters = character_registry.characters()
    locations = location_registry.locations()
    return ScreenplayDraftDocument(
        metadata=_make_metadata(
            project_id=project_id,
            title=title,
            original_author=original_author,
            language=language,
            source_chapter_count=len(chapters),
            model=model,
        ),
        adaptation_config=adaptation_config or AdaptationConfig(),
        chapters=chapters,
        characters=characters,
        locations=locations,
        screenplay=Screenplay(scenes=scenes),
        timeline=timeline,
        story_bible=_assemble_story_bible(characters, locations, scenes),
        adaptation_changes=[],
        validation=EmbeddedValidation(schema_version=SCREENPLAY_SCHEMA_VERSION),
        revision_notes=[],
    )


def _index_scene_contents(
    scene_contents: list[SceneContentOutput],
    scene_ids: list[str],
) -> dict[str, SceneContentOutput]:
    valid_scene_ids = set(scene_ids)
    content_by_scene_id: dict[str, SceneContentOutput] = {}
    for content in scene_contents:
        if content.scene_id in content_by_scene_id:
            raise ValueError(f"duplicate scene content for {content.scene_id!r}")
        if content.scene_id not in valid_scene_ids:
            raise ValueError(f"scene content references unknown scene_id {content.scene_id!r}")
        content_by_scene_id[content.scene_id] = content
    missing_scene_ids = [scene_id for scene_id in scene_ids if scene_id not in content_by_scene_id]
    if missing_scene_ids:
        raise ValueError(f"missing scene content for {missing_scene_ids[0]!r}")
    return content_by_scene_id


def _seq_id(prefix: str, index: int) -> str:
    return f"{prefix}-{index:03d}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug_core(name: str) -> str:
    parts: list[str] = []
    previous_was_separator = False
    for character in name.strip().casefold():
        if character.isascii() and character.isalnum() or "\u4e00" <= character <= "\u9fff":
            parts.append(character)
            previous_was_separator = False
        elif not previous_was_separator:
            parts.append("-")
            previous_was_separator = True
    return _SLUG_SEPARATOR_RE.sub("-", "".join(parts)).strip("-")


def _assemble_key_events(chapter: ChapterSummaryOutput) -> list[KeyEvent]:
    return [
        KeyEvent(
            event_id=f"{chapter.chapter_id}-ev-{index:03d}",
            text=key_event.text,
            status="pending_review",
        )
        for index, key_event in enumerate(chapter.key_events, start=1)
    ]


def _assemble_chapters(chapter_summaries: list[ChapterSummaryOutput]) -> list[Chapter]:
    return [
        Chapter(
            chapter_id=chapter.chapter_id,
            order=index,
            title=chapter.title,
            summary=chapter.summary,
            key_events=_assemble_key_events(chapter),
        )
        for index, chapter in enumerate(chapter_summaries, start=1)
    ]


def _assemble_timeline(
    chapter_summaries: list[ChapterSummaryOutput],
    scenes: list[Scene],
) -> list[TimelineEntry]:
    """Derive a deterministic story timeline from chapter key events.

    P0a "timeline extraction" is a backend-owned aggregation, not a new LLM
    stage. One entry is emitted per chapter key event in chapter order then
    event order. ``related_scenes`` is computed deterministically as the scenes
    whose ``source_chapters`` include the originating chapter (preserving scene
    order). ``time`` stays ``None`` since P0a does not model absolute time.
    """
    scenes_by_chapter: dict[str, list[str]] = {}
    for scene in scenes:
        for chapter_id in scene.source_chapters:
            scenes_by_chapter.setdefault(chapter_id, []).append(scene.scene_id)
    timeline: list[TimelineEntry] = []
    for chapter in chapter_summaries:
        related_scenes = scenes_by_chapter.get(chapter.chapter_id, [])
        for event_index, key_event in enumerate(chapter.key_events, start=1):
            timeline.append(
                TimelineEntry(
                    entry_id=f"{chapter.chapter_id}-tl-{event_index:03d}",
                    description=key_event.text,
                    time=None,
                    source_chapters=[chapter.chapter_id],
                    related_scenes=list(related_scenes),
                )
            )
    return timeline


def _assemble_story_bible(
    characters: list[Character],
    locations: list[Location],
    scenes: list[Scene],
) -> StoryBible:
    """Derive a deterministic Story Bible overview from assembled tables.

    P0a "story bible" is a backend-owned aggregation, not a new LLM stage. For
    each character (in table order) it collects the scenes (in scene order)
    whose ``characters`` include that id; for each location it collects the
    scenes whose ``location_id`` matches. It introduces no new data.
    """
    character_profiles = [
        CharacterProfile(
            character_id=character.character_id,
            name=character.name,
            scene_ids=[
                scene.scene_id
                for scene in scenes
                if character.character_id in scene.characters
            ],
        )
        for character in characters
    ]
    location_profiles = [
        LocationProfile(
            location_id=location.location_id,
            name=location.name,
            scene_ids=[
                scene.scene_id
                for scene in scenes
                if scene.location_id == location.location_id
            ],
        )
        for location in locations
    ]
    return StoryBible(characters=character_profiles, locations=location_profiles)


def _assemble_content_block(
    scene_id: str,
    index: int,
    block: Any,
    character_registry: _CharacterRegistry,
) -> ActionBlock | DialogueBlock | VoiceOverBlock | NoteBlock:
    block_id = f"{scene_id}-blk-{index:03d}"
    if isinstance(block, ModelActionBlock):
        return ActionBlock(block_id=block_id, order=index, text=block.text)
    if isinstance(block, ModelDialogueBlock):
        return DialogueBlock(
            block_id=block_id,
            order=index,
            speaker=character_registry.register(block.speaker_name),
            speaker_name=block.speaker_name,
            line=block.line,
            emotion=block.emotion,
            action_hint=block.action_hint,
        )
    if isinstance(block, ModelVoiceOverBlock):
        return VoiceOverBlock(block_id=block_id, order=index, text=block.text)
    if isinstance(block, ModelNoteBlock):
        return NoteBlock(block_id=block_id, order=index, text=block.text)
    raise TypeError(f"unsupported content block type {type(block).__name__}")


def _assemble_scenes(
    scene_plan: ScenePlanOutput,
    scene_ids: list[str],
    content_by_scene_id: dict[str, SceneContentOutput],
    character_registry: _CharacterRegistry,
    location_registry: _LocationRegistry,
) -> list[Scene]:
    scenes: list[Scene] = []
    for index, (scene_id, plan_item) in enumerate(zip(scene_ids, scene_plan.scenes, strict=True), start=1):
        content = content_by_scene_id[scene_id]
        location_id = (
            location_registry.register(plan_item.location_name)
            if plan_item.location_name is not None
            else None
        )
        scenes.append(
            Scene(
                scene_id=scene_id,
                order=index,
                title=plan_item.title,
                source_chapters=plan_item.source_chapters,
                summary=plan_item.summary,
                content_blocks=[
                    _assemble_content_block(
                        scene_id,
                        block_index,
                        block,
                        character_registry,
                    )
                    for block_index, block in enumerate(content.content_blocks, start=1)
                ],
                location_id=location_id,
                location_name=plan_item.location_name,
                time=plan_item.time,
                characters=[
                    character_registry.register(name) for name in plan_item.characters
                ],
                scene_type=None,
                estimated_duration_seconds=None,
                dramatic_goal=plan_item.dramatic_goal,
                conflict=plan_item.conflict,
                adaptation_notes=content.adaptation_notes,
                quality_flags=content.quality_flags,
            )
        )
    return scenes


def _make_metadata(
    *,
    project_id: str,
    title: str,
    original_author: str,
    language: str,
    source_chapter_count: int,
    model: str,
) -> Metadata:
    return Metadata(
        project_id=project_id,
        title=title,
        original_author=original_author,
        schema_version=SCREENPLAY_SCHEMA_VERSION,
        schema_doc_version=SCREENPLAY_SCHEMA_DOC_VERSION,
        generator_version=SCREENPLAY_GENERATOR_VERSION,
        prompt_version=SCREENPLAY_PROMPT_VERSION,
        generated_at=_now_iso(),
        language=language,
        source_chapter_count=source_chapter_count,
        model=model,
    )


__all__ = [
    "assemble_screenplay",
]
