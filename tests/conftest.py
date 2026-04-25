import os

import httpx
import pytest

# Force-set env vars before any app module is imported.
# Using direct assignment (not setdefault) so tests always use known values,
# even when real secrets are present in the shell environment.
os.environ["DEVIN_API_KEY"] = "test-devin-key"
os.environ["GITHUB_TOKEN"] = "test-github-token"
os.environ["GITHUB_REPO"] = "testuser/superset"
os.environ["WEBHOOK_SECRET"] = "testsecret"
os.environ["DEVIN_BASE_URL"] = "https://api.devin.ai/v1"

from app.main import app  # noqa: E402 — must come after env setup
from app import store     # noqa: E402
from app import webhook   # noqa: E402
from app import devin_client  # noqa: E402
from app import github_client  # noqa: E402

# Ensure module-level variables match the test env vars.
# These are loaded at import time and won't pick up os.environ changes.
webhook.WEBHOOK_SECRET = "testsecret"
devin_client.DEVIN_API_KEY = "test-devin-key"
devin_client.DEVIN_BASE_URL = "https://api.devin.ai/v1"
devin_client.GITHUB_REPO = "testuser/superset"
github_client.GITHUB_TOKEN = "test-github-token"
github_client.GITHUB_REPO = "testuser/superset"


@pytest.fixture
async def client():
    """Async HTTP client wired directly to the FastAPI app. No live server needed."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture(autouse=True)
def reset_store():
    """Automatically wipe in-memory state before and after every test."""
    store.clear()
    yield
    store.clear()
