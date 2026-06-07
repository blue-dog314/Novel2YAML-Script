"""Scene-level regeneration endpoint tests."""

from __future__ import annotations

import json
from typing import Any, cast

from fastapi import FastAPI
from fastapi.testclient import TestClient
from generation import FakeLLMClient

from conftest import create_confirmed_project


def _app(client: TestClient) -> FastAPI:
    return cast(FastAPI, client.app)


def _three_scene_plan() -> str:
    chapter_ids = ["ch-1", "ch-2", "ch-3"]
    return json.dumps(
        {
            "scenes": [
                {
                    "title": f"Scene {n}",
                    "source_chapters": chapter_ids,
                    "location_name": "Main location",
                    "time": "Day",
                    "characters": ["Alice"],
                    "dramatic_goal": "Advance the drama.",
                    "conflict": "Rising pressure.",
                    "summary": f"Scene {n} summary.",
                }
                for n in (1, 2, 3)
            ]
        },
        sort_keys=True,
    )


def _scene_content(scene_id: str, text: str) -> str:
    return json.dumps(
        {
            "scene_id": scene_id,
            "content_blocks": [{"type": "action", "text": text}],
            "adaptation_notes": [],
            "quality_flags": [],
            "covered_key_events": [
                {
                    "key_event_id": f"ch-{order}-ev-001",
                    "fidelity_status": "faithful",
                    "covered_by_block_index": 1,
                }
                for order in (1, 2, 3)
            ],
        },
        sort_keys=True,
    )


def _action_texts(scene: dict[str, Any]) -> list[str]:
    return [block["text"] for block in scene["content_blocks"] if block["type"] == "action"]


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


def test_regenerate_only_target_scene_changes_multi_scene(client: TestClient) -> None:
    # Inject a 3-scene plan and per-scene content so the generated screenplay
    # has more than one scene. The same FakeLLMClient instance is reused across
    # the generate and regenerate requests; its scene_content queue is consumed
    # in order (3 calls during generate, 1 more during regenerate), so the
    # regenerated sc-002 gets a distinct, recognisable block.
    llm = FakeLLMClient(
        responses={
            "scene_planning": [_three_scene_plan()],
            "scene_content_generation": [
                _scene_content("sc-001", "Original scene one."),
                _scene_content("sc-002", "Original scene two."),
                _scene_content("sc-003", "Original scene three."),
                _scene_content("sc-002", "Regenerated scene two."),
            ],
        }
    )
    _app(client).state.llm_client = llm

    project_id = create_confirmed_project(client)
    generate_response = client.post("/screenplays/generate", json={"project_id": project_id})
    assert generate_response.status_code == 201
    job = generate_response.json()
    assert job["status"] == "succeeded"
    screenplay_id = str(job["screenplay_id"])

    original = client.get(f"/screenplays/{screenplay_id}/artifacts").json()
    original_scenes = original["document"]["screenplay"]["scenes"]
    assert len(original_scenes) == 3

    response = client.post(
        f"/screenplays/{screenplay_id}/scenes/regenerate",
        json={"scene_id": "sc-002"},
    )
    assert response.status_code == 201
    payload = response.json()
    new_screenplay_id = payload["screenplay_id"]
    assert new_screenplay_id != screenplay_id

    new_scenes = payload["document"]["screenplay"]["scenes"]
    assert len(new_scenes) == 3

    by_id = {scene["scene_id"]: scene for scene in new_scenes}
    original_by_id = {scene["scene_id"]: scene for scene in original_scenes}

    # Target scene content actually changed.
    assert _action_texts(original_by_id["sc-002"]) == ["Original scene two."]
    assert _action_texts(by_id["sc-002"]) == ["Regenerated scene two."]

    # Every non-target scene is byte-for-byte unchanged (content blocks too).
    for scene_id in ("sc-001", "sc-003"):
        assert by_id[scene_id]["order"] == original_by_id[scene_id]["order"]
        assert by_id[scene_id]["content_blocks"] == original_by_id[scene_id]["content_blocks"]

    # Scene ids/order preserved across the whole screenplay.
    assert [scene["scene_id"] for scene in new_scenes] == ["sc-001", "sc-002", "sc-003"]
    assert [scene["order"] for scene in new_scenes] == [1, 2, 3]

    # Old screenplay still retrievable and unchanged.
    old = client.get(f"/screenplays/{screenplay_id}/artifacts").json()
    assert old["screenplay_id"] == screenplay_id
    assert old["document"]["screenplay"]["scenes"] == original_scenes
    assert payload["validation_report"]["errors"] == []
