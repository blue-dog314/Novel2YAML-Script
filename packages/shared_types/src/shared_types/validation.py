"""Structured validation report contract.

Mirrors REVIEW_SUGGESTIONS.md section 4 and SKILL.md section 8. Issues are split
by severity into distinct types so that ``errors`` can only hold error-severity
issues and ``warnings`` can only hold warning-severity issues at the type level.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from ._config import FORBID_EXTRA_CONFIG

ValidationIssueSeverity = Literal["error", "warning"]


class ValidationErrorIssue(BaseModel):
    """An error-severity validation issue."""

    model_config = FORBID_EXTRA_CONFIG

    code: str
    message: str
    path: str | None = None
    severity: Literal["error"] = "error"


class ValidationWarningIssue(BaseModel):
    """A warning-severity validation issue."""

    model_config = FORBID_EXTRA_CONFIG

    code: str
    message: str
    path: str | None = None
    severity: Literal["warning"] = "warning"


class ValidationReport(BaseModel):
    """Result of running the deterministic validation layers.

    ``coverage_validation_passed`` defaults to ``None`` because P0a-lite-1 does
    not gate on coverage; ``None`` means "not evaluated", which is treated as a
    pass by the branding guard.
    """

    model_config = FORBID_EXTRA_CONFIG

    yaml_parse_passed: bool
    schema_validation_passed: bool
    reference_validation_passed: bool
    coverage_validation_passed: bool | None = None
    errors: list[ValidationErrorIssue] = []
    warnings: list[ValidationWarningIssue] = []
    suggested_fixes: list[str] = []
