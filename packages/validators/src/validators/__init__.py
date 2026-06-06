"""Deterministic validation layers for screenplay draft documents."""

from __future__ import annotations

import re
from typing import Any

from pydantic import ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError
from shared_types import (
    ActionBlock,
    DialogueBlock,
    ScreenplayDraftDocument,
    ValidatedScreenplay,
    ValidationErrorIssue,
    ValidationReport,
)
from shared_types.internal import mark_validated

MODULE_NAME = "validators"

_CONTROL_CHARACTER_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def validate_yaml_text(yaml_text: str) -> tuple[ScreenplayDraftDocument | None, ValidationReport]:
    """Validate YAML text through syntax, schema, reference, and coverage layers."""
    syntax_errors = _validate_syntax_text(yaml_text)
    if syntax_errors:
        return None, _report(
            yaml_parse_passed=False,
            schema_validation_passed=False,
            reference_validation_passed=False,
            coverage_validation_passed=False,
            errors=syntax_errors,
        )

    yaml = YAML(typ="safe")
    try:
        raw_data = yaml.load(yaml_text)
    except YAMLError as exc:
        return None, _report(
            yaml_parse_passed=False,
            schema_validation_passed=False,
            reference_validation_passed=False,
            coverage_validation_passed=False,
            errors=[_issue("YAML_PARSE_FAILED", str(exc))],
        )

    try:
        document = ScreenplayDraftDocument.model_validate(raw_data)
    except ValidationError as exc:
        return None, _report(
            yaml_parse_passed=True,
            schema_validation_passed=False,
            reference_validation_passed=False,
            coverage_validation_passed=False,
            errors=_pydantic_issues(exc),
        )

    return document, validate_document(document)


def validate_document(document: ScreenplayDraftDocument) -> ValidationReport:
    """Validate an already parsed screenplay draft document."""
    reference_errors = _validate_references(document)
    coverage_errors = _validate_coverage(document)
    return _report(
        yaml_parse_passed=True,
        schema_validation_passed=True,
        reference_validation_passed=len(reference_errors) == 0,
        coverage_validation_passed=len(coverage_errors) == 0,
        errors=[*reference_errors, *coverage_errors],
    )


def validate_and_mark(document: ScreenplayDraftDocument) -> ValidatedScreenplay:
    """Return a validated screenplay only when all deterministic layers pass."""
    report = validate_document(document)
    if report.coverage_validation_passed is not True:
        raise ValueError("validate_and_mark: coverage validation did not explicitly pass")
    return mark_validated(document, report)


def validate_yaml_text_and_mark(yaml_text: str) -> ValidatedScreenplay:
    """Validate YAML text and return a branded validated screenplay on success."""
    document, report = validate_yaml_text(yaml_text)
    if document is None:
        raise ValueError("validate_yaml_text_and_mark: YAML did not produce a valid document")
    if report.coverage_validation_passed is not True:
        raise ValueError("validate_yaml_text_and_mark: coverage validation did not explicitly pass")
    return mark_validated(document, report)


def _validate_syntax_text(yaml_text: str) -> list[ValidationErrorIssue]:
    if _CONTROL_CHARACTER_RE.search(yaml_text):
        return [_issue("ILLEGAL_CONTROL_CHARACTER", "YAML text contains illegal control characters")]
    return []


def _validate_references(document: ScreenplayDraftDocument) -> list[ValidationErrorIssue]:
    errors: list[ValidationErrorIssue] = []
    chapter_ids = [chapter.chapter_id for chapter in document.chapters]
    chapter_orders = [chapter.order for chapter in document.chapters]
    scene_ids = [scene.scene_id for scene in document.screenplay.scenes]
    scene_orders = [scene.order for scene in document.screenplay.scenes]
    character_ids = {character.character_id for character in document.characters}
    location_ids = {location.location_id for location in document.locations}

    errors.extend(_duplicate_issues(chapter_ids, "DUPLICATE_CHAPTER_ID", "chapters"))
    errors.extend(_duplicate_issues(chapter_orders, "DUPLICATE_CHAPTER_ORDER", "chapters.order"))
    errors.extend(_duplicate_issues(scene_ids, "DUPLICATE_SCENE_ID", "screenplay.scenes"))
    errors.extend(_duplicate_issues(scene_orders, "DUPLICATE_SCENE_ORDER", "screenplay.scenes.order"))

    if len(document.chapters) != document.metadata.source_chapter_count:
        errors.append(
            _issue(
                "SOURCE_CHAPTER_COUNT_MISMATCH",
                "metadata.source_chapter_count must match the number of chapters",
                "metadata.source_chapter_count",
            )
        )

    valid_chapter_ids = set(chapter_ids)
    for scene_index, scene in enumerate(document.screenplay.scenes):
        scene_path = f"screenplay.scenes[{scene_index}]"
        if not scene.source_chapters:
            errors.append(
                _issue(
                    "SCENE_SOURCE_CHAPTERS_EMPTY",
                    "scene must include at least one source chapter",
                    f"{scene_path}.source_chapters",
                )
            )
        for source_chapter in scene.source_chapters:
            if source_chapter not in valid_chapter_ids:
                errors.append(
                    _issue(
                        "UNKNOWN_SOURCE_CHAPTER",
                        f"scene references unknown chapter {source_chapter!r}",
                        f"{scene_path}.source_chapters",
                    )
                )

        block_orders = [block.order for block in scene.content_blocks]
        errors.extend(
            _duplicate_issues(
                block_orders,
                "DUPLICATE_BLOCK_ORDER",
                f"{scene_path}.content_blocks.order",
            )
        )
        block_ids = [block.block_id for block in scene.content_blocks]
        errors.extend(
            _duplicate_issues(block_ids, "DUPLICATE_BLOCK_ID", f"{scene_path}.content_blocks")
        )

        if document.characters:
            for block_index, block in enumerate(scene.content_blocks):
                if isinstance(block, DialogueBlock) and block.speaker not in character_ids:
                    errors.append(
                        _issue(
                            "UNKNOWN_SPEAKER",
                            f"dialogue references unknown speaker {block.speaker!r}",
                            f"{scene_path}.content_blocks[{block_index}].speaker",
                        )
                    )
            for character_id in scene.characters:
                if character_id not in character_ids:
                    errors.append(
                        _issue(
                            "UNKNOWN_SCENE_CHARACTER",
                            f"scene references unknown character {character_id!r}",
                            f"{scene_path}.characters",
                        )
                    )

        if document.locations and scene.location_id is not None and scene.location_id not in location_ids:
            errors.append(
                _issue(
                    "UNKNOWN_LOCATION",
                    f"scene references unknown location {scene.location_id!r}",
                    f"{scene_path}.location_id",
                )
            )

    return errors


def _validate_coverage(document: ScreenplayDraftDocument) -> list[ValidationErrorIssue]:
    errors: list[ValidationErrorIssue] = []
    if not document.chapters:
        errors.append(_issue("CHAPTERS_EMPTY", "document must include chapters", "chapters"))
    if not document.screenplay.scenes:
        errors.append(_issue("SCREENPLAY_EMPTY", "screenplay must include at least one scene", "screenplay.scenes"))

    for scene_index, scene in enumerate(document.screenplay.scenes):
        if not scene.content_blocks:
            errors.append(
                _issue(
                    "SCENE_CONTENT_BLOCKS_EMPTY",
                    "scene must include at least one content block",
                    f"screenplay.scenes[{scene_index}].content_blocks",
                )
            )
        elif not any(
            isinstance(block, (ActionBlock, DialogueBlock))
            for block in scene.content_blocks
        ):
            errors.append(
                _issue(
                    "SCENE_MISSING_ACTION_OR_DIALOGUE",
                    "scene must include at least one action or dialogue block",
                    f"screenplay.scenes[{scene_index}].content_blocks",
                )
            )

    covered_chapters = {
        source_chapter
        for scene in document.screenplay.scenes
        for source_chapter in scene.source_chapters
    }
    omitted_chapters = {
        source_chapter
        for change in document.adaptation_changes
        if change.type == "omitted"
        for source_chapter in change.source_chapters
    }
    for chapter in document.chapters:
        if chapter.chapter_id not in covered_chapters and chapter.chapter_id not in omitted_chapters:
            errors.append(
                _issue(
                    "CHAPTER_NOT_COVERED",
                    f"chapter {chapter.chapter_id!r} is neither covered by a scene nor marked omitted",
                    "chapters",
                )
            )

    return errors


def _duplicate_issues(values: list[Any], code: str, path: str) -> list[ValidationErrorIssue]:
    seen: set[Any] = set()
    duplicates: set[Any] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return [_issue(code, f"duplicate value {value!r}", path) for value in sorted(duplicates, key=str)]


def _pydantic_issues(exc: ValidationError) -> list[ValidationErrorIssue]:
    issues: list[ValidationErrorIssue] = []
    for error in exc.errors():
        path = ".".join(str(part) for part in error["loc"])
        issues.append(_issue("SCHEMA_VALIDATION_FAILED", str(error["msg"]), path or None))
    return issues


def _issue(code: str, message: str, path: str | None = None) -> ValidationErrorIssue:
    return ValidationErrorIssue(code=code, message=message, path=path)


def _report(
    *,
    yaml_parse_passed: bool,
    schema_validation_passed: bool,
    reference_validation_passed: bool,
    coverage_validation_passed: bool,
    errors: list[ValidationErrorIssue],
) -> ValidationReport:
    return ValidationReport(
        yaml_parse_passed=yaml_parse_passed,
        schema_validation_passed=schema_validation_passed,
        reference_validation_passed=reference_validation_passed,
        coverage_validation_passed=coverage_validation_passed,
        errors=errors,
    )


__all__ = [
    "MODULE_NAME",
    "validate_and_mark",
    "validate_document",
    "validate_yaml_text",
    "validate_yaml_text_and_mark",
]
