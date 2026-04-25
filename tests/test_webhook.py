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


async def test_duplicate_issue_returns_ignored(client, monkeypatch):
    from app import store

    def mock_create_session(issue: dict) -> None:
        store.add_session(
            "mock-session", issue["number"], issue["title"],
            issue["html_url"], "http://devin",
        )

    monkeypatch.setattr("app.webhook.create_session", mock_create_session)

    payload = _make_payload(issue_number=7)
    headers = {
        "X-GitHub-Event": "issues",
        "X-Hub-Signature-256": _sign(payload),
        "Content-Type": "application/json",
    }

    first = await client.post("/webhook", content=payload, headers=headers)
    assert first.status_code == 200
    assert first.json()["status"] == "accepted"

    second = await client.post("/webhook", content=payload, headers=headers)
    assert second.status_code == 200
    assert second.json()["status"] == "ignored"
    assert "already exists" in second.json()["reason"]


async def test_duplicate_blocked_by_store_session(client, monkeypatch):
    from app import store
    monkeypatch.setattr("app.webhook.create_session", lambda issue: None)

    store.add_session("existing-session", 7, "title", "url", "url")

    payload = _make_payload(issue_number=7)
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
    assert "already exists" in response.json()["reason"]
