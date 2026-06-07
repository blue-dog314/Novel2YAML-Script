"""Static workbench mount tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_workbench_index_served(client: TestClient) -> None:
    response = client.get("/app/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert 'data-workbench="novel-to-screenplay"' in response.text


def test_workbench_vendor_vue_served(client: TestClient) -> None:
    response = client.get("/app/vendor/vue.global.js")

    assert response.status_code == 200
    # Must be the full build that bundles the in-browser template compiler,
    # NOT the runtime-only build: app.js uses a string `template` option, which
    # requires runtime compilation. The runtime-only build omits
    # ``compileToFunction``, so the page would silently fail to render. Asserting
    # on the symbol (rather than file size) is what actually distinguishes the
    # two builds.
    assert "compileToFunction" in response.text
