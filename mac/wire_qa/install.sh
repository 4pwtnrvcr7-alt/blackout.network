#!/bin/bash
# BLACKOUT.NETWORK Wire post-publish QA (com.blackout.wireqa). Re-running is safe.
# Copies wire_qa.py + the launchd plist into ~/blackout_mac/wire_qa/, loads the KeepAlive job, runs one pass, prints PASS/FAIL.
# Reads the sync key (BN_SYNC_SECRET) from ~/blackout_mac/.env at run time to sign holds; never copies or prints it.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/blackout_mac/wire_qa"
LA="$HOME/Library/LaunchAgents"
LABEL="com.blackout.wireqa"
PLIST="$LA/$LABEL.plist"
[ -d "$HOME/blackout_mac" ] || { echo "STOPPED: ~/blackout_mac not found"; exit 1; }
PY=/usr/bin/python3; [ -x "$PY" ] || PY="$(command -v python3)"
[ -n "$PY" ] || { echo "STOPPED: no python3"; exit 1; }
mkdir -p "$DEST/logs" "$LA"
cp "$HERE/wire_qa.py" "$DEST/wire_qa.py"
"$PY" -c "import ast,sys;ast.parse(open(sys.argv[1]).read())" "$DEST/wire_qa.py" || { echo "STOPPED: wire_qa.py syntax"; exit 1; }
sed -e "s#__HOME__#$HOME#g" -e "s#/usr/bin/python3#$PY#" "$HERE/$LABEL.plist" > "$PLIST"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST" && launchctl enable "gui/$(id -u)/$LABEL"
sleep 25
if launchctl print "gui/$(id -u)/$LABEL" 2>/dev/null | grep -q "state = running"; then
  echo "PASS: $LABEL running. Logs: $DEST/logs/ (YYYYMMDD.jsonl, wire_qa.log)"
  tail -n 3 "$DEST/logs/wire_qa.log" 2>/dev/null
else
  echo "FAIL: $LABEL not running. See $DEST/logs/launchd.err.log"; tail -n 20 "$DEST/logs/launchd.err.log" 2>/dev/null; exit 1
fi
