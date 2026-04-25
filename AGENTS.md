# AGENTS.md

This file contains the working conventions for any AI agent operating in this repository. Read it before touching any file.

---

## What This Repo Is

A lightweight event-driven control plane that automatically triggers Devin AI to remediate GitHub security issues. The full implementation spec lives in `PROJECT.md`. This file governs *how* you work, not *what* you build.

---

## General Rules

- **Read `PROJECT.md` in full before writing any code.** It contains the task list, acceptance criteria, and the order of operations. Do not skip ahead.
- **Complete one task at a time.** Do not start the next task until the current task's acceptance criteria are fully met and its tests pass.
- **Commit after every completed task.** Use the format: `task(N): <short description>` e.g. `task(2): implement webhook handler`.
- **Never hardcode secrets.** All credentials and config come from environment variables via `.env`.
- **Keep it simple.** If two approaches solve the problem, choose the simpler one. This is an MVP.

---

## Code Conventions

- **Language:** Python 3.11
- **Framework:** FastAPI with async handlers throughout
- **HTTP client:** `httpx` with `AsyncClient` — never use `requests`
- **Config:** Load all env vars at module level using `os.getenv()` with `python-dotenv`
- **Error handling:** Log errors and continue — never let a background task crash the process silently
- **Persistence:** Session and event state is stored in SQLite (`data/store.db`) using Python's stdlib `sqlite3`. Do not add heavier databases (Postgres, MySQL, etc.) or ORMs.
- **No external dependencies beyond what is in `requirements.txt`.** Do not add packages without updating that file.

---

## File Conventions

- One responsibility per module — don't let files grow beyond ~100 lines
- All application code lives under `app/`
- Tests live under `tests/` and mirror the `app/` structure (e.g. `tests/test_webhook.py`)
- Scripts live under `scripts/` and must be executable (`chmod +x`)

---

## Testing

- Use `pytest` with `pytest-asyncio` for all async tests
- Use `httpx.AsyncClient` with FastAPI's `app` directly for endpoint tests — no live server needed
- Mock all external HTTP calls (Devin API, GitHub API) using `respx` or `unittest.mock`
- Every task in `PROJECT.md` specifies which tests must pass before moving on — write those tests, run them, then proceed

---

## Docker

- The only command needed to run the system is `docker-compose up`
- A named Docker volume (`db-data`) is mounted at `/app/data` to persist the SQLite database across container restarts
- The image must build cleanly from scratch with no errors
- `GET /health` must return 200 for the Docker healthcheck to pass

---

## Commit Checklist (before marking any task done)

- [ ] Acceptance criteria from `PROJECT.md` are fully met
- [ ] All tests for this task pass: `pytest tests/`
- [ ] No secrets in code
- [ ] `docker-compose up` still starts cleanly
- [ ] Changes committed with the correct message format
