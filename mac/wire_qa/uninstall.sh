#!/bin/bash
launchctl bootout "gui/$(id -u)/com.blackout.wireqa" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/com.blackout.wireqa.plist"
echo "removed com.blackout.wireqa (logs kept in ~/blackout_mac/wire_qa/logs)"
