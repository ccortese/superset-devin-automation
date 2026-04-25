# Task 8 — Observability Dashboard

**Previous task:** `tasks/task7.md`  
**Next task:** `tasks/task9.md`

---

## Goal

Build `app/dashboard/index.html` — a single self-contained file with no external CDN dependencies. Vanilla HTML, CSS, and JavaScript only. Auto-refreshes every 15 seconds.

---

## Files to Create

```
app/dashboard/index.html
```

No test file for this task — verification is manual in the browser.

---

## Implementation

### app/dashboard/index.html

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Devin Remediation Dashboard</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      background: #0d1117;
      color: #c9d1d9;
      font-family: system-ui, -apple-system, sans-serif;
      font-size: 14px;
      padding: 24px;
    }

    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
    }

    header h1 { font-size: 20px; color: #f0f6fc; }
    #last-updated { font-size: 12px; color: #8b949e; }

    .kpi-row {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 16px;
      margin-bottom: 32px;
    }

    .kpi-card {
      background: #161b22;
      border: 1px solid #30363d;
      border-radius: 8px;
      padding: 16px;
    }

    .kpi-card .label { font-size: 12px; color: #8b949e; margin-bottom: 8px; }
    .kpi-card .value { font-size: 28px; font-weight: 600; color: #f0f6fc; }

    section { margin-bottom: 32px; }

    section h2 {
      font-size: 12px;
      font-weight: 600;
      color: #8b949e;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 12px;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      background: #161b22;
      border: 1px solid #30363d;
      border-radius: 8px;
      overflow: hidden;
    }

    th {
      background: #21262d;
      padding: 10px 16px;
      text-align: left;
      font-size: 12px;
      color: #8b949e;
      font-weight: 600;
    }

    td { padding: 10px 16px; border-top: 1px solid #30363d; }
    tr:hover td { background: #1c2128; }

    a { color: #58a6ff; text-decoration: none; }
    a:hover { text-decoration: underline; }

    .status-running {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      color: #3fb950;
    }

    .pulse {
      width: 8px;
      height: 8px;
      background: #3fb950;
      border-radius: 50%;
      animation: pulse 1.5s ease-in-out infinite;
    }

    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.3; }
    }

    .badge-success { color: #3fb950; font-weight: 600; }
    .badge-failed  { color: #f85149; font-weight: 600; }

    #event-log {
      background: #161b22;
      border: 1px solid #30363d;
      border-radius: 8px;
      padding: 12px 16px;
      max-height: 200px;
      overflow-y: auto;
      font-family: monospace;
      font-size: 12px;
    }

    .event-entry {
      padding: 4px 0;
      border-bottom: 1px solid #21262d;
      color: #8b949e;
    }

    .event-entry:last-child { border-bottom: none; }
    .event-entry .ts { color: #484f58; margin-right: 8px; }
    .event-entry .type { color: #58a6ff; margin-right: 8px; }

    .empty {
      color: #484f58;
      padding: 16px;
      text-align: center;
      font-style: italic;
      display: block;
    }
  </style>
</head>
<body>

<header>
  <h1>🛡️ Devin Vulnerability Remediation</h1>
  <span id="last-updated">Loading...</span>
</header>

<div class="kpi-row">
  <div class="kpi-card">
    <div class="label">Total Sessions</div>
    <div class="value" id="kpi-total">—</div>
  </div>
  <div class="kpi-card">
    <div class="label">Success Rate</div>
    <div class="value" id="kpi-success-rate">—</div>
  </div>
  <div class="kpi-card">
    <div class="label">Avg Duration (min)</div>
    <div class="value" id="kpi-avg-duration">—</div>
  </div>
  <div class="kpi-card">
    <div class="label">PRs Opened</div>
    <div class="value" id="kpi-prs">—</div>
  </div>
</div>

<section>
  <h2>Active Sessions</h2>
  <table>
    <thead>
      <tr>
        <th>Issue</th>
        <th>Started</th>
        <th>Status</th>
      </tr>
    </thead>
    <tbody id="active-tbody">
      <tr><td colspan="3"><span class="empty">No active sessions</span></td></tr>
    </tbody>
  </table>
</section>

<section>
  <h2>Completed Remediations</h2>
  <table>
    <thead>
      <tr>
        <th>Issue</th>
        <th>Pull Request</th>
        <th>Duration</th>
        <th>Result</th>
      </tr>
    </thead>
    <tbody id="completed-tbody">
      <tr><td colspan="4"><span class="empty">No completed sessions</span></td></tr>
    </tbody>
  </table>
</section>

<section>
  <h2>Event Log</h2>
  <div id="event-log"><span class="empty">No events yet</span></div>
</section>

<script>
  function fmtTime(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleTimeString();
  }

  function fmtDuration(startIso, endIso) {
    if (!startIso || !endIso) return '—';
    const mins = ((new Date(endIso) - new Date(startIso)) / 60000).toFixed(1);
    return `${mins} min`;
  }

  async function fetchJSON(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`${url} returned ${r.status}`);
    return r.json();
  }

  async function refresh() {
    try {
      const [sessions, analytics, events] = await Promise.all([
        fetchJSON('/api/sessions'),
        fetchJSON('/api/analytics'),
        fetchJSON('/api/events'),
      ]);

      // KPI cards
      document.getElementById('kpi-total').textContent = analytics.total ?? '—';
      document.getElementById('kpi-success-rate').textContent =
        analytics.success_rate != null ? `${analytics.success_rate}%` : '—';
      document.getElementById('kpi-avg-duration').textContent =
        analytics.avg_duration_minutes ?? '—';
      document.getElementById('kpi-prs').textContent = analytics.prs_opened ?? '—';

      // Active sessions
      const active = sessions.filter(s => s.status === 'running');
      const activeTbody = document.getElementById('active-tbody');
      if (active.length === 0) {
        activeTbody.innerHTML = '<tr><td colspan="3"><span class="empty">No active sessions</span></td></tr>';
      } else {
        activeTbody.innerHTML = active.map(s => `
          <tr>
            <td><a href="${s.issue_url}" target="_blank">#${s.issue_number} ${s.issue_title}</a></td>
            <td>${fmtTime(s.started_at)}</td>
            <td><span class="status-running"><span class="pulse"></span>running</span></td>
          </tr>
        `).join('');
      }

      // Completed sessions
      const done = sessions.filter(s => s.status === 'finished' || s.status === 'failed');
      const doneTbody = document.getElementById('completed-tbody');
      if (done.length === 0) {
        doneTbody.innerHTML = '<tr><td colspan="4"><span class="empty">No completed sessions</span></td></tr>';
      } else {
        doneTbody.innerHTML = done.map(s => `
          <tr>
            <td><a href="${s.issue_url}" target="_blank">#${s.issue_number} ${s.issue_title}</a></td>
            <td>${s.pr_url
              ? `<a href="${s.pr_url}" target="_blank">View PR →</a>`
              : '—'
            }</td>
            <td>${fmtDuration(s.started_at, s.finished_at)}</td>
            <td>${s.status === 'finished'
              ? '<span class="badge-success">✅ Fixed</span>'
              : '<span class="badge-failed">❌ Failed</span>'
            }</td>
          </tr>
        `).join('');
      }

      // Event log
      const logEl = document.getElementById('event-log');
      if (events.length === 0) {
        logEl.innerHTML = '<span class="empty">No events yet</span>';
      } else {
        logEl.innerHTML = events.map(e => `
          <div class="event-entry">
            <span class="ts">${fmtTime(e.created_at)}</span>
            <span class="type">[${e.type}]</span>
            ${e.message}
          </div>
        `).join('');
      }

      document.getElementById('last-updated').textContent =
        `Last updated: ${new Date().toLocaleTimeString()}`;

    } catch (err) {
      console.error('Dashboard refresh failed:', err);
    }
  }

  // Initial load + auto-refresh every 15 seconds
  refresh();
  setInterval(refresh, 15000);
</script>

</body>
</html>
```

---

## Acceptance Criteria

Verify these manually in a browser after running `docker-compose up`:

- [ ] `GET /dashboard` returns HTTP 200 with `text/html` content type
- [ ] Page loads with no JavaScript errors in the browser console
- [ ] KPI cards show `—` on initial load, then populate after first fetch
- [ ] Active Sessions table shows a pulsing green dot for `status == "running"`
- [ ] Completed table shows "View PR →" as a clickable link when `pr_url` is set
- [ ] Completed table shows ✅ for `"finished"` and ❌ for `"failed"`
- [ ] "Last updated" timestamp in the header updates every 15 seconds
- [ ] Run `./scripts/simulate_webhook.sh` then refresh — a new running session appears

**Do not proceed to Task 9 until manually verified in a browser with `docker-compose up`.**
