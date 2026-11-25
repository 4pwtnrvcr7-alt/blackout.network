#!/bin/bash
# Idempotent starter for the live Web Push sender (feed loop + notifier loop). Safe: no scanner, no render_sync push, no start.sh.
# Sends only for stories that cross the bar after the notifier's state.db started_at (set it to now by hand after a long outage to skip the back-catalogue).
cd /workspace/launch/webpush
pgrep -f "bn_webpush_feed.py loop" >/dev/null || { nohup setsid nice -n 10 python3 bn_webpush_feed.py loop >> /workspace/webpush_box/feed.out 2>&1 & }
pgrep -f "bn_webpush_run.py loop" >/dev/null || { nohup setsid nice -n 10 /workspace/.webpushenv/bin/python bn_webpush_run.py loop >> /workspace/webpush_box/run.out 2>&1 & }
sleep 2; pgrep -fa "bn_webpush_(feed|run).py loop" | cut -c1-80
