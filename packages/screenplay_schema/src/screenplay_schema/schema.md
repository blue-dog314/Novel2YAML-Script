# Screenplay YAML Schema

Version: `0.1.0`

This document summarizes the P0a-lite screenplay document schema. The authoritative machine-readable schema is packaged as `screenplay.schema.json` and is generated from `shared_types.ScreenplayDraftDocument`.

## Top-level fields

The screenplay document uses these required top-level fields:

1. `metadata`
2. `adaptation_config`
3. `chapters`
4. `characters`
5. `locations`
6. `screenplay`
7. `adaptation_changes`
8. `validation`
9. `revision_notes`

## Required metadata

`metadata` includes explicit version fields:

- `schema_version`
- `schema_doc_version`
- `generator_version`
- `prompt_version`

It also requires `source_chapter_count >= 3`.

## Screenplay body

`screenplay.scenes` contains ordered scenes. Each scene includes `source_chapters` and ordered `content_blocks`.

Supported content block types:

- `action`
- `dialogue`
- `voice_over`
- `note`

## Author editing guide

Recommended author edits:

- `screenplay.scenes[].title`
- `screenplay.scenes[].summary`
- `screenplay.scenes[].dramatic_goal`
- `screenplay.scenes[].conflict`
- `screenplay.scenes[].content_blocks[].text`
- `screenplay.scenes[].content_blocks[].line`
- `screenplay.scenes[].content_blocks[].emotion`
- `screenplay.scenes[].content_blocks[].action_hint`
- `screenplay.scenes[].adaptation_notes`
- `adaptation_changes[].description`
- `adaptation_changes[].reason`
- `revision_notes[].text`

Edit with care:

- IDs such as `chapter_id`, `scene_id`, `block_id`, `character_id`, and `location_id`
- order fields such as `chapters[].order`, `screenplay.scenes[].order`, and `content_blocks[].order`
- reference fields such as `source_chapters`, `characters`, `speaker`, `location_id`, and `affected_scenes`

Do not manually forge system-owned fields:

- `metadata.schema_version`
- `metadata.schema_doc_version`
- `metadata.generator_version`
- `metadata.prompt_version`
- `metadata.generated_at`
- `validation`

## Adaptation changes

Use `adaptation_changes` to explain meaningful author or generation edits that
change the source material:

- `merged`: multiple source beats were combined.
- `omitted`: source material was intentionally left out.
- `added`: new bridge or connective material was added.
- `reordered`: material appears in a different order.
- `compressed`: source material was shortened.
- `expanded`: source material was elaborated.
- `changed_pov`: point of view changed.

For all non-`added` changes, `source_chapters` must identify the source
chapters involved. `affected_scenes` must reference existing scenes when set.
An `omitted` chapter is valid only when its key events are marked `omitted` or
`merged`.

## Validation boundary

JSON Schema covers required fields, types, enums, numeric ranges, and unknown-field rejection. Runtime validators remain responsible for reference and coverage checks such as valid `source_chapters`, duplicate orders, empty scenes, and chapter coverage.
