"""Politics add-on, part 2: (a) the prediction-market TRACK RECORD built from resolved US political markets, refreshed once a day;
(b) odds history for the live market cards (upstream price history, cached hourly, merged with this dashboard's own 10-minute snapshots).
Read-only public endpoints only (Polymarket Gamma + CLOB prices-history; Kalshi trade-api v2 incl. /historical). No accounts, no keys, no trading.
Everything is cached in politics.db. Outcomes are taken only from the platforms' own resolution fields; nothing is inferred or invented."""
import json, time, re, sqlite3, urllib.parse, sys, threading
from datetime import datetime, timezone

HORIZONS = (30, 7, 1)
TRIVIAL = 0.97          # favorites priced above this at the horizon are left out of the headline figure
DECIDED = 0.95          # "decision time" = first day from which the eventual winner stayed >= 95% until close
STALE_DAYS = 3          # a horizon price must come from a point no older than this
MAX_SCORE = 300         # resolved events scored per platform (largest by volume first)
MAX_OUT = 6             # outcomes fetched per multi-outcome event (largest by volume, plus the winner)
CLOB = "https://clob.polymarket.com"
PM_HIST_TAGS = ["politics", "us-presidential-election", "midterms", "senate-elections", "congress", "us-politics", "us-government", "governor", "governor-midterms", "elections", "house-of-representatives"]
PM_SKIP_T = re.compile(r"(mention|\bsay\b|tweets?|\bposts?\b|Truth Social|Fed decision|interest rate|\bbps\b|price of|bitcoin|crypto|how many times|# of times)", re.I)

def P():
    return sys.modules.get("politics") or __import__("politics")
def now_ts(): return int(time.time())
def pts(s):
    if not s: return None
    try: return int(datetime.fromisoformat(str(s).replace("Z", "+00:00").replace(" ", "T").replace("+00+00:00", "+00:00")).timestamp())
    except Exception:
        try: return int(datetime.strptime(str(s)[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp())
        except Exception: return None
def db():
    c = P().pdb()
    c.execute("CREATE TABLE IF NOT EXISTS hist_events(platform TEXT, event_id TEXT, title TEXT, topic TEXT, url TEXT, close_ts INTEGER, decided_ts INTEGER, winner TEXT, n_outcomes INTEGER, n_fetched INTEGER, volume REAL, status TEXT, horizons TEXT, scored_at TEXT, PRIMARY KEY(platform, event_id))")
    c.execute("CREATE TABLE IF NOT EXISTS hist_runs(ts TEXT, platform TEXT, candidates INTEGER, scored INTEGER, with_history INTEGER, errors INTEGER, seconds INTEGER, note TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS snaps(src TEXT, id TEXT, outcome TEXT, ts INTEGER, p REAL)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_snaps ON snaps(src, id, outcome, ts)")
    c.execute("CREATE TABLE IF NOT EXISTS odds_cache(src TEXT, id TEXT, outcome TEXT, kind TEXT, fetched INTEGER, ok INTEGER, points TEXT, PRIMARY KEY(src, id, outcome, kind))")
    return c
def get(url, timeout=40):
    time.sleep(0.12); return P().get(url, timeout=timeout)

# ---------------- price series ----------------
def pm_series(token, kind="max"):
    """Polymarket CLOB price history for one outcome token -> [(ts, p)]. kind: 'max' (daily) or 'week' (hourly, last 7 days)."""
    tries = [("interval=max&fidelity=1440",), ("interval=max&fidelity=60",)] if kind == "max" else [("interval=1w&fidelity=60",)]
    for (q,) in tries:
        try:
            h = get(f"{CLOB}/prices-history?market={token}&{q}").get("history") or []
            s = [(int(x["t"]), float(x["p"])) for x in h if x.get("p") is not None]
            if s: return s
        except Exception: pass
    return []
def ks_price(cd):
    """Kalshi candle -> price. Live API uses *_dollars keys, /historical uses plain keys; trade close first, else a tight bid/ask midpoint, else previous trade."""
    f = P().fnum
    def k(d, n): d = d or {}; return d.get(n + "_dollars", d.get(n))
    pr = cd.get("price") or {}
    if k(pr, "close") is not None: return f(k(pr, "close"))
    b, a = f(k(cd.get("yes_bid"), "close")), f(k(cd.get("yes_ask"), "close"))
    if b is not None and a is not None and 0 < a and a - b <= 0.2: return round((b + a) / 2, 4)
    return f(k(pr, "previous"))
def ks_series(ticker, series, start, end, period=1440, historical=False):
    base = P().KS_BASE
    url = (f"{base}/historical/markets/{ticker}/candlesticks" if historical else f"{base}/series/{series}/markets/{ticker}/candlesticks") + \
          f"?start_ts={int(start)}&end_ts={int(end)}&period_interval={period}"
    try: cs = get(url).get("candlesticks") or []
    except Exception:
        if historical: return []
        try: cs = get(f"{base}/historical/markets/{ticker}/candlesticks?start_ts={int(start)}&end_ts={int(end)}&period_interval={period}").get("candlesticks") or []
        except Exception: return []
    out = []
    for cd in cs:
        p = ks_price(cd)
        if p is not None and cd.get("end_period_ts"): out.append((int(cd["end_period_ts"]), p))
    return out

# ---------------- scoring one resolved event ----------------
def at(series, t):
    best = None
    for ts, p in series:
        if ts <= t: best = (ts, p)
        else: break
    if best and t - best[0] <= STALE_DAYS * 86400: return best[1]
    return None
def score(outs):
    """outs: [{name, series, won}] with exactly one won=True. Returns (decided_ts, horizons dict, status)."""
    win = next(o for o in outs if o["won"])
    ws = sorted(win["series"])
    if not ws: return None, {}, "price history unavailable (not scored)"
    T = ws[-1][0]; i = len(ws)
    while i > 0 and ws[i - 1][1] >= DECIDED: i -= 1
    if i == 0: return ws[0][0], {}, "winner was already ≥95% when price history starts (no horizon data)"
    if i < len(ws): T = ws[i][0]
    H = {}
    for h in HORIZONS:
        t = T - h * 86400; pr = [(o["name"], at(sorted(o["series"]), t), o["won"]) for o in outs]
        pw = next(p for n, p, w in pr if w)
        avail = [(n, p, w) for n, p, w in pr if p is not None]
        if pw is None or not avail: H[str(h)] = None; continue
        fav = max(avail, key=lambda x: x[1])
        H[str(h)] = {"fav": fav[0], "p_fav": round(fav[1], 4), "p_win": round(pw, 4), "won": bool(fav[2]), "n_priced": len(avail)}
    part = any(not o["series"] for o in outs)
    st = "daily price history" + (" (some lower-volume outcomes had no history)" if part else "")
    if all(v is None for v in H.values()): st = "price history too short for the 30/7/1-day horizons"
    return T, H, st

def save(c, row):
    c.execute("INSERT OR REPLACE INTO hist_events VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", row); c.commit()

# ---------------- Polymarket harvest ----------------
def pm_candidates():
    Pm = P(); seen = {}
    for tag in PM_HIST_TAGS:
        for off in range(0, 400, 100):
            q = urllib.parse.urlencode({"closed": "true", "tag_slug": tag, "limit": 100, "offset": off, "order": "volume", "ascending": "false"})
            try: d = get(f"{Pm.PM_BASE}/events?{q}")
            except Exception: break
            for e in d: seen.setdefault(e.get("id"), e)
            if len(d) < 100: break
    out = []
    for e in seen.values():
        tags = {t.get("slug") for t in (e.get("tags") or []) if t.get("slug")}; title = (e.get("title") or "").strip()
        if tags & Pm.PM_SKIP or PM_SKIP_T.search(title): continue
        if not (tags & Pm.PM_US or Pm.US_HINT.search(title)) or Pm.FOREIGN.search(title): continue
        ms = [m for m in (e.get("markets") or []) if m.get("outcomePrices") and m.get("clobTokenIds")]
        if not ms or not all(m.get("closed") for m in ms): continue
        try:
            for m in ms: m["_p"] = [float(x) for x in json.loads(m["outcomePrices"])]; m["_t"] = json.loads(m["clobTokenIds"]); m["_o"] = json.loads(m["outcomes"])
        except Exception: continue
        if not all(sorted(m["_p"]) == [0.0, 1.0] for m in ms): continue          # only cleanly resolved markets (one side paid $1)
        if len(ms) == 1:
            m = ms[0]; outs = [{"name": n, "token": t, "won": p == 1.0, "vol": P().fnum(m.get("volume"))} for n, t, p in zip(m["_o"], m["_t"], m["_p"])]
            if [o["name"].lower() for o in outs] == ["yes", "no"]: outs = [dict(outs[0], name="Yes"), dict(outs[1], name="No")]
            binary = True
        else:
            if not e.get("negRisk"): continue                                     # multi-market but not mutually exclusive (e.g. date ladders): skip
            outs = [{"name": (m.get("groupItemTitle") or m.get("question") or "").strip(), "token": m["_t"][0], "won": m["_p"][0] == 1.0, "vol": P().fnum(m.get("volume")) or 0} for m in ms]
            binary = False
        if sum(o["won"] for o in outs) != 1: continue
        out.append({"id": e.get("slug"), "title": title, "url": f"https://polymarket.com/event/{e.get('slug')}", "vol": P().fnum(e.get("volume")) or 0,
                    "close": pts(e.get("closedTime") or e.get("endDate")), "outs": outs, "binary": binary})
    out.sort(key=lambda x: -x["vol"]); return out
def pm_harvest(c):
    cands = pm_candidates(); done = {r[0] for r in c.execute("SELECT event_id FROM hist_events WHERE platform='Polymarket'")}
    n = hist = err = 0
    for ev in cands[:MAX_SCORE]:
        if ev["id"] in done: continue
        outs = ev["outs"]
        if ev["binary"]:
            s = pm_series(outs[0]["token"]); outs[0]["series"] = s; outs[1]["series"] = [(t, round(1 - p, 4)) for t, p in s]
        else:
            keep = sorted(outs, key=lambda o: -(o["vol"] or 0))[:MAX_OUT]
            if not any(o["won"] for o in keep): keep.append(next(o for o in outs if o["won"]))
            for o in keep: o["series"] = pm_series(o["token"])
            outs = keep
        try: T, H, st = score(outs)
        except Exception: err += 1; continue
        win = next(o["name"] for o in outs if o["won"]); n += 1; hist += bool(H and any(H.values()))
        save(c, ("Polymarket", ev["id"], ev["title"], P().topic(ev["title"]), ev["url"], ev["close"], T, win, len(ev["outs"]), len(outs), ev["vol"], st, json.dumps(H), P().iso()))
    return len(cands), n, hist, err

# ---------------- Kalshi harvest ----------------
def ks_us_series(s):
    Pm = P(); t = s.get("title") or ""
    if any("international" in (x or "").lower() for x in (s.get("tags") or [])): return False
    return bool(Pm.US_HINT.search(t)) and not Pm.FOREIGN.search(t) and not Pm.KS_SKIP.search(t)
def ks_markets(series):
    base = P().KS_BASE; out = []
    for hist in (True, False):
        cur = ""
        for _ in range(10):
            q = {"series_ticker": series, "limit": 1000}
            if not hist: q["status"] = "settled"
            if cur: q["cursor"] = cur
            try: d = get(f"{base}/{'historical/markets' if hist else 'markets'}?" + urllib.parse.urlencode(q))
            except Exception: break
            for m in d.get("markets") or []: m["_hist"] = hist; out.append(m)
            cur = d.get("cursor")
            if not cur: break
    return out
def ks_harvest(c):
    Pm = P(); base = Pm.KS_BASE
    series = []
    for cat in ("Elections", "Politics"):
        try: series += [s for s in get(f"{base}/series?category={cat}").get("series") or [] if ks_us_series(s)]
        except Exception: pass
    state = Pm.meta_get("ks_hist_series", {}) or {}
    ev = {}
    for s in series:
        tk = s["ticker"]; lu = s.get("last_updated_ts") or ""
        if tk in state and state[tk] >= lu: continue
        for m in ks_markets(tk):
            if (m.get("result") or "") not in ("yes", "no"): continue
            e = ev.setdefault(m["event_ticker"], {"series": tk, "ms": []}); e["ms"].append(m)
        state[tk] = lu or Pm.iso()
    Pm.meta_set("ks_hist_series", state)
    # merge newly found events into a persistent candidate list
    cand = Pm.meta_get("ks_hist_cands", {}) or {}
    for et_, e in ev.items():
        ms = e["ms"]; yes = [m for m in ms if m["result"] == "yes"]
        if len(ms) > 1 and len(yes) != 1: continue
        vol = sum(Pm.fnum(m.get("volume_fp")) or 0 for m in ms)
        if vol <= 0: continue
        cand[et_] = {"series": e["series"], "vol": vol, "ms": [{k: m.get(k) for k in ("ticker", "yes_sub_title", "title", "result", "open_time", "close_time", "volume_fp", "_hist")} for m in ms]}
    Pm.meta_set("ks_hist_cands", cand)
    done = {r[0] for r in c.execute("SELECT event_id FROM hist_events WHERE platform='Kalshi'")}
    todo = sorted(cand.items(), key=lambda kv: -kv[1]["vol"])[:MAX_SCORE]
    n = hist = err = 0
    for et_, e in todo:
        if et_ in done: continue
        ms = e["ms"]
        try: evd = get(f"{base}/events/{urllib.parse.quote(et_)}").get("event") or {}
        except Exception: evd = {}
        title = (evd.get("title") or (ms[0].get("title") if len(ms) == 1 else et_) or et_).strip()
        if Pm.FOREIGN.search(title) or Pm.KS_SKIP.search(title): continue
        if len(ms) == 1:
            m = ms[0]; s = ks_series(m["ticker"], e["series"], pts(m["open_time"]) or 0, pts(m["close_time"]) or now_ts(), historical=m["_hist"])
            outs = [{"name": "Yes", "series": s, "won": m["result"] == "yes"}, {"name": "No", "series": [(t, round(1 - p, 4)) for t, p in s], "won": m["result"] == "no"}]
            nout = 2
        else:
            keep = sorted(ms, key=lambda m: -(Pm.fnum(m.get("volume_fp")) or 0))[:MAX_OUT]
            if not any(m["result"] == "yes" for m in keep): keep.append(next(m for m in ms if m["result"] == "yes"))
            outs = [{"name": (m.get("yes_sub_title") or m.get("ticker")).strip(), "won": m["result"] == "yes",
                     "series": ks_series(m["ticker"], e["series"], pts(m["open_time"]) or 0, pts(m["close_time"]) or now_ts(), historical=m["_hist"])} for m in keep]
            nout = len(ms)
        try: T, H, st = score(outs)
        except Exception: err += 1; continue
        win = next(o["name"] for o in outs if o["won"]); n += 1; hist += bool(H and any(H.values()))
        close = max([pts(m.get("close_time")) or 0 for m in ms] or [0])
        save(c, ("Kalshi", et_, title, Pm.topic(title), f"https://kalshi.com/markets/{e['series'].lower()}", close, T, win, nout, len(outs), e["vol"], st, json.dumps(H), Pm.iso()))
    return len(cand), n, hist, err

def harvest():
    lk = getattr(sys, "_bn_pol_hist_lock", None) or threading.Lock(); sys._bn_pol_hist_lock = lk
    if not lk.acquire(blocking=False): return False
    try:
        c = db(); P().meta_set("hist_running", P().iso())
        for name, fn in (("Polymarket", pm_harvest), ("Kalshi", ks_harvest)):
            t0 = time.time()
            try: cn, n, h, e = fn(c); note = None
            except Exception as ex: cn = n = h = e = 0; note = f"{type(ex).__name__}: {ex}"[:300]
            c.execute("INSERT INTO hist_runs VALUES(?,?,?,?,?,?,?,?)", (P().iso(), name, cn, n, h, e, int(time.time() - t0), note)); c.commit()
        c.close(); P().meta_set("hist_last", P().iso())
    finally:
        P().meta_set("hist_running", None); lk.release()
    return True

# ---------------- metrics ----------------
def metrics():
    c = db(); rows = [dict(r) for r in c.execute("SELECT * FROM hist_events ORDER BY close_ts DESC")]
    runs = [dict(r) for r in c.execute("SELECT * FROM hist_runs ORDER BY rowid DESC LIMIT 6")]; c.close()
    for r in rows: r["horizons"] = json.loads(r["horizons"] or "{}"); r["topic"] = P().topic(r["title"])
    def agg(sel, h):
        xs = [r["horizons"].get(str(h)) for r in sel]; xs = [x for x in xs if x]
        def blk(ys):
            fav = [y for y in ys if y["p_fav"] > 0.5]
            return {"n": len(ys), "n_fav": len(fav), "acc": round(100 * sum(y["won"] for y in fav) / len(fav), 1) if fav else None,
                    "brier": round(sum((y["p_fav"] - (1 if y["won"] else 0)) ** 2 for y in ys) / len(ys), 4) if ys else None}
        return {"all": blk(xs), "nontrivial": blk([x for x in xs if x["p_fav"] <= TRIVIAL])}
    groups = {}
    for plat in ("all", "Polymarket", "Kalshi"):
        sel = [r for r in rows if plat == "all" or r["platform"] == plat]
        groups[plat] = {"all": {str(h): agg(sel, h) for h in HORIZONS}}
        for tp in sorted({r["topic"] for r in sel}):
            groups[plat][tp] = {str(h): agg([r for r in sel if r["topic"] == tp], h) for h in HORIZONS}
    counts = {p: {"resolved": len([r for r in rows if r["platform"] == p]), "with_history": len([r for r in rows if r["platform"] == p and any(r["horizons"].values())])} for p in ("Polymarket", "Kalshi")}
    hz = {p: {str(h): len([r for r in rows if r["platform"] == p and r["horizons"].get(str(h))]) for h in HORIZONS} for p in ("Polymarket", "Kalshi")}
    return {"groups": groups, "counts": counts, "horizon_counts": hz, "events": rows[:400], "runs": runs, "last": P().meta_get("hist_last"), "running": P().meta_get("hist_running"),
            "method": {"horizons_days": HORIZONS, "trivial_cut": TRIVIAL, "decided": DECIDED, "stale_days": STALE_DAYS, "max_scored": MAX_SCORE, "max_outcomes": MAX_OUT}}

# ---------------- live odds history ----------------
def record_snaps(src, items):
    c = db(); t = now_ts()
    c.executemany("INSERT INTO snaps VALUES(?,?,?,?,?)", [(src, m["id"], o["name"], t, o["p"]) for m in items for o in m.get("outcomes") or []])
    c.execute("DELETE FROM snaps WHERE ts < ?", (t - 400 * 86400,)); c.commit(); c.close()
def upstream(src, m, o, kind):
    """kind 'all' = daily over the market's life, 'week' = hourly for 7 days."""
    if src == "Polymarket":
        if not o.get("token"): return None
        s = pm_series(o["token"], "max" if kind == "all" else "week")
        if o.get("invert"): s = [(t, round(1 - p, 4)) for t, p in s]
        return s
    if not o.get("ticker"): return None
    end = now_ts(); start = end - 7 * 86400 if kind == "week" else (pts(o.get("open")) or end - 400 * 86400)
    s = ks_series(o["ticker"], m.get("series") or o["ticker"].split("-")[0], start, end, 60 if kind == "week" else 1440)
    if o.get("invert"): s = [(t, round(1 - p, 4)) for t, p in s]
    return s
def history(src, m, names, max_age=3600, kinds=("all", "week"), fetch=True):
    c = db(); out = {}
    for o in [o for o in m.get("outcomes") or [] if o["name"] in names]:
        pts_ = {}; okk = {}
        for kind in kinds:
            r = c.execute("SELECT * FROM odds_cache WHERE src=? AND id=? AND outcome=? AND kind=?", (src, m["id"], o["name"], kind)).fetchone()
            if r and (now_ts() - r["fetched"] < max_age or not fetch): s = json.loads(r["points"]); ok = r["ok"]
            elif not fetch: s, ok = [], 0
            else:
                try: s = upstream(src, m, o, kind); ok = 1 if s else 0
                except Exception: s, ok = [], 0
                if s is None:          # no token/ticker known yet (older cache): don't cache a failure
                    okk[kind] = False; continue
                c.execute("INSERT OR REPLACE INTO odds_cache VALUES(?,?,?,?,?,?,?)", (src, m["id"], o["name"], kind, now_ts(), ok, json.dumps(s))); c.commit()
            okk[kind] = bool(ok)
            for t, p in s: pts_[int(t)] = ("u", p)
        own = [(r["ts"], r["p"]) for r in c.execute("SELECT ts, p FROM snaps WHERE src=? AND id=? AND outcome=? ORDER BY ts", (src, m["id"], o["name"]))]
        last_u = max([t for t, v in pts_.items()] or [0])
        for t, p in own:
            if t > last_u: pts_[t] = ("s", p)
        ser = sorted((t, round(v[1], 4), v[0]) for t, v in pts_.items())
        out[o["name"]] = {"points": ser, "upstream_ok": okk, "own_snapshots": len(own)}
    c.close(); return out
def spark(series, n=48):
    if not series: return []
    t1 = series[-1][0]; t0 = t1 - 30 * 86400; s = [x for x in series if x[0] >= t0] or series[-n:]
    if len(s) > n: step = len(s) / n; s = [s[int(i * step)] for i in range(n)] + [s[-1]]
    return [[t, p] for t, p, *_ in s]
