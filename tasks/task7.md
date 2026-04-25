# Task 7 — API Routes

**Previous task:** `tasks/task6.md`  
**Next task:** `tasks/task8.md`

---

## Goal

Build `app/api.py` — HTTP endpoints that expose the in-memory store and analytics as JSON. Also bring `app/main.py` to its final form by wiring in all routers and the static dashboard mount.

---

## Files to Create / Modify

```
app/api.py          ← create
app/main.py         ← update to final form
tests/test_api.py
```

---

## Implementation

### app/api.py

```python
from fastapi import APIRouter

from app import store
from app.analytics import get_summary

router = APIRouter(prefix="/api")


@router.get("/sessions")
async def list_sessions():
    """Return all sessions from the in-memory store."""
    return store.get_all_sessions()


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Return a single session by ID, or {"error": "not found"}."""
    match = next((s for s in store.get_all_sessions() if s["id"] == session_id), None)
    if match is None:
        return {"error": "not found"}
    return match


@router.get("/analytics")
async def analytics():
    """Return combined local stats + Devin Analytics API data."""
    return await get_summary()


@router.get("/events")
async def list_events():
    """Return the 50 most recent events, newest first."""
    return store.get_recent_events(limit=50)
```

### app/main.py (final form)

This is the complete, final version of `main.py`. Replace the previous version entirely.

```python
import os
import sys

from dotenv import load_dotenv
load_dotenv()

# Fail fast if any required environment variables are missing
_REQUIRED = ["DEVIN_API_KEY", "GITHUB_TOKEN", "GITHUB_REPO", "WEBHOOK_SECRET"]
_missing = [v for v in _REQUIRED if not os.getenv(v)]
if _missing:
    print(f"[ERROR] Missing required environment variables: {', '.join(_missing)}", file=sys.stderr)
    sys.exit(1)

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import router as api_router
from app.webhook import router as webhook_router

app = FastAPI(title="Devin Remediation Control Plane")

app.include_router(webhook_router)
app.include_router(api_router)

# Serve static assets (CSS, JS if ever separated) under /static
app.mount("/static", StaticFiles(directory="app/dashboard"), name="static")


@app.get("/dashboard", include_in_schema=False)
async def dashboard():
    """Serve the single-page observability dashboard."""
    return FileResponse("app/dashboard/index.html")


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}
```

### tests/test_api.py

```python
import httpx
import pytest
import respx

from app import store
from app.devin_client import DEVIN_BASE_URL
from app.main import app


@pytest.mark.asyncio
async def test_list_sessions_empty():
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        r = await client.get("/api/sessions")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_list_sessions_returns_all():
    store.add_session("s1", 1, "SQL injection", "http://i1", "http://d1")
    store.add_session("s2", 2, "Weak hash", "http://i2", "http://d2")
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        r = await client.get("/api/sessions")
    assert len(r.json()) == 2


@pytest.mark.asyncio
async def test_get_session_found():
    store.add_session("abc123", 1, "SQL injection", "http://issue", "http://devin")
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        r = await client.get("/api/sessions/abc123")
    assert r.status_code == 200
    assert r.json()["id"] == "abc123"


@pytest.mark.asyncio
async def test_get_session_not_found():
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        r = await client.get("/api/sessions/nonexistent")
    assert r.json() == {"error": "not found"}


@pytest.mark.asyncio
async def test_analytics_includes_devin_api_stats():
    with respx.mock:
        respx.get(f"{DEVIN_BASE_URL}/analytics/sessions").mock(
            return_value=httpx.Response(200, json={"total_sessions": 3})
        )
        async with httpx.AsyncClient(app=app, base_url="http://test") as client:
            r = await client.get("/api/analytics")
    assert r.status_code == 200
    body = r.json()
    assert "devin_api_stats" in body
    assert body["devin_api_stats"]["total_sessions"] == 3


@pytest.mark.asyncio
async def test_events_returns_logged_events():
    store.log_event("test_event", "something happened", issue_number=1)
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        r = await client.get("/api/events")
    assert r.status_code == 200
    events = r.json()
    assert len(events) == 1
    assert events[0]["type"] == "test_event"


@pytest.mark.asyncio
async def test_dashboard_returns_html():
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        r = await client.get("/dashboard")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
```

---

## Acceptance Criteria

- [ ] `GET /api/sessions` returns `[]` when store is empty
- [ ] `GET /api/sessions` returns all sessions when the store has entries
- [ ] `GET /api/sessions/{id}` returns the session dict when found
- [ ] `GET /api/sessions/nonexistent` returns `{"error": "not found"}`
- [ ] `GET /api/analytics` response includes `"devin_api_stats"` key
- [ ] `GET /api/events` returns a list of logged events
- [ ] `GET /dashboard` returns HTTP 200 with `text/html` content type
- [ ] `GET /health` still returns `{"status": "ok", ...}`
- [ ] `pytest tests/test_api.py` passes (7 tests)

**Do not proceed to Task 8 until every item above is confirmed.**
