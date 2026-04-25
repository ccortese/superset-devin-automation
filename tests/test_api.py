import httpx
import pytest
import respx

from app import store
from app.devin_client import DEVIN_BASE_URL


@pytest.mark.asyncio
async def test_list_sessions_empty(client):
    r = await client.get("/api/sessions")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_list_sessions_returns_all(client):
    store.add_session("s1", 1, "SQL injection", "http://i1", "http://d1")
    store.add_session("s2", 2, "Weak hash", "http://i2", "http://d2")
    r = await client.get("/api/sessions")
    assert len(r.json()) == 2


@pytest.mark.asyncio
async def test_get_session_found(client):
    store.add_session("abc123", 1, "SQL injection", "http://issue", "http://devin")
    r = await client.get("/api/sessions/abc123")
    assert r.status_code == 200
    assert r.json()["id"] == "abc123"


@pytest.mark.asyncio
async def test_get_session_not_found(client):
    r = await client.get("/api/sessions/nonexistent")
    assert r.json() == {"error": "not found"}


@pytest.mark.asyncio
async def test_analytics_includes_devin_api_stats(client):
    with respx.mock:
        respx.get(f"{DEVIN_BASE_URL}/analytics/sessions").mock(
            return_value=httpx.Response(200, json={"total_sessions": 3})
        )
        r = await client.get("/api/analytics")
    assert r.status_code == 200
    body = r.json()
    assert "devin_api_stats" in body
    assert body["devin_api_stats"]["total_sessions"] == 3


@pytest.mark.asyncio
async def test_events_returns_logged_events(client):
    store.log_event("test_event", "something happened", issue_number=1)
    r = await client.get("/api/events")
    assert r.status_code == 200
    events = r.json()
    assert len(events) == 1
    assert events[0]["type"] == "test_event"
