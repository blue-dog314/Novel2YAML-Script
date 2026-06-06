"""Shared Pydantic model configuration.

This module is deliberately NOT re-exported from the public barrel (underscore
prefix). It holds the single ``extra="forbid"`` config reused by every contract
layer so a stray or misspelled field becomes a hard ``ValidationError`` rather
than a silent drop (SKILL.md sections 5/12).
"""

from __future__ import annotations

from pydantic import ConfigDict

FORBID_EXTRA_CONFIG = ConfigDict(extra="forbid")
