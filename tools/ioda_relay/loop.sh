#!/bin/bash
# IODA relay (Nov 24 2026): every 10 min build the IODA snapshot on the box and push only data/ioda_relay.json to Render
# (signed one-file push, same channel as meshtastic/story_reports). Non-posting. Never runs render_sync cycle/once/loop.
# Stop: pkill -f /workspace/launch/ioda_relay/loop.sh
D=/workspace/launch/ioda_relay
while true; do
  { echo "[$(date -u +%FT%TZ)]"; timeout 240 python3 $D/collect.py; echo "collect exit=$?"; timeout 120 python3 $D/push.py --src $D/data/ioda_relay.json; echo "push exit=$?"; } >> $D/relay.log 2>&1
  sleep 600
done
