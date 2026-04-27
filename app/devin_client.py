import asyncio
import logging
import os
import re

import httpx

from app import store

logger = logging.getLogger(__name__)

DEVIN_BASE_URL = os.getenv("DEVIN_BASE_URL", "https://api.devin.ai/v1")
DEVIN_API_KEY = os.getenv("DEVIN_API_KEY", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "")

# Devin session states that indicate the session has finished (success or failure).
# The API may return the terminal state in either "status" or "status_enum".
TERMINAL_STATES = {"finished", "stopped", "failed", "blocked", "cancelled"}

POLL_INTERVAL_SECONDS = 30
MAX_POLL_INTERVAL_SECONDS = 300  # 5 minutes
MAX_CONSECUTIVE_ERRORS = 10


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
    try:
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
    except Exception as exc:
        logger.error("Failed to create Devin session for issue #%s: %s", issue["number"], exc)
        store.log_event(
            "error",
            f"Failed to create Devin session for issue #{issue['number']}: {exc}",
            issue_number=issue["number"],
        )
        return

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
    consecutive_errors = 0

    while True:
        try:
            data = await get_session(session_id)
            status = data.get("status_enum") or data.get("status") or "unknown"
            consecutive_errors = 0

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
                        f"Devin has remediated this issue.\n\n"
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
                        f"Devin session ended with status `{status}` "
                        f"but no pull request was found.\n\n"
                        f"**Session:** {session_url}"
                    )

                try:
                    await comment_on_issue(issue_number, msg)
                except Exception as exc:
                    logger.error("Failed to comment on issue #%s: %s", issue_number, exc)
                return

            await asyncio.sleep(backoff)
            backoff = min(backoff * 1.5, MAX_POLL_INTERVAL_SECONDS)

        except Exception as e:
            consecutive_errors += 1
            store.log_event(
                "error",
                f"Poll error for session {session_id}: {e}",
                session_id=session_id,
            )
            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                store.update_session(session_id, status="failed")
                store.log_event(
                    "session_failed",
                    f"Session {session_id} marked failed after {MAX_CONSECUTIVE_ERRORS} consecutive poll errors",
                    session_id=session_id,
                    issue_number=issue_number,
                )
                try:
                    await comment_on_issue(
                        issue_number,
                        f"Devin session failed after {MAX_CONSECUTIVE_ERRORS} consecutive poll errors.\n\n"
                        f"**Session:** {session_id}",
                    )
                except Exception:
                    logger.error("Failed to comment on issue #%s after poll error limit", issue_number)
                return
            await asyncio.sleep(60)


async def resume_active_sessions() -> None:
    """
    Resume monitoring for all sessions that are still in 'running' state.
    Called on application startup to recover from container restarts.
    """
    active = store.get_active_sessions()
    if not active:
        return
    logger.info("Resuming monitoring for %d active session(s)", len(active))
    for session in active:
        session_id = session["id"]
        issue_number = session["issue_number"]
        store.log_event(
            "monitoring_resumed",
            f"Resumed monitoring for session {session_id} (issue #{issue_number})",
            session_id=session_id,
            issue_number=issue_number,
        )
        asyncio.create_task(_monitor_session(session_id, issue_number))
