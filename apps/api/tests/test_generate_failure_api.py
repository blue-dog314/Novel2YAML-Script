"""Job and artifact negative tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_unknown_job_returns_404(client: TestClient) -> None:
    response = client.get("/jobs/missing")

    assert response.status_code == 404


def test_unknown_screenplay_returns_404(client: TestClient) -> None:
    response = client.get("/screenplays/missing/artifacts")

    assert response.status_code == 404


def test_generate_unknown_project_returns_404(client: TestClient) -> None:
    response = client.post("/screenplays/generate", json={"project_id": "missing"})

    assert response.status_code == 404
