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
