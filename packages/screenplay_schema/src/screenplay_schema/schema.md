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

## Validation boundary

JSON Schema covers required fields, types, enums, numeric ranges, and unknown-field rejection. Runtime validators remain responsible for reference and coverage checks such as valid `source_chapters`, duplicate orders, empty scenes, and chapter coverage.
