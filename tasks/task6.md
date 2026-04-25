# Task 6 — Analytics

**Previous task:** `tasks/task5.md`  
**Next task:** `tasks/task7.md`

---

## Goal

Build `app/analytics.py` — aggregates in-memory session stats with live data from the Devin Analytics API. This combined summary powers the dashboard KPI cards.

---

## Files to Create

```
app/analytics.py
tests/test_analytics.py
```

---

## Implementation

### app/analytics.py

```python
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
```

### tests/test_analytics.py

```python
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
```

---

## Acceptance Criteria

- [ ] `success_rate` is `0.0` when total sessions is 0 — no divide-by-zero error
- [ ] `success_rate` is calculated as `completed / total * 100`, rounded to 1 decimal
- [ ] `prs_opened` counts only sessions with a non-null `pr_url`
- [ ] `in_progress` counts sessions with `status == "running"`
- [ ] `devin_api_stats` key is always present in the response
- [ ] `devin_api_stats` is `{}` when the Devin Analytics API is unavailable
- [ ] `avg_duration_minutes` is `0.0` when no sessions have a `finished_at`
- [ ] `pytest tests/test_analytics.py` passes (6 tests)

**Do not proceed to Task 7 until every item above is confirmed.**
