# Task 2 — In-Memory Store

**Previous task:** `tasks/task1.md`  
**Next task:** `tasks/task3.md`

---

## Goal

Build `app/store.py` — the single source of truth for all session and event state. A module-level dict. No database, no external dependencies.

---

## Files to Create

```
app/store.py
tests/test_store.py
```

---

## Implementation

### app/store.py

```python
from datetime import datetime, timezone
from typing import Optional

# Module-level state — resets when the process restarts
_sessions: dict[str, dict] = {}
_events: list[dict] = []


def add_session(
    session_id: str,
    issue_number: int,
    issue_title: str,
    issue_url: str,
    devin_url: str,
) -> dict:
    """Add a new session to the store. Initial status is 'running'."""
    session = {
        "id": session_id,
        "issue_number": issue_number,
        "issue_title": issue_title,
        "issue_url": issue_url,
        "devin_url": devin_url,
        "status": "running",
        "pr_url": None,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
    }
    _sessions[session_id] = session
    return session


def update_session(
    session_id: str,
    status: str,
    pr_url: Optional[str] = None,
) -> Optional[dict]:
    """
    Update a session's status. Sets finished_at when status is terminal.
    Returns None if session_id does not exist.
    """
    if session_id not in _sessions:
        return None
    _sessions[session_id]["status"] = status
    if pr_url:
        _sessions[session_id]["pr_url"] = pr_url
    if status in ("finished", "failed"):
        _sessions[session_id]["finished_at"] = datetime.now(timezone.utc).isoformat()
    return _sessions[session_id]


def get_all_sessions() -> list[dict]:
    """Return all sessions as a list, unfiltered."""
    return list(_sessions.values())


def get_active_sessions() -> list[dict]:
    """Return only sessions with status == 'running'."""
    return [s for s in _sessions.values() if s["status"] == "running"]


def log_event(
    event_type: str,
    message: str,
    issue_number: Optional[int] = None,
    session_id: Optional[str] = None,
) -> None:
    """Append a timestamped event to the event log."""
    _events.append({
        "type": event_type,
        "message": message,
        "issue_number": issue_number,
        "session_id": session_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })


def get_recent_events(limit: int = 50) -> list[dict]:
    """Return the most recent events first, capped at limit."""
    return list(reversed(_events[-limit:]))


def clear() -> None:
    """Reset all state. Used in tests only — do not call in production code."""
    _sessions.clear()
    _events.clear()
```

### tests/test_store.py

```python
from app import store


def test_add_session_returns_running_status():
    s = store.add_session("abc", 1, "SQL injection", "http://issue", "http://devin")
    assert s["status"] == "running"
    assert s["pr_url"] is None
    assert s["finished_at"] is None
    assert s["started_at"] is not None


def test_add_session_is_retrievable():
    store.add_session("abc", 1, "title", "http://issue", "http://devin")
    sessions = store.get_all_sessions()
    assert len(sessions) == 1
    assert sessions[0]["id"] == "abc"


def test_update_session_to_finished():
    store.add_session("abc", 1, "SQL injection", "http://issue", "http://devin")
    updated = store.update_session("abc", "finished", pr_url="https://github.com/user/repo/pull/1")
    assert updated["status"] == "finished"
    assert updated["pr_url"] == "https://github.com/user/repo/pull/1"
    assert updated["finished_at"] is not None


def test_update_session_to_failed_sets_finished_at():
    store.add_session("abc", 1, "title", "url", "url")
    updated = store.update_session("abc", "failed")
    assert updated["status"] == "failed"
    assert updated["pr_url"] is None
    assert updated["finished_at"] is not None


def test_update_session_nonexistent_returns_none():
    result = store.update_session("does-not-exist", "finished")
    assert result is None


def test_get_active_sessions_excludes_finished():
    store.add_session("running-1", 1, "title", "url", "url")
    store.add_session("done-1", 2, "title2", "url", "url")
    store.update_session("done-1", "finished")
    active = store.get_active_sessions()
    assert len(active) == 1
    assert active[0]["id"] == "running-1"


def test_log_event_and_retrieve():
    store.log_event("webhook_received", "Issue #1 received", issue_number=1)
    events = store.get_recent_events()
    assert len(events) == 1
    assert events[0]["type"] == "webhook_received"
    assert events[0]["issue_number"] == 1


def test_get_recent_events_most_recent_first():
    store.log_event("first", "msg1")
    store.log_event("second", "msg2")
    events = store.get_recent_events()
    assert events[0]["type"] == "second"
    assert events[1]["type"] == "first"


def test_get_recent_events_respects_limit():
    for i in range(10):
        store.log_event("evt", f"message {i}")
    events = store.get_recent_events(limit=3)
    assert len(events) == 3


def test_clear_resets_sessions_and_events():
    store.add_session("abc", 1, "title", "url", "url")
    store.log_event("test", "msg")
    store.clear()
    assert store.get_all_sessions() == []
    assert store.get_recent_events() == []
```

---

## Acceptance Criteria

- [ ] `add_session()` returns session with `status == "running"` and `pr_url == None`
- [ ] `update_session()` sets `finished_at` for `"finished"` and `"failed"` statuses
- [ ] `update_session()` returns `None` for an unknown `session_id`
- [ ] `get_active_sessions()` excludes sessions with terminal statuses
- [ ] `get_recent_events()` returns most recent first, capped at `limit`
- [ ] `clear()` empties both `_sessions` and `_events`
- [ ] `pytest tests/test_store.py` passes (10 tests)

**Do not proceed to Task 3 until every item above is confirmed.**
