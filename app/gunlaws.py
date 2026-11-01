"""Gun Laws tab (nav "Gun Laws", deep link #gunlaws, t319): Second Amendment and firearms cases in U.S. courts (Supreme Court docket
and petitions, notable federal appeals / district / state cases), firearms bills in Congress, Nov. 3 ballot measures, prediction
markets and blackout.network's transparent statistical estimates. Read-only over gunlaws.db, which the box builds with
gunlaws_collect.py (daily full refresh, hourly market prices) and pushes through render_sync.py. Live market prices are re-read
from the public Kalshi / Polymarket APIs here (cached 60 s). Never touches scanner/scoring/push/jets.

Routes (addons.py "/api/gunlaws"):
  /api/gunlaws              everything except bill details and price history
  /api/gunlaws/bills        firearms bills (list fields)
  /api/gunlaws/bill?id=     one bill with its CRS summary, subjects and committees
  /api/gunlaws/history?key=&t=   price history for one market outcome (upstream daily/hourly + our hourly snapshots)
  /api/gunlaws/live         current prices for every tracked market (60 s cache)"""
import json, os, sqlite3, threading, time, urllib.request, urllib.parse

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "gunlaws.db")
STATIC = os.path.join(BASE, "gunlaws_static")
FILES = {"app.js": "application/javascript", "app.css": "text/css"}
KS = "https://api.elections.kalshi.com/trade-api/v2"; PM = "https://gamma-api.polymarket.com"
UA = "Mozilla/5.0 (compatible; blackout.network gun-laws tab; live market prices)"
_lock = threading.Lock(); _cache = {"mtime": None, "main": None, "bills": None}; _live = {"at": 0, "data": None}

def _conn():
    if not os.path.exists(DB): return None
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=10); return c
def _m(c, k, d=None):
    r = c.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
    return json.loads(r[0]) if r else d
def _slim_market(m):
    m = dict(m); m["outcomes"] = [{k: v for k, v in o.items() if k not in ("hist", "snaps")} | {"n_hist": len(o.get("hist") or []), "n_snaps": len(o.get("snaps") or []),
                                   "spark": _spark(o)} for o in m.get("outcomes") or []]
    return m
def _spark(o, days=30):
    cut = time.time() - days * 86400
    pts = [p for p in (o.get("hist") or []) if p[0] >= cut]
    last_up = pts[-1][0] if pts else 0
    pts += [p for p in (o.get("snaps") or []) if p[0] > last_up and p[0] >= cut]
    if len(pts) > 60:   # thin to ~60 points for the sparkline
        step = len(pts) / 60.0; pts = [pts[int(i * step)] for i in range(60)] + [pts[-1]]
    return pts
def main():
    c = _conn()
    if not c: return 503, {"error": "Gun Laws data has not synced yet. It is refreshed on the scanner node and pushed to the site."}
    try:
        mt = os.path.getmtime(DB)
        with _lock:
            if _cache["mtime"] == mt and _cache["main"]: return 200, _cache["main"]
        mk = _m(c, "markets") or {}
        bills = _m(c, "bills") or []
        stages = {}
        for b in bills: stages[b["stage"]] = stages.get(b["stage"], 0) + 1
        sc = []
        for x in _m(c, "scotus") or []:   # trim what the page never shows
            x = {k: v for k, v in x.items() if k not in ("json_url", "fetched", "qp_link")}
            if not x.get("cur"): x["entries"] = (x.get("entries") or [])[-6:]
            sc.append(x)
        out = {"updated": _m(c, "updated"), "scotus": sc, "scotus_src": _m(c, "scotus_src"), "scotus_rows": len(_m(c, "scotus_rows") or []),
               "curated": _m(c, "curated") or {}, "model": _m(c, "model"), "reversal": _m(c, "reversal"),
               "markets": {"items": [_slim_market(x) for x in mk.get("items") or []], "at": mk.get("at"), "errors": mk.get("errors"), "searched": mk.get("searched")},
               "market_index": {k: v for k, v in (_m(c, "market_index") or {}).items() if k != "found"},
               "bills_src": _m(c, "bills_src"), "bill_stages": stages, "bills_omnibus": [{k: b.get(k) for k in ("id", "label", "title", "url")} for b in _m(c, "bills_omnibus") or []],
               "label": "blackout.network statistical estimates, not legal advice"}
        with _lock: _cache.update(mtime=mt, main=out, bills=None)
        return 200, out
    finally: c.close()
def bills():
    c = _conn()
    if not c: return 503, {"error": "not synced yet"}
    try:
        mt = os.path.getmtime(DB)
        with _lock:
            if _cache["mtime"] == mt and _cache["bills"]: return 200, _cache["bills"]
        keep = ("id", "label", "title", "short", "chamber", "introduced", "sponsor", "cosponsors", "cos_party", "stage", "vetoed", "law_date", "latest", "url", "crs_tagged", "policy")
        out = {"bills": [{k: b.get(k) for k in keep} for b in _m(c, "bills") or []], "src": _m(c, "bills_src")}
        with _lock:
            if _cache["mtime"] == mt: _cache["bills"] = out
        return 200, out
    finally: c.close()
def bill(qs):
    bid = (qs.get("id") or [""])[0][:20]
    c = _conn()
    if not c: return 503, {"error": "not synced yet"}
    try:
        for b in _m(c, "bills") or []:
            if b["id"] == bid: return 200, b
        return 404, {"error": "no such bill"}
    finally: c.close()
def history(qs):
    key = (qs.get("key") or [""])[0][:160]; t = (qs.get("t") or [""])[0][:160]
    c = _conn()
    if not c: return 503, {"error": "not synced yet"}
    try:
        for m in (_m(c, "markets") or {}).get("items") or []:
            if m["key"] != key: continue
            for o in m["outcomes"]:
                if (o.get("ticker") or "") == t:
                    return 200, {"key": key, "title": m["title"], "name": o.get("name"), "src": m["src"], "url": m["url"], "hist": o.get("hist") or [], "snaps": o.get("snaps") or []}
        return 404, {"error": "market not tracked"}
    finally: c.close()
def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=12) as r: return json.loads(r.read())
def _f(x):
    try: return None if x in (None, "") else float(x)
    except Exception: return None
def live():
    with _lock:
        if _live["data"] and time.time() - _live["at"] < 60: return 200, _live["data"]
    c = _conn()
    if not c: return 503, {"error": "not synced yet"}
    try: items = (_m(c, "markets") or {}).get("items") or []
    finally: c.close()
    kt = [o["ticker"] for m in items if m["src"] == "Kalshi" for o in m["outcomes"] if o.get("ticker")]
    pe = sorted({m["event"] for m in items if m["src"] == "Polymarket" and m.get("event")})
    prices, errs = {}, []
    try:
        for i in range(0, len(kt), 50):
            d = _get(f"{KS}/markets?tickers={urllib.parse.quote(','.join(kt[i:i+50]))}&limit=100")
            for m in d.get("markets") or []:
                b, a, l = _f(m.get("yes_bid_dollars")), _f(m.get("yes_ask_dollars")), _f(m.get("last_price_dollars"))
                mid = round((b + a) / 2, 4) if b is not None and a and a - b <= .25 else l
                prices["Kalshi:" + m["ticker"]] = {"mid": mid, "bid": b, "ask": a, "last": l, "volume": _f(m.get("volume_fp")), "status": m.get("status")}
    except Exception as e: errs.append("Kalshi: " + str(e)[:120])
    for slug in pe:
        try:
            for e in _get(f"{PM}/events?slug={urllib.parse.quote(slug)}") or []:
                for m in e.get("markets") or []:
                    try: p = json.loads(m.get("outcomePrices") or "[]")
                    except Exception: continue
                    if p: prices["Polymarket:" + (m.get("slug") or "")] = {"mid": round(float(p[0]), 4), "bid": _f(m.get("bestBid")), "ask": _f(m.get("bestAsk")), "volume": _f(m.get("volume")),
                                                                           "status": "closed" if m.get("closed") else "active"}
        except Exception as ex: errs.append("Polymarket: " + str(ex)[:120])
    # a source that failed (e.g. Kalshi HTTP 429) keeps its last good prices instead of dropping them;
    # on errors back off for 3 minutes so we don't hammer a rate-limited API
    prev = (_live.get("good") or {})
    for k, v in prev.items():
        if k not in prices: prices[k] = v
    good = {**prev, **prices}
    stale = sorted({e.split(":")[0] for e in errs})
    out = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "prices": prices, "errors": errs, "stale": stale, "cache_seconds": 180 if errs else 60}
    with _lock: _live.update(at=time.time() + (120 if errs else 0), data=out, good=good)
    return 200, out
def handle_get(path, qs):
    n = path[len("/api/gunlaws/"):] if path.startswith("/api/gunlaws/") else ""
    if n in FILES:
        with open(os.path.join(STATIC, n), "rb") as fh: return 200, fh.read(), FILES[n]
    if path in ("/api/gunlaws", "/api/gunlaws/"): return main()
    if n == "bills": return bills()
    if n == "bill": return bill(qs)
    if n == "history": return history(qs)
    if n == "live": return live()
    return 404, {"error": "not found"}
