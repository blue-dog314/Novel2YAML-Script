"""Internal-only validation factory.

This module is deliberately NOT re-exported from ``shared_types/__init__.py``.
Only the validators layer should import ``mark_validated`` (via
``shared_types.internal``) so that generation, exporter, and api layers do not
mint a ``ValidatedScreenplay``. This is a convention-level boundary, not a hard
guarantee: any code that imports this module can call it.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .screenplay_document import EmbeddedValidation, ScreenplayDraftDocument
from .validated import ValidatedScreenplay
from .validation import ValidationReport


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def mark_validated(
    doc: ScreenplayDraftDocument, report: ValidationReport
) -> ValidatedScreenplay:
    """Wrap a draft document as a ``ValidatedScreenplay`` after a guard.

    Raises ``ValueError`` unless every relevant layer of ``report`` passed.
    ``coverage_validation_passed`` of ``None`` is treated as a pass because
    P0a-lite-1 does not gate on coverage.

    On success the document's embedded ``validation`` block is rewritten
    (``passed=True``, ``validated_at`` set) via ``model_copy`` of that single
    sub-field; the full tree is not re-dumped or re-validated.
    """
    coverage_ok = (
        report.coverage_validation_passed is None
        or report.coverage_validation_passed is True
    )
    all_passed = (
        report.yaml_parse_passed
        and report.schema_validation_passed
        and report.reference_validation_passed
        and coverage_ok
        and len(report.errors) == 0
    )
    if not all_passed:
        raise ValueError(
            "mark_validated: cannot mark a document whose validation report "
            "did not pass"
        )

    updated_doc = doc.model_copy(
        update={
            "validation": EmbeddedValidation(
                schema_version=doc.validation.schema_version,
                validated_at=_utc_now_iso(),
                passed=True,
            )
        }
    )
    return ValidatedScreenplay(document=updated_doc, report=report)
