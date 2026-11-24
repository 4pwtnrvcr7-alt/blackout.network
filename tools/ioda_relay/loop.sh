#!/bin/bash
# IODA relay (Nov 24 2026): every 10 min build the IODA snapshots on the box (Internet layer + the IODA data behind
# /api/netmap/data); every 2 min make sure Render has the latest data/ioda_relay.json and data/ioda_relay_data.json
# (a Render redeploy wipes pushed data; push*.py only send when Render's copy is missing or different).
# Signed one-file pushes, same channel as meshtastic/story_reports. Non-posting. Never runs render_sync cycle/once/loop.
# Stop: pkill -f /workspace/launch/ioda_relay/loop.sh
D=/workspace/launch/ioda_relay
i=0
while true; do
  {
    if [ $((i % 5)) -eq 0 ]; then
      echo "[$(date -u +%FT%TZ)]"
      timeout 240 python3 $D/collect.py; echo "collect exit=$?"
      timeout 240 python3 $D/collect_data.py; echo "collect_data exit=$?"
    fi
    timeout 120 python3 $D/push.py --src $D/data/ioda_relay.json | grep -v "skip (Render has"
    timeout 120 python3 $D/push_data.py --src $D/data/ioda_relay_data.json | grep -v "skip (Render has"
  } >> $D/relay.log 2>&1
  i=$((i + 1)); sleep 120
done
