import httpx
import pytest
import respx

from app.github_client import comment_on_issue


@pytest.mark.asyncio
async def test_comment_posts_to_correct_url(monkeypatch):
    monkeypatch.setattr("app.github_client.GITHUB_TOKEN", "test-token")
    monkeypatch.setattr("app.github_client.GITHUB_REPO", "testuser/superset")

    with respx.mock:
        route = respx.post(
            "https://api.github.com/repos/testuser/superset/issues/3/comments"
        ).mock(return_value=httpx.Response(201, json={"id": 999, "body": "PR opened!"}))

        result = await comment_on_issue(3, "PR opened!")

    assert route.called
    assert result["id"] == 999


@pytest.mark.asyncio
async def test_comment_raises_on_non_2xx(monkeypatch):
    monkeypatch.setattr("app.github_client.GITHUB_TOKEN", "test-token")
    monkeypatch.setattr("app.github_client.GITHUB_REPO", "testuser/superset")

    with respx.mock:
        respx.post(
            "https://api.github.com/repos/testuser/superset/issues/3/comments"
        ).mock(return_value=httpx.Response(401, json={"message": "Unauthorized"}))

        with pytest.raises(httpx.HTTPStatusError):
            await comment_on_issue(3, "PR opened!")


@pytest.mark.asyncio
async def test_comment_uses_bearer_auth(monkeypatch):
    monkeypatch.setattr("app.github_client.GITHUB_TOKEN", "my-secret-token")
    monkeypatch.setattr("app.github_client.GITHUB_REPO", "testuser/superset")

    with respx.mock:
        route = respx.post(
            "https://api.github.com/repos/testuser/superset/issues/1/comments"
        ).mock(return_value=httpx.Response(201, json={"id": 1}))

        await comment_on_issue(1, "hello")

    request = route.calls[0].request
    assert "Bearer my-secret-token" in request.headers["Authorization"]


@pytest.mark.asyncio
async def test_comment_sends_correct_body(monkeypatch):
    monkeypatch.setattr("app.github_client.GITHUB_TOKEN", "test-token")
    monkeypatch.setattr("app.github_client.GITHUB_REPO", "testuser/superset")

    with respx.mock:
        route = respx.post(
            "https://api.github.com/repos/testuser/superset/issues/1/comments"
        ).mock(return_value=httpx.Response(201, json={"id": 1}))

        await comment_on_issue(1, "PR opened at https://github.com/u/r/pull/5")

    import json
    request_body = json.loads(route.calls[0].request.content)
    assert request_body["body"] == "PR opened at https://github.com/u/r/pull/5"
