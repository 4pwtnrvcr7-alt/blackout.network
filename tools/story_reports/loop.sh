#!/bin/bash
# Story-report refresh (t1276u). Every 30 min: rebuild data/story_reports.json from the newsletter analyst notes + public
# /api/state, then push only that one file to Render (signed). Never runs render_sync cycle/once/loop, never touches blackout.db.
# Start (from a shell that has the sync env, same as public_stats_loop.sh):
#   nohup /workspace/launch/story_reports/loop.sh >> /workspace/launch/story_reports/loop.out 2>&1 &
# Stop: pkill -f /workspace/launch/story_reports/loop.sh
D=/workspace/launch/story_reports
LOG=$D/story_reports.log
mkdir -p $D/data
while true; do
  {
    echo "[$(date -u +%FT%TZ)] cycle start"
    timeout 600 python3 $D/build.py --out $D/data/story_reports.json --cache $D/net_cache.json
    echo "build exit=$?"
    timeout 120 python3 $D/push.py --src $D/data/story_reports.json
    echo "push exit=$?"
  } >> "$LOG" 2>&1
  sleep 1800
done
