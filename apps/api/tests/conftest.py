"""Shared API test fixtures."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from api import create_app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(create_app()) as test_client:
        yield test_client


def create_confirmed_project(client: TestClient, *, chapter_count: int = 3) -> str:
    response = client.post(
        "/projects",
        json={
            "title": "测试小说",
            "original_author": "作者",
            "language": "zh",
            "rights_confirmed": True,
            "chapters": [
                {"title": f"第{index}章", "text": f"第{index}章正文。"}
                for index in range(1, chapter_count + 1)
            ],
        },
    )
    assert response.status_code == 201
    project_id = str(response.json()["project_id"])
    confirm_response = client.post(f"/projects/{project_id}/chapters/confirm")
    assert confirm_response.status_code == 200
    return project_id
