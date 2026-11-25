# Web Push sender (box side)

Render stores subscriptions (`webpush.db`, Render-owned) and serves the Alerts panel and `/sw.js`. It never sends and never holds the
VAPID private key. The box sends, with `/workspace/blackout/webpush_notifier.py` (unmodified), fed by two local files:

- `bn_webpush_feed.py loop` (every 30 s): pulls Render's `webpush.db` over the signed `GET /internal/sync/pull` (read-only) to
  `/workspace/webpush_box/render_subs.db`, and builds `live_clusters.db` from the public `/api/state` (rank, high_at, eff_families).
- `bn_webpush_run.py loop`: imports the notifier and points it at those two files. Rules unchanged: Major = rank 7+ with 2+ source
  families, All = rank 5+, 6 per hour per subscriber, one per story, only stories after signup and after the sender started.
- `run_webpush_live.sh`: idempotent starter, also called from `/workspace/launch/social/ensure_loops.sh`.

Why this exists: the box's own `blackout.db` stopped being the live Wire (Render owns it), `run_webpush.sh` died in early November and
nothing restarted it, so no push was sent after Nov 7. State and logs: `/workspace/webpush_box/` (`webpush.log`, `feed.log`, `state.db`).
Never run `render_sync` push, `start.sh`, a scanner or `newsletter_worker.py` for this. Check: `pgrep -fa bn_webpush`, `tail /workspace/webpush_box/webpush.log`.
Copy kept here for version control; the running copy is `/workspace/launch/webpush/`.
