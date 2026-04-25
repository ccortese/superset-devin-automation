# Task 1 — Scaffold & Docker

**Previous task:** None — this is the first task.  
**Next task:** `tasks/task2.md`

---

## Goal

Create the full repo skeleton, Docker configuration, env template, and a minimal FastAPI app with a single `/health` endpoint. Every subsequent task builds on top of this foundation.

---

## Files to Create

```
superset-devin-automation/
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── requirements.txt
├── pytest.ini
├── app/
│   ├── __init__.py
│   └── main.py
└── tests/
    ├── conftest.py
    └── test_main.py
```

Also create these files as stubs (full content added in later tasks):

```
app/webhook.py
app/github_client.py
app/analytics.py
app/api.py
app/dashboard/index.html
scripts/simulate_webhook.sh
tests/test_store.py
tests/test_webhook.py
tests/test_devin_client.py
tests/test_github_client.py
tests/test_analytics.py
tests/test_api.py
```

**`app/store.py`** — needs a minimal `clear()` function so the autouse fixture in `conftest.py` works from Task 1 onward:

```python
# Minimal stub — full implementation in Task 2.

def clear():
    """Reset all state. Populated in Task 2."""
    pass
```

**`app/devin_client.py`** — needs a `create_session` stub because `webhook.py` (Task 3) imports it at module level:

```python
# Minimal stub — full implementation in Task 4.


async def create_session(issue: dict) -> None:
    """Create a Devin session. Populated in Task 4."""
    pass
```

---

## Implementation

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### docker-compose.yml

```yaml
version: '3.8'
services:
  automation:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### .env.example

Values prefixed with `$` are pulled automatically from Devin's shell state (secrets). Set these in your Devin secrets store before running.

```bash
DEVIN_API_KEY=$DEVIN_API_KEY
GITHUB_TOKEN=$GITHUB_TOKEN
GITHUB_REPO=$GITHUB_REPO
WEBHOOK_SECRET=$WEBHOOK_SECRET
DEVIN_BASE_URL=https://api.devin.ai/v1
```

### requirements.txt

```
fastapi>=0.110.0
uvicorn[standard]>=0.29.0
httpx>=0.27.0
python-dotenv>=1.0.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
respx>=0.21.0
```

### pytest.ini

```ini
[pytest]
asyncio_mode = auto
```

### app/\_\_init\_\_.py

```python
# empty — marks app/ as a Python package
```

### app/main.py

```python
import os
import sys

from dotenv import load_dotenv
load_dotenv()

# Fail fast if any required environment variables are missing
_REQUIRED = ["DEVIN_API_KEY", "GITHUB_TOKEN", "GITHUB_REPO", "WEBHOOK_SECRET"]
_missing = [v for v in _REQUIRED if not os.getenv(v)]
if _missing:
    print(f"[ERROR] Missing required environment variables: {', '.join(_missing)}", file=sys.stderr)
    sys.exit(1)

from datetime import datetime, timezone
from fastapi import FastAPI

app = FastAPI(title="Devin Remediation Control Plane")


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}
```

> **Note:** Routers for `/webhook` and `/api/*` are wired in during Task 7. Do not add them here.

### tests/conftest.py

Shared fixtures automatically available to all test files via pytest discovery.

```python
import os

import httpx
import pytest

# Set env vars before any app module is imported
os.environ.setdefault("DEVIN_API_KEY", "test-devin-key")
os.environ.setdefault("GITHUB_TOKEN", "test-github-token")
os.environ.setdefault("GITHUB_REPO", "testuser/superset")
os.environ.setdefault("WEBHOOK_SECRET", "testsecret")
os.environ.setdefault("DEVIN_BASE_URL", "https://api.devin.ai/v1")

from app.main import app  # noqa: E402 — must come after env setup
from app import store     # noqa: E402


@pytest.fixture
async def client():
    """Async HTTP client wired directly to the FastAPI app. No live server needed."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as c:
        yield c


@pytest.fixture(autouse=True)
def reset_store():
    """Automatically wipe in-memory state before and after every test."""
    store.clear()
    yield
    store.clear()
```

### tests/test_main.py

```python
async def test_health_returns_ok(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "timestamp" in data
```

---

## Acceptance Criteria

- [ ] `docker-compose up` builds and starts with zero errors
- [ ] `curl http://localhost:8000/health` returns `{"status": "ok", "timestamp": "..."}`
- [ ] `curl http://localhost:8000/docs` returns 200 (FastAPI Swagger UI)
- [ ] All five variables present in `.env.example`
- [ ] `pytest tests/test_main.py` passes (1 test)

**Do not proceed to Task 2 until every item above is confirmed.**
