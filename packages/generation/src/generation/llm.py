"""LLM client protocol and deterministic test double."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, cast

from .prompts import (
    STAGE_REPAIR,
    STAGE_SCENE_CONTENT,
    STAGE_SCENE_PLANNING,
    STAGE_SUMMARIZING,
    STRUCTURED_INPUT_BEGIN,
    STRUCTURED_INPUT_END,
)


class LLMClient(Protocol):
    """Minimal completion protocol used by generation stages."""

    def complete(self, *, system: str, user: str) -> str:
        """Return a raw JSON string for the given system and user prompts."""


@dataclass(frozen=True)
class FakeLLMCall:
    """A recorded fake-client call."""

    stage: str
    system: str
    user: str


class FakeLLMClient:
    """Deterministic LLM test double.

    Optional queued ``responses`` are consumed per stage. When no queued
    response exists, the fake derives a valid DTO JSON object from the prompt
    payload, which keeps end-to-end tests fully deterministic.
    """

    def __init__(self, responses: Mapping[str, Sequence[str]] | None = None) -> None:
        self._responses = {
            stage: list(stage_responses)
            for stage, stage_responses in (responses or {}).items()
        }
        self.calls: list[FakeLLMCall] = []

    def complete(self, *, system: str, user: str) -> str:
        stage = _detect_stage(system)
        self.calls.append(FakeLLMCall(stage=stage, system=system, user=user))
        queued_responses = self._responses.get(stage)
        if queued_responses:
            return queued_responses.pop(0)
        return _default_response(stage, user)


_STAGE_RE = re.compile(r"^STAGE:(?P<stage>[a-z_]+)$", re.MULTILINE)


def _detect_stage(system: str) -> str:
    match = _STAGE_RE.search(system)
    if match is None:
        return "unknown"
    return match.group("stage")


def _default_response(stage: str, user: str) -> str:
    if stage == STAGE_SUMMARIZING:
        return _default_chapter_summary(user)
    if stage == STAGE_SCENE_PLANNING:
        return _default_scene_plan(user)
    if stage == STAGE_SCENE_CONTENT:
        return _default_scene_content(user)
    if stage == STAGE_REPAIR:
        return _json({"fixed": False, "reason": "No preset repair response.", "result": None})
    return _json({})


def _default_chapter_summary(user: str) -> str:
    payload = _extract_payload(user)
    chapter_id = str(payload.get("chapter_id", "ch-1"))
    title = str(payload.get("title", "Chapter"))
    return _json(
        {
            "chapter_id": chapter_id,
            "title": title,
            "summary": f"{title} is condensed into a screenplay-ready beat.",
            "key_events": [
                {
                    "text": f"The central event of {title} moves the adaptation forward.",
                    "importance": "high",
                }
            ],
            "characters_mentioned": ["Alice"],
            "locations_mentioned": ["Main location"],
            "open_questions": [],
        }
    )


def _default_scene_plan(user: str) -> str:
    payload = _extract_payload(user)
    summaries = _as_dict_list(payload.get("chapter_summaries", []))
    chapter_ids = [
        str(summary.get("chapter_id", f"ch-{index}"))
        for index, summary in enumerate(summaries, start=1)
    ]
    summary_text = " ".join(str(summary.get("summary", "")) for summary in summaries).strip()
    return _json(
        {
            "scenes": [
                {
                    "title": "Opening Adaptation",
                    "source_chapters": chapter_ids,
                    "location_name": "Main location",
                    "time": "Day",
                    "characters": ["Alice"],
                    "dramatic_goal": "Convert the source beats into playable drama.",
                    "conflict": "The protagonist faces rising pressure.",
                    "summary": summary_text or "The confirmed chapters become one scene.",
                }
            ]
        }
    )


def _default_scene_content(user: str) -> str:
    payload = _extract_payload(user)
    scene_id = str(payload.get("scene_id", "sc-001"))
    plan_item = payload.get("plan_item", {})
    if not isinstance(plan_item, dict):
        plan_item = {}
    title = str(plan_item.get("title", "the scene"))
    return _json(
        {
            "scene_id": scene_id,
            "content_blocks": [
                {
                    "type": "action",
                    "text": f"The scene begins with the pressure of {title}.",
                },
                {
                    "type": "dialogue",
                    "speaker_name": "Alice",
                    "line": "We have to decide what this moment means.",
                    "emotion": "focused",
                    "action_hint": "holds her ground",
                },
            ],
            "adaptation_notes": ["Condensed chapter-level source material."],
            "quality_flags": [],
        }
    )


def _extract_payload(user: str) -> dict[str, Any]:
    raw_payload = _between(user, STRUCTURED_INPUT_BEGIN, STRUCTURED_INPUT_END)
    if raw_payload is None:
        return {}
    loaded = json.loads(raw_payload)
    if not isinstance(loaded, dict):
        return {}
    return cast(dict[str, Any], loaded)


def _between(text: str, begin: str, end: str) -> str | None:
    start = text.find(begin)
    if start == -1:
        return None
    start += len(begin)
    stop = text.find(end, start)
    if stop == -1:
        return None
    return text[start:stop].strip()


def _as_dict_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [cast(dict[str, Any], item) for item in value if isinstance(item, dict)]


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


__all__ = [
    "FakeLLMCall",
    "FakeLLMClient",
    "LLMClient",
]
