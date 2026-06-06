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


def test_unknown_project_returns_404(client: TestClient) -> None:
    response = client.get("/projects/missing/chapters")

    assert response.status_code == 404
