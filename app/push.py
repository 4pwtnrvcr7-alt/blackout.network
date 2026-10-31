"""Blackout push hook. After each scan, POST every newly qualifying cluster once to BLACKOUT_WEBHOOK_URL.
Rule: main feed (watchlist=0) AND rank >= push_min_rank AND eff_families >= push_min_sources AND pushed_at IS NULL.
Config: /workspace/blackout/config.json (push_min_rank, push_min_sources).
Secrets: /workspace/blackout/push.env (KEY=VALUE lines, chmod 600) if present, else process env:
  BLACKOUT_WEBHOOK_URL, BLACKOUT_WEBHOOK_KEY.  The key is never logged or printed."""
import os, json, stat
from datetime import datetime, timezone
import requests
import scanner as S

BASE = S.BASE
ENV_FILE = f"{BASE}/push.env"
LOG = f"{BASE}/logs/push.log"

def log(msg):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as f: f.write(f"[{S.iso(S.now())}] {msg}\n")

def load_env():
    env = {}
    if os.path.exists(ENV_FILE):
        if stat.S_IMODE(os.stat(ENV_FILE).st_mode) & 0o077: os.chmod(ENV_FILE, 0o600)
        for line in open(ENV_FILE):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line: continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    else:
        for k in ("BLACKOUT_WEBHOOK_URL", "BLACKOUT_WEBHOOK_KEY"):
            if os.environ.get(k): env[k] = os.environ[k]
    return env

def cfg():
    try: return json.load(open(f"{BASE}/config.json"))
    except Exception: return {}

def push_new():
    env = load_env()
    url, key = env.get("BLACKOUT_WEBHOOK_URL"), env.get("BLACKOUT_WEBHOOK_KEY")
    if not url or not key:
        log("push disabled (BLACKOUT_WEBHOOK_URL / BLACKOUT_WEBHOOK_KEY not set)")
        return {"status": "disabled"}
    c = cfg(); pr = int(c.get("push_min_rank", 7)); ps = int(c.get("push_min_sources", 2))
    db = S.db()
    rows = [dict(r) for r in db.execute("""SELECT * FROM clusters WHERE watchlist=0 AND rank>=? AND eff_families>=? AND pushed_at IS NULL
                                           ORDER BY rank DESC, score DESC""", (pr, ps))]
    sent, failed = [], []
    for r in rows:
        body = {"cluster_id": r["cluster_id"], "rank": r["rank"], "score": r["score"], "title": r["title"], "location": r["location"],
                "event_time": r["event_time"], "links": [l["url"] for l in json.loads(r["links"] or "[]")]}
        try:
            resp = requests.post(url, json=body, timeout=15,
                                 headers={"Authorization": f"Bearer {key}", "X-Webhook-Key": key, "Content-Type": "application/json"})
            ok = 200 <= resp.status_code < 300
        except Exception as ex:
            ok, resp = False, None
            log(f"push FAILED cluster={r['cluster_id']} error={type(ex).__name__}")
        if ok:
            db.execute("UPDATE clusters SET pushed_at=? WHERE cluster_id=?", (S.iso(S.now()), r["cluster_id"]))
            db.commit(); sent.append(r["cluster_id"])
            log(f"pushed cluster={r['cluster_id']} rank={r['rank']} status={resp.status_code}")
        else:
            failed.append(r["cluster_id"])   # not marked pushed -> retried after the next scan
            if resp is not None: log(f"push FAILED cluster={r['cluster_id']} status={resp.status_code}")
    db.close()
    return {"status": "ok", "candidates": len(rows), "sent": sent, "failed": failed}

def push_jet_spike(alert):
    """Jet takeoff spike hook (informational, separate from threat pushes). Same webhook; disabled while push.env is absent."""
    env = load_env()
    url, key = env.get("BLACKOUT_WEBHOOK_URL"), env.get("BLACKOUT_WEBHOOK_KEY")
    if not url or not key:
        log(f"jet spike push disabled (webhook not set) hour={alert.get('hour')}")
        return {"status": "disabled"}
    try:
        resp = requests.post(url, json=alert, timeout=15,
                             headers={"Authorization": f"Bearer {key}", "X-Webhook-Key": key, "Content-Type": "application/json"})
        ok = 200 <= resp.status_code < 300
        log(f"jet spike push hour={alert.get('hour')} status={resp.status_code}")
        return {"status": "sent" if ok else "failed"}
    except Exception as ex:
        log(f"jet spike push FAILED hour={alert.get('hour')} error={type(ex).__name__}")
        return {"status": "failed"}

if __name__ == "__main__":
    print(json.dumps(push_new(), indent=1))
