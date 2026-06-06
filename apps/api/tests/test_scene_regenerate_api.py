"""Scene-level regeneration endpoint tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from conftest import create_confirmed_project


def _generate_screenplay_id(client: TestClient) -> tuple[str, str]:
    project_id = create_confirmed_project(client)
    response = client.post("/screenplays/generate", json={"project_id": project_id})
    assert response.status_code == 201
    job = response.json()
    assert job["status"] == "succeeded"
    return project_id, str(job["screenplay_id"])


def test_regenerate_unknown_screenplay_returns_404(client: TestClient) -> None:
    response = client.post(
        "/screenplays/sp-does-not-exist/scenes/regenerate",
        json={"scene_id": "sc-001"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Screenplay not found."


def test_regenerate_unknown_scene_id_returns_404(client: TestClient) -> None:
    _, screenplay_id = _generate_screenplay_id(client)

    response = client.post(
        f"/screenplays/{screenplay_id}/scenes/regenerate",
        json={"scene_id": "sc-999"},
    )

    assert response.status_code == 404
    assert "sc-999" in response.json()["detail"]


def test_regenerate_produces_new_screenplay_and_keeps_old(client: TestClient) -> None:
    _, screenplay_id = _generate_screenplay_id(client)

    original = client.get(f"/screenplays/{screenplay_id}/artifacts").json()
    original_scenes = original["document"]["screenplay"]["scenes"]

    response = client.post(
        f"/screenplays/{screenplay_id}/scenes/regenerate",
        json={"scene_id": "sc-001"},
    )

    assert response.status_code == 201
    payload = response.json()
    new_screenplay_id = payload["screenplay_id"]
    assert new_screenplay_id != screenplay_id

    # The old screenplay is preserved and still retrievable.
    old_response = client.get(f"/screenplays/{screenplay_id}/artifacts")
    assert old_response.status_code == 200
    assert old_response.json()["screenplay_id"] == screenplay_id

    # The new screenplay keeps non-target scene ids/order intact.
    new_scenes = payload["document"]["screenplay"]["scenes"]
    assert len(new_scenes) == len(original_scenes)
    for original_scene, new_scene in zip(original_scenes, new_scenes):
        assert new_scene["scene_id"] == original_scene["scene_id"]
        assert new_scene["order"] == original_scene["order"]
    assert payload["validation_report"]["errors"] == []
