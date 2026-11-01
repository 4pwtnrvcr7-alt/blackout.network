#!/bin/bash
# PRE-PUBLISH GATE (t338): run before every push to main. Fails (exit 1) if any link added or changed by the commits you are about
# to push (plus staged/unstaged edits) is dead: 404/410, a host that doesn't exist, or a soft 404 (redirect to a homepage or a
# "not found" page). Bot-blocked (403/429) and label/landing mismatches are printed as warnings to review; --strict fails them too.
#   tools/prepublish.sh            # compares against gh/main (fetch first)
#   tools/prepublish.sh --strict
# Optional: install as a git pre-push hook:  ln -sf ../../tools/prepublish.sh .git/hooks/pre-push
set -e
cd "$(dirname "$0")/.."
BASE_REF=${BN_BASE_REF:-gh/main}
git rev-parse --verify -q "$BASE_REF" >/dev/null || BASE_REF=HEAD~1
python3 -m py_compile app/*.py tools/linkcheck.py
python3 tools/linkcheck.py gate --base-ref "$BASE_REF" "$@"
