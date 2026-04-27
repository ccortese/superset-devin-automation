import httpx
import pytest
import respx

from app import store
from app.devin_client import (
    DEVIN_BASE_URL,
    MAX_CONSECUTIVE_ERRORS,
    _monitor_session,
    build_prompt,
    create_session,
    extract_pr_url,
    get_analytics,
    get_session,
    resume_active_sessions,
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


@pytest.mark.asyncio
async def test_create_session_logs_error_on_api_failure():
    """When the Devin API fails, create_session should log an error event, not crash."""
    issue = {
        "number": 42,
        "title": "Test vuln",
        "body": "body",
        "html_url": "https://github.com/testuser/superset/issues/42",
    }
    with respx.mock:
        respx.post(f"{DEVIN_BASE_URL}/sessions").mock(
            return_value=httpx.Response(429, json={"error": "rate limited"})
        )
        await create_session(issue)

    # No session should be created
    assert store.get_all_sessions() == []
    # An error event should be logged
    events = store.get_recent_events()
    assert any(e["type"] == "error" and "issue #42" in e["message"] for e in events)


@pytest.mark.asyncio
async def test_resume_active_sessions_spawns_monitoring(monkeypatch):
    """On startup, resume_active_sessions should spawn monitors for running sessions."""
    store.add_session(
        session_id="ses-1",
        issue_number=10,
        issue_title="Test",
        issue_url="https://github.com/testuser/superset/issues/10",
        devin_url="https://app.devin.ai/sessions/ses-1",
    )
    # Track which sessions get monitoring resumed
    resumed = []
    import asyncio

    async def fake_monitor(session_id, issue_number):
        resumed.append((session_id, issue_number))

    monkeypatch.setattr("app.devin_client._monitor_session", fake_monitor)
    await resume_active_sessions()
    # Give the task a chance to run
    await asyncio.sleep(0.1)
    assert ("ses-1", 10) in resumed


@pytest.mark.asyncio
async def test_resume_active_sessions_skips_finished(monkeypatch):
    """Finished sessions should not be re-monitored on startup."""
    store.add_session(
        session_id="ses-done",
        issue_number=20,
        issue_title="Done",
        issue_url="https://github.com/testuser/superset/issues/20",
        devin_url="https://app.devin.ai/sessions/ses-done",
    )
    store.update_session("ses-done", status="finished", pr_url="https://github.com/test/pull/1")

    resumed = []
    import asyncio

    async def fake_monitor(session_id, issue_number):
        resumed.append((session_id, issue_number))

    monkeypatch.setattr("app.devin_client._monitor_session", fake_monitor)
    await resume_active_sessions()
    await asyncio.sleep(0.1)
    assert resumed == []


@pytest.mark.asyncio
async def test_resume_logs_monitoring_resumed_event(monkeypatch):
    """resume_active_sessions should log a monitoring_resumed event."""
    store.add_session(
        session_id="ses-log",
        issue_number=30,
        issue_title="Log test",
        issue_url="https://github.com/testuser/superset/issues/30",
        devin_url="https://app.devin.ai/sessions/ses-log",
    )

    async def fake_monitor(session_id, issue_number):
        pass

    monkeypatch.setattr("app.devin_client._monitor_session", fake_monitor)
    await resume_active_sessions()

    events = store.get_recent_events()
    assert any(e["type"] == "monitoring_resumed" and "ses-log" in e["message"] for e in events)


@pytest.mark.asyncio
async def test_monitor_session_fails_after_max_consecutive_errors(monkeypatch):
    """After MAX_CONSECUTIVE_ERRORS poll failures, session should be marked failed."""
    store.add_session(
        session_id="ses-err",
        issue_number=99,
        issue_title="Error test",
        issue_url="https://github.com/testuser/superset/issues/99",
        devin_url="https://app.devin.ai/sessions/ses-err",
    )

    call_count = 0

    async def fake_get_session(session_id):
        nonlocal call_count
        call_count += 1
        raise httpx.HTTPStatusError(
            "Not Found",
            request=httpx.Request("GET", f"{DEVIN_BASE_URL}/sessions/{session_id}"),
            response=httpx.Response(404),
        )

    async def fake_comment(issue_number, body):
        pass

    import asyncio

    original_sleep = asyncio.sleep

    monkeypatch.setattr("app.devin_client.get_session", fake_get_session)
    monkeypatch.setattr("app.github_client.comment_on_issue", fake_comment)
    monkeypatch.setattr("asyncio.sleep", lambda _: original_sleep(0))

    await _monitor_session("ses-err", 99)

    assert call_count == MAX_CONSECUTIVE_ERRORS
    session = store.get_session_by_id("ses-err")
    assert session["status"] == "failed"
    events = store.get_recent_events()
    assert any(
        e["type"] == "session_failed" and "consecutive poll errors" in e["message"]
        for e in events
    )
