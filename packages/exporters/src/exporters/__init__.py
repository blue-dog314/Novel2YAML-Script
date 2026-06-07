"""YAML export helpers for screenplay draft documents."""

from __future__ import annotations

from io import StringIO
from typing import Any

from ruamel.yaml import YAML
from shared_types import ScreenplayDraftDocument, ValidationReport
from validators import validate_yaml_text

MODULE_NAME = "exporters"


def _to_serializable(document: ScreenplayDraftDocument) -> dict[str, Any]:
    return document.model_dump(mode="json", exclude_none=False)


def _represent_none(representer: Any, data: None) -> Any:
    return representer.represent_scalar("tag:yaml.org,2002:null", "null")


def _represent_str(representer: Any, data: str) -> Any:
    # Render multi-line text as an author-friendly literal block scalar (`|-`)
    # so embedded newlines are written as real indented lines instead of escaped
    # `\n` sequences. Short single-line strings keep the default scalar style.
    if "\n" in data:
        return representer.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return representer.represent_scalar("tag:yaml.org,2002:str", data)


def _make_yaml() -> YAML:
    yaml = YAML()
    yaml.allow_unicode = True
    setattr(yaml, "default_flow_style", False)
    setattr(yaml, "sort_base_mapping_type_on_output", False)
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.representer.add_representer(type(None), _represent_none)
    yaml.representer.add_representer(str, _represent_str)
    return yaml


def export_yaml(document: ScreenplayDraftDocument) -> str:
    """Serialize a screenplay draft document into author-friendly YAML."""
    stream = StringIO()
    _make_yaml().dump(_to_serializable(document), stream)
    return stream.getvalue()


def export_validated_yaml(document: ScreenplayDraftDocument) -> tuple[str, ValidationReport]:
    """Export YAML, re-parse it, and return the validation report when valid."""
    yaml_text = export_yaml(document)
    _, report = validate_yaml_text(yaml_text)
    if not (
        report.yaml_parse_passed
        and report.schema_validation_passed
        and report.reference_validation_passed
        and report.coverage_validation_passed is True
        and not report.errors
    ):
        raise ValueError("export_validated_yaml: exported YAML did not pass validation")
    return yaml_text, report


__all__ = [
    "MODULE_NAME",
    "export_validated_yaml",
    "export_yaml",
]
