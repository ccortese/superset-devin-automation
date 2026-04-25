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
