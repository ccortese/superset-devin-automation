# Task 3 — GitHub Webhook Handler

**Previous task:** `tasks/task2.md`  
**Next task:** `tasks/task4.md`

---

## Goal

Build `app/webhook.py` — receives GitHub issue events, validates the HMAC-SHA256 signature, filters for the `devin-remediate` label, and enqueues a Devin session as a background task.

Also update `app/main.py` to include the webhook router.

---

## Files to Modify / Create

```
app/webhook.py      ← create
app/main.py         ← add webhook router
tests/test_webhook.py
```

---

## Implementation

### app/webhook.py

```python
import hashlib
import hmac
import os

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from app import store
from app.devin_client import create_session

router = APIRouter()

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")


def _verify_signature(payload: bytes, header: str) -> bool:
    """Return True if the HMAC-SHA256 signature matches the payload."""
    expected = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, header)


@router.post("/webhook")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if not _verify_signature(body, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    payload = await request.json()

    if payload.get("action") != "labeled":
        return {"status": "ignored", "reason": "not a label event"}

    label_name = payload.get("label", {}).get("name", "")
    if label_name != "devin-remediate":
        return {"status": "ignored", "reason": f"label '{label_name}' not targeted"}

    issue = payload["issue"]
    store.log_event(
        "webhook_received",
        f"Issue #{issue['number']}: {issue['title']}",
        issue_number=issue["number"],
    )

    # Enqueue as a background task so we return 200 immediately.
    # GitHub webhooks expect a response within 10 seconds.
    background_tasks.add_task(create_session, issue)

    return {"status": "accepted", "issue": issue["number"]}
```

### app/main.py (updated)

Add the webhook router. Keep everything else from Task 1 unchanged.

```python
import os
import sys

from dotenv import load_dotenv
load_dotenv()

_REQUIRED = ["DEVIN_API_KEY", "GITHUB_TOKEN", "GITHUB_REPO", "WEBHOOK_SECRET"]
_missing = [v for v in _REQUIRED if not os.getenv(v)]
if _missing:
    print(f"[ERROR] Missing required environment variables: {', '.join(_missing)}", file=sys.stderr)
    sys.exit(1)

from datetime import datetime, timezone
from fastapi import FastAPI
from app.webhook import router as webhook_router

app = FastAPI(title="Devin Remediation Control Plane")
app.include_router(webhook_router)


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}
```

> **Note:** The `/api/*` router and dashboard static mount are added in Task 7.

### tests/test_webhook.py

```python
import hashlib
import hmac
import json

SECRET = "testsecret"  # matches conftest.py os.environ default


def _sign(payload: bytes, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def _make_payload(
    action: str = "labeled",
    label: str = "devin-remediate",
    issue_number: int = 1,
) -> bytes:
    return json.dumps({
        "action": action,
        "label": {"name": label},
        "issue": {
            "number": issue_number,
            "title": "[SECURITY] SQL injection",
            "body": "Found in models.py line 42.",
            "html_url": f"https://github.com/testuser/superset/issues/{issue_number}",
        },
        "repository": {"full_name": "testuser/superset"},
    }).encode()


async def test_valid_webhook_accepted(client, monkeypatch):
    monkeypatch.setattr("app.webhook.create_session", lambda issue: None)
    payload = _make_payload()
    response = await client.post(
        "/webhook",
        content=payload,
        headers={
            "X-GitHub-Event": "issues",
            "X-Hub-Signature-256": _sign(payload),
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert response.json()["issue"] == 1


async def test_invalid_signature_returns_403(client):
    payload = _make_payload()
    response = await client.post(
        "/webhook",
        content=payload,
        headers={
            "X-GitHub-Event": "issues",
            "X-Hub-Signature-256": "sha256=badhash",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 403


async def test_missing_signature_returns_403(client):
    payload = _make_payload()
    response = await client.post(
        "/webhook",
        content=payload,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 403


async def test_wrong_label_returns_ignored(client):
    payload = _make_payload(label="some-other-label")
    response = await client.post(
        "/webhook",
        content=payload,
        headers={
            "X-GitHub-Event": "issues",
            "X-Hub-Signature-256": _sign(payload),
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"


async def test_non_labeled_action_returns_ignored(client):
    payload = _make_payload(action="opened")
    response = await client.post(
        "/webhook",
        content=payload,
        headers={
            "X-GitHub-Event": "issues",
            "X-Hub-Signature-256": _sign(payload),
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"


async def test_valid_webhook_logs_event(client, monkeypatch):
    from app import store
    monkeypatch.setattr("app.webhook.create_session", lambda issue: None)
    payload = _make_payload()
    await client.post(
        "/webhook",
        content=payload,
        headers={
            "X-GitHub-Event": "issues",
            "X-Hub-Signature-256": _sign(payload),
            "Content-Type": "application/json",
        },
    )
    events = store.get_recent_events()
    assert any(e["type"] == "webhook_received" for e in events)
```

---

## Acceptance Criteria

- [ ] Valid HMAC + `devin-remediate` label → `{"status": "accepted", "issue": <number>}`
- [ ] Invalid HMAC signature → HTTP 403
- [ ] Missing signature header → HTTP 403
- [ ] Wrong label name → `{"status": "ignored"}`
- [ ] Action other than `"labeled"` → `{"status": "ignored"}`
- [ ] Accepted webhook logs a `webhook_received` event to the store
- [ ] `pytest tests/test_webhook.py` passes (6 tests)

**Do not proceed to Task 4 until every item above is confirmed.**
