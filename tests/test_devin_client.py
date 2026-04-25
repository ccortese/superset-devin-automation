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
