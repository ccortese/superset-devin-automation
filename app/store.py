import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional

DB_PATH = os.getenv("DB_PATH", "data/store.db")


def _get_conn() -> sqlite3.Connection:
    """Return a SQLite connection with row-factory enabled."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init_db() -> None:
    """Create tables if they don't exist."""
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            issue_number INTEGER NOT NULL,
            issue_title TEXT NOT NULL,
            issue_url TEXT NOT NULL,
            devin_url TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'running',
            pr_url TEXT,
            started_at TEXT NOT NULL,
            finished_at TEXT
        );
        CREATE TABLE IF NOT EXISTS events (
            rowid INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            message TEXT NOT NULL,
            issue_number INTEGER,
            session_id TEXT,
            created_at TEXT NOT NULL
        );
    """)
    conn.close()


_init_db()


def _row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def add_session(
    session_id: str,
    issue_number: int,
    issue_title: str,
    issue_url: str,
    devin_url: str,
) -> dict:
    """Add a new session to the store. Initial status is 'running'."""
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_conn()
    conn.execute(
        """INSERT INTO sessions (id, issue_number, issue_title, issue_url, devin_url, status, pr_url, started_at, finished_at)
           VALUES (?, ?, ?, ?, ?, 'running', NULL, ?, NULL)""",
        (session_id, issue_number, issue_title, issue_url, devin_url, now),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    conn.close()
    return _row_to_dict(row)


def update_session(
    session_id: str,
    status: str,
    pr_url: Optional[str] = None,
) -> Optional[dict]:
    """
    Update a session's status. Sets finished_at when status is terminal.
    Returns None if session_id does not exist.
    """
    conn = _get_conn()
    existing = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if existing is None:
        conn.close()
        return None

    finished_at = datetime.now(timezone.utc).isoformat() if status in ("finished", "failed") else existing["finished_at"]
    new_pr_url = pr_url if pr_url else existing["pr_url"]

    conn.execute(
        "UPDATE sessions SET status = ?, pr_url = ?, finished_at = ? WHERE id = ?",
        (status, new_pr_url, finished_at, session_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    conn.close()
    return _row_to_dict(row)


def get_all_sessions() -> list[dict]:
    """Return all sessions as a list, unfiltered."""
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM sessions ORDER BY started_at DESC").fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def get_active_sessions() -> list[dict]:
    """Return only sessions with status == 'running'."""
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM sessions WHERE status = 'running' ORDER BY started_at DESC").fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def has_session_for_issue(issue_number: int) -> bool:
    """Return True if a session already exists for the given issue number."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT 1 FROM sessions WHERE issue_number = ? LIMIT 1",
        (issue_number,),
    ).fetchone()
    conn.close()
    return row is not None


def log_event(
    event_type: str,
    message: str,
    issue_number: Optional[int] = None,
    session_id: Optional[str] = None,
) -> None:
    """Append a timestamped event to the event log."""
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_conn()
    conn.execute(
        "INSERT INTO events (type, message, issue_number, session_id, created_at) VALUES (?, ?, ?, ?, ?)",
        (event_type, message, issue_number, session_id, now),
    )
    conn.commit()
    conn.close()


def get_recent_events(limit: int = 50) -> list[dict]:
    """Return the most recent events first, capped at limit."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT type, message, issue_number, session_id, created_at FROM events ORDER BY rowid DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def clear() -> None:
    """Reset all state. Used in tests only — do not call in production code."""
    conn = _get_conn()
    conn.execute("DELETE FROM sessions")
    conn.execute("DELETE FROM events")
    conn.commit()
    conn.close()
