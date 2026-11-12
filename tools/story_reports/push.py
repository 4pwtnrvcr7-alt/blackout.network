#!/usr/bin/env python3
"""Signed one-file push of data/story_reports.json to the Render public node.

Same channel as /workspace/launch/growth/push_public_stats.py: render_sync.Client + render_sync.push() with exactly one file.
Never calls render_sync cycle/once/loop, never packages or pushes a database, never prints a secret.
The rel path data/story_reports.json is already accepted by Render today (render_rules.SYNC_DIRS has "data"), so no Render
config change is needed. Pushes when the file changed OR when Render's manifest lacks it / has another hash (a Render redeploy
wipes pushed data; the next run restores it within one interval).
usage: push.py [--src PATH] [--dry-run]
"""
import argparse, json, os, sys, time
BOX = "/workspace/blackout"                  # only render_sync.py / render_rules.py are imported from here (read-only use)
REL = "data/story_reports.json"
STATE = "/workspace/launch/story_reports/push.state"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="/workspace/launch/story_reports/data/story_reports.json")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not os.path.isfile(a.src): print(f"story_reports push: skip (missing {a.src})"); return 0
    try: json.load(open(a.src))
    except Exception as ex: print(f"story_reports push: refuse (invalid JSON: {ex})"); return 2
    rs_dir = os.environ.get("BN_RENDER_SYNC_DIR", BOX)
    if rs_dir not in sys.path: sys.path.insert(0, rs_dir)
    import render_sync as R, render_rules as RR
    kind = RR.sync_kind(REL)
    if kind != "data": print(f"story_reports push: refuse (kind={kind!r}, expected data)"); return 2
    h = R.sha_file(a.src)
    env = R.load_env()
    if not env.get("BN_RENDER_URL") or len(env.get("BN_SYNC_SECRET") or "") < 32:
        print("story_reports push: skip (sync not configured in this shell)"); return 0
    cl = R.Client(env["BN_RENDER_URL"], env.get("BN_SYNC_SECRET", ""))
    code, body = cl.req("GET", "/internal/sync/manifest")
    if code != 200: print(f"story_reports push: manifest HTTP {code}"); return 1
    remote = (json.loads(body).get("files") or {}).get(REL)
    if remote == h: print(f"story_reports push: skip (Render has {h[:12]})"); return 0
    if a.dry_run: print(f"story_reports push: would push {REL} {h[:12]} (Render has {str(remote)[:12]})"); return 0
    sent, batches = R.push(cl, [(REL, a.src, h)], {})
    if not sent: print("story_reports push: push returned 0 files"); return 1
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE + ".tmp", "w") as f:
        json.dump({"sha256": h, "rel": REL, "t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "bytes": os.path.getsize(a.src)}, f)
    os.replace(STATE + ".tmp", STATE)
    print(f"story_reports push: pushed 1 file / {batches} batch sha={h[:12]}"); return 0

if __name__ == "__main__":
    raise SystemExit(main())
