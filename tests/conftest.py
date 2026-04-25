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
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture(autouse=True)
def reset_store():
    """Automatically wipe in-memory state before and after every test."""
    store.clear()
    yield
    store.clear()
