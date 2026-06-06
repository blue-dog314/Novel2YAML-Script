"""Screenplay JSON Schema contract for the novel-to-screenplay MVP."""

from __future__ import annotations

import json
from copy import deepcopy
from importlib.resources import files
from typing import Any, cast

from shared_types import SCREENPLAY_SCHEMA_VERSION, ScreenplayDraftDocument

MODULE_NAME = "screenplay_schema"
SCHEMA_ID = "novel-to-screenplay.screenplay.schema.json"
SCHEMA_FILENAME = "screenplay.schema.json"
SCHEMA_DOC_FILENAME = "schema.md"


def build_screenplay_schema() -> dict[str, Any]:
    """Build the JSON Schema from the shared_types document contract."""
    schema = ScreenplayDraftDocument.model_json_schema()
    schema["$id"] = SCHEMA_ID
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["x-schema-version"] = SCREENPLAY_SCHEMA_VERSION
    return schema


def get_screenplay_schema() -> dict[str, Any]:
    """Return the packaged static JSON Schema."""
    schema_path = files(__package__).joinpath(SCHEMA_FILENAME)
    return cast(dict[str, Any], json.loads(schema_path.read_text(encoding="utf-8")))


def get_generated_screenplay_schema() -> dict[str, Any]:
    """Return a fresh schema generated from the current shared_types model."""
    return deepcopy(build_screenplay_schema())


__all__ = [
    "MODULE_NAME",
    "SCHEMA_DOC_FILENAME",
    "SCHEMA_FILENAME",
    "SCHEMA_ID",
    "build_screenplay_schema",
    "get_generated_screenplay_schema",
    "get_screenplay_schema",
]
