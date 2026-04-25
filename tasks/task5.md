# Task 5 — GitHub Client

**Previous task:** `tasks/task4.md`  
**Next task:** `tasks/task6.md`

---

## Goal

Build `app/github_client.py` — posts a comment to a GitHub issue when remediation completes. This is the only GitHub API call the system makes.

---

## Files to Create

```
app/github_client.py
tests/test_github_client.py
```

---

## Implementation

### app/github_client.py

```python
import os

import httpx

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "")


async def comment_on_issue(issue_number: int, body: str) -> dict:
    """
    Post a comment on a GitHub issue.
    Raises httpx.HTTPStatusError on non-2xx responses.
    """
    url = f"https://api.github.com/repos/{GITHUB_REPO}/issues/{issue_number}/comments"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(url, headers=headers, json={"body": body})
        response.raise_for_status()
        return response.json()
```

### tests/test_github_client.py

Note: Tests use `monkeypatch.setattr` (not `monkeypatch.setenv`) because `GITHUB_TOKEN` and `GITHUB_REPO` are loaded as **module-level** variables at import time. Changing `os.environ` after import has no effect on the already-bound module variables.

```python
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

        await comment_on_issue(1, "✅ PR opened at https://github.com/u/r/pull/5")

    import json
    request_body = json.loads(route.calls[0].request.content)
    assert request_body["body"] == "✅ PR opened at https://github.com/u/r/pull/5"
```

---

## Acceptance Criteria

- [ ] `comment_on_issue()` POSTs to `https://api.github.com/repos/{GITHUB_REPO}/issues/{number}/comments`
- [ ] Authorization header uses `Bearer` token format
- [ ] Returns the parsed response JSON on success (201)
- [ ] Raises `httpx.HTTPStatusError` on non-2xx response
- [ ] Request body contains `{"body": <comment_text>}`
- [ ] `pytest tests/test_github_client.py` passes (4 tests)

**Do not proceed to Task 6 until every item above is confirmed.**
