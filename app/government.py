"""Government tab (nav "Government", deep link #government): a blackout.network composite health index for the U.S. government
(0-100, NOT an official rating) and a lazy-loaded org chart from the President down to governors, state legislators and big-city
mayors, with official photos and published office contacts. Read-only over government.db, which the box builds daily with
government_collect.py from free keyless public sources and pushes through render_sync.py. Never touches scanner/scoring/push/jets.

Routes (addons.py): /api/government            summary (scores, coverage, sources, freshness)
                    /api/government/scores     full scoring detail (every agency, component, weight, source, date)
                    /api/government/node?id=   one node + breadcrumbs + paged children (?offset=&limit=)
                    /api/government/search?q=&branch=&state=   instant search (name, office, state, city)
                    /api/government/img?id=    photo proxy (only the URL stored for that node; cached on disk, 7 days)"""
import json, os, re, sqlite3, threading, time, hashlib, urllib.request, urllib.error

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "government.db")
STATIC = os.path.join(BASE, "government_static")
FILES = {"app.js": "application/javascript", "app.css": "text/css"}
IMG_DIR = os.path.join(os.environ.get("BN_STATE_DIR", "/tmp/bn_state"), "gov_img")
IMG_MAX_BYTES = 3 * 1024 * 1024; IMG_CACHE_CAP = 250 * 1024 * 1024; IMG_TTL = 7 * 86400
UA = "Mozilla/5.0 (compatible; blackout.network government tab image cache)"
BRANCHES = ("executive", "legislative", "judicial", "state", "local")
_lock = threading.Lock(); _cache = {"mtime": None, "summary": None}

def _conn():
    if not os.path.exists(DB): return None
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=10); c.row_factory = sqlite3.Row; return c
def _meta(c, k):
    r = c.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
    return json.loads(r[0]) if r else None
def _row(r, full=False):
    d = dict(r); ex = {}
    try: ex = json.loads(d.pop("extra") or "{}") or {}
    except Exception: d.pop("extra", None)
    if not isinstance(ex, dict): ex = {}
    d["extra"] = ex
    d["has_photo"] = bool(d.get("photo_url")) and d.get("photo_status") == "ok"
    d.pop("photo_url", None)   # the browser only ever sees the proxied URL
    if not full:
        for k in ("about", "photo_license", "source_url", "contact_form", "website", "address"): d.pop(k, None)
        d["extra"] = {k: v for k, v in ex.items() if k in ("city", "agency", "population")}
    return d
def _children_count(c, ids):
    if not ids: return {}
    q = ",".join("?" * len(ids))
    return {r[0]: r[1] for r in c.execute(f"SELECT parent, count(*) FROM nodes WHERE parent IN ({q}) GROUP BY parent", ids)}
def _crumbs(c, nid):
    out = []; seen = set()
    while nid and nid not in seen:
        seen.add(nid); r = c.execute("SELECT id, parent, name, kind FROM nodes WHERE id=?", (nid,)).fetchone()
        if not r: break
        out.append({"id": r["id"], "name": r["name"], "kind": r["kind"]}); nid = r["parent"]
    return out[::-1]

def summary():
    c = _conn()
    if not c: return 503, {"error": "Government data has not synced yet. It is refreshed daily on the scanner node and pushed to the site."}
    try:
        mt = os.path.getmtime(DB)
        with _lock:
            if _cache["mtime"] == mt and _cache["summary"]: return 200, _cache["summary"]
        sc = _meta(c, "scores") or {}; srcs = _meta(c, "sources") or {}; upd = _meta(c, "updated")
        cov = {}
        for b in BRANCHES:
            r = c.execute("SELECT count(*) n, sum(kind='person') p, sum(kind='person' AND photo_status='ok') ph, sum(kind='person' AND email IS NOT NULL) em, "
                          "sum(kind='person' AND phone IS NOT NULL) phn, sum(kind='person' AND address IS NOT NULL) ad, sum(kind='person' AND contact_form IS NOT NULL) cf, "
                          "sum(kind='person' AND website IS NOT NULL) web FROM nodes WHERE branch=?", (b,)).fetchone()
            cov[b] = {k: r[k] or 0 for k in r.keys()}
        counts = {
            "federal_agencies": c.execute("SELECT count(*) FROM nodes WHERE kind='agency'").fetchone()[0],
            "federal_courts": c.execute("SELECT count(*) FROM nodes WHERE kind='court'").fetchone()[0],
            "cabinet": c.execute("SELECT count(*) FROM nodes WHERE parent='exec:cabinet'").fetchone()[0],
            "senators": c.execute("SELECT count(*) FROM nodes WHERE id LIKE 'bio:%' AND parent LIKE 'leg:senate:%'").fetchone()[0],
            "representatives": c.execute("SELECT count(*) FROM nodes WHERE id LIKE 'bio:%' AND parent LIKE 'leg:house:%'").fetchone()[0],
            "justices": c.execute("SELECT count(*) FROM nodes WHERE id LIKE 'jus:%'").fetchone()[0],
            "governors": c.execute("SELECT count(*) FROM nodes WHERE id LIKE 'gov:%'").fetchone()[0],
            "state_legislators": c.execute("SELECT count(*) FROM nodes WHERE id LIKE 'os:%'").fetchone()[0],
            "mayors": c.execute("SELECT count(*) FROM nodes WHERE id LIKE 'mayor:%'").fetchone()[0],
            "nodes": c.execute("SELECT count(*) FROM nodes").fetchone()[0]}
        ex = (sc.get("executive") or {})
        ag = [a for a in ex.get("agencies", []) if a.get("score") is not None and a.get("branch", "executive") == "executive"]
        slim = lambda a: {k: a.get(k) for k in ("code", "name", "abbr", "score", "n_components", "branch")}
        states = [dict(r) for r in c.execute("SELECT state, name FROM nodes WHERE parent='states' ORDER BY name")]
        out = {"updated": upd, "overall": sc.get("overall"), "branches": sc.get("branches"), "computed": sc.get("computed"), "fy": sc.get("fy"),
               "weights": ex.get("weights"), "n_scored": ex.get("n_scored"), "n_agencies": ex.get("n_total"), "min_components": ex.get("min_components"),
               "top": [slim(a) for a in ag[:5]], "bottom": [slim(a) for a in ag[-5:][::-1]], "legislative": sc.get("legislative"), "judicial": sc.get("judicial"),
               "counts": counts, "coverage": cov, "sources": srcs, "states": states,
               "label": "blackout.network composite index — not an official rating"}
        with _lock: _cache.update(mtime=mt, summary=out)
        return 200, out
    finally: c.close()

def scores():
    c = _conn()
    if not c: return 503, {"error": "not synced yet"}
    try:
        sc = _meta(c, "scores") or {}
        # link scored agencies to their org-chart node
        keys = {r[0]: r[1] for r in c.execute("SELECT score_key, id FROM nodes WHERE score_key IS NOT NULL")}
        for a in (sc.get("executive") or {}).get("agencies", []): a["node"] = keys.get(a["code"])
        return 200, {**sc, "sources": _meta(c, "sources"), "label": "blackout.network composite index — not an official rating"}
    finally: c.close()

def _int(qs, k, d, lo, hi):
    try: return max(lo, min(hi, int((qs.get(k) or [d])[0])))
    except Exception: return d
def node(qs):
    nid = (qs.get("id") or ["us"])[0][:120]; off = _int(qs, "offset", 0, 0, 100000); lim = _int(qs, "limit", 60, 1, 200)
    st = (qs.get("state") or [""])[0].upper()[:2]
    c = _conn()
    if not c: return 503, {"error": "not synced yet"}
    try:
        r = c.execute("SELECT * FROM nodes WHERE id=?", (nid,)).fetchone()
        if not r: return 404, {"error": "no such node"}
        where = "parent=?"; args = [nid]
        if st and re.fullmatch(r"[A-Z]{2}", st): where += " AND (state=? OR state IS NULL)"; args.append(st)
        total = c.execute(f"SELECT count(*) FROM nodes WHERE {where}", args).fetchone()[0]
        kids = c.execute(f"SELECT * FROM nodes WHERE {where} ORDER BY sort, name LIMIT ? OFFSET ?", args + [lim, off]).fetchall()
        cc = _children_count(c, [k["id"] for k in kids])
        sc = None
        if r["score_key"]:
            for a in ((_meta(c, "scores") or {}).get("executive") or {}).get("agencies", []):
                if a["code"] == r["score_key"]: sc = a; break
        d = _row(r, full=True); d["n_children"] = total; d["score"] = sc
        return 200, {"node": d, "crumbs": _crumbs(c, nid), "children": [{**_row(k), "n_children": cc.get(k["id"], 0)} for k in kids],
                     "offset": off, "limit": lim, "total": total}
    finally: c.close()

def search(qs):
    q = (qs.get("q") or [""])[0].strip()[:80]; br = (qs.get("branch") or [""])[0]; st = (qs.get("state") or [""])[0].upper()[:2]
    lim = _int(qs, "limit", 25, 1, 60)
    toks = re.findall(r"[\w'.-]+", q, re.U)
    if not toks and not st: return 200, {"q": q, "results": []}
    c = _conn()
    if not c: return 503, {"error": "not synced yet"}
    try:
        args = []; where = []
        if toks:
            fts = " ".join('"' + t.replace('"', "") + '"*' for t in toks[:6])
            where.append("n.id IN (SELECT id FROM nodes_fts WHERE nodes_fts MATCH ?)"); args.append(fts)
        if br in BRANCHES: where.append("n.branch=?"); args.append(br)
        if st and re.fullmatch(r"[A-Z]{2}", st): where.append("n.state=?"); args.append(st)
        if not toks: where.append("n.kind='person'")
        rows = c.execute(f"SELECT n.* FROM nodes n WHERE {' AND '.join(where)} ORDER BY (n.kind='person') DESC, "
                         f"CASE n.branch WHEN 'executive' THEN 0 WHEN 'legislative' THEN 1 WHEN 'judicial' THEN 2 WHEN 'state' THEN 3 ELSE 4 END, n.name LIMIT ?", args + [lim]).fetchall()
        out = []
        for r in rows:
            cr = _crumbs(c, r["parent"]); d = _row(r); d["path"] = " › ".join(x["name"] for x in cr[1:]); out.append(d)
        return 200, {"q": q, "results": out}
    except sqlite3.OperationalError as e: return 400, {"error": "bad query", "detail": str(e)[:80]}
    finally: c.close()

def _img_prune():
    try:
        fs = [(os.path.getmtime(p), os.path.getsize(p), p) for p in (os.path.join(IMG_DIR, f) for f in os.listdir(IMG_DIR))]
        tot = sum(f[1] for f in fs)
        for mt, sz, p in sorted(fs):
            if tot <= IMG_CACHE_CAP: break
            os.unlink(p); tot -= sz
    except Exception: pass
def img(qs):
    nid = (qs.get("id") or [""])[0][:120]
    c = _conn()
    if not c: return 404, {"error": "no data"}
    try: r = c.execute("SELECT photo_url, photo_status FROM nodes WHERE id=?", (nid,)).fetchone()
    finally: c.close()
    if not r or not r["photo_url"] or not r["photo_url"].startswith("https://"): return 404, {"error": "no official image"}
    url = r["photo_url"]; os.makedirs(IMG_DIR, exist_ok=True)
    p = os.path.join(IMG_DIR, hashlib.sha1(url.encode()).hexdigest())
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < IMG_TTL:
        b = open(p, "rb").read(); ct = open(p + ".ct").read() if os.path.exists(p + ".ct") else "image/jpeg"
        return 200, b, ct
    try:
        fetch = url + "?w=480" if url.startswith("https://www.whitehouse.gov/wp-content/uploads/") and "?" not in url else url   # WordPress resized copy (originals run 6 MB+)
        req = urllib.request.Request(fetch, headers={"User-Agent": UA, "Accept": "image/*"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            ct = (resp.headers.get("Content-Type") or "").split(";")[0].strip(); b = resp.read(IMG_MAX_BYTES + 1)
        if len(b) > IMG_MAX_BYTES: return 404, {"error": "image too large"}
        if not ct.startswith("image/") or ct == "image/svg+xml":
            ct = "image/jpeg" if b[:3] == b"\xff\xd8\xff" else "image/png" if b[:4] == b"\x89PNG" else "image/webp" if b[8:12] == b"WEBP" else "image/gif" if b[:3] == b"GIF" else None
            if not ct: return 404, {"error": "source did not return an image"}
        with open(p + ".tmp", "wb") as f: f.write(b)
        os.replace(p + ".tmp", p); open(p + ".ct", "w").write(ct); _img_prune()
        return 200, b, ct
    except Exception as e:
        if os.path.exists(p): return 200, open(p, "rb").read(), open(p + ".ct").read() if os.path.exists(p + ".ct") else "image/jpeg"
        return 404, {"error": "official image unavailable"}

def handle_get(path, qs):
    n = path[len("/api/government/"):] if path.startswith("/api/government/") else ""
    if n in FILES:
        with open(os.path.join(STATIC, n), "rb") as fh: return 200, fh.read(), FILES[n]
    if path == "/api/government": return summary()
    if n == "scores": return scores()
    if n == "node": return node(qs)
    if n == "search": return search(qs)
    if n == "img": return img(qs)
    return 404, {"error": "not found"}

def handle_stream(path, qs, h):
    """Same as handle_get, but photos and static files go out with a browser cache header (everything else: no-store via h.send)."""
    res = handle_get(path, qs)
    if path.startswith("/api/government/img") and res[0] == 200 and len(res) == 3:
        b, ct = res[1], res[2]
        h.send_response(200); h.send_header("Content-Type", ct); h.send_header("Cache-Control", "public, max-age=86400")
        h.send_header("X-Content-Type-Options", "nosniff"); h.send_header("Referrer-Policy", "same-origin"); h.send_header("Content-Length", str(len(b))); h.end_headers(); h.wfile.write(b)
        return
    return h.send(*res)
