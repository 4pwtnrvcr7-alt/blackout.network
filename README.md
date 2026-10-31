# blackout.network

**The world's threats, scored and sourced, before cable news catches up.**

blackout.network is a free public early-warning and research utility. It gathers reports on conflict, disasters,
outbreaks, unrest, space weather and aviation activity from public sources, scores each event for severity and
confirmation, and links every item back to its sources.

## What this repository is

This is the **read-only public web node** that serves the dashboard at https://blackout.network. It contains the
dashboard pages (HTML/CSS/JS), charts, maps, guides, source links and the small Python web server that serves them.

It does **not** contain any alert data, databases, admin tools or credentials. The scanning and scoring run on a
separate scanner node, which pushes fresh data to this site over a signed HTTPS channel (`/internal/sync/*`).
Until the first push arrives, the site shows a short "Syncing" page.

## How it runs

- Hosted as a Docker web service (see `render.yaml` and `Dockerfile`); entry point `python3 render_app.py` in `app/`.
- Health check: `/healthz`. Sync status: `/api/status`.
- One environment variable must be set on the host, never in this repository:
  - `BN_SYNC_SECRET`: the shared secret used to verify pushes from the scanner node.
- `PORT` is provided by the host.
- The public node is read-only: scan controls, alert settings and admin functions are not available here.

## Reporting a problem

Every page has a **Report a problem** button (bottom left), and each alert card has a small flag that pre-fills the item.
Before sending, the visitor sees exactly what will be sent: their category and description, the page address without any
query string, the dashboard tab, time, browser user agent, window size, language, time zone, site build, the last scan time
on screen and up to 10 recent script error messages. No cookies, form contents or IP addresses are stored (only a
daily-rotating anonymous hash used for rate limiting).

- `POST /api/report` stores the report in a small queue on this node; the scanner node collects it within about a minute
  over the signed channel (`/api/reports/pull`, `/api/reports/ack`) and pushes back each report's public status
  (`/api/reports/status`). The host's disk is ephemeral, so a report sent seconds before a restart can be lost.
- `/report-status` (and `/report-status/<ID>`) shows one report by its unguessable reference ID: what was sent, queue
  position, status, the published response and a timeline. There is no listing or search; lookups are rate-limited.
- Review, triage and replies happen on the scanner node, not here. Public replies are published only after a second
  person reviews them.

## Repository layout

```
Dockerfile        container build for the public node
render.yaml       Render blueprint (free web service)
requirements.txt  Python dependencies
app/              web server, add-on modules, dashboard and static assets
                  (reports.py + reports_static/: problem-report widget and status page; usage_stats.py: aggregate traffic counts)
```
