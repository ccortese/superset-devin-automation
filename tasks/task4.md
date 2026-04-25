# Task 4 — Devin API Client

**Previous task:** `tasks/task3.md`  
**Next task:** `tasks/task5.md`

---

## Goal

Build `app/devin_client.py` — wraps the Devin API for session creation, status polling, and analytics. Includes the background monitor loop that polls until a session reaches a terminal state.

Devin API reference: https://docs.devin.ai/api-reference/overview

---

## Files to Create

```
app/devin_client.py
tests/test_devin_client.py
```

---

## Implementation

### app/devin_client.py

```python
import asyncio
import os
import re

import httpx

from app import store

DEVIN_BASE_URL = os.getenv("DEVIN_BASE_URL", "https://api.devin.ai/v1")
DEVIN_API_KEY = os.getenv("DEVIN_API_KEY", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "")

# Devin session states that indicate the session has finished (success or failure)
TERMINAL_STATES = {"finished", "stopped", "failed", "blocked", "cancelled"}

POLL_INTERVAL_SECONDS = 30
MAX_POLL_INTERVAL_SECONDS = 300  # 5 minutes


def _auth_headers() -> dict:
    return {
        "Authorization": f"Bearer {DEVIN_API_KEY}",
        "Content-Type": "application/json",
    }


def build_prompt(issue: dict) -> str:
    """Build the remediation prompt sent to Devin for a given GitHub issue."""
    return f"""You are a security engineer remediating a vulnerability in the Apache Superset repository.

## Repository
GitHub: {GITHUB_REPO}
Clone the repository if it is not already available to you.

## Issue #{issue['number']}: {issue['title']}

{issue['body']}

## Your Task
1. Locate the relevant file(s) in the codebase
2. Implement a fix that addresses the root cause without breaking existing functionality
3. Verify existing tests pass: pytest superset/tests/ -x -q
4. Open a pull request with:
   - Title: fix(security): {issue['title']}
   - Body: Closes #{issue['number']}. Describe what you changed and why.

Proceed immediately without asking for clarification.
"""


def extract_pr_url(session_data: dict) -> str | None:
    """
    Search all string fields in the session response for a GitHub PR URL.
    Returns the first match or None.
    Only matches /pull/ URLs — not /issues/.
    """
    text = str(session_data)
    match = re.search(r'https://github\.com/[^/\s]+/[^/\s]+/pull/\d+', text)
    return match.group(0) if match else None


async def create_session(issue: dict) -> None:
    """
    Create a Devin session for the given issue, record it in the store,
    and spawn a background task to monitor it until completion.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{DEVIN_BASE_URL}/sessions",
            headers=_auth_headers(),
            json={
                "prompt": build_prompt(issue),
                "idempotency_key": f"issue-{issue['number']}",
            },
        )
        response.raise_for_status()
        data = response.json()

    session_id = data["session_id"]
    devin_url = data.get("url", "")

    store.add_session(
        session_id=session_id,
        issue_number=issue["number"],
        issue_title=issue["title"],
        issue_url=issue["html_url"],
        devin_url=devin_url,
    )
    store.log_event(
        "session_started",
        f"Devin session {session_id} created for issue #{issue['number']}",
        issue_number=issue["number"],
        session_id=session_id,
    )

    asyncio.create_task(_monitor_session(session_id, issue["number"]))


async def get_session(session_id: str) -> dict:
    """Fetch full session details from the Devin API."""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"{DEVIN_BASE_URL}/sessions/{session_id}",
            headers=_auth_headers(),
        )
        response.raise_for_status()
        return response.json()


async def get_analytics() -> dict:
    """
    Fetch session analytics from the Devin Analytics API.
    Returns an empty dict on any failure — callers must handle missing keys gracefully.
    """
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{DEVIN_BASE_URL}/analytics/sessions",
                headers=_auth_headers(),
            )
            if response.status_code == 200:
                return response.json()
    except Exception:
        pass
    return {}


async def _monitor_session(session_id: str, issue_number: int) -> None:
    """
    Internal background task. Polls the Devin session every POLL_INTERVAL_SECONDS
    until it reaches a terminal state. Uses exponential backoff capped at
    MAX_POLL_INTERVAL_SECONDS. On completion, updates the store and posts a
    GitHub comment with the PR link (or failure notice).
    """
    from app.github_client import comment_on_issue  # imported here to avoid circular import

    backoff = POLL_INTERVAL_SECONDS

    while True:
        try:
            data = await get_session(session_id)
            status = data.get("status", "unknown")

            if status in TERMINAL_STATES:
                pr_url = extract_pr_url(data)
                session_url = data.get("url", session_id)

                if pr_url:
                    store.update_session(session_id, status="finished", pr_url=pr_url)
                    store.log_event(
                        "pr_opened",
                        f"PR opened: {pr_url}",
                        session_id=session_id,
                        issue_number=issue_number,
                    )
                    msg = (
                        f"✅ Devin has remediated this issue.\n\n"
                        f"**Pull Request:** {pr_url}\n"
                        f"**Session:** {session_url}"
                    )
                else:
                    store.update_session(session_id, status="failed")
                    store.log_event(
                        "session_failed",
                        f"Session {session_id} ended with status '{status}' — no PR found",
                        session_id=session_id,
                        issue_number=issue_number,
                    )
                    msg = (
                        f"⚠️ Devin session ended with status `{status}` "
                        f"but no pull request was found.\n\n"
                        f"**Session:** {session_url}"
                    )

                await comment_on_issue(issue_number, msg)
                return

            await asyncio.sleep(backoff)
            backoff = min(backoff * 1.5, MAX_POLL_INTERVAL_SECONDS)

        except Exception as e:
            store.log_event(
                "error",
                f"Poll error for session {session_id}: {e}",
                session_id=session_id,
            )
            await asyncio.sleep(60)
```

### tests/test_devin_client.py

```python
import httpx
import pytest
import respx

from app import store
from app.devin_client import (
    DEVIN_BASE_URL,
    build_prompt,
    extract_pr_url,
    get_analytics,
    get_session,
)


def test_extract_pr_url_found():
    data = {"output": "Done! See PR at https://github.com/user/superset/pull/42 for details."}
    assert extract_pr_url(data) == "https://github.com/user/superset/pull/42"


def test_extract_pr_url_not_found():
    data = {"output": "Session completed but no pull request was opened."}
    assert extract_pr_url(data) is None


def test_extract_pr_url_does_not_match_issues_url():
    data = {"output": "See https://github.com/user/superset/issues/1 for context."}
    assert extract_pr_url(data) is None


def test_build_prompt_contains_issue_number_and_title():
    issue = {"number": 5, "title": "MD5 weak hashing", "body": "Replace MD5 with SHA-256."}
    prompt = build_prompt(issue)
    assert "Issue #5" in prompt
    assert "MD5 weak hashing" in prompt


def test_build_prompt_contains_issue_body():
    issue = {"number": 1, "title": "Test", "body": "Replace MD5 with SHA-256."}
    prompt = build_prompt(issue)
    assert "Replace MD5 with SHA-256." in prompt


def test_build_prompt_instructs_no_clarification():
    issue = {"number": 1, "title": "Test", "body": "Body"}
    prompt = build_prompt(issue)
    assert "without asking for clarification" in prompt


@pytest.mark.asyncio
async def test_get_session_returns_parsed_json():
    with respx.mock:
        respx.get(f"{DEVIN_BASE_URL}/sessions/abc123").mock(
            return_value=httpx.Response(200, json={"session_id": "abc123", "status": "running"})
        )
        result = await get_session("abc123")
    assert result["session_id"] == "abc123"
    assert result["status"] == "running"


@pytest.mark.asyncio
async def test_get_analytics_returns_data_on_success():
    with respx.mock:
        respx.get(f"{DEVIN_BASE_URL}/analytics/sessions").mock(
            return_value=httpx.Response(200, json={"total": 5, "completed": 4})
        )
        result = await get_analytics()
    assert result["total"] == 5


@pytest.mark.asyncio
async def test_get_analytics_returns_empty_dict_on_http_error():
    with respx.mock:
        respx.get(f"{DEVIN_BASE_URL}/analytics/sessions").mock(
            return_value=httpx.Response(500)
        )
        result = await get_analytics()
    assert result == {}


@pytest.mark.asyncio
async def test_get_analytics_returns_empty_dict_on_network_error():
    with respx.mock:
        respx.get(f"{DEVIN_BASE_URL}/analytics/sessions").mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        result = await get_analytics()
    assert result == {}
```

---

## Acceptance Criteria

- [ ] `extract_pr_url()` returns the PR URL when present in session data
- [ ] `extract_pr_url()` returns `None` when no PR URL found
- [ ] `extract_pr_url()` does not match `/issues/` URLs — only `/pull/`
- [ ] `build_prompt()` includes issue number, title, and body
- [ ] `build_prompt()` instructs Devin to proceed without asking for clarification
- [ ] `get_analytics()` returns an empty dict on HTTP 500 without raising
- [ ] `get_analytics()` returns an empty dict on network error without raising
- [ ] `pytest tests/test_devin_client.py` passes (10 tests)

**Do not proceed to Task 5 until every item above is confirmed.**
