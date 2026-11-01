"""t414 scanner freshness watchdog (read-only on blackout.db). Writes sources_freshness.json (synced to Render with sources*.json)
and logs/scanner_freshness.json for the hourly threat-check routine. Never emails or messages anyone.
Stale = no successful scan within 2x interval_minutes, or any active source failing for 6+ hours.
Usage: python3 scanner_freshness.py [loop]"""
import json, os, sqlite3, sys, time
from datetime import datetime, timezone, timedelta
BASE = os.path.dirname(os.path.abspath(__file__))
OUT = [os.path.join(BASE, "sources_freshness.json"), os.path.join(BASE, "logs", "scanner_freshness.json")]
def pt(s):
    try: return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception: return None
def check():
    now = datetime.now(timezone.utc)
    try: iv = int(json.load(open(os.path.join(BASE, "config.json"))).get("interval_minutes", 60))
    except Exception: iv = 60
    c = sqlite3.connect(f"file:{os.path.join(BASE, 'blackout.db')}?mode=ro", uri=True, timeout=20); c.row_factory = sqlite3.Row
    last = c.execute("SELECT finished, ok_sources, failed_sources FROM scans WHERE error IS NULL AND finished IS NOT NULL ORDER BY id DESC LIMIT 1").fetchone()
    fails = []
    for r in c.execute("SELECT name, url, last_ok, last_checked, error FROM source_health WHERE ok=0"):
        lo = pt(r["last_ok"] or "")
        hrs = (now - lo).total_seconds() / 3600 if lo else None
        if hrs is None or hrs >= 6:
            fails.append({"name": r["name"], "last_ok": r["last_ok"], "hours_failing": round(hrs, 1) if hrs else None, "error": (r["error"] or "")[:160]})
    c.close()
    lf = pt(last["finished"]) if last else None
    age = round((now - lf).total_seconds() / 60, 1) if lf else None
    scan_stale = age is None or age > 2 * iv
    st = {"checked": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "interval_minutes": iv, "last_scan": last["finished"] if last else None,
          "last_scan_age_min": age, "scan_stale": scan_stale, "sources_failing_6h": fails,
          "stale": bool(scan_stale or fails), "notice": None}
    if scan_stale: st["notice"] = f"Data may be stale: last successful scan {age or '?'} min ago (expected every {iv} min)."
    elif fails: st["notice"] = f"Some sources may be stale: {len(fails)} failing 6+ h ({', '.join(f['name'][:40] for f in fails[:3])})."
    for p in OUT:
        tmp = p + ".tmp"; json.dump(st, open(tmp, "w"), indent=1); os.replace(tmp, p)
    return st
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "loop":
        while True:
            try: check()
            except Exception as e: print(datetime.now().isoformat(), "freshness error", e, flush=True)
            time.sleep(600)
    else: print(json.dumps(check(), indent=1))
