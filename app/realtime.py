"""Realtime Wire + heat map stream (Nov 21 2026, Matt pt1688u: "push new data to the site as soon as the scanners find it ...
a steady stream of information coming into the wire ... the heat map updating in realtime with each new item").

Before: the Mac's scanner committed a scan, render_sync.py re-uploaded the whole blackout.db on its next 60 s cycle (geo.db only every
5 minutes), /api/signal/heat cached 60 s, the Wire polled every 12 s and the map reloaded every 5 minutes.
Now:
  POST /internal/rt/push   box-signed (same BN_SYNC_SECRET HMAC as /internal/sync/*; render_app.py checks it) small gzip JSON delta from
                           the Mac's rt_push.py: new/changed clusters, their new alerts, geo.db rows and scan rows. Upserted into this
                           node's copies of blackout.db / geo.db (newer rows only, idempotent), caches dropped, browsers told at once.
                           The reply carries this node's watermarks, so the Mac only ever sends what is missing (dedupe + self-healing).
  POST /internal/rt/poll   box-signed long-poll (25 s): returns at once when a visitor pressed Refresh, so the Mac pushes its newest rows now.
  GET  /api/rt/stream      Server-Sent Events: 'hello', 'rt' (new Wire items + their map rows + Wire counts), 'status'. Each connection
                           closes after 10 minutes (the browser reconnects), at most BN_RT_MAX_CLIENTS (default 300) at a time.
  GET  /api/rt/since?seq=  polling fallback (same 'rt' events from a ring buffer), for browsers without SSE or when the cap is hit.
  POST /api/rt/refresh     the Wire / map Refresh button: drops caches, asks the Mac for anything newer, waits up to 6 s, returns counts.
  GET  /api/rt/status      public, secret-free health. GET /api/rt/client.js the browser helper (BNRT).
The full render_sync.py upload keeps working unchanged (backward compatible): after each one, after_sync() re-applies recent deltas the
upload may have raced past and announces anything new it brought, so browsers get pushed updates even before the Mac bundle is updated.
Kill switch: BN_REALTIME=0 (endpoints answer 404, pages fall back to their old polling). Never touches scanner.py, scoring, push.py,
jets.py, aviation_watch.py or config.json; it only writes rows the scanner itself produced on the Mac."""
import builtins, gzip, json, os, queue, sqlite3, sys, threading, time
from collections import deque
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "blackout.db"); GDB = os.path.join(BASE, "geo.db")
STATIC = os.path.join(BASE, "realtime_static")
MAX_CLIENTS = int(os.environ.get("BN_RT_MAX_CLIENTS", "300"))
KEEPALIVE_S = 15; STREAM_LIFE_S = 600; JOURNAL_S = 1800; JOURNAL_ROWS = 30000; RING = 60
MAX_ROWS = 5000; MAX_RAW = 64 << 20
EV_ITEMS = 120; EV_HEAT = 400       # per event; bigger bursts (e.g. a full re-geocode) send a 'reload' hint instead

def on(): return os.environ.get("BN_REALTIME", "1") != "0"
def _iso(t=None): return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t if t is not None else time.time()))

ST = getattr(builtins, "_bn_rt", None)
if ST is None:
    ST = builtins._bn_rt = {"clients": set(), "lock": threading.Lock(), "db": threading.Lock(), "seq": 0, "ring": deque(maxlen=RING),
                            "journal": deque(), "jrows": 0, "cv": threading.Condition(), "want": 0.0, "ingests": 0, "rows": 0,
                            "last_ingest": None, "last_ingest_new": 0, "new_total": 0, "mac_seen": None, "mac_ver": None, "wm_first": None, "wm_geo": None,
                            "last_bust": 0.0, "last_meta_bust": 0.0, "refresh_ip": {}, "last_ask": 0.0, "events": 0, "last_scan": None,
                            "errors": 0, "last_error": None, "boot": time.time()}

# ------------------------------------------------------------------ table rules (pk, newer-than condition for an update)
RULES = {
    "clusters": ("cluster_id", DB, "COALESCE(excluded.updated, excluded.first_seen, '') >= COALESCE(clusters.updated, clusters.first_seen, '')"),
    "alerts":   ("id", DB, "COALESCE(excluded.last_seen, '') >= COALESCE(alerts.last_seen, '')"),
    "scans":    ("id", DB, None),
    "geo":      ("id", GDB, "COALESCE(excluded.geocoded_at, '') >= COALESCE(geo.geocoded_at, '')"),
}
_COLS = {}
def _cols(c, path, table):
    k = (path, table, os.stat(path).st_ino)
    if k not in _COLS: _COLS[k] = [r[1] for r in c.execute(f'PRAGMA table_info("{table}")')]
    return _COLS[k]

def _clean_row(r):
    if not isinstance(r, dict): return None
    out = {}
    for k, v in r.items():
        if not isinstance(k, str) or len(k) > 40: return None
        if v is None or isinstance(v, (int, float, str)): out[k] = v if not isinstance(v, str) else v[:200000]
        else: out[k] = json.dumps(v)[:200000]
    return out

def _upsert(c, path, table, rows, track_new=False):
    """Insert or update rows (newer only). Returns (changed_ids, new_ids)."""
    pk, _, cond = RULES[table]
    have = _cols(c, path, table)
    if not have: return [], []
    changed, new = [], []
    for r in rows:
        r = _clean_row(r)
        if not r or r.get(pk) in (None, ""): continue
        cols = [k for k in r if k in have]
        if pk not in cols: continue
        existed = c.execute(f'SELECT 1 FROM "{table}" WHERE "{pk}"=?', (r[pk],)).fetchone() is not None if track_new else True
        ph = ",".join("?" * len(cols)); cl = ",".join(f'"{x}"' for x in cols)
        if cond is None:
            sql = f'INSERT OR IGNORE INTO "{table}"({cl}) VALUES({ph})'
        else:
            upd = ",".join(f'"{x}"=excluded."{x}"' for x in cols if x != pk) or f'"{pk}"=excluded."{pk}"'
            sql = f'INSERT INTO "{table}"({cl}) VALUES({ph}) ON CONFLICT("{pk}") DO UPDATE SET {upd} WHERE {cond}'
        before = c.total_changes
        c.execute(sql, [r[x] for x in cols])
        if c.total_changes != before:
            changed.append(r[pk])
            if track_new and not existed: new.append(r[pk])
    return changed, new

def _apply(d, journal=True):
    """Apply one delta dict {clusters, alerts, scans, geo}. Returns (changed cluster ids, new cluster ids, changed geo ids, scans)."""
    ch_c = new_c = ch_g = []; n_sc = 0
    with ST["db"]:
        if os.path.exists(DB) and any(d.get(t) for t in ("clusters", "alerts", "scans")):
            c = sqlite3.connect(DB, timeout=20)
            try:
                ch_c, new_c = _upsert(c, DB, "clusters", (d.get("clusters") or [])[:MAX_ROWS], track_new=True)
                _upsert(c, DB, "alerts", (d.get("alerts") or [])[:MAX_ROWS])
                n_sc = len(_upsert(c, DB, "scans", (d.get("scans") or [])[:200])[0])
                c.commit()
            finally: c.close()
        if os.path.exists(GDB) and d.get("geo"):
            g = sqlite3.connect(GDB, timeout=20)
            try: ch_g, _ = _upsert(g, GDB, "geo", (d.get("geo") or [])[:MAX_ROWS]); g.commit()
            finally: g.close()
    if journal:
        now = time.time(); n = sum(len(d.get(t) or []) for t in RULES)
        ST["journal"].append((now, {t: d.get(t) or [] for t in RULES})); ST["jrows"] += n
        while ST["journal"] and (ST["journal"][0][0] < now - JOURNAL_S or ST["jrows"] > JOURNAL_ROWS):
            _, old = ST["journal"].popleft(); ST["jrows"] -= sum(len(v) for v in old.values())
    return ch_c, new_c, ch_g, n_sc

# ------------------------------------------------------------------ watermarks (what this node already has)
def _one(path, sql):
    if not os.path.exists(path): return None
    try:
        c = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10)
        try: return c.execute(sql).fetchone()
        finally: c.close()
    except sqlite3.Error: return None

def watermarks():
    cl = _one(DB, "SELECT COALESCE(updated, first_seen) t, cluster_id FROM clusters ORDER BY t DESC, cluster_id DESC LIMIT 1")
    al = _one(DB, "SELECT first_seen, id FROM alerts ORDER BY first_seen DESC, id DESC LIMIT 1")
    sc = _one(DB, "SELECT MAX(id), MAX(finished) FROM scans")
    ge = _one(GDB, "SELECT geocoded_at, id FROM geo ORDER BY geocoded_at DESC, id DESC LIMIT 1")
    return {"clusters": list(cl) if cl else None, "alerts": list(al) if al else None, "scans": sc[0] if sc else None,
            "geo": list(ge) if ge else None, "has_db": os.path.exists(DB), "has_geo": os.path.exists(GDB)}

def _wm_init():
    if ST["wm_first"] is None:
        r = _one(DB, "SELECT MAX(first_seen) FROM clusters"); ST["wm_first"] = (r[0] if r else None) or ""
    if ST["wm_geo"] is None:
        r = _one(GDB, "SELECT MAX(geocoded_at) FROM geo"); ST["wm_geo"] = (r[0] if r else None) or ""

# ------------------------------------------------------------------ caches + broadcast
def _mod(name):
    m = sys.modules.get(name)
    if m is None:
        try:
            import importlib; m = importlib.import_module(name)
        except Exception: return None
    return m

def bust(force=False):
    """Drop the map feed cache (and, at most every 2 minutes, the Wire totals) so the next read is current."""
    now = time.time()
    sm = sys.modules.get("signal_map")
    if sm is not None and hasattr(sm, "_HEAT"):
        try:
            with sm._HLOCK: sm._HEAT["t"] = 0.0; sm._HEAT["g"] = sm._HEAT.get("g", 0) + 1
        except Exception: pass
    wt = sys.modules.get("wire_timeline")
    if wt is not None and hasattr(wt, "bust_pages"):
        try:
            wt.bust_pages(); ST["last_meta_bust"] = now
        except Exception: pass
    elif force or now - ST["last_meta_bust"] > 120:
        if wt is not None and hasattr(wt, "bust_meta"):
            try: wt.bust_meta(); ST["last_meta_bust"] = now
            except Exception: pass
    ST["last_bust"] = now

def _last_scan():
    r = _one(DB, "SELECT MAX(finished) FROM scans WHERE finished IS NOT NULL")
    return r[0] if r else None

def _send_all(msg):
    with ST["lock"]:
        for q in list(ST["clients"]):
            try: q.put_nowait(msg)
            except queue.Full: ST["clients"].discard(q)

def announce(new_ids, geo_ids=(), src="push"):
    """Tell every open page: full Wire items for new clusters, map rows for new + re-placed ones, and the Wire's own counts."""
    new_ids = list(dict.fromkeys(new_ids or [])); geo_ids = [g for g in dict.fromkeys(geo_ids or []) if g not in set(new_ids)]
    if not new_ids and not geo_ids: return None
    wt, ha = _mod("wire_timeline"), _mod("heat_all")
    items = []
    try: items = wt.items_for(new_ids[:EV_ITEMS]) if wt and new_ids else []
    except Exception as ex: ST["last_error"] = "items: " + str(ex)[:160]
    heat, heat_reload = [], len(new_ids) + len(geo_ids) > EV_HEAT
    try:
        if ha and not heat_reload:
            import map_pins
            heat, _ = map_pins.filter_heat_rows(ha.rows_for(new_ids + geo_ids), ha.COLS)
    except Exception as ex: ST["last_error"] = "heat: " + str(ex)[:160]; heat_reload = True
    wc = None
    try: wc = ha.wire_counts() if ha else None
    except Exception: pass
    ls = _last_scan(); ST["last_scan"] = ls
    with ST["lock"]:
        ST["seq"] += 1; seq = ST["seq"]
    ev = {"seq": seq, "at": _iso(), "src": src, "new": [i["id"] for i in items], "items": items, "more_new": max(0, len(new_ids) - len(items)),
          "heat": {"cols": getattr(ha, "COLS", None), "rows": heat, "reload": heat_reload}, "wire_counts": wc, "last_scan": ls}
    ST["ring"].append(ev); ST["events"] += 1
    _send_all(f"id: {seq}\nevent: rt\ndata: {json.dumps(ev, separators=(',', ':'), default=str)}\n\n".encode())
    return ev

# ------------------------------------------------------------------ entry points used by render_app.py
def _decode(raw):
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.GzipFile(fileobj=__import__("io").BytesIO(raw)).read(MAX_RAW + 1)
        if len(raw) > MAX_RAW: raise ValueError("delta too large")
    d = json.loads(raw or b"{}")
    if not isinstance(d, dict): raise ValueError("delta must be an object")
    return d

def ingest(raw):
    """Body of POST /internal/rt/push (already HMAC-verified by render_app). Returns (code, body)."""
    if not on(): return 404, {"error": "not found"}
    t0 = time.time()
    try: d = _decode(raw)
    except Exception as ex: return 400, {"error": "bad delta: " + str(ex)[:160]}
    ST["mac_seen"] = t0; ST["mac_ver"] = str(d.get("v") or "")[:20]
    _wm_init()
    try: ch_c, new_c, ch_g, n_sc = _apply(d)
    except sqlite3.Error as ex:
        ST["errors"] += 1; ST["last_error"] = str(ex)[:200]; return 503, {"error": "database busy, retry", "wm": watermarks()}
    n = sum(len(d.get(t) or []) for t in RULES)
    if ch_c or ch_g or n_sc:
        bust()
        if new_c:
            r = _one(DB, f"SELECT MAX(first_seen) FROM clusters"); ST["wm_first"] = max(ST["wm_first"] or "", (r[0] if r else "") or "")
        if ch_g:
            r = _one(GDB, "SELECT MAX(geocoded_at) FROM geo"); ST["wm_geo"] = max(ST["wm_geo"] or "", (r[0] if r else "") or "")
        announce(new_c, ch_g, "push")
    if n_sc:
        ls = _last_scan()
        if ls != ST.get("last_scan_sent"):
            ST["last_scan_sent"] = ls
            _send_all(f"event: status\ndata: {json.dumps({'last_scan': ls, 'at': _iso()})}\n\n".encode())
    ST["ingests"] += 1; ST["rows"] += n; ST["last_ingest"] = time.time(); ST["last_ingest_new"] = len(new_c); ST["new_total"] += len(new_c)
    with ST["cv"]: ST["cv"].notify_all()
    return 200, {"status": "ok", "rows": n, "changed": len(ch_c), "new": len(new_c), "geo": len(ch_g), "scans": n_sc,
                 "ms": round(1000 * (time.time() - t0)), "wm": watermarks()}

def poll(raw):
    """Body of POST /internal/rt/poll (HMAC-verified). Long-poll: returns when a visitor asks for fresh data, or after `wait` seconds."""
    if not on(): return 404, {"error": "not found"}
    try: d = _decode(raw)
    except Exception: d = {}
    wait = max(1.0, min(25.0, float(d.get("wait") or 25)))
    seen = float(d.get("seen_want") or 0)
    ST["mac_seen"] = time.time(); ST["mac_ver"] = str(d.get("v") or ST["mac_ver"] or "")[:20]
    end = time.time() + wait
    with ST["cv"]:
        while ST["want"] <= seen and time.time() < end:
            ST["cv"].wait(timeout=max(0.1, end - time.time()))
    ST["mac_seen"] = time.time()
    return 200, {"want": ST["want"] > seen, "want_at": ST["want"], "wm": watermarks()}

def after_sync(done):
    """render_app.handle_push calls this after a full render_sync upload installed files: re-apply recent deltas the upload may have
    raced past, then announce clusters / geo rows that arrived only through the upload (old Mac bundle, or anything missed)."""
    if not on() or not any(f in ("blackout.db", "geo.db") for f in (done or [])): return None
    with ST["db"]:
        jr = list(ST["journal"])
    for _, d in jr:
        try: _apply(d, journal=False)
        except Exception: pass
    _wm_init()
    bust()
    new_ids, geo_ids = [], []
    r = None
    try:
        c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=10)
        try:
            new_ids = [x[0] for x in c.execute("SELECT cluster_id FROM clusters WHERE first_seen>? AND watchlist IN (0,1) ORDER BY first_seen DESC LIMIT 600", (ST["wm_first"] or "",))]
            r = c.execute("SELECT MAX(first_seen) FROM clusters").fetchone()
        finally: c.close()
    except sqlite3.Error: pass
    if r and r[0]: ST["wm_first"] = max(ST["wm_first"] or "", r[0])
    try:
        g = sqlite3.connect(f"file:{GDB}?mode=ro", uri=True, timeout=10)
        try:
            geo_ids = [x[0] for x in g.execute("SELECT id FROM geo WHERE geocoded_at>? ORDER BY geocoded_at DESC LIMIT 600", (ST["wm_geo"] or "",))]
            r2 = g.execute("SELECT MAX(geocoded_at) FROM geo").fetchone()
        finally: g.close()
        if r2 and r2[0]: ST["wm_geo"] = max(ST["wm_geo"] or "", r2[0])
    except sqlite3.Error: pass
    ev = announce(new_ids, geo_ids, "sync") if (new_ids or geo_ids) else None
    ls = _last_scan()
    if ls != ST.get("last_scan_sent"):
        ST["last_scan_sent"] = ls
        _send_all(f"event: status\ndata: {json.dumps({'last_scan': ls, 'at': _iso()})}\n\n".encode())
    with ST["cv"]: ST["cv"].notify_all()
    return ev

def refresh(ip):
    """POST /api/rt/refresh (public, rate-limited): drop caches, ask the Mac for anything newer, wait briefly for it."""
    if not on(): return 404, {"error": "not found"}
    now = time.time(); rip = ST["refresh_ip"]
    if len(rip) > 5000: rip.clear()
    if now - rip.get(ip, 0) < 4: return 429, {"error": "slow down", "retry_s": 4}
    rip[ip] = now
    bust(force=now - ST["last_bust"] > 10)
    mac_on = bool(ST["mac_seen"] and now - ST["mac_seen"] < 90)
    pulled = 0; asked = False
    if mac_on:
        asked = True; before = ST["ingests"]; t_ask = now; n0 = ST["new_total"]
        if now - ST["last_ask"] > 8:
            ST["last_ask"] = now
            with ST["cv"]: ST["want"] = now; ST["cv"].notify_all()
        else: t_ask = ST["last_ask"]
        end = now + 6
        with ST["cv"]:
            while time.time() < end and not (ST["last_ingest"] and ST["last_ingest"] >= t_ask and ST["ingests"] > before):
                ST["cv"].wait(timeout=0.25)
        pulled = ST["new_total"] - n0
    return 200, {"ok": True, "mac": "online" if mac_on else "offline", "asked_scanner": asked, "pulled_new": pulled,
                 "seq": ST["seq"], "last_scan": _last_scan(), "now": _iso()}

def public():
    now = time.time()
    return {"enabled": on(), "clients": len(ST["clients"]), "max_clients": MAX_CLIENTS, "events": ST["events"], "seq": ST["seq"],
            "mac_connected": bool(ST["mac_seen"] and now - ST["mac_seen"] < 90), "mac_version": ST["mac_ver"] or None,
            "last_push": _iso(ST["last_ingest"]) if ST["last_ingest"] else None,
            "last_push_age_s": round(now - ST["last_ingest"]) if ST["last_ingest"] else None,
            "pushes": ST["ingests"], "rows": ST["rows"], "errors": ST["errors"]}

# ------------------------------------------------------------------ GET routes (/api/rt/*), served through addons.ROUTES
FILES = {"client.js": "application/javascript"}
def handle_get(path, qs):
    if not on(): return 404, {"error": "not found"}
    if path == "/api/rt/status": return 200, public()
    if path == "/api/rt/since":
        try: seq = int((qs.get("seq") or ["0"])[0])
        except ValueError: return 400, {"error": "seq must be a number"}
        evs = [e for e in list(ST["ring"]) if e["seq"] > seq]
        old = bool(ST["ring"]) and seq and seq < ST["ring"][0]["seq"] - 1
        return 200, {"seq": ST["seq"], "events": evs[-20:], "reset": bool(old or seq > ST["seq"]), "last_scan": ST["last_scan"] or _last_scan(), "now": _iso()}
    if path.startswith("/api/rt/"):
        n = path[len("/api/rt/"):]
        if n in FILES:
            with open(os.path.join(STATIC, n), "rb") as fh: return 200, fh.read(), FILES[n]
    return 404, {"error": "not found"}

def handle_stream(path, qs, h):
    if path != "/api/rt/stream": return h.send(*handle_get(path, qs))
    if not on(): return h.send(404, {"error": "not found"})
    if len(ST["clients"]) >= MAX_CLIENTS: return h.send(503, {"error": "too many live connections; polling instead"})
    q = queue.Queue(maxsize=200)
    h.send_response(200); h.send_header("Content-Type", "text/event-stream; charset=utf-8"); h.send_header("Cache-Control", "no-store, no-transform")
    h.send_header("X-Accel-Buffering", "no"); h.send_header("Connection", "keep-alive"); h.end_headers()
    with ST["lock"]: ST["clients"].add(q)
    t_end = time.time() + STREAM_LIFE_S
    try:
        last = h.headers.get("Last-Event-ID")
        hello = {"seq": ST["seq"], "last_scan": ST["last_scan"] or _last_scan(), "now": _iso(), "keepalive_s": KEEPALIVE_S}
        h.wfile.write(f"retry: 4000\nevent: hello\ndata: {json.dumps(hello)}\n\n".encode())
        if last and last.isdigit():   # reconnect: replay what this page missed (ring buffer)
            for e in [e for e in list(ST["ring"]) if e["seq"] > int(last)][-10:]:
                h.wfile.write(f"id: {e['seq']}\nevent: rt\ndata: {json.dumps(e, separators=(',', ':'), default=str)}\n\n".encode())
        h.wfile.flush()
        while time.time() < t_end:
            try: msg = q.get(timeout=KEEPALIVE_S)
            except queue.Empty: msg = b": k\n\n"
            h.wfile.write(msg); h.wfile.flush()
    except (BrokenPipeError, ConnectionResetError, OSError): pass
    finally:
        with ST["lock"]: ST["clients"].discard(q)
        h.close_connection = True
