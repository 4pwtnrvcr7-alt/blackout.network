# Meshtastic integration: rollback

The patch is one commit on top of the story-reports commit. Nothing is started by deploying it.

## Undo the code
- `git revert <meshtastic commit>` on main, then push following the deploy checklist (one push per hour).
- Or revert just these files: addons.py, sitenav.py, sitenav_ui.py, growth.py, growth_static/app.js and dashboard.html. The new files (app/meshnet*, tools/meshtastic, docs/meshtastic, app/tests/test_meshnet.py) can stay; they do nothing once unrouted.
- Fast kill without a revert: remove the two "/mesh" and "/api/mesh" lines from addons.py ROUTES. The menu and share button would then go to 404, so a full revert is cleaner.

## Stop the data
- Stop the box loop: `pkill -f /workspace/launch/meshtastic/loop.sh`
- Without new data, the pages show a "feed stale" state after 20 minutes, and /api/mesh/signal returns no signals. To blank them right away, push an empty file: `echo '{}' > /workspace/launch/meshtastic/data/mesh_nodes.json && python3 /workspace/launch/meshtastic/push.py`

## Public chat feed
- It is OFF by default and stays off unless the Render env `BN_MESH_PUBLIC_FEED=liamcottle` is set. To turn it off, unset the variable.

## Client-side features
- Live Chat and Push to Mesh run in the visitor's browser on their own radio. Removing the routes, or the bng-mesh button in growth.py, disables them. Nothing on the server needs cleanup.

## Start after deploy (only once Matt approves)
1. Run the install steps in the header of tools/meshtastic/loop.sh. They copy collect.py, push.py, loop.sh, the geojson and render_rules.py to /workspace/launch/meshtastic.
2. `chmod +x /workspace/launch/meshtastic/loop.sh && nohup /workspace/launch/meshtastic/loop.sh >> /workspace/launch/meshtastic/loop.out 2>&1 &` (logs go to /workspace/launch/meshtastic/mesh.log)
3. The baseline needs 36 samples (about 6 hours) before any drop-off signal can appear.
