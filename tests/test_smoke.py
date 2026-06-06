"""Smoke test: verify shared_types can be imported and version constants are correct."""

import shared_types


def test_schema_version() -> None:
    assert shared_types.SCREENPLAY_SCHEMA_VERSION == "0.2.0"


def test_schema_doc_version() -> None:
    assert shared_types.SCREENPLAY_SCHEMA_DOC_VERSION == "0.2.0"


def test_generator_version() -> None:
    assert shared_types.SCREENPLAY_GENERATOR_VERSION == "0.2.0"


def test_prompt_version() -> None:
    assert shared_types.SCREENPLAY_PROMPT_VERSION == "0.1.0"
