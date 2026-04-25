from datetime import datetime

from app import store
from app.devin_client import get_analytics


async def get_summary() -> dict:
    """
    Return a combined analytics summary.

    Local stats come from the in-memory store.
    devin_api_stats comes from the Devin Analytics API.

    Never raises — devin_api_stats will be an empty dict if the API is unavailable.
    """
    sessions = store.get_all_sessions()

    total = len(sessions)
    completed = sum(1 for s in sessions if s["status"] == "finished")
    failed = sum(1 for s in sessions if s["status"] == "failed")
    in_progress = sum(1 for s in sessions if s["status"] == "running")
    prs_opened = sum(1 for s in sessions if s.get("pr_url"))
    success_rate = round((completed / total * 100) if total > 0 else 0.0, 1)

    durations: list[float] = []
    for s in sessions:
        if s.get("started_at") and s.get("finished_at"):
            try:
                start = datetime.fromisoformat(s["started_at"])
                end = datetime.fromisoformat(s["finished_at"])
                durations.append((end - start).total_seconds() / 60)
            except (ValueError, TypeError):
                pass

    avg_duration_minutes = round(sum(durations) / len(durations), 1) if durations else 0.0
    devin_api_stats = await get_analytics()

    return {
        "total": total,
        "completed": completed,
        "failed": failed,
        "in_progress": in_progress,
        "prs_opened": prs_opened,
        "success_rate": success_rate,
        "avg_duration_minutes": avg_duration_minutes,
        "devin_api_stats": devin_api_stats,
    }
