"""Live push add-on: Server-Sent Events at /api/stream. One watcher thread polls blackout.db (READ-ONLY) every 3 s for
new clusters and finished scans, and timeline.db for new source snapshots. New items are pushed to every open page.
Snapshot-eligible items (rank 4+ or 2+ sources) are held up to HOLD_S seconds so the screenshot ships in the same event;
after that the text goes out and the image follows as a 'snapshot' event. Never touches scoring, scanner or push.py."""
import builtins, json, os, queue, sqlite3, threading, time
BASE = os.path.dirname(os.path.abspath(__file__)); TDB = os.path.join(BASE, "timeline.db")
HOLD_S = 30; POLL_S = 3; KEEPALIVE_S = 15; MAX_CLIENTS = 50
ST = getattr(builtins, "_bn_live", None)
if ST is None:
    ST = builtins._bn_live = {"clients": set(), "lock": threading.Lock(), "started": False, "last_seen": None, "last_scan": None, "pending": {}, "await_img": {}, "sent": 0}
def _src():
    c = sqlite3.connect(f"file:{BASE}/blackout.db?mode=ro", uri=True, timeout=20); c.row_factory = sqlite3.Row; return c
def _snap(ids):
    if not ids or not os.path.exists(TDB): return {}
    c = sqlite3.connect(f"file:{TDB}?mode=ro", uri=True, timeout=20)
    try: return {r[0]: (r[1], r[2], r[3]) for r in c.execute(f"SELECT cluster_id,status,file,captured_at FROM snapshots WHERE cluster_id IN ({','.join('?'*len(ids))})", list(ids))}
    except sqlite3.OperationalError: return {}
    finally: c.close()
def broadcast(event, data):
    msg = f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n".encode()
    with ST["lock"]:
        for q in list(ST["clients"]):
            try: q.put_nowait(msg)
            except queue.Full: ST["clients"].discard(q)
    ST["sent"] += 1
def _item(r):
    return {k: r[k] for k in ("cluster_id", "title", "category", "location", "score", "rank", "confidence", "watchlist", "eff_families", "n_families", "first_seen", "event_time")} | \
           {"families": json.loads(r["families"] or "[]"), "links": json.loads(r["links"] or "[]")[:4], "high": bool(r["watchlist"] == 0 and r["rank"] >= 7 and r["eff_families"] >= 2)}
def _eligible(r): return r["rank"] >= 4 or r["eff_families"] >= 2 or r["n_families"] >= 2
def _watch():
    while True:
        try:
            c = _src()
            try:
                if ST["last_seen"] is None:
                    ST["last_seen"] = c.execute("SELECT MAX(first_seen) FROM clusters").fetchone()[0] or ""
                    ST["last_scan"] = c.execute("SELECT MAX(id) FROM scans").fetchone()[0] or 0
                rows = c.execute("SELECT * FROM clusters WHERE first_seen>? ORDER BY first_seen ASC LIMIT 500", (ST["last_seen"],)).fetchall()
                sc = c.execute("SELECT * FROM scans WHERE id>? ORDER BY id", (ST["last_scan"],)).fetchall()
            finally: c.close()
            now = time.time()
            for r in rows:
                ST["last_seen"] = max(ST["last_seen"], r["first_seen"]); it = _item(r)
                if r["watchlist"] == 2: continue   # suppressed items (no threat signal) are never shown, so never pushed
                if _eligible(r): ST["pending"][r["cluster_id"]] = (now, it)
                else: broadcast("alert", {**it, "snapshot": None})
            # release held items: with snapshot if ready, else after HOLD_S as text-only
            snaps = _snap(set(ST["pending"]) | set(ST["await_img"]))
            for cid, (t0, it) in list(ST["pending"].items()):
                s = snaps.get(cid)
                if s and s[0] == "ok": broadcast("alert", {**it, "snapshot": {"file": "snapshots/" + s[1], "captured_at": s[2]}}); del ST["pending"][cid]
                elif now - t0 >= HOLD_S:
                    broadcast("alert", {**it, "snapshot": None, "snapshot_pending": True}); del ST["pending"][cid]; ST["await_img"][cid] = now
            for cid, t0 in list(ST["await_img"].items()):
                s = snaps.get(cid)
                if s and s[0] == "ok": broadcast("snapshot", {"cluster_id": cid, "file": "snapshots/" + s[1], "captured_at": s[2]}); del ST["await_img"][cid]
                elif now - t0 > 3600: del ST["await_img"][cid]
            for s in sc:
                ST["last_scan"] = max(ST["last_scan"], s["id"]); broadcast("scan", dict(s))
        except Exception as ex:
            print("livepush watcher:", ex, flush=True)
        time.sleep(POLL_S)
if not ST["started"]:
    ST["started"] = True; threading.Thread(target=_watch, daemon=True, name="livepush").start()
def handle_get(path, qs):
    return 200, {"clients": len(ST["clients"]), "events_sent": ST["sent"], "held_for_snapshot": len(ST["pending"]), "awaiting_image": len(ST["await_img"]), "hold_seconds": HOLD_S}
def handle_stream(path, qs, h):
    if path != "/api/stream": return h.send(*handle_get(path, qs))
    if len(ST["clients"]) >= MAX_CLIENTS: return h.send(503, {"error": "too many live connections"})
    q = queue.Queue(maxsize=500)
    h.send_response(200); h.send_header("Content-Type", "text/event-stream; charset=utf-8"); h.send_header("Cache-Control", "no-store")
    h.send_header("X-Accel-Buffering", "no"); h.send_header("Connection", "keep-alive"); h.end_headers()
    with ST["lock"]: ST["clients"].add(q)
    try:
        h.wfile.write(f"retry: 5000\nevent: hello\ndata: {json.dumps({'hold_seconds': HOLD_S, 'poll_seconds': POLL_S})}\n\n".encode()); h.wfile.flush()
        while True:
            try: msg = q.get(timeout=KEEPALIVE_S)
            except queue.Empty: msg = b": keepalive\n\n"
            h.wfile.write(msg); h.wfile.flush()
    except (BrokenPipeError, ConnectionResetError, OSError): pass
    finally:
        with ST["lock"]: ST["clients"].discard(q)
        h.close_connection = True
