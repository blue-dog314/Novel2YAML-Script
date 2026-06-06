"""Project endpoint tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_create_project_requires_rights_confirmation(client: TestClient) -> None:
    response = client.post(
        "/projects",
        json={
            "title": "测试小说",
            "original_author": "作者",
            "rights_confirmed": False,
            "chapters": [{"title": "第一章", "text": "正文"}],
        },
    )

    assert response.status_code == 403


def test_chapter_listing_hides_source_text(client: TestClient) -> None:
    response = client.post(
        "/projects",
        json={
            "title": "测试小说",
            "original_author": "作者",
            "language": "zh",
            "rights_confirmed": True,
            "chapters": [{"title": "第一章", "text": "不要在列表返回原文"}],
        },
    )
    assert response.status_code == 201
    project_id = response.json()["project_id"]

    chapters_response = client.get(f"/projects/{project_id}/chapters")

    assert chapters_response.status_code == 200
    payload = chapters_response.json()
    assert payload["chapters"][0]["char_count"] == len("不要在列表返回原文")
    assert "text" not in payload["chapters"][0]


def test_confirm_chapters_is_idempotent(client: TestClient) -> None:
    create_response = client.post(
        "/projects",
        json={
            "title": "测试小说",
            "original_author": "作者",
            "rights_confirmed": True,
            "chapters": [{"title": "第一章", "text": "正文"}],
        },
    )
    project_id = create_response.json()["project_id"]

    first = client.post(f"/projects/{project_id}/chapters/confirm")
    second = client.post(f"/projects/{project_id}/chapters/confirm")

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["chapters_confirmed"] is True


def test_generation_notice_summarizes_cost_and_risks(client: TestClient) -> None:
    create_response = client.post(
        "/projects",
        json={
            "title": "测试小说",
            "original_author": "作者",
            "language": "zh",
            "rights_confirmed": True,
            "chapters": [
                {"title": "第一章", "text": "正文一"},
                {"title": "第二章", "text": "正文二二"},
                {"title": "第三章", "text": "正文三三三"},
            ],
        },
    )
    project_id = create_response.json()["project_id"]

    notice_response = client.get(f"/projects/{project_id}/generation-notice")

    assert notice_response.status_code == 200
    notice = notice_response.json()
    assert notice["project_id"] == project_id
    assert notice["chapter_count"] == 3
    assert notice["total_char_count"] == len("正文一正文二二正文三三三")
    assert notice["estimated_scene_count"] == 6
    assert "provider pricing" in notice["cost_notice"]
    assert any("Confirm chapters" in item for item in notice["risk_notice"])


def test_unknown_project_returns_404(client: TestClient) -> None:
    response = client.get("/projects/missing/chapters")

    assert response.status_code == 404


def test_delete_project_removes_project_and_artifacts(client: TestClient) -> None:
    from conftest import create_confirmed_project

    project_id = create_confirmed_project(client)
    generate_response = client.post("/screenplays/generate", json={"project_id": project_id})
    assert generate_response.status_code == 201
    screenplay_id = generate_response.json()["screenplay_id"]
    assert screenplay_id is not None

    delete_response = client.delete(f"/projects/{project_id}")

    assert delete_response.status_code == 204
    # Project, its chapters/source text, and the generated screenplay are all gone.
    assert client.get(f"/projects/{project_id}/chapters").status_code == 404
    assert client.get(f"/screenplays/{screenplay_id}/artifacts").status_code == 404


def test_delete_unknown_project_returns_404(client: TestClient) -> None:
    response = client.delete("/projects/missing")

    assert response.status_code == 404
