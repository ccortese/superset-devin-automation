# Superset Devin Vulnerability Remediation

Event-driven control plane that automatically remediates GitHub security issues using Devin AI.

When an issue in the Superset fork is labeled `devin-remediate`, the system:
1. Receives a GitHub webhook event
2. Creates a Devin AI session with full issue context
3. Polls until the session completes
4. Posts the resulting PR link back to the issue as a comment
5. Updates the observability dashboard in real time

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
│  store.py         SQLite-backed session + event state
│  analytics.py     aggregates store + Devin Analytics API
│  api.py           GET /api/* endpoints for the dashboard
│  dashboard/       single-page HTML UI, auto-refreshes
└──────────────────────────────────┘
         │
         ▼
   docker-compose up  (only command needed)
```

## Running Locally

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- A [Devin API key](https://app.devin.ai/settings/api)
- A GitHub Personal Access Token with `repo` scope
- (Optional) [ngrok](https://ngrok.com/) for receiving live webhooks during local development

### 1. Clone and configure

```bash
git clone https://github.com/ccortese/superset-devin-automation.git
cd superset-devin-automation
cp .env.example .env
```

Edit `.env` and fill in the required values:

```env
DEVIN_API_KEY=<your Devin API key>
GITHUB_TOKEN=<your GitHub PAT>
GITHUB_REPO=ccortese/superset
WEBHOOK_SECRET=<a random secret string>
```

### 2. Build and start

```bash
docker compose build
docker compose up -d
```

### 3. Verify it's running

```bash
curl http://localhost:8000/health
# → {"status":"ok","timestamp":"..."}
```

Open the dashboard at **http://localhost:8000/dashboard**.

### 4. Rebuild after pulling updates

```bash
git pull origin main
docker compose down
docker compose build
docker compose up -d
```

### 5. Reset the database (optional)

To wipe all session and event data and start fresh:

```bash
docker compose down -v
docker compose up -d
```

The `-v` flag removes the Docker volume that persists the SQLite database.

## Register the GitHub Webhook

1. Go to your Superset fork → **Settings → Webhooks → Add webhook**
2. **Payload URL:** your server URL + `/webhook`
   - For local dev: run `ngrok http 8000` and use the `https://` ngrok URL
3. **Content type:** `application/json`
4. **Secret:** same value as `WEBHOOK_SECRET` in your `.env`
5. **Events:** select "Issues"
6. Click **Add webhook**

To trigger a remediation: open any issue in your Superset fork and apply the `devin-remediate` label.

## Test Locally (No GitHub Needed)

```bash
WEBHOOK_SECRET=<your secret> ./scripts/simulate_webhook.sh 1 "[SECURITY] SQL injection risk"
```

Then check the dashboard and API:

```bash
curl http://localhost:8000/api/sessions
curl http://localhost:8000/api/analytics
curl http://localhost:8000/api/events
```

## Running Tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

All 56 tests should pass. Tests mock all external HTTP calls (Devin API, GitHub API) so no credentials are needed.

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| POST | `/webhook` | GitHub webhook receiver |
| GET | `/dashboard` | Observability UI |
| GET | `/api/sessions` | All remediation sessions |
| GET | `/api/sessions/{id}` | Single session detail |
| GET | `/api/analytics` | Analytics summary (includes Devin API data) |
| GET | `/api/events` | Event log (last 50) |
| GET | `/health` | Health check |
| GET | `/docs` | FastAPI auto-docs |

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DEVIN_API_KEY` | Yes | Devin API key from [app.devin.ai/settings/api](https://app.devin.ai/settings/api) |
| `GITHUB_TOKEN` | Yes | GitHub PAT with `repo` scope |
| `GITHUB_REPO` | Yes | Target repository, e.g. `ccortese/superset` |
| `WEBHOOK_SECRET` | Yes | HMAC secret — must match the secret configured in your GitHub webhook |
| `DEVIN_BASE_URL` | No | Default: `https://api.devin.ai/v1` |
| `DB_PATH` | No | SQLite database path. Default: `data/store.db` |

## Remediated Vulnerabilities (Merged PRs on [ccortese/superset](https://github.com/ccortese/superset))

These pull requests were automatically created by the control plane via Devin AI sessions and merged into the Superset fork:

| PR | CVE / Issue | Vulnerability | Fix |
|---|---|---|---|
| [#27](https://github.com/ccortese/superset/pull/27) | [CVE-2023-46104](https://github.com/ccortese/superset/issues/24) | ZIP bomb DoS via malicious import | Added max entry count, total size limit, and blocked file extension checks to `check_is_safe_zip()` |
| [#31](https://github.com/ccortese/superset/pull/31) | [CVE-2024-53948](https://github.com/ccortese/superset/issues/20) | SQL injection in Row Level Security `clause` field | Added `validate_rls_clause()` that rejects subqueries, UNIONs, stacked statements, and DML/DDL via sqlglot AST analysis |
| [#33](https://github.com/ccortese/superset/pull/33) | [CVE-2024-53951](https://github.com/ccortese/superset/issues/23) | Ownership takeover of dashboards and charts | Added `validate_owners_update()` requiring existing ownership before modifying the owners list |
| [#34](https://github.com/ccortese/superset/pull/34) | [CVE-2024-53949](https://github.com/ccortese/superset/issues/22) | SQL function denylist bypass via inline block comments | Added `strip_sql_block_comments()` to normalize SQL before denylist matching |
| [#36](https://github.com/ccortese/superset/pull/36) | [#35](https://github.com/ccortese/superset/issues/35) | Missing CSRF token validation documentation | Added documentation comment explaining why `WTF_CSRF_ENABLED` must remain enabled |

## Related Repositories

- **This repo:** Automation control plane
- **[ccortese/superset](https://github.com/ccortese/superset):** Forked Apache Superset with security issues

## Data Persistence

Session and event data is stored in a SQLite database at `data/store.db` (configurable via `DB_PATH`). The Docker volume `db-data` ensures data survives container restarts.

## Duplicate Prevention

If a webhook arrives for an issue that already has a session, it is silently ignored (returns `{"status": "ignored", "reason": "session already exists for issue #N"}`). This prevents duplicate Devin sessions and wasted API calls.
