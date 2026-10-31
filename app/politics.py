"""Politics add-on (tab "🏛 Politics", deep link #politics). Strictly neutral, read-only view.
- Political developments: the scanner's existing alerts in category 'political' from blackout.db (opened read-only via file:blackout.db?mode=ro),
  The Wire (watchlist=0) and Watchlist (watchlist=1) only; suppressed rows (watchlist=2) are not shown, same as the rest of the dashboard.
- Prediction markets: free public read-only APIs, no account, no key, no trading.
    Polymarket Gamma API  https://gamma-api.polymarket.com/events (politics-related tags), refreshed every 10 min.
    Kalshi public API     https://api.elections.kalshi.com/trade-api/v2 : a discovery sweep of open events every 6 h ranks US political
                          events by 24 h volume; the top ones are re-read individually every 10 min.
  Results are cached in a sidecar politics.db (never blackout.db). If an API fails, the last good snapshot is kept and the source is marked unavailable.
Titles, questions and outcome names are shown verbatim from the source. Nothing here changes scores, ranks or the scanner."""
import os, sys, json, re, time, gzip, sqlite3, threading, urllib.request, urllib.parse, importlib
from datetime import datetime, timezone, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
PDB = os.path.join(BASE, "politics.db"); BDB = "file:" + os.path.join(BASE, "blackout.db") + "?mode=ro"
STATIC = os.path.join(BASE, "politics_static")
UA = "blackout.network-dashboard/1.0 (private personal dashboard; read-only, polite 10-minute poll)"
REFRESH = 600            # market refresh, seconds
KS_DISCOVER = 6 * 3600   # Kalshi discovery sweep
FORCE_MIN = 90           # a manual Refresh re-fetches markets at most this often
PM_BASE = "https://gamma-api.polymarket.com"; KS_BASE = "https://api.elections.kalshi.com/trade-api/v2"
PM_TAGS = [("politics", 60), ("midterms", 40), ("congress", 20), ("us-politics", 20), ("us-government", 20), ("scotus", 10)]
PM_US = {"united-states", "us-presidential-election", "midterms", "congress", "us-politics", "us-government", "senate-elections", "senate-midterms",
         "governor-midterms", "house-of-representatives", "scotus", "supreme-court", "trump-cabinet", "gov-shutdown", "government-shutdown", "us-elections",
         "midterms-control", "speaker", "house", "governor"}
PM_SKIP = {"tweets-markets", "pop-culture", "mention-markets", "mentions", "sports", "crypto-prices", "celebrities", "reality-tv"}
FOREIGN = re.compile(r"\b(UK|U\.K\.|Brit\w*|Brazil\w*|Israel\w*|India\w*|Canad\w*|Mexic\w*|German\w*|Japan\w*|Korea\w*|France|French|EU|European|Pope|NATO|Prime Minister|Parliament\w*|Netanyahu|Likud|Xi Jinping|China|Chinese|Russia\w*|Ukrain\w*|Venezuel\w*|Iran\w*|Hungar\w*|Poland|Polish|Colombia\w*|Peru\w*|Chile\w*|Argentin\w*|Australia\w*|Bulgaria\w*|Wales|Welsh|Ireland|Irish|Scotland|Scottish|Africa\w*|G7|Sheinbaum|Taiwan\w*|Philippin\w*|Turk\w*|Ital\w*|Spain|Spanish|Portug\w*|Dutch|Netherlands|Sweden|Swedish|Norw\w*|Denmark|Danish|Finland|Finnish|Austria\w*|Swiss|Switzerland|Belgi\w*|Czech|Romania\w*|Greece|Greek|Thai\w*|Vietnam\w*|Indonesia\w*|Malaysia\w*|Pakistan\w*|Bangladesh\w*|Nigeria\w*|Kenya\w*|Egypt\w*|Saudi|Qatar|Syria\w*|Lebanon|Iraq\w*|Gaza|Palestin\w*|Hamas|Hezbollah|Ecuador\w*|Bolivia\w*|Cuba\w*|Haiti\w*|Hondura\w*|Guatemala\w*|Nicaragua\w*|Panama|Costa Rica|Dominican|Jamaica\w*|New Zealand|Greenland|Quebec|Ontario|Alberta|Bavaria\w*|Tokyo|London|Paris|Seoul|Moscow|Kyiv|Kiev|Beijing)\b")
US_HINT = re.compile(r"\b(Senate|House|Congress\w*|Governor|President\w*|Speaker|midterm\w*|nominee|nomination|Supreme Court|SCOTUS|shutdown|Act|filibuster|impeach\w*|Cabinet|Trump\w*|Vance|Electoral|Attorney General|Secretary|DNC|RNC|Fed chair|Mayor|U\.S\.|US|USA|United States|federal|tariff\w*|executive order|pardon\w*|Democrat\w*|Republican\w*|GOP|White House|Justice|veto|debt ceiling|recount|ballot|primary|caucus)\b")
KS_SKIP = re.compile(r"(\bposts?\b|\btweets?\b|\bsay\b|\bmention|Truth Social|word|phrase|\bpost count|approval average on|RCP approval)", re.I)
KS_DISTRICT = re.compile(r"^(KXHOUSERACE|HOUSE[A-Z]{2}\d)")

def iso(d=None): return (d or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
def et(s):
    if not s: return None
    try:
        from zoneinfo import ZoneInfo
        d = datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).astimezone(ZoneInfo("America/New_York"))
        return d.strftime("%b %-d, %Y %-I:%M %p ") + d.tzname()
    except Exception: return s
def fnum(x):
    try: return float(x)
    except Exception: return None

def pdb():
    c = sqlite3.connect(PDB, timeout=20); c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE IF NOT EXISTS cache(src TEXT PRIMARY KEY, fetched_at TEXT, ok INTEGER, error TEXT, last_good_at TEXT, payload TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS fetchlog(ts TEXT, src TEXT, ok INTEGER, n INTEGER, ms INTEGER, kbytes INTEGER, error TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT)")
    return c
def meta_get(k, d=None):
    c = pdb(); r = c.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone(); c.close()
    return json.loads(r["v"]) if r else d
def meta_set(k, v):
    c = pdb(); c.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", (k, json.dumps(v))); c.commit(); c.close()

_NET = {"bytes": 0}
def get(url, timeout=30):
    r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json", "Accept-Encoding": "gzip"}), timeout=timeout)
    b = r.read(60_000_000); _NET["bytes"] += len(b)
    if r.headers.get("Content-Encoding") == "gzip": b = gzip.decompress(b)
    return json.loads(b)

def topic(title):
    t = title or ""
    if re.search(r"which party|control|balance of power|\bseats?\b|trifecta|majority|wave\b|popular vote|generic ballot|tsunami", t, re.I) and re.search(r"House|Senate|Congress|midterm", t, re.I): return "Control of Congress"
    if re.search(r"Senate", t, re.I) and re.search(r"winner|win|race|election|margin|combo|closest", t, re.I): return "Senate races"
    if re.search(r"Governor|governorship", t, re.I): return "Governor races"
    if re.search(r"House", t, re.I) and re.search(r"winner|race|district|-\d\d", t, re.I): return "House races"
    if re.search(r"20(28|32)|nominee|nomination|presidential|\bPresident\b|inaugurat|Electoral College|popular vote", t, re.I): return "Presidential & nominations"
    if re.search(r"Mayor|Attorney General|election|race\b|winner", t, re.I): return "Other races"
    return "Policy & government"

# ---------------- ownership profiles + source/pollster references ----------------
OWN = os.path.join(STATIC, "ownership.json")
def ownership():
    try:
        with open(OWN) as f: return json.load(f)
    except Exception: return {"orgs": [], "watch": []}
def refs(text):
    """Names of profiled organizations or watched pollsters that the text actually mentions (patterns live in ownership.json)."""
    o = ownership(); found = []
    for org in o.get("orgs", []) + o.get("watch", []):
        for pat in org.get("match") or []:
            if re.search(pat, text or ""): found.append(org["id"]); break
    return found
_H = {"mt": 0, "mod": None}
def H():
    f = os.path.join(BASE, "politics_history.py"); mt = os.path.getmtime(f)
    if _H["mod"] is None or mt != _H["mt"]:
        ph = sys.modules.get("politics_history")
        _H["mod"] = importlib.reload(ph) if ph else importlib.import_module("politics_history"); _H["mt"] = mt
    return _H["mod"]

# ---------------- Polymarket ----------------
def polymarket():
    seen = {}
    for tag, lim in PM_TAGS:
        q = urllib.parse.urlencode({"active": "true", "closed": "false", "archived": "false", "tag_slug": tag, "limit": lim, "order": "volume24hr", "ascending": "false"})
        for e in get(f"{PM_BASE}/events?{q}"): seen.setdefault(e.get("id"), e)
        time.sleep(0.4)
    out = []
    for e in seen.values():
        tags = {t.get("slug") for t in (e.get("tags") or []) if t.get("slug")}
        title = (e.get("title") or "").strip()
        if tags & PM_SKIP or not (tags & PM_US): continue
        if FOREIGN.search(title) and not (tags & {"midterms", "congress", "us-politics", "us-government", "senate-elections", "governor-midterms"}): continue
        oc = []; reftxt = " ".join([e.get("description") or "", e.get("resolutionSource") or ""])
        for m in e.get("markets") or []:
            if m.get("closed") or not m.get("active") or not m.get("outcomePrices"): continue
            reftxt += " " + (m.get("description") or "") + " " + (m.get("resolutionSource") or "")
            try: names = json.loads(m.get("outcomes") or "[]"); prices = [float(p) for p in json.loads(m["outcomePrices"])]; toks = json.loads(m.get("clobTokenIds") or "[]")
            except Exception: continue
            if not names or len(names) != len(prices): continue
            if [n.lower() for n in names] == ["yes", "no"]:
                oc.append({"name": (m.get("groupItemTitle") or m.get("question") or "").strip(), "p": prices[0], "q": m.get("question"),
                           "bid": fnum(m.get("bestBid")), "ask": fnum(m.get("bestAsk")), "last": fnum(m.get("lastTradePrice")), "vol": fnum(m.get("volume")), "token": toks[0] if toks else None})
            else:
                for i, (n, p) in enumerate(zip(names, prices)): oc.append({"name": n, "p": p, "q": m.get("question"), "vol": fnum(m.get("volume")), "token": toks[i] if i < len(toks) else None})
        if not oc: continue
        single = len(e.get("markets") or []) == 1 and oc[0]["name"] == (e["markets"][0].get("question") or "").strip()
        if single: oc = [dict(oc[0], name="Yes"), dict(oc[0], name="No", p=round(1 - oc[0]["p"], 4), bid=None, ask=None, last=None, invert=True)]
        oc.sort(key=lambda x: -x["p"])
        out.append({"refs": refs(reftxt + " " + title), "src": "Polymarket", "id": e.get("slug"), "title": title, "topic": topic(title), "url": f"https://polymarket.com/event/{e.get('slug')}",
                    "volume": fnum(e.get("volume")), "volume24h": fnum(e.get("volume24hr")), "vol_unit": "USD", "end": e.get("endDate"),
                    "n_outcomes": len(oc), "outcomes": oc[:6], "updated": e.get("updatedAt")})
    out.sort(key=lambda x: -(x["volume24h"] or 0))
    return out[:40]

# ---------------- Kalshi ----------------
def ks_us(e):
    title = e.get("title") or ""; st = e.get("series_ticker") or ""
    if e.get("category") not in ("Politics", "Elections"): return False
    if KS_DISTRICT.match(st) or KS_SKIP.search(title) or (e.get("sub_title") and KS_SKIP.search(e["sub_title"])): return False
    if FOREIGN.search(title + " " + (e.get("sub_title") or "")): return False
    return bool(US_HINT.search(title + " " + (e.get("sub_title") or "")))
def ks_discover():
    """One paced sweep of all open Kalshi events (nested markets, gzip) to rank US political events by 24 h volume. Runs every 6 h."""
    cur, pages, cands = "", 0, []
    while pages < 200:
        q = {"status": "open", "limit": 200, "with_nested_markets": "true"}
        if cur: q["cursor"] = cur
        d = get(f"{KS_BASE}/events?" + urllib.parse.urlencode(q), timeout=60); pages += 1
        for e in d.get("events") or []:
            if ks_us(e):
                ms = e.get("markets") or []
                cands.append((sum(fnum(m.get("volume_24h_fp")) or 0 for m in ms), sum(fnum(m.get("volume_fp")) or 0 for m in ms), e["event_ticker"]))
        cur = d.get("cursor")
        if not cur or not d.get("events"): break
        time.sleep(0.25)
    cands.sort(reverse=True)
    top = [t for _, _, t in cands[:45]]
    meta_set("kalshi_tracked", {"at": iso(), "pages": pages, "candidates": len(cands), "tickers": top})
    return top
def kalshi(force_discover=False):
    tr = meta_get("kalshi_tracked")
    if force_discover or not tr or not tr.get("tickers") or (time.time() - datetime.strptime(tr["at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()) > KS_DISCOVER:
        ks_discover(); tr = meta_get("kalshi_tracked")
    out, errs = [], 0
    for t in tr["tickers"]:
        try: d = get(f"{KS_BASE}/events/{urllib.parse.quote(t)}?with_nested_markets=true", timeout=20)
        except Exception: errs += 1; continue
        e = d.get("event") or {}; ms = e.get("markets") or d.get("markets") or []
        oc = []
        for m in ms:
            if m.get("status") not in ("active", "open"): continue
            last, bid, ask = fnum(m.get("last_price_dollars")), fnum(m.get("yes_bid_dollars")), fnum(m.get("yes_ask_dollars"))
            if last and last > 0: p, basis = last, "last trade"
            elif bid is not None and ask and ask > 0: p, basis = round((bid + ask) / 2, 4), "bid/ask midpoint"
            else: continue
            oc.append({"name": (m.get("yes_sub_title") or m.get("title") or m.get("ticker") or "").strip(), "p": p, "basis": basis, "q": m.get("title"),
                       "bid": bid, "ask": ask, "last": last, "vol": fnum(m.get("volume_fp")), "close": m.get("close_time"), "ticker": m.get("ticker"), "open": m.get("open_time")})
        if not oc: continue
        if len(oc) == 1 and not e.get("mutually_exclusive"):
            o = oc[0]; oc = [dict(o, name="Yes"), dict(o, name="No", p=round(1 - o["p"], 4), bid=None, ask=None, last=None, invert=True)]
        oc.sort(key=lambda x: -x["p"])
        st = (e.get("series_ticker") or t.split("-")[0]).lower()
        reftxt = " ".join([json.dumps(e.get("settlement_sources") or [])] + [(m.get("rules_primary") or "") + " " + (m.get("rules_secondary") or "") for m in ms])
        title = (e.get("title") or "").strip()
        closes = sorted(x["close"] for x in oc if x.get("close"))
        out.append({"refs": refs(reftxt + " " + title), "series": e.get("series_ticker") or t.split("-")[0], "src": "Kalshi", "id": t, "title": title, "sub_title": e.get("sub_title"), "topic": topic(title), "url": f"https://kalshi.com/markets/{st}",
                    "volume": sum(fnum(m.get("volume_fp")) or 0 for m in ms), "volume24h": sum(fnum(m.get("volume_24h_fp")) or 0 for m in ms), "vol_unit": "contracts",
                    "end": closes[0] if closes else None, "n_outcomes": len(oc), "outcomes": oc[:6]})
        time.sleep(0.15)
    if not out and errs: raise RuntimeError(f"all {errs} event requests failed")
    out.sort(key=lambda x: -(x["volume24h"] or 0))
    return out[:40], {"discovered_at": tr.get("at"), "candidates": tr.get("candidates"), "tracked": len(tr.get("tickers") or []), "event_errors": errs}

# ---------------- refresh + cache ----------------
_lock = getattr(sys, "_bn_politics_lock", None) or threading.Lock(); sys._bn_politics_lock = _lock
def refresh_src(src):
    t0 = time.time(); b0 = _NET["bytes"]; extra = {}
    try:
        if src == "polymarket": items = polymarket()
        else: items, extra = kalshi()
        ok, err = 1, None
    except Exception as ex:
        items, ok, err = None, 0, f"{type(ex).__name__}: {ex}"[:300]
    now = iso(); c = pdb()
    if ok:
        c.execute("INSERT OR REPLACE INTO cache VALUES(?,?,?,?,?,?)", (src, now, 1, None, now, json.dumps({"items": items, "extra": extra})))
    else:
        r = c.execute("SELECT * FROM cache WHERE src=?", (src,)).fetchone()
        c.execute("INSERT OR REPLACE INTO cache VALUES(?,?,?,?,?,?)", (src, now, 0, err, r["last_good_at"] if r else None, r["payload"] if r else None))
    c.execute("INSERT INTO fetchlog VALUES(?,?,?,?,?,?,?)", (now, src, ok, len(items or []), int((time.time() - t0) * 1000), (_NET["bytes"] - b0) // 1024, err))
    c.execute("DELETE FROM fetchlog WHERE rowid NOT IN (SELECT rowid FROM fetchlog ORDER BY rowid DESC LIMIT 3000)")
    c.commit(); c.close()
    if ok and items:
        try: H().record_snaps(items[0]["src"], items)
        except Exception as ex: print("politics snaps:", ex, flush=True)
def refresh_all():
    if not _lock.acquire(blocking=False): return False
    try:
        for s in ("polymarket", "kalshi"): refresh_src(s)
        meta_set("last_cycle", iso())
        warm_history()
    finally: _lock.release()
    return True

def cached(src):
    c = pdb(); r = c.execute("SELECT payload FROM cache WHERE src=?", (src.lower(),)).fetchone(); c.close()
    return (json.loads(r["payload"]) or {}).get("items") or [] if r and r["payload"] else []
def warm_history():
    """Upstream price history for each card's leading outcome, cached for an hour (sparklines). Errors only leave a gap."""
    for src in ("Polymarket", "Kalshi"):
        for m in cached(src):
            try: H().history(src, m, [m["outcomes"][0]["name"]], max_age=3600)
            except Exception as ex: print("politics history:", ex, flush=True)
def maybe_harvest():
    last = meta_get("hist_last"); run = meta_get("hist_running")
    age = time.time() - datetime.strptime(last, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp() if last else 1e9
    if age < 86400 or any(t.name == "politics_hist" and t.is_alive() for t in threading.enumerate()): return
    threading.Thread(target=lambda: H().harvest(), name="politics_hist", daemon=True).start()
def _wake():
    w = getattr(sys, "_bn_politics_wake", None)
    if w is None: w = threading.Event(); sys._bn_politics_wake = w
    return w
def _loop():
    time.sleep(10)
    while True:
        mod = sys.modules.get("politics") or sys.modules.get(__name__)
        try: mod.refresh_all()
        except Exception as ex: print("politics markets:", ex, flush=True)
        try: mod.maybe_harvest()
        except Exception as ex: print("politics track record:", ex, flush=True)
        _wake().clear(); _wake().wait(REFRESH)
def _ensure_worker():
    if any(t.name == "politics_markets" and t.is_alive() for t in threading.enumerate()): return
    threading.Thread(target=_loop, name="politics_markets", daemon=True).start()
_ensure_worker()

# ---------------- political alerts (blackout.db, read-only) ----------------
def alerts(window):
    hours = {"24h": 24, "7d": 168}.get(window, 24)
    b = sqlite3.connect(BDB, uri=True, timeout=30); b.row_factory = sqlite3.Row
    now = datetime.now(timezone.utc)
    def cnt(h):
        cut = iso(now - timedelta(hours=h))
        return {r["watchlist"]: r["n"] for r in b.execute("SELECT watchlist, COUNT(*) n FROM clusters WHERE category='political' AND watchlist IN (0,1) AND COALESCE(event_time, first_seen)>=? GROUP BY watchlist", (cut,))}
    cut = iso(now - timedelta(hours=hours))
    rows = [dict(r) for r in b.execute("""SELECT cluster_id, title, category, location, event_time, first_seen, updated, score, rank, confidence, n_items, n_families,
              eff_families, families, links, watchlist, brief, rising FROM clusters WHERE category='political' AND watchlist IN (0,1)
              AND COALESCE(event_time, first_seen)>=? ORDER BY rank DESC, score DESC, COALESCE(event_time, first_seen) DESC LIMIT 200""", (cut,))]
    c24, c7 = cnt(24), cnt(168); b.close()
    for r in rows:
        for k in ("families", "links"):
            try: r[k] = json.loads(r[k] or "[]")
            except Exception: r[k] = []
    return rows, {"24h": {"wire": c24.get(0, 0), "watchlist": c24.get(1, 0)}, "7d": {"wire": c7.get(0, 0), "watchlist": c7.get(1, 0)}}

def data(window, force=False):
    if force:
        lc = meta_get("last_cycle")
        age = time.time() - datetime.strptime(lc, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp() if lc else 1e9
        if age > FORCE_MIN: refresh_all()
        try: maybe_harvest()
        except Exception as ex: print("politics track record:", ex, flush=True)
    rows, counts = alerts(window)
    c = pdb(); srcs = {}
    for r in c.execute("SELECT * FROM cache"):
        p = json.loads(r["payload"]) if r["payload"] else {"items": [], "extra": {}}
        srcs[r["src"]] = {"ok": bool(r["ok"]), "error": r["error"], "fetched_at": r["fetched_at"], "fetched_at_et": et(r["fetched_at"]),
                          "last_good_at": r["last_good_at"], "last_good_at_et": et(r["last_good_at"]), "items": p.get("items") or [], "extra": p.get("extra") or {}}
    log = [dict(r) for r in c.execute("SELECT * FROM fetchlog ORDER BY rowid DESC LIMIT 12")]
    c.close()
    h = H()
    for k, s in srcs.items():
        for m in s["items"]:
            try:
                ser = h.history(m["src"], m, [m["outcomes"][0]["name"]], fetch=False).get(m["outcomes"][0]["name"]) or {}
                m["spark"] = h.spark(ser.get("points") or []); m["spark_src"] = sorted({x[2] for x in (ser.get("points") or [])})
            except Exception: m["spark"] = []
            for o in m.get("outcomes") or []:
                for k2 in ("token", "ticker", "open", "invert"): o.pop(k2, None)
    alert_refs = sorted({x for r in rows for x in refs(" ".join([r.get("title") or "", r.get("brief") or ""]))})
    for s in ("polymarket", "kalshi"):
        srcs.setdefault(s, {"ok": None, "error": "first fetch still running", "items": [], "extra": {}})
    return {"generated": iso(), "generated_et": et(iso()), "window": window, "alerts": rows, "counts": counts, "markets": srcs, "fetchlog": log,
            "refresh_seconds": REFRESH, "kalshi_discover_hours": KS_DISCOVER // 3600, "alert_refs": alert_refs}

def handle_get(path, qs):
    if path in ("/api/politics/app.js", "/api/politics/app.css"):
        f = os.path.join(STATIC, os.path.basename(path))
        with open(f, "rb") as fh: return 200, fh.read(), "application/javascript" if f.endswith(".js") else "text/css"
    if path == "/api/politics/ownership.json":
        o = ownership(); seen = {}
        for src in ("Polymarket", "Kalshi"):
            for m in cached(src):
                for r in m.get("refs") or []: seen.setdefault(r, []).append(f"{src}: {m['title']}")
        rows, _ = alerts("7d")
        for r in rows:
            for x in refs(" ".join([r.get("title") or "", r.get("brief") or ""])): seen.setdefault(x, []).append("Alert: " + (r.get("title") or "")[:120])
        o["detected"] = {k: v[:8] for k, v in seen.items()}; o["detected_n"] = {k: len(v) for k, v in seen.items()}
        return 200, o
    if path == "/api/politics/accuracy":
        return 200, H().metrics()
    if path == "/api/politics/history":
        src = (qs.get("src") or [""])[0]; mid = (qs.get("id") or [""])[0]
        m = next((x for x in cached(src) if x["id"] == mid), None)
        if not m: return 404, {"error": "market not in the current list"}
        hist = H().history(src, m, [o["name"] for o in m["outcomes"][:3]], max_age=1800)
        return 200, {"src": src, "id": mid, "title": m["title"], "url": m["url"], "series": hist, "now": int(time.time())}
    if path == "/api/politics":
        w = (qs.get("window") or ["24h"])[0]
        return 200, data(w if w in ("24h", "7d") else "24h", (qs.get("force") or ["0"])[0] == "1")
    return 404, {"error": "not found"}
