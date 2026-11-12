#!/bin/bash
# Meshtastic public-node refresh (BLACKOUT.NETWORK /mesh). NOT STARTED BY THIS PATCH: Matt/CoS start it after deploy.
# Every 10 min: one GET of meshmap.net/nodes.json (conditional, descriptive UA) -> data/mesh_nodes.json, then push only that one
# file to Render (signed, same channel as story_reports). Never runs render_sync cycle/once/loop, never touches blackout.db.
# Start (from a shell that has the sync env):
#   mkdir -p /workspace/launch/meshtastic && cp tools/meshtastic/*.py tools/meshtastic/loop.sh /workspace/launch/meshtastic/ && mkdir -p /workspace/launch/meshtastic/geo/{gridstatus_static,signal_map_static} && cp app/gridstatus_static/sections.geojson /workspace/launch/meshtastic/geo/gridstatus_static/ && cp app/signal_map_static/world.geojson /workspace/launch/meshtastic/geo/signal_map_static/ && cp app/render_rules.py /workspace/launch/meshtastic/render_rules.py
#   nohup /workspace/launch/meshtastic/loop.sh >> /workspace/launch/meshtastic/loop.out 2>&1 &
# Stop: pkill -f /workspace/launch/meshtastic/loop.sh
D=${BN_MESH_DIR:-/workspace/launch/meshtastic}
LOG=$D/mesh.log
mkdir -p $D/data
while true; do
  {
    timeout 180 python3 $D/collect.py --out $D/data/mesh_nodes.json --state $D/state.json
    echo "collect exit=$?"
    timeout 120 python3 $D/push.py --src $D/data/mesh_nodes.json
    echo "push exit=$?"
  } >> "$LOG" 2>&1
  sleep 600
done
