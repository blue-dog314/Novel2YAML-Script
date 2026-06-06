"""Tests for the OpenAI-compatible LLM client."""

from __future__ import annotations

import json
from types import TracebackType
from typing import Any, cast
from urllib.error import URLError
from urllib.request import Request

import pytest

from generation import OpenAICompatibleLLMClient


class FakeHTTPResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def __enter__(self) -> FakeHTTPResponse:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def _completion(content: str) -> dict[str, Any]:
    return {"choices": [{"message": {"content": content}}]}


def test_openai_compatible_client_posts_chat_completion(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[Request] = []

    def fake_urlopen(request: Request, timeout: float) -> FakeHTTPResponse:
        requests.append(request)
        assert timeout == 12.0
        return FakeHTTPResponse(_completion('{"ok": true}'))

    monkeypatch.setattr("generation.llm.urlopen", fake_urlopen)

    client = OpenAICompatibleLLMClient(
        api_key="secret",
        model="test-model",
        base_url="https://provider.example/v1/",
        timeout_seconds=12.0,
        max_retries=0,
    )

    result = client.complete(system="system prompt", user="user prompt")

    assert result == '{"ok": true}'
    assert len(requests) == 1
    request = requests[0]
    assert request.full_url == "https://provider.example/v1/chat/completions"
    assert request.get_header("Authorization") == "Bearer secret"
    assert request.data is not None
    request_data = cast(bytes, request.data)
    body = json.loads(request_data.decode("utf-8"))
    assert body["model"] == "test-model"
    assert body["response_format"] == {"type": "json_object"}
    assert body["messages"] == [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "user prompt"},
    ]


def test_openai_compatible_client_retries_temporary_transport_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def fake_urlopen(request: Request, timeout: float) -> FakeHTTPResponse:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise URLError("temporary failure")
        return FakeHTTPResponse(_completion('{"fixed": true}'))

    monkeypatch.setattr("generation.llm.urlopen", fake_urlopen)
    monkeypatch.setattr("generation.llm.sleep", lambda seconds: None)

    client = OpenAICompatibleLLMClient(api_key="secret", model="test-model", max_retries=1)

    assert client.complete(system="system", user="user") == '{"fixed": true}'
    assert calls == 2


def test_openai_compatible_client_from_env_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_MODEL", "test-model")

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        OpenAICompatibleLLMClient.from_env()


def test_openai_compatible_client_from_env_reads_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://provider.example/v1")
    monkeypatch.setenv("OPENAI_TIMEOUT_SECONDS", "9.5")
    monkeypatch.setenv("OPENAI_MAX_RETRIES", "4")

    client = OpenAICompatibleLLMClient.from_env()

    assert client.api_key == "secret"
    assert client.model == "test-model"
    assert client.base_url == "https://provider.example/v1"
    assert client.timeout_seconds == 9.5
    assert client.max_retries == 4
