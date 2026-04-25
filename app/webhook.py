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


def _validate_issue(payload: dict) -> dict:
    """Extract and validate the issue object from a webhook payload."""
    issue = payload.get("issue")
    if not isinstance(issue, dict):
        raise HTTPException(status_code=400, detail="Missing or invalid 'issue' field")
    for field in ("number", "title", "body", "html_url"):
        if field not in issue:
            raise HTTPException(status_code=400, detail=f"Issue missing required field: {field}")
    if not isinstance(issue["number"], int):
        raise HTTPException(status_code=400, detail="Issue number must be an integer")
    return issue


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

    issue = _validate_issue(payload)
    store.log_event(
        "webhook_received",
        f"Issue #{issue['number']}: {issue['title']}",
        issue_number=issue["number"],
    )

    background_tasks.add_task(create_session, issue)

    return {"status": "accepted", "issue": issue["number"]}
