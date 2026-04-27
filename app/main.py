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

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import router as api_router
from app.devin_client import resume_active_sessions
from app.webhook import router as webhook_router

# ---------------------------------------------------------------------------
# CSRF / request-forgery protection
# ---------------------------------------------------------------------------
# FastAPI does not include built-in CSRF middleware. This application relies
# on the following controls instead:
#
# 1. **Webhook endpoint (POST /webhook)** – Every incoming request is
#    validated against an HMAC-SHA256 signature derived from WEBHOOK_SECRET.
#    See webhook.py `_verify_signature()`. Without the shared secret an
#    attacker cannot forge a valid request, which provides equivalent
#    protection to a CSRF token for this endpoint.
#
# 2. **API endpoints (GET /api/*)** – All API routes are read-only GET
#    requests that do not mutate state, so they are not susceptible to
#    CSRF attacks.
#
# 3. **Dashboard (GET /dashboard)** – Serves a static HTML page with no
#    form submissions and no cookie-based authentication, so CSRF is not
#    applicable.
#
# If mutating (POST/PUT/DELETE) API routes are added in the future, a
# proper CSRF middleware (e.g. starlette-csrf) or token-based auth header
# requirement should be introduced.
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Resume monitoring for any sessions that were running before a restart."""
    await resume_active_sessions()
    yield


app = FastAPI(title="Devin Remediation Control Plane", lifespan=lifespan)

app.include_router(webhook_router)
app.include_router(api_router)

# Serve static assets (CSS, JS if ever separated) under /static
app.mount("/static", StaticFiles(directory="app/dashboard"), name="static")


@app.get("/dashboard", include_in_schema=False)
async def dashboard():
    """Serve the single-page observability dashboard."""
    return FileResponse("app/dashboard/index.html")


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}
