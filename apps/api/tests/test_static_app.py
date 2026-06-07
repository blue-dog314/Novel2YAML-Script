"""Static workbench mount tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_workbench_index_served(client: TestClient) -> None:
    response = client.get("/app/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert 'data-workbench="novel-to-screenplay"' in response.text


def test_workbench_vendor_vue_served(client: TestClient) -> None:
    response = client.get("/app/vendor/vue.global.prod.js")

    assert response.status_code == 200
    assert len(response.content) > 1000
