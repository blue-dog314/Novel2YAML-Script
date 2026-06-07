"""LLM client protocol and deterministic test double."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from os import environ
from time import sleep
from typing import Any, Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .prompts import (
    SOURCE_TEXT_BEGIN,
    SOURCE_TEXT_END,
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


def resolve_actual_model(llm: LLMClient, requested_model: str) -> str:
    """Return the model the client will actually call, not the requested name.

    Real providers send their own configured model (``OPENAI_MODEL`` for the
    OpenAI-compatible client), so recording the caller-supplied ``request.model``
    in metadata would be misleading. When the client exposes a non-empty ``model``
    attribute, that authoritative value wins; otherwise the requested name (used
    by the deterministic fake) is kept.
    """
    actual = getattr(llm, "model", None)
    if isinstance(actual, str) and actual.strip():
        return actual
    return requested_model


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


@dataclass(frozen=True)
class OpenAICompatibleLLMClient:
    """HTTP client for OpenAI-compatible chat completions.

    The client intentionally uses the standard library so enabling a real
    provider does not add a package install step. Configure it with
    ``OPENAI_API_KEY`` and ``OPENAI_MODEL``; optional settings are
    ``OPENAI_BASE_URL``, ``OPENAI_TIMEOUT_SECONDS``, and ``OPENAI_MAX_RETRIES``.
    """

    api_key: str
    model: str
    base_url: str = "https://api.openai.com/v1"
    timeout_seconds: float = 60.0
    max_retries: int = 2

    @classmethod
    def from_env(cls) -> OpenAICompatibleLLMClient:
        """Build a client from environment variables."""
        api_key = environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY must be set for the OpenAI-compatible LLM provider.")
        model = environ.get("OPENAI_MODEL")
        if not model:
            raise RuntimeError("OPENAI_MODEL must be set for the OpenAI-compatible LLM provider.")
        return cls(
            api_key=api_key,
            model=model,
            base_url=environ.get("OPENAI_BASE_URL", cls.base_url),
            timeout_seconds=_env_float("OPENAI_TIMEOUT_SECONDS", cls.timeout_seconds),
            max_retries=_env_int("OPENAI_MAX_RETRIES", cls.max_retries),
        )

    def complete(self, *, system: str, user: str) -> str:
        """Return the assistant message content from a chat completion."""
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
        }
        request_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            request = Request(
                _chat_completions_url(self.base_url),
                data=request_body,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    raw_response = response.read().decode("utf-8")
                loaded = json.loads(raw_response)
                if not isinstance(loaded, dict):
                    raise RuntimeError("LLM provider response was not a JSON object.")
                return _extract_completion_content(cast(dict[str, Any], loaded))
            except HTTPError as exc:
                message = _http_error_message(exc)
                last_error = RuntimeError(message)
                if not _should_retry_http(exc.code) or attempt >= self.max_retries:
                    raise last_error from exc
            except (TimeoutError, URLError) as exc:
                last_error = RuntimeError(f"LLM provider request failed: {exc}")
                if attempt >= self.max_retries:
                    raise last_error from exc
            sleep(_retry_delay_seconds(attempt))
        if last_error is not None:
            raise last_error
        raise RuntimeError("LLM provider request failed without an error detail.")


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
    source_text = _extract_source_text(user)
    if _contains_cjk(title) or _contains_cjk(source_text):
        snippet = _snippet(source_text, fallback=title)
        return _json(
            {
                "chapter_id": chapter_id,
                "title": title,
                "summary": f"{title}\uff1a{snippet}",
                "key_events": [
                    {
                        "text": f"{title}\u7684\u6838\u5fc3\u4e8b\u4ef6\u63a8\u52a8\u6539\u7f16\u8fdb\u5165\u4e0b\u4e00\u4e2a\u620f\u5267\u8282\u70b9\u3002",
                        "importance": "high",
                    }
                ],
                "characters_mentioned": ["\u4e3b\u89d2"],
                "locations_mentioned": ["\u4e3b\u8981\u5730\u70b9"],
                "open_questions": [],
            }
        )
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
    if _summaries_contain_cjk(summaries):
        scenes = []
        for index, summary in enumerate(summaries, start=1):
            chapter_id = str(summary.get("chapter_id", f"ch-{index}"))
            title = str(summary.get("title", f"\u7b2c{index}\u7ae0"))
            summary_text = str(summary.get("summary", "")).strip()
            characters = _as_str_list(summary.get("characters_mentioned", [])) or ["\u4e3b\u89d2"]
            locations = _as_str_list(summary.get("locations_mentioned", []))
            scenes.append(
                {
                    "title": f"{title}\u6539\u7f16\u573a",
                    "source_chapters": [chapter_id],
                    "location_name": locations[0] if locations else "\u4e3b\u8981\u5730\u70b9",
                    "time": "\u672a\u6307\u5b9a",
                    "characters": characters,
                    "dramatic_goal": f"\u628a{title}\u7684\u5173\u952e\u60c5\u8282\u8f6c\u5316\u4e3a\u53ef\u8868\u6f14\u7684\u620f\u5267\u884c\u52a8\u3002",
                    "conflict": "\u4e3b\u89d2\u5728\u7ebf\u7d22\u3001\u538b\u529b\u4e0e\u9009\u62e9\u4e4b\u95f4\u88ab\u63a8\u5411\u4e0b\u4e00\u6b65\u3002",
                    "summary": summary_text or f"{title}\u7684\u6838\u5fc3\u60c5\u8282\u88ab\u89c4\u5212\u4e3a\u4e00\u573a\u620f\u3002",
                }
            )
        return _json({"scenes": scenes})
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
    if _contains_cjk(json.dumps(plan_item, ensure_ascii=False)):
        location = str(plan_item.get("location_name") or "\u4e3b\u8981\u5730\u70b9")
        characters = _as_str_list(plan_item.get("characters", []))
        speaker_name = characters[0] if characters else "\u4e3b\u89d2"
        return _json(
            {
                "scene_id": scene_id,
                "content_blocks": [
                    {
                        "type": "action",
                        "text": f"\u3010{title}\u3011\u5f00\u573a\uff1a{location}\u7684\u6c14\u6c1b\u88ab\u538b\u4f4e\uff0c\u89d2\u8272\u5e26\u7740\u5173\u952e\u7ebf\u7d22\u8d70\u5165\u573a\u666f\u3002",
                    },
                    {
                        "type": "action",
                        "text": "\u73af\u5883\u7ec6\u8282\u88ab\u653e\u5927\uff0c\u6bcf\u4e00\u4e2a\u52a8\u4f5c\u90fd\u5728\u628a\u51b2\u7a81\u63a8\u5411\u660e\u9762\u3002",
                    },
                    {
                        "type": "dialogue",
                        "speaker_name": speaker_name,
                        "line": "\u6211\u4eec\u4e0d\u80fd\u518d\u56de\u907f\u8fd9\u4e2a\u9009\u62e9\u4e86\u3002",
                        "emotion": "\u514b\u5236",
                        "action_hint": "\u770b\u5411\u5173\u952e\u7ebf\u7d22",
                    },
                ],
                "adaptation_notes": ["\u4fdd\u7559\u7ae0\u8282\u6838\u5fc3\u4e8b\u4ef6\uff0c\u6539\u5199\u4e3a\u53ef\u8868\u6f14\u7684\u573a\u9762\u52a8\u4f5c\u3002"],
                "quality_flags": [],
            }
        )
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


def _extract_source_text(user: str) -> str:
    # Source-text markers carry a per-request nonce suffix (SOURCE_TEXT_BEGIN:<nonce>),
    # so match on the stable prefix and recover the exact begin/end markers.
    start = user.find(SOURCE_TEXT_BEGIN)
    if start == -1:
        return ""
    line_end = user.find("\n", start)
    if line_end == -1:
        return ""
    begin_marker = user[start:line_end]
    nonce_suffix = begin_marker[len(SOURCE_TEXT_BEGIN) :]
    end_marker = f"{SOURCE_TEXT_END}{nonce_suffix}"
    return _between(user, begin_marker, end_marker) or ""


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


def _as_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= character <= "\u9fff" for character in text)


def _summaries_contain_cjk(summaries: list[dict[str, Any]]) -> bool:
    return any(_contains_cjk(json.dumps(summary, ensure_ascii=False)) for summary in summaries)


def _snippet(text: str, *, fallback: str, max_chars: int = 64) -> str:
    compact = " ".join(text.split())
    if not compact:
        return fallback
    for stop in ("\u3002", "\uff01", "\uff1f", ".", "!", "?"):
        index = compact.find(stop)
        if 0 <= index < max_chars:
            return compact[: index + 1]
    if len(compact) <= max_chars:
        return compact
    return f"{compact[: max_chars - 3]}..."


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _chat_completions_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/chat/completions"


def _extract_completion_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("LLM provider response did not include choices.")
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise RuntimeError("LLM provider choice was not an object.")
    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise RuntimeError("LLM provider choice did not include a message.")
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = [
            str(item.get("text", ""))
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        ]
        if text_parts:
            return "".join(text_parts)
    raise RuntimeError("LLM provider message content was not text.")


def _http_error_message(exc: HTTPError) -> str:
    body = _read_http_error_body(exc)
    if body:
        return f"LLM provider returned HTTP {exc.code}: {body}"
    return f"LLM provider returned HTTP {exc.code}."


def _read_http_error_body(exc: HTTPError) -> str:
    try:
        return exc.read().decode("utf-8", errors="replace")
    except Exception:
        return ""


def _should_retry_http(status_code: int) -> bool:
    return status_code in {408, 409, 429} or status_code >= 500


def _retry_delay_seconds(attempt: int) -> float:
    delay = 0.25 * (2.0**attempt)
    if delay > 2.0:
        return 2.0
    return delay


def _env_float(name: str, default: float) -> float:
    raw_value = environ.get(name)
    if raw_value is None:
        return default
    try:
        parsed = float(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a number.") from exc
    if parsed <= 0:
        raise RuntimeError(f"{name} must be greater than zero.")
    return parsed


def _env_int(name: str, default: int) -> int:
    raw_value = environ.get(name)
    if raw_value is None:
        return default
    try:
        parsed = int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer.") from exc
    if parsed < 0:
        raise RuntimeError(f"{name} must be zero or greater.")
    return parsed


__all__ = [
    "FakeLLMCall",
    "FakeLLMClient",
    "LLMClient",
    "OpenAICompatibleLLMClient",
]
