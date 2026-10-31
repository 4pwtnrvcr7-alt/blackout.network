"""Timeline add-on: hourly histogram of every cataloged item since the bot started (backfilled from blackout.db, read-only)
plus the items and source snapshots for any time window. Starts snapshot_worker.py (separate process, /workspace/.shotenv)
if it is not running. Writes nothing to blackout.db; snapshots live in timeline.db + snapshots/. Never touches scoring."""
import json, os, re, sqlite3, subprocess, time
from datetime import datetime, timezone, timedelta
BASE = os.path.dirname(os.path.abspath(__file__)); SNAP = os.path.join(BASE, "snapshots"); TDB = os.path.join(BASE, "timeline.db")
PIDF = os.path.join(BASE, "logs", "snapshot_worker.pid"); PY = "/workspace/.shotenv/bin/python"
def _alive():
    try:
        pid = int(open(PIDF).read().strip())
        return "snapshot_worker" in open(f"/proc/{pid}/cmdline").read()
    except Exception: return False
def ensure_worker():
    if _alive() or os.environ.get("BN_NO_SNAPSHOTS"): return
    log = open(os.path.join(BASE, "logs", "snapshot_worker.log"), "a")
    subprocess.Popen([PY, os.path.join(BASE, "snapshot_worker.py")], cwd=BASE, stdout=log, stderr=log, stdin=subprocess.DEVNULL, start_new_session=True)
    time.sleep(.5)
ensure_worker()
def src():
    c = sqlite3.connect(f"file:{BASE}/blackout.db?mode=ro", uri=True, timeout=20); c.row_factory = sqlite3.Row; return c
def snaps(ids=None):
    if not os.path.exists(TDB): return {}
    c = sqlite3.connect(f"file:{TDB}?mode=ro", uri=True, timeout=20); c.row_factory = sqlite3.Row
    try: rows = c.execute("SELECT * FROM snapshots").fetchall()
    except sqlite3.OperationalError: rows = []
    c.close(); return {r["cluster_id"]: dict(r) for r in rows if ids is None or r["cluster_id"] in ids}
def iso(d): return d.strftime("%Y-%m-%dT%H:%M:%SZ")
def overview():
    c = src()
    try:
        rows = c.execute("""SELECT substr(first_seen,1,13) h, COUNT(*) n, SUM(watchlist=0 AND rank>=7 AND eff_families>=2) high, MAX(score) mx, SUM(watchlist=0) main
                            FROM clusters GROUP BY h ORDER BY h""").fetchall()
        first = c.execute("SELECT MIN(first_seen) FROM clusters").fetchone()[0]; total = c.execute("SELECT COUNT(*) FROM clusters").fetchone()[0]
    finally: c.close()
    s = snaps(); ok = [x for x in s.values() if x["status"] == "ok"]
    du = sum(x["bytes"] or 0 for x in ok)
    return {"start": first, "now": iso(datetime.now(timezone.utc)), "total": total,
            "hours": [{"h": r["h"] + ":00:00Z", "n": r["n"], "high": r["high"] or 0, "max": r["mx"], "main": r["main"]} for r in rows],
            "snapshots": {"ok": len(ok), "failed": sum(1 for x in s.values() if x["status"] != "ok"), "bytes": du, "cap_bytes": 3 * 1024 ** 3, "worker_running": _alive(),
                          "rule": "rank 4+ or 2+ source families; max 180/hour, 12 s apart; stops at 3 GB"}}
def items(frm, to, limit=400):
    c = src()
    try: rows = [dict(r) for r in c.execute("""SELECT cluster_id,title,category,location,score,rank,confidence,families,links,event_time,first_seen,watchlist,eff_families,n_families,brief
                                               FROM clusters WHERE first_seen>=? AND first_seen<? ORDER BY first_seen ASC LIMIT ?""", (frm, to, limit))]
    finally: c.close()
    s = snaps({r["cluster_id"] for r in rows})
    for r in rows:
        r["families"] = json.loads(r["families"] or "[]"); r["links"] = json.loads(r["links"] or "[]")[:6]; x = s.get(r["cluster_id"])
        r["snapshot"] = {"file": "snapshots/" + x["file"], "captured_at": x["captured_at"], "url": x["url"]} if x and x["status"] == "ok" else ({"status": x["status"]} if x else None)
    return rows
def handle_get(path, qs):
    ensure_worker()
    if path == "/api/timeline": return 200, overview()
    if path == "/api/timeline/items":
        frm = (qs.get("from") or [""])[0]; to = (qs.get("to") or [""])[0]
        if not (re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", frm) and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", to)): return 400, {"error": "from/to must be ISO UTC like 2026-10-30T14:00:00Z"}
        return 200, {"from": frm, "to": to, "items": items(frm, to)}
    if path.startswith("/snapshots/"):
        name = path[len("/snapshots/"):]
        if not re.fullmatch(r"[A-Za-z0-9_\-]+\.jpg", name): return 404, {"error": "not found"}
        f = os.path.join(SNAP, name)
        if not os.path.isfile(f): return 404, {"error": "not found"}
        with open(f, "rb") as fh: return 200, fh.read(), "image/jpeg"
    return 404, {"error": "not found"}
