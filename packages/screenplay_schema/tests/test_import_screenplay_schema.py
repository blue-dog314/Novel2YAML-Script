"""Contract tests for the packaged screenplay JSON Schema."""

from __future__ import annotations

import json
from importlib.resources import files

import screenplay_schema
from shared_types import SCREENPLAY_SCHEMA_VERSION, ScreenplayDraftDocument


EXPECTED_TOP_LEVEL_REQUIRED = [
    "metadata",
    "adaptation_config",
    "screenplay",
    "validation",
]

EXPECTED_TOP_LEVEL_PROPERTIES = [
    "metadata",
    "adaptation_config",
    "chapters",
    "characters",
    "locations",
    "screenplay",
    "timeline",
    "adaptation_changes",
    "validation",
    "revision_notes",
]


def test_module_name() -> None:
    assert screenplay_schema.MODULE_NAME == "screenplay_schema"


def test_packaged_schema_matches_generated_schema() -> None:
    assert screenplay_schema.get_screenplay_schema() == screenplay_schema.get_generated_screenplay_schema()


def test_schema_identity_and_version() -> None:
    schema = screenplay_schema.get_screenplay_schema()
    assert schema["$id"] == screenplay_schema.SCHEMA_ID
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["x-schema-version"] == SCREENPLAY_SCHEMA_VERSION


def test_top_level_schema_contract() -> None:
    schema = screenplay_schema.get_screenplay_schema()
    assert schema["additionalProperties"] is False
    assert schema["required"] == EXPECTED_TOP_LEVEL_REQUIRED
    assert list(schema["properties"]) == EXPECTED_TOP_LEVEL_PROPERTIES


def test_schema_matches_shared_types_json_schema() -> None:
    generated = ScreenplayDraftDocument.model_json_schema()
    generated["$id"] = screenplay_schema.SCHEMA_ID
    generated["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    generated["x-schema-version"] = SCREENPLAY_SCHEMA_VERSION
    assert screenplay_schema.get_screenplay_schema() == generated


def test_key_enums_are_present() -> None:
    defs = screenplay_schema.get_screenplay_schema()["$defs"]
    assert defs["KeyEvent"]["properties"]["status"]["enum"] == [
        "adapted",
        "partially_adapted",
        "merged",
        "omitted",
        "pending_review",
    ]
    assert defs["AdaptationChange"]["properties"]["type"]["enum"] == [
        "merged",
        "omitted",
        "added",
        "reordered",
        "compressed",
        "expanded",
        "changed_pov",
    ]


def test_source_chapter_count_minimum_is_present() -> None:
    defs = screenplay_schema.get_screenplay_schema()["$defs"]
    assert defs["Metadata"]["properties"]["source_chapter_count"]["minimum"] == 3


def test_static_schema_file_is_valid_json() -> None:
    schema_path = files(screenplay_schema).joinpath(screenplay_schema.SCHEMA_FILENAME)
    assert json.loads(schema_path.read_text(encoding="utf-8")) == screenplay_schema.get_screenplay_schema()


def test_schema_doc_mentions_runtime_validator_boundary() -> None:
    doc_path = files(screenplay_schema).joinpath(screenplay_schema.SCHEMA_DOC_FILENAME)
    doc = doc_path.read_text(encoding="utf-8")
    assert "Runtime validators" in doc
    assert "source_chapter_count >= 3" in doc
