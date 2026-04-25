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
from app.webhook import router as webhook_router

app = FastAPI(title="Devin Remediation Control Plane")
app.include_router(webhook_router)


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}
