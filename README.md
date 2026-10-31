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

## Repository layout

```
Dockerfile        container build for the public node
render.yaml       Render blueprint (free web service)
requirements.txt  Python dependencies
app/              web server, add-on modules, dashboard and static assets
```
