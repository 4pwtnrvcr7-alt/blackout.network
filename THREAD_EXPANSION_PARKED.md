# The Thread expansion — PARKED (2026-10-31, per Matt t206)
Status: builder written and run once locally (14,221 nodes / 54,127 edges, 30-day window). NOT wired into the site:
no route in addons.py, no front end, no loop started, never pushed to main, thread_graph.json not in the sync allowlist.
Files: thread_graph.py (builder + /api/thread_graph handler), thread_graph_*.json (one local build), thread_cache/ (raw public-feed cache).
Git: branch `thread-expansion-parked` on GitHub (code only, no data).
To resume: add "/api/thread_graph": "thread_graph" to addons.py ROUTES, add "thread_graph.json" to render_rules.SYNC_JSON (both copies),
write thread_static/app.js + app.css (canvas renderer), run `python3 thread_graph.py loop`, then re-enable The Thread (THREAD_ENABLED).
Known follow-ups: CISA advisory RSS dates use 2-digit years (parse_t misses them); 5 MB JSON is heavy for phones (cap/slim before shipping).
