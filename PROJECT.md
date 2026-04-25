# PROJECT.md — Vulnerability Remediation Control Plane

Architectural overview and implementation index. The full spec for each task lives in `tasks/`.

---

## What This Builds

An event-driven control plane that automatically remediates GitHub security issues using Devin AI. When an issue is labeled `devin-remediate`, the system:

1. Receives a GitHub webhook event
2. Creates a Devin session with full issue context
3. Polls the session until it reaches a terminal state
4. Posts the resulting PR link back to the GitHub issue
5. Surfaces all activity in a real-time observability dashboard

---

## Architecture

```
GitHub Issue (labeled "devin-remediate")
         │
         ▼ POST /webhook
┌──────────────────────────────────┐
│         FastAPI Backend           │
│                                   │
│  webhook.py       validates HMAC, enqueues background task
│  devin_client.py  creates Devin session, polls until done
│  github_client.py posts PR comment back to issue
│  store.py         in-memory session + event state
│  analytics.py     aggregates store + Devin Analytics API
│  api.py           GET /api/* endpoints for the dashboard
│  dashboard/       single-page HTML UI, auto-refreshes
└──────────────────────────────────┘
         │
         ▼
   docker-compose up  (only command needed)
```

**State:** Module-level dicts in `store.py`. No database. State resets on container restart — acceptable for a demo.

---

## Repo Structure

```
superset-devin-automation/
├── AGENTS.md                ← working conventions for agents
├── PROJECT.md               ← this file
├── tasks/
│   ├── task1.md             ← Scaffold & Docker
│   ├── task2.md             ← In-Memory Store
│   ├── task3.md             ← GitHub Webhook Handler
│   ├── task4.md             ← Devin API Client
│   ├── task5.md             ← GitHub Client
│   ├── task6.md             ← Analytics
│   ├── task7.md             ← API Routes
│   ├── task8.md             ← Observability Dashboard
│   ├── task9.md             ← Simulate Webhook Script
│   └── task10.md            ← README & Final Verification
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── README.md
├── requirements.txt
├── pytest.ini
├── app/
│   ├── __init__.py          ← empty, marks app as a package
│   ├── main.py              ← FastAPI app, env validation, router wiring
│   ├── store.py             ← in-memory state
│   ├── webhook.py           ← POST /webhook handler
│   ├── devin_client.py      ← Devin API wrapper + polling loop
│   ├── github_client.py     ← GitHub API wrapper
│   ├── analytics.py         ← summary aggregation
│   ├── api.py               ← GET /api/* routes
│   └── dashboard/
│       └── index.html       ← observability UI
├── scripts/
│   └── simulate_webhook.sh
└── tests/
    ├── conftest.py
    ├── test_main.py
    ├── test_store.py
    ├── test_webhook.py
    ├── test_devin_client.py
    ├── test_github_client.py
    ├── test_analytics.py
    └── test_api.py
```

---

## Tech Stack

| Layer | Choice | Reason |
|---|---|---|
| Web framework | FastAPI | Async-native, auto-docs at `/docs` |
| HTTP client | httpx | Async, used for Devin + GitHub API calls |
| State | Python dict (in-memory) | Zero dependencies, sufficient for demo |
| Config | python-dotenv | 12-factor env var loading |
| Container | python:3.11-slim | Small image, fast builds |
| Orchestration | Docker Compose | Single-command startup |

---

## Environment Variables

```bash
# .env.example
# Values prefixed with $ are pulled from Devin's shell state (secrets).
# Set DEVIN_API_KEY, GITHUB_TOKEN, GITHUB_REPO, and WEBHOOK_SECRET
# in your Devin secrets store before running.
DEVIN_API_KEY=$DEVIN_API_KEY
GITHUB_TOKEN=$GITHUB_TOKEN
GITHUB_REPO=$GITHUB_REPO
WEBHOOK_SECRET=$WEBHOOK_SECRET
DEVIN_BASE_URL=https://api.devin.ai/v1
```

All five are required. The app exits on startup with a clear error if any are missing.

---

## Dependencies

```
# requirements.txt
fastapi>=0.110.0
uvicorn[standard]>=0.29.0
httpx>=0.27.0
python-dotenv>=1.0.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
respx>=0.21.0
```

---

## pytest Configuration

```ini
# pytest.ini
[pytest]
asyncio_mode = auto
```

---

## API Surface

| Method | Path | Description |
|---|---|---|
| POST | `/webhook` | GitHub issue label event receiver |
| GET | `/dashboard` | Observability UI |
| GET | `/api/sessions` | All sessions |
| GET | `/api/sessions/{id}` | Single session detail |
| GET | `/api/analytics` | Analytics summary (includes Devin API) |
| GET | `/api/events` | Event log (last 50) |
| GET | `/health` | Docker healthcheck |
| GET | `/docs` | FastAPI auto-docs |

---

## Data Flow

```
1. GitHub fires POST /webhook
         │
         ▼
2. webhook.py validates HMAC signature
         │
         ▼
3. devin_client.create_session() called as BackgroundTask
         │
         ├── POSTs to Devin API → gets session_id
         ├── Writes session to store.py
         └── Spawns asyncio task: _monitor_session()
                   │
                   ▼ (polls every 30s with exponential backoff)
4. Session reaches terminal state
         │
         ├── extract_pr_url() parses PR link from session data
         ├── store.update_session() marks finished/failed
         └── github_client.comment_on_issue() posts result
                   │
                   ▼
5. Dashboard polls /api/sessions + /api/analytics every 15s
         │
         └── Renders updated state to the viewer
```

---

## Session States

```
running  →  finished  (Devin opened a PR)
running  →  failed    (terminal state, no PR found)
```

---

## Task Index

Work through tasks in order. Do not start a task until the previous task's acceptance criteria are met and tests pass.

| Task | File | What it builds |
|---|---|---|
| 1 | `tasks/task1.md` | Scaffold, Docker, health endpoint, conftest |
| 2 | `tasks/task2.md` | In-memory store (`store.py`) |
| 3 | `tasks/task3.md` | GitHub webhook handler (`webhook.py`) |
| 4 | `tasks/task4.md` | Devin API client (`devin_client.py`) |
| 5 | `tasks/task5.md` | GitHub API client (`github_client.py`) |
| 6 | `tasks/task6.md` | Analytics aggregation (`analytics.py`) |
| 7 | `tasks/task7.md` | API routes (`api.py`) + final `main.py` |
| 8 | `tasks/task8.md` | Observability dashboard (`index.html`) |
| 9 | `tasks/task9.md` | Simulate webhook script |
| 10 | `tasks/task10.md` | README + final end-to-end verification |
