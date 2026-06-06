"""Validated-screenplay wrapper.

``ValidatedScreenplay`` is the structure the validators layer returns once a
document has passed validation: it pairs a ``ScreenplayDraftDocument`` with the
``ValidationReport`` that cleared it. It lives in its own module so it can
reference both the document and report layers without import cycles.

This wrapper does NOT provide a runtime forgery guarantee. Any code that can
import it can construct it; the "validated" status is a type-level and
convention-level boundary, not a hard security guarantee.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .screenplay_document import ScreenplayDraftDocument
from .validation import ValidationReport


class ValidatedScreenplay(BaseModel):
    """An immutable snapshot of a document plus its passing validation report.

    ``frozen=True`` expresses that this is a post-validation snapshot; the
    wrapped ``document`` already carries ``validation.passed = True``. See the
    module docstring: this is a convention-level boundary, not a guarantee that
    the wrapper cannot be constructed by other code.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    document: ScreenplayDraftDocument
    report: ValidationReport
