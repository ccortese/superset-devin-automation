# Task 10 — README & Final Verification

**Previous task:** `tasks/task9.md`  
**Next task:** None — this is the final task.

---

## Goal

Write `README.md` and run the complete end-to-end verification checklist. The project is not complete until every item on the checklist is checked off.

---

## Files to Create

```
README.md
```

---

## Implementation

### README.md

Write the README with exactly these sections and content:

```markdown
# Superset Devin Vulnerability Remediation

Event-driven control plane that automatically remediates GitHub security issues using Devin AI.

When an issue in the Superset fork is labeled `devin-remediate`, the system:
1. Receives a GitHub webhook event
2. Creates a Devin AI session with full issue context
3. Polls until the session completes
4. Posts the resulting PR link back to the issue as a comment
5. Updates the observability dashboard in real time

## Architecture

​```
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
​```

## Quick Start

​```bash
git clone https://github.com/YOUR_USERNAME/superset-devin-automation.git
cd superset-devin-automation
cp .env.example .env
# Edit .env — fill in DEVIN_API_KEY, GITHUB_TOKEN, GITHUB_REPO, WEBHOOK_SECRET
docker-compose up
​```

Open http://localhost:8000/dashboard

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

​```bash
./scripts/simulate_webhook.sh 1 "[SECURITY] SQL injection risk"
​```

Then check the dashboard and API:

​```bash
curl http://localhost:8000/api/sessions
curl http://localhost:8000/api/analytics
curl http://localhost:8000/api/events
​```

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

Values in `.env` are populated from Devin's shell state using `$VAR_NAME` syntax. Set these in your Devin secrets store before running.

| Variable | Secret Reference | Description |
|---|---|---|
| `DEVIN_API_KEY` | `$DEVIN_API_KEY` | From [app.devin.ai/settings/api](https://app.devin.ai/settings/api) |
| `GITHUB_TOKEN` | `$GITHUB_TOKEN` | GitHub PAT with `repo` scope |
| `GITHUB_REPO` | `$GITHUB_REPO` | Format: `username/superset` |
| `WEBHOOK_SECRET` | `$WEBHOOK_SECRET` | Must match the secret set in your GitHub webhook |
| `DEVIN_BASE_URL` | Optional | Default: `https://api.devin.ai/v1` |

## Related Repositories

- **This repo:** Automation control plane
- **[YOUR_USERNAME/superset](https://github.com/YOUR_USERNAME/superset):** Forked Apache Superset with security issues
```

---

## Final Verification Checklist

Run every item below. **The project is complete only when every item is checked off.**

### Docker

- [ ] `docker-compose up` builds and starts with zero errors
- [ ] `curl http://localhost:8000/health` returns `{"status": "ok", "timestamp": "..."}`
- [ ] `curl http://localhost:8000/docs` returns HTTP 200

### Webhook

- [ ] `./scripts/simulate_webhook.sh` returns `{"status": "accepted", "issue": 1}`
- [ ] `WEBHOOK_SECRET=wrong ./scripts/simulate_webhook.sh` returns HTTP 403

### API

- [ ] `curl http://localhost:8000/api/sessions` returns a list containing the session from the simulate script
- [ ] `curl http://localhost:8000/api/analytics` response body includes `"devin_api_stats"` key
- [ ] `curl http://localhost:8000/api/events` returns a list containing a `webhook_received` event

### Dashboard

- [ ] `http://localhost:8000/dashboard` renders in browser with no console errors
- [ ] KPI cards show real numbers (not `—`) after the simulate script has been run
- [ ] Active sessions table shows the simulated session with a pulsing green indicator
- [ ] "Last updated" timestamp in the header updates automatically every 15 seconds

### Tests

- [ ] `pytest tests/ -v` — all tests pass, zero failures, zero errors

---

**The project is complete only when every item above is checked off.**
