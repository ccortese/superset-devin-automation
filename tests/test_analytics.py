import httpx
import pytest
import respx

from app import store
from app.analytics import get_summary
from app.devin_client import DEVIN_BASE_URL


def _mock_devin_ok(payload: dict = {}):
    """Helper: mock the Devin Analytics API with a 200 response."""
    return respx.get(f"{DEVIN_BASE_URL}/analytics/sessions").mock(
        return_value=httpx.Response(200, json=payload)
    )


@pytest.mark.asyncio
async def test_empty_store_no_errors():
    with respx.mock:
        _mock_devin_ok()
        result = await get_summary()
    assert result["total"] == 0
    assert result["success_rate"] == 0.0
    assert result["avg_duration_minutes"] == 0.0
    assert "devin_api_stats" in result


@pytest.mark.asyncio
async def test_success_rate_one_of_two():
    store.add_session("a", 1, "title", "url", "url")
    store.add_session("b", 2, "title", "url", "url")
    store.update_session("a", "finished", pr_url="https://github.com/u/r/pull/1")
    store.update_session("b", "failed")

    with respx.mock:
        _mock_devin_ok()
        result = await get_summary()

    assert result["total"] == 2
    assert result["completed"] == 1
    assert result["failed"] == 1
    assert result["success_rate"] == 50.0


@pytest.mark.asyncio
async def test_prs_opened_counts_non_null_pr_url():
    store.add_session("a", 1, "title", "url", "url")
    store.add_session("b", 2, "title", "url", "url")
    store.update_session("a", "finished", pr_url="https://github.com/u/r/pull/1")
    store.update_session("b", "failed")

    with respx.mock:
        _mock_devin_ok()
        result = await get_summary()

    assert result["prs_opened"] == 1


@pytest.mark.asyncio
async def test_in_progress_counted():
    store.add_session("a", 1, "title", "url", "url")  # status defaults to "running"

    with respx.mock:
        _mock_devin_ok()
        result = await get_summary()

    assert result["in_progress"] == 1


@pytest.mark.asyncio
async def test_devin_api_stats_included_in_response():
    with respx.mock:
        _mock_devin_ok({"total_sessions": 42, "success_rate": 0.9})
        result = await get_summary()
    assert result["devin_api_stats"]["total_sessions"] == 42


@pytest.mark.asyncio
async def test_devin_api_unavailable_does_not_raise():
    with respx.mock:
        respx.get(f"{DEVIN_BASE_URL}/analytics/sessions").mock(
            return_value=httpx.Response(503)
        )
        result = await get_summary()
    assert result["devin_api_stats"] == {}
    assert result["total"] == 0  # local stats still work
