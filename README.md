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

## Link checks (required before every push)

Every link on the site must work **and** go where its label says. Two tools enforce it:

- **Pre-publish gate:** run `tools/prepublish.sh` before pushing to `main` (or install it as a hook:
  `ln -sf ../../tools/prepublish.sh .git/hooks/pre-push`). It compiles the Python and runs `tools/linkcheck.py gate`, which
  checks every URL added or changed by the commits being pushed (plus staged/unstaged edits). It **fails** on a dead link
  (404/410, a host that does not exist, a redirect loop) or a soft 404 (redirected to a homepage or error page, or a title/heading
  that says "not found"), and on any URL already flagged dead. Bot-blocked links (401/403/429/999, challenge pages) are rechecked
  in a real headless Chromium and reported as *unverified*; landing pages whose title/host share nothing with the link's label
  are reported as *mismatch*. Both are warnings; `--strict` makes them failures.
- **Full crawl / nightly:** `tools/linkcheck.py collect --base <site>` renders every page and every dashboard tab with
  Playwright (accordions opened, lists scrolled, "show more" pressed) and collects every rendered link plus every URL in the JSON
  the pages load (sources, preppers, broadcasts, government, gun laws, midterms, ...) and a rotating sample of the global Sources
  directory; `tools/linkcheck.py check --inv inventory.json` checks them (real browser User-Agent, GET, redirects followed).
  The scanner node runs `tools/linkcheck.py nightly` at about 3:30 AM ET: it writes `linkcheck_report.json` and
  `linkcheck_dead.json`. A link that is dead two runs in a row gets a data-level `dead` flag (never deleted); the flags sync to
  the site, `/api/linkcheck/dead` serves them and `/linkguard.js` hides those links on every page (a row that is only the link is
  hidden, a link inside text becomes plain text). The flag clears as soon as a run finds the link working.
- Quick check of specific URLs: `tools/linkcheck.py url https://example.org/a https://example.org/b`.
