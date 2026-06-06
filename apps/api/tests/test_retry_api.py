"""Retry endpoint tests for resuming failed jobs from their last stage."""

from __future__ import annotations

from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient
from generation import FakeLLMClient

from conftest import create_confirmed_project


def _app(client: TestClient) -> FastAPI:
    return cast(FastAPI, client.app)


def test_retry_unknown_job_returns_404(client: TestClient) -> None:
    response = client.post("/jobs/job-does-not-exist/retry")

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found."


def test_retry_succeeded_job_returns_409(client: TestClient) -> None:
    project_id = create_confirmed_project(client)
    generate_response = client.post("/screenplays/generate", json={"project_id": project_id})
    job = generate_response.json()
    assert job["status"] == "succeeded"

    response = client.post(f"/jobs/{job['job_id']}/retry")

    assert response.status_code == 409


def test_retry_non_retryable_failure_returns_409(client: TestClient) -> None:
    # Fewer than three chapters triggers chapter_count_insufficient, which is
    # not retryable.
    project_id = create_confirmed_project(client, chapter_count=2)
    generate_response = client.post("/screenplays/generate", json={"project_id": project_id})
    job = generate_response.json()
    assert job["status"] == "failed"
    assert job["error"]["retryable"] is False

    response = client.post(f"/jobs/{job['job_id']}/retry")

    assert response.status_code == 409
    assert response.json()["detail"] == job["error"]["suggested_action"]


def test_retry_resumes_from_last_completed_stage(client: TestClient) -> None:
    # Force a failure during scene content generation so chapter summaries and
    # the scene plan are completed and cached on the failed job.
    _app(client).state.llm_client = FakeLLMClient(
        responses={
            "scene_content_generation": ['{"scene_id": "sc-001"}'],
            "repair": ['{"fixed": false, "reason": "no fix", "result": null}'],
        }
    )
    project_id = create_confirmed_project(client)

    generate_response = client.post("/screenplays/generate", json={"project_id": project_id})
    failed_job = generate_response.json()
    assert failed_job["status"] == "failed"
    assert failed_job["error"]["failed_stage"] == "scene_content_generation"

    # Swap in a healthy client and retry; cached early stages must not be re-run.
    healthy_llm = FakeLLMClient()
    _app(client).state.llm_client = healthy_llm

    retry_response = client.post(f"/jobs/{failed_job['job_id']}/retry")

    assert retry_response.status_code == 200
    retried_job = retry_response.json()
    assert retried_job["status"] == "succeeded"
    assert retried_job["screenplay_id"] is not None
    assert retried_job["error"] is None
    assert retried_job["job_id"] == failed_job["job_id"]

    stages = [call.stage for call in healthy_llm.calls]
    assert "summarizing" not in stages
    assert "scene_planning" not in stages
    assert "scene_content_generation" in stages

    artifacts_response = client.get(f"/screenplays/{retried_job['screenplay_id']}/artifacts")
    assert artifacts_response.status_code == 200
    assert artifacts_response.json()["validation_report"]["errors"] == []
