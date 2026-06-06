"""Tests for resume-able generation with typed intermediate artifacts."""

from __future__ import annotations

import json
from typing import Any

import pytest

from generation import (
    ChapterInput,
    FakeLLMClient,
    GenerationArtifacts,
    PipelineFailure,
    generate_screenplay_with_artifacts,
)

FIXED_NOW = "2026-06-06T00:00:00+00:00"


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("generation.assembly._now_iso", lambda: FIXED_NOW)


def _chapters() -> list[ChapterInput]:
    return [
        ChapterInput(
            chapter_id=f"ch-{index}",
            title=f"Chapter {index}",
            text=f"Source text for chapter {index}.",
        )
        for index in range(1, 4)
    ]


def _run(
    llm: FakeLLMClient,
    *,
    resume_from: GenerationArtifacts | None = None,
) -> tuple[Any, GenerationArtifacts]:
    return generate_screenplay_with_artifacts(
        chapters=_chapters(),
        project_id="proj-1",
        title="Test Novel",
        original_author="Author Name",
        language="en",
        model="fake-model",
        llm=llm,
        resume_from=resume_from,
    )


def _repair_response(result: dict[str, Any] | None, *, fixed: bool = True) -> str:
    return json.dumps(
        {
            "fixed": fixed,
            "reason": "fixed" if fixed else "not fixed",
            "result": result,
        },
        sort_keys=True,
    )


def test_with_artifacts_success_returns_full_artifacts() -> None:
    document, artifacts = _run(FakeLLMClient())

    assert document is not None
    assert artifacts.chapter_summaries is not None
    assert artifacts.scene_plan is not None
    assert artifacts.scene_contents is not None


def test_resume_skips_early_stages() -> None:
    _, seed = _run(FakeLLMClient())

    llm = FakeLLMClient()
    resume_from = GenerationArtifacts(
        chapter_summaries=seed.chapter_summaries,
        scene_plan=seed.scene_plan,
    )
    document, artifacts = _run(llm, resume_from=resume_from)

    stages = [call.stage for call in llm.calls]
    assert "summarizing" not in stages
    assert "scene_planning" not in stages
    assert stages == ["scene_content_generation"]
    assert document is not None
    assert artifacts.scene_contents is not None


def test_full_resume_makes_no_llm_calls() -> None:
    _, seed = _run(FakeLLMClient())

    llm = FakeLLMClient()
    resume_from = GenerationArtifacts(
        chapter_summaries=seed.chapter_summaries,
        scene_plan=seed.scene_plan,
        scene_contents=seed.scene_contents,
    )
    document, artifacts = _run(llm, resume_from=resume_from)

    assert llm.calls == []
    assert document is not None
    assert artifacts.scene_contents is not None


def test_failure_carries_completed_artifacts() -> None:
    llm = FakeLLMClient(
        responses={
            "scene_content_generation": ['{"scene_id": "sc-001"}'],
            "repair": [_repair_response(None, fixed=False)],
        }
    )

    with pytest.raises(PipelineFailure) as exc_info:
        _run(llm)

    exc = exc_info.value
    assert exc.artifacts is not None
    assert exc.artifacts.chapter_summaries is not None
    assert exc.artifacts.scene_plan is not None
    assert exc.artifacts.scene_contents is None
    assert exc.error.completed_artifacts == ["chapter_summaries", "scene_plan"]
