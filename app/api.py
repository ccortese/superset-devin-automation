from fastapi import APIRouter, Query

from app import store
from app.analytics import get_summary

router = APIRouter(prefix="/api")

MAX_EVENT_LIMIT = 200


@router.get("/sessions")
async def list_sessions():
    """Return all sessions from the in-memory store."""
    return store.get_all_sessions()


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Return a single session by ID, or {"error": "not found"}."""
    match = store.get_session_by_id(session_id)
    if match is None:
        return {"error": "not found"}
    return match


@router.get("/analytics")
async def analytics():
    """Return combined local stats + Devin Analytics API data."""
    return await get_summary()


@router.get("/events")
async def list_events(limit: int = Query(default=50, ge=1, le=MAX_EVENT_LIMIT)):
    """Return the most recent events, newest first."""
    return store.get_recent_events(limit=limit)
