"""BLACKOUT.NETWORK apple_style_v1, Phase 2 (Nov 3 2026): minimal site chrome + new homepage.

Kill switch: on by default; BN_APPLE=0 turns it off, and the site renders exactly as before
(no CSS/JS injection, no wordmark swap, no homepage section, /api/apple/* -> 404).
Serves /bn-apple.css, /bn-apple.js and /api/apple/home (a slim same-origin summary of /api/state, /api/solar_seismic,
/api/grid and /api/sources/catalog, built in-process so the homepage never downloads the full payloads).
Nothing here is invented: every number comes from those endpoints, with its own timestamp."""
import os, sys, json, time, html, threading

BASE = os.path.dirname(os.path.abspath(__file__))
ENABLED = lambda: os.environ.get("BN_APPLE", "1") != "0"
E = lambda s: html.escape(str(s if s is not None else ""), quote=True)
_cache = {"t": 0, "v": None}; _lock = threading.Lock()

def _body(r):
    if not r or r[0] != 200: return None
    b = r[1]
    if isinstance(b, (bytes, bytearray)): b = json.loads(b.decode("utf-8"))
    elif isinstance(b, str): b = json.loads(b)
    return b if isinstance(b, dict) else None

def _slim(x):
    return {k: x.get(k) for k in ("cluster_id", "title", "category", "location", "lat", "lon", "rank", "n_families", "updated", "first_seen")}

# Memory (Render limit, 1:27 PM ET): caches are single-flight. Only one thread rebuilds a stale snapshot; every other request gets the
# last one immediately (or waits for the first build). Before, each concurrent request at expiry rebuilt its own copy (api_state,
# the sources catalog, solar_seismic JSON), so a burst of N requests held N full copies at once.
_build = {"home": threading.Lock(), "dash": threading.Lock()}
def _single(key, cache, ttl, build):
    v = cache["v"]
    if v and time.time() - cache["t"] < ttl: return v
    lk = _build[key]
    if not lk.acquire(blocking=not v, timeout=20 if not v else -1): return cache["v"]
    try:
        if cache["v"] and time.time() - cache["t"] < ttl: return cache["v"]
        out = build()
        with _lock: cache.update(t=time.time(), v=out)
        return out
    finally: lk.release()
_src = {"t": 0, "n": None}
def _sources_total(srv):
    """The catalog is heavy (whole source list); the homepage only needs its total, refreshed every 15 min."""
    if _src["n"] is not None and time.time() - _src["t"] < 900: return _src["n"]
    c = _body(srv._addon_mod("sources").handle_get("/api/sources/catalog", {"per": ["1"]}))
    _src.update(t=time.time(), n=(c or {}).get("total")); c = None
    return _src["n"]
def home_data():
    return _single("home", _cache, 60, _home_build)
def _home_build():
    srv = sys.modules.get("server"); out = {"generated": None, "main": [], "counts": {}, "kp": None, "quake": None, "grid": None, "sources": None}
    try:
        st = srv.api_state(); out["generated"] = st.get("generated")
        main = st.get("main") or []
        for x in main: out["counts"][x.get("category") or "other"] = out["counts"].get(x.get("category") or "other", 0) + 1
        out["main"] = [_slim(x) for x in sorted(main, key=lambda x: (-(x.get("rank") or 0), -(x.get("n_families") or 0)))[:40]]
        out["wire_total"] = len(main)
    except Exception: pass
    try:
        ss = _body(srv._addon_mod("solar_seismic").handle_get("/api/solar_seismic", {}))
        kp = (ss.get("now") or {}).get("kp") or {}
        if kp.get("value") is not None: out["kp"] = {k: kp.get(k) for k in ("value", "t", "t_et", "max24")}
        q = (ss.get("quakes_notable") or [None])[0]
        if q: out["quake"] = {k: q.get(k) for k in ("mag", "place", "t", "t_et")}
    except Exception: pass
    try:
        g = _body(srv._addon_mod("gridwatch").handle_get("/api/grid", {})); s = g.get("summary") or {}
        ranks = [int(k) for k, v in (s.get("by_rank") or {}).items() if k.isdigit() and v]
        out["grid"] = {"total": s.get("total"), "top": max(ranks) if ranks else None, "by_kind": s.get("by_kind"), "generated": g.get("generated")}
    except Exception: pass
    try:
        out["sources"] = _sources_total(srv)
    except Exception: pass
    return out

# ---- Active Threat Monitoring (homepage chart cards). Slim, same-origin, cached 2 min; every number from stored or same-origin data. ----
_dcache = {"t": 0, "v": None}
def _iso(t):
    from datetime import datetime, timezone
    try: return datetime.strptime(str(t)[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
    except Exception: return None
def _r(c, f):
    try: return f()
    except Exception: return None
# ---------------- widget board (t99u/t100u): elections, conflict regions, outbreaks, hardship, quake map. Read-only, in-process, cached with dash_data.
def elections_card(now):
    srv = sys.modules.get("server"); M = srv._addon_mod("midterms")
    from datetime import datetime
    b = M._base() or {}; off = M.official() or {}
    import midterms_hub as MH
    t = MH._poll_table() or {}
    closes = []
    for st in t.get("states") or []:
        for c in st.get("closes") or []:
            d = MH._dt(c.get("at_et"))
            if d: closes.append((d.timestamp(), st["state"], st["name"], c.get("zone")))
    closes.sort()
    nxt = [c for c in closes if c[0] > now]
    nt = nxt[0][0] if nxt else None
    wave = sorted({c[2] + (" (" + c[3] + " time)" if c[3] else "") for c in nxt if c[0] == nt}) if nt else []
    closed = len({c[1] for c in closes if c[0] <= now})
    last = closes[-1][0] if closes else None
    waves = []
    for ts in sorted({c[0] for c in closes}):
        waves.append([ts, len({c[1] for c in closes if c[0] == ts})])
    feeds = (off.get("feeds") or {})
    def live_for(r):
        f = feeds.get(r.get("state")) or {}
        for c in f.get("contests") or []:
            if c.get("kind") == r.get("office") and (r.get("office") != "house" or c.get("district") == r.get("district")):
                return c, f
        return None, None
    def lead(r):
        c, f = live_for(r)
        if c and (c.get("votes") or 0) > 0:
            op = sorted([o for o in c.get("options") or [] if o.get("votes")], key=lambda o: -o["votes"])
            if op:
                tot = sum(o["votes"] for o in c.get("options") or []) or 1
                m = (op[0]["votes"] - (op[1]["votes"] if len(op) > 1 else 0)) * 100.0 / tot
                return {"name": op[0]["name"], "code": op[0].get("code"), "margin": round(m, 1), "rep": [c.get("reporting"), c.get("total_units"), c.get("unit")],
                        "src": f.get("source"), "t": c.get("as_of") or f.get("as_of"), "won": bool(op[0].get("winner_by_state"))}
        pc = [x for x in ((r.get("page") or {}).get("results") or {}).get("candidates") or [] if x.get("pct") is not None] or [x for x in r.get("candidates") or [] if x.get("pct") is not None]
        if len(pc) >= 1:
            pc = sorted(pc, key=lambda x: -float(x["pct"]))
            return {"name": pc[0]["name"], "code": pc[0].get("code"), "margin": round(float(pc[0]["pct"]) - (float(pc[1]["pct"]) if len(pc) > 1 else 0), 1), "rep": None,
                    "src": "Wikipedia (as published)", "t": b.get("built"), "won": any(x.get("winner") for x in r.get("candidates") or [])}
        return None
    def key(office, rows, k=4):
        rows = [r for r in rows if r.get("office") == office and (r.get("consensus") or {}).get("v") is not None]
        rows.sort(key=lambda r: (abs(float(r["consensus"]["v"])), r.get("label") or ""))
        out = []
        for r in rows[:k]:
            pcl = MH._dt(r.get("poll_close"))
            out.append({"label": r.get("label") if office != "house" else r.get("label"), "rating": (r.get("consensus") or {}).get("t"),
                        "close": pcl.timestamp() if pcl else None, "lead": lead(r)})
        return out
    allr = (b.get("races") or []) + (b.get("house") or [])
    return {"next": nt, "wave": wave[:8], "wave_n": len(wave), "closed": closed, "states": len({c[1] for c in closes}), "last": last, "waves": waves,
            "first": closes[0][0] if closes else None,
            "senate": key("senate", allr), "governor": key("governor", allr), "house": key("house", allr),
            "t": (off.get("fetched") or b.get("built")), "night": bool(M.election_night())}

_REG = [("il", "Israel and Gaza", r"\b(israel|israeli|gaza|idf|hamas|hezbollah|west bank|lebanon|houthi|yemen|netanyahu|tel aviv|jerusalem)"),
        ("ir", "Iran", r"\b(iran|iranian|tehran|irgc|khamenei|araghchi)"),
        ("ru", "Russia and Ukraine", r"\b(russia|russian|ukraine|ukrainian|kyiv|kiev|kharkiv|moscow|kremlin|putin|zelensk|donetsk|crimea|odesa)"),
        ("uk", "UK and London", r"\b(uk|u\.k\.|britain|british|london|england|scotland|wales|met police|downing street)\b")]
_HEALTH = [("ebola", "Ebola", r"\b(ebola|marburg)"), ("measles", "Measles", r"\bmeasles")]
_DIS = r"\b(outbreak|virus|ebola|marburg|cholera|measles|influenza|h5n1|bird flu|avian flu|mpox|dengue|plague|pathogen|epidemic|pandemic|polio|tuberculosis|meningitis|anthrax|rift valley)"
_US = r"\b(u\.s\.|us|usa|america|american|national guard|ice|fbi|dhs|capitol|washington|new york|chicago|los angeles|portland|minneapolis|texas|california|florida|state of emergency)\b"
_UNREST = r"\b(protest|protesters|riot|unrest|curfew|clashes|national guard|martial law|looting|political violence|insurrection|shooting at|militia)"
_FOOD = r"\b(food (shortage|supply|prices|bank|insecurity|recall)|supply chain|shortage|recall|grocery|snap benefits|snap\b|ports?\b strike|shipping (disruption|delays)|diesel|baby formula|egg prices|meat plant|rail strike|dockworkers)"

def wire_groups(now):
    import re, sqlite3
    c = sqlite3.connect(f"file:{BASE}/blackout.db?mode=ro", uri=True, timeout=5)
    try:
        cut = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 7 * 86400))
        rows = c.execute("SELECT cluster_id, title, category, location, rank, first_seen, updated FROM clusters WHERE watchlist=0 AND updated>=? ORDER BY updated DESC LIMIT 6000", (cut,)).fetchall()
    finally: c.close()
    def day(ts):
        return time.strftime("%Y-%m-%d", time.gmtime(ts - 5 * 3600))
    days = [day(now - i * 86400) for i in range(6, -1, -1)]
    def agg(match):
        n24 = 0; d = {x: [0, 0] for x in days}; top = None; mx = 0
        for cid, t, cat, loc, rk, fs, up in rows:
            if not match(t or "", cat or "", loc or ""): continue
            ft = _iso(fs) or 0; ut = _iso(up) or 0; rk = int(rk or 0)
            k = day(ft) if ft else None
            if k in d: d[k][1 if rk >= 7 else 0] += 1
            if ut >= now - 86400:
                n24 += 1; mx = max(mx, rk)
                ok = re.match(r"^[A-Za-z0-9\"'(]", t or "") and not re.match(r"^(www\.|https?:)", t or "") and not re.search("[\u2600-\u27BF\U0001F000-\U0001FFFF]", t or "")
                if ok and (top is None or (rk, ut) > (top[0], top[1])): top = (rk, ut, cid, t, loc)
        n7 = sum(a + b for a, b in d.values())
        tp = None
        if top:
            import site_page as SP
            try: tt = SP.clean_title(top[3])
            except Exception: tt = top[3]
            tp = {"rank": top[0], "t": top[1], "url": f"/wire/{top[2]}" if re.match(r"^[0-9a-f]{16}$", top[2] or "") else "/#wire", "title": re.sub(r"\s+", " ", tt or "")[:150], "loc": top[4]}
        return {"n24": n24, "n7": n7, "max24": mx, "days": [[k] + d[k] for k in days], "top": tp}
    W = lambda t, cat: cat == "war/conflict" or (cat == "political" and re.search(r"\b(strike|missile|drone|attack|troops|war|military)", t.lower()))
    conf = {}
    used = []
    for k, label, rx in _REG:
        r = re.compile(rx, re.I); used.append(r)
        conf[k] = dict(agg(lambda t, cat, loc, r=r: bool(W(t, cat)) and bool(r.search(t + " " + loc))), label=label)
    conf["other"] = dict(agg(lambda t, cat, loc: bool(W(t, cat)) and not any(r.search(t + " " + loc) for r in used)), label="Other conflict zones")
    dis = re.compile(_DIS, re.I)
    H = lambda t, cat: (cat == "disease" and not re.search(r"\b(weather|storm|tornado|war) outbreak", t, re.I)) or (cat == "political" and dis.search(t))
    health = {}
    hused = []
    for k, label, rx in _HEALTH:
        r = re.compile(rx, re.I); hused.append(r)
        health[k] = dict(agg(lambda t, cat, loc, r=r: bool(r.search(t)) and (cat in ("disease", "political", "war/conflict", "other"))), label=label)
    health["other"] = dict(agg(lambda t, cat, loc: bool(H(t, cat)) and not any(r.search(t) for r in hused)), label="Other outbreaks")
    un, us, fd = re.compile(_UNREST, re.I), re.compile(_US, re.I), re.compile(_FOOD, re.I)
    hard = {"unrest": dict(agg(lambda t, cat, loc: cat in ("political", "war/conflict", "other") and bool(un.search(t)) and bool(us.search(t + " " + loc))), label="Unrest in the U.S."),
            "food": dict(agg(lambda t, cat, loc: bool(fd.search(t))), label="Food and supply chain")}
    return {"conf": conf, "health": health, "hard": hard}

# t106u: Nuclear threat (War group) and Election disputes (Elections group). Real Wire items only: confirmed stories plus single-source
# watchlist items (marked as such), last 7 days, titles matched by keyword. Headlines shown are cleaned (no emoji, livestream or profane posts).
_NUK = r"\b(nuclear (strike|strikes|attack|weapons?|war|threats?|test|tests|testing|warheads?|arsenal|plant|power plant|deterrent|doctrine|submarines?|missiles?|escalation|talks|program|programme|facility|facilities|sites?|deal|bomb|capable|forces|drills?|exercise|alert|advisory|warning)|nukes?\b|warheads?|icbms?\b|intercontinental ballistic|tactical nuclear|zaporizhzhia nuclear|znpp|chornobyl|chernobyl|doomsday clock|iaea|uranium enrichment|enriched uranium|enrich uranium|plutonium|dirty bomb|radiation leak|radioactive|new start|sarmat|burevestnik|oreshnik)"
_ELC = r"\b(election|elections|ballot|ballots|vote|votes|voting|voter|voters|polls\b|polling|precincts?|recount|certification|canvass\w*|electoral|midterms?)\b"
_DSP = (r"\b(lawsuits?|sue[sd]?|suing|court|judge|ruling|injunction|recount|certif\w*|challeng\w*|disput\w*|contested|fraud|intimidat\w*|suppress\w*|purg\w*|"
        r"irregularit\w*|delay(ed|s)?|extended|extends?|long lines|glitch\w*|malfunction\w*|observers?|poll watchers?|monitors?|doj|justice department|bomb threats?|"
        r"disinformation|misinformation|provisional|rejected|turned away|voter id|voter rolls?|redistrict\w*|gerrymander\w*|federal agents|ice agents|national guard|sanctions|evacuat\w*)\b"
        r"|\b(rnc|dnc|democrats?|republicans?|gop|democratic party|republican party)\b.{0,40}\b(sues?|sued|files?|filed|lawsuit|challeng\w*|asks?|seeks?|demands?|deploys?|sends?|monitor\w*|court|requests?|urges?)\b")
_FOREIGN = r"\b(india|delhi|pakistan|bangladesh|britain|british|u\.k\.|canada|canadian|brazil|mexico|nigeria|kenya|uganda|tanzania|cameroon|venezuela|argentina|philippines|japan|korea|taiwan|germany|france|italy|spain|poland|hungary|romania|moldova|serbia|turkey|israel|iran|iraq|russia|ukraine|belarus|nato)\b"
_BAD = r"(\bf\W?u?c?k|\bf\*ck|\bshit|\bdamn|\[live\]|\blive:|\bwatch:|blueanon|\bmaga\b|^\W*(rt|breaking)\b)"
def _clean_hl(t):
    import re
    t = re.sub(r"\s+", " ", t or "").strip()
    if re.search(_BAD, t, re.I): return None
    t = re.sub(r"^[^A-Za-z0-9\"'(]+", "", t)
    if len(t) < 25 or re.search("[\u2600-\u27BF\U0001F000-\U0001FFFF]", t) or re.match(r"^(www\.|https?:|#|@)", t): return None
    if sum(ch.isupper() for ch in t) > 0.5 * sum(ch.isalpha() for ch in t): return None
    try:
        import site_page as SP; t = SP.clean_title(t)
    except Exception: pass
    return t[:160]
def special_cards(now):
    import re, sqlite3
    c = sqlite3.connect(f"file:{BASE}/blackout.db?mode=ro", uri=True, timeout=5)
    try:
        cut = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 7 * 86400))
        rows = c.execute("SELECT cluster_id, title, category, rank, first_seen, updated, watchlist FROM clusters WHERE watchlist IN (0,1,2) AND updated>=? "
                         "ORDER BY updated DESC LIMIT 5000", (cut,)).fetchall()
    finally: c.close()
    day = lambda ts: time.strftime("%Y-%m-%d", time.gmtime(ts - 5 * 3600))
    days = [day(now - i * 86400) for i in range(6, -1, -1)]
    nk, ec, dp = re.compile(_NUK, re.I), re.compile(_ELC, re.I), re.compile(_DSP, re.I)
    def agg(match):
        d = {x: [0, 0] for x in days}; n24 = 0; mx = 0; conf24 = 0; latest = []; seen = set()
        for cid, t, cat, rk, fs, up, wl in rows:
            t = t or ""
            if cat == "ufo/uap" or not match(t, wl): continue
            ft = _iso(fs) or 0; ut = _iso(up) or 0; rk = int(rk or 0)
            k = day(ft) if ft else None
            if k in d: d[k][1 if rk >= 7 else 0] += 1
            if ut >= now - 86400:
                n24 += 1; mx = max(mx, rk); conf24 += (wl == 0)
            if len(latest) < 3:
                h = _clean_hl(t)
                if h and h.lower()[:60] not in seen:
                    seen.add(h.lower()[:60])
                    latest.append({"title": h, "t": ut, "rank": rk, "single": wl != 0,
                                   "url": f"/wire/{cid}" if re.match(r"^[0-9a-f]{16}$", cid or "") else "/#wire"})
        return {"n24": n24, "conf24": conf24, "n7": sum(a + b for a, b in d.values()), "max24": mx, "days": [[k] + d[k] for k in days], "latest": latest}
    fr = re.compile(_FOREIGN, re.I)
    # Nuclear: confirmed + single-source items. Disputes: also rank 0-1 items the feed suppresses (local polling-place reports are often rank 1).
    return {"nuke": agg(lambda t, wl: wl in (0, 1) and bool(nk.search(t))),
            "disp": agg(lambda t, wl: bool(ec.search(t)) and bool(dp.search(t)) and not fr.search(t))}

def comms_card():
    import sqlite3
    srv = sys.modules.get("server"); ns = srv._addon_mod("netstatus")
    c = sqlite3.connect(f"file:{ns.NDB}?mode=ro", uri=True, timeout=5)
    try:
        lt = c.execute("SELECT MAX(ts) FROM checks WHERE kind!='isp'").fetchone()[0]
        it = c.execute("SELECT MAX(ts) FROM checks WHERE kind='isp' AND grp='ISPs'").fetchone()[0]
        rows = c.execute("SELECT src, grp, level, status FROM checks WHERE ts=? AND kind!='isp'", (lt,)).fetchall() if lt else []
        isp = c.execute("SELECT src, grp, level, status FROM checks WHERE ts=? AND kind='isp' AND grp='ISPs'", (it,)).fetchall() if it else []
    finally: c.close()
    bad = lambda rs: [{"src": r[0], "level": r[2], "status": r[3]} for r in rs if (r[2] or 0) >= 2]
    return {"isp_n": len(isp), "isp_bad": bad(isp), "isp": [r[0] for r in isp], "isp_t": it, "cloud_n": len(rows), "cloud_bad": bad(rows), "t": lt}

_A0 = {"rings": None, "key": None, "map": None}
def _world():
    """Country outlines from the self-hosted admin0.geojson, reduced once to <=60 points per ring at 0.1 degree (a few hundred KB),
    so the full GeoJSON is never kept in memory."""
    if _A0["rings"] is None:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "heatmap_static", "admin0.geojson"), encoding="utf-8") as fh: feats = json.load(fh)["features"]
        rings = []
        for f in feats:
            g = f.get("geometry") or {}; polys = g.get("coordinates") or []
            if g.get("type") == "Polygon": polys = [polys]
            for poly in polys:
                ring = poly[0] if poly else []
                if len(ring) < 4: continue
                pts = tuple((round(x, 1), round(y, 1)) for x, y in ring[::max(1, len(ring) // 60)])
                xs = [q[0] for q in pts]; ys = [q[1] for q in pts]
                rings.append((min(xs), max(xs), min(ys), max(ys), pts))
        feats = None; _A0["rings"] = rings
    return _A0["rings"]
def quake_map(big):
    """Small inline SVG around the quake (equirectangular crop of country outlines, no tiles). One cached map, keyed by quake."""
    if big.get("lat") is None: return None
    lat, lon = float(big["lat"]), float(big["lon"]); key = (round(lat, 3), round(lon, 3))
    if _A0["key"] == key: return _A0["map"]
    w, h = 40.0, 22.0; x0, y1 = lon - w / 2, lat + h / 2
    def P(x, y): return f"{(x - x0) * 300 / w:.0f} {(y1 - y) * 165 / h:.0f}"
    paths = []
    for mnx, mxx, mny, mxy, pts in _world():
        if mxx < x0 - 5 or mnx > x0 + w + 5 or mxy < y1 - h - 5 or mny > y1 + 5: continue
        paths.append("M" + "L".join(P(x, y) for x, y in pts) + "Z")
    m = {"d": "".join(paths)[:9000], "x": round((lon - x0) * 300 / w), "y": round((y1 - lat) * 165 / h)}
    _A0.update(key=key, map=m)
    return m

BOARD = [("el", "Elections", "Midterms 2026, live on election night", [("el_next", "Polls closing", "/midterms"), ("el_sen", "Senate: closest races", "/midterms"), ("el_gov", "Governor: closest races", "/midterms"), ("el_house", "House: closest races", "/midterms"), ("el_disp", "Election disputes", "/#wire")]),
         ("cf", "War and conflict", "Stories on The Wire by region", [("c_nuke", "Nuclear threat", "/#wire"), ("c_il", "Israel, Gaza and region", "/#wire"), ("c_ir", "Iran", "/#wire"), ("c_ru", "Russia and Ukraine", "/#wire"), ("c_uk", "UK and London", "/#wire"), ("c_other", "Other conflict zones", "/#heatmap")]),
         ("hl", "Health and outbreaks", "Outbreak reports on The Wire", [("h_ebola", "Ebola", "/#medical"), ("h_measles", "Measles", "/#medical"), ("h_other", "Other outbreaks", "/#medical")]),
         ("hd", "Hardship risks", "Power, communications, supply and order at home", [("grid", "U.S. power grid", "/#grid"), ("comms", "Phones, internet and cloud", "/#network"), ("food", "Food and supply chain", "/#wire"), ("unrest", "Unrest in the U.S.", "/#wire")]),
         ("nh", "Natural hazards", "Earthquakes, space weather and severe weather", [("quake", "Earthquakes", "/#solar"), ("kp", "Geomagnetic storms", "/#solar"), ("wx", "Weather threats to power", "/#grid"), ("flare", "Solar flares", "/#solar")])]
BOARD = [g for k in ("cf", "el", "hl", "hd", "nh") for g in BOARD if g[0] == k]   # t106u: War and conflict first
def _board_html():
    def card(k, label, href):
        return (f'<article class="bna-card bna-mc" data-mc="{k}"><button type="button" class="bna-mh" aria-expanded="false" aria-controls="bna_mx_{k}">'
                f'<span class="bna-k">{E(label)}</span><span class="bna-mv" data-f="v">&ndash;</span><span class="bna-ms" data-f="s"></span>'
                f'<span class="bna-ch" data-f="c" aria-hidden="true"></span><span class="bna-mf"><span class="bna-src" data-f="t"></span><span class="bna-chev" aria-hidden="true"></span></span></button>'
                f'<div class="bna-mx" id="bna_mx_{k}" hidden><div data-f="x"></div><a class="bna-lnk" href="{href}">See full page</a></div></article>')
    out = ['<section class="bna-sec" id="bna_dash" aria-labelledby="bna_h_now"><div class="bna-wrap bna-sech"><h2 id="bna_h_now">Active Threat Monitoring</h2></div>']
    for g, title, sub, cards in BOARD:
        links = ('<nav class="bna-group-links" aria-label="Nuclear reporting and preparedness">'
                 '<a class="bna-lnk" href="/nuclear">Nuclear reporting</a>'
                 '<a class="bna-lnk" href="/nuclear#prep">Nuclear Preparedness</a></nav>') if g == "cf" else ""
        out.append(f'<div class="bna-wrap bna-grp" data-g="{g}" role="group" aria-labelledby="bna_g_{g}"><div class="bna-gh"><h3 id="bna_g_{g}"><i aria-hidden="true"></i>{E(title)}</h3><p>{E(sub)}</p>{links}</div>'
                   f'<div class="bna-mgrid">' + "".join(card(*c) for c in cards) + '</div></div>')
    out.append('</section>')
    return "".join(out)

def dash_data():
    return _single("dash", _dcache, 90, _dash_build)
def _dash_build():
    import sqlite3
    srv = sys.modules.get("server"); now = time.time(); out = {"now": now}
    ss = _r(None, lambda: _body(srv._addon_mod("solar_seismic").handle_get("/api/solar_seismic", {}))) or {}
    nw = ss.get("now") or {}; bins = ss.get("bins") or []
    def kp_card():
        kp = nw.get("kp") or {}
        if kp.get("value") is None: return None
        ser = [[_iso(b.get("bin_start")), b.get("kp")] for b in bins[-24:] if b.get("kp") is not None]
        return {"value": kp.get("value"), "g": kp.get("g"), "max24": kp.get("max24"), "t": kp.get("t"), "series": ser,
                "fc": [x.get("G") for x in ((nw.get("scales") or {}).get("forecast") or [])][:3]}
    out["kp"] = _r(None, kp_card)
    def quake_card():
        q = nw.get("quake") or {}; lst = ss.get("map") or []
        day = [x for x in lst if (_iso(x.get("t")) or 0) >= now - 86400 and x.get("mag") is not None]
        cls = [0, 0, 0, 0, 0, 0]   # <4, 4-4.9, 5-5.9, 6-6.9, 7-7.9, 8+
        for x in day: cls[min(5, max(0, int(float(x["mag"])) - 3))] += 1
        big = max(day, key=lambda x: x["mag"]) if day else None
        lt = q.get("latest") or {}
        pick = big or lt
        wk = [x for x in lst if x.get("mag") is not None and float(x["mag"]) >= 5]
        sig = max(wk, key=lambda x: _iso(x.get("t")) or 0) if wk else None
        return {"n24": len(day), "classes": cls, "big": {k: pick.get(k) for k in ("mag", "place", "t", "tsunami", "url", "lat", "lon")} if pick else None,
                "sig": {k: sig.get(k) for k in ("mag", "place", "t", "tsunami", "url", "lat", "lon")} if sig else None,
                "week_n": q.get("count"), "src_t": max((x.get("t") for x in lst), default=None)}
    out["quake"] = _r(None, quake_card)
    def flare_card():
        x = nw.get("xray") or {}; fl = nw.get("flare") or {}
        ser = [[_iso(b.get("bin_start")), b.get("xray_max")] for b in bins[-24:] if b.get("xray_max")]
        return {"cls": x.get("class"), "flux": x.get("flux"), "t_et": x.get("t_et"), "count": fl.get("count"),
                "biggest": {k: (fl.get("biggest") or {}).get(k) for k in ("class", "t")}, "r": ((nw.get("scales") or {}).get("now") or {}).get("R"), "series": ser}
    out["flare"] = _r(None, flare_card)
    def wind_card():
        w = nw.get("wind") or {}; ser = [[_iso(p.get("t")), p.get("proton_speed")] for p in (ss.get("wind24") or [])[::3] if p.get("proton_speed")]
        return {"speed": w.get("speed"), "bz": w.get("bz"), "t_et": w.get("t_et"), "series": ser}
    out["wind"] = _r(None, wind_card)
    def grid_card():
        gs = _body(srv._addon_mod("gridstatus").handle_get("/api/gridstatus", {})) or {}
        secs = [v for v in (gs.get("sections") or {}).values() if isinstance(v, dict)]
        live = [v for v in secs if v.get("status") not in ("nodata_ok", None)]
        cnt = {}
        for v in live: cnt[v["status"]] = cnt.get(v["status"], 0) + 1
        odin = sum(int(((v.get("odin") or {}).get("outages")) or 0) for v in secs)
        utils = sum(int(((v.get("odin") or {}).get("reporting_outages")) or 0) for v in secs)
        nws = {"extreme": sum(int(((v.get("nws") or {}).get("extreme")) or 0) for v in secs),
               "warnings": sum(int(((v.get("nws") or {}).get("warnings")) or 0) for v in secs),
               "power": sum(int(((v.get("nws") or {}).get("power_alerts")) or 0) for v in secs)}
        hist = (_body(srv._addon_mod("gridstatus").handle_get("/api/gridstatus/history", {})) or {}).get("history") or []
        per = {}
        for h in hist:
            t = _iso(h.get("ts"))
            if t is None or t < now - 48 * 3600 or h.get("status") == "nodata_ok": continue
            p = per.setdefault(t, [0, 0]); p[0] += h.get("status") == "watch"; p[1] += h.get("status") not in ("online", "watch")
        flagged = [{"name": v.get("name"), "status": v.get("status"), "why": (v.get("reasons") or [""])[0]} for v in live if v.get("status") != "online"]
        return {"regions": len(live), "status": cnt, "outages": odin, "utilities": utils, "series": [[t] + per[t] for t in sorted(per)], "flagged": flagged[:6],
                "nws": nws, "t": (gs.get("freshness") or {}).get("sections", {}).get("ts") or gs.get("generated"),
                "nws_t": ((gs.get("freshness") or {}).get("nws") or {}).get("ts"),
                "storms": [{"title": w.get("title"), "rank": w.get("rank"), "location": w.get("location")} for w in (gs.get("weather") or [])[:3]]}
    out["grid"] = _r(None, grid_card)
    def net_card():
        ns = srv._addon_mod("netstatus"); a = ns.alerts()
        c = sqlite3.connect(f"file:{ns.NDB}?mode=ro", uri=True, timeout=5)
        try:
            cut = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 86400))
            rows = c.execute("SELECT ts, COUNT(DISTINCT src), SUM(level>=2) FROM checks WHERE ts>=? AND kind!='isp' GROUP BY ts ORDER BY ts", (cut,)).fetchall()
        finally: c.close()
        ser = [[_iso(r[0]), r[2] or 0] for r in rows]
        if len(ser) > 96: k = len(ser) / 96.0; ser = [max(ser[int(i * k):int((i + 1) * k)], key=lambda p: p[1]) for i in range(96)]
        return {"count": a.get("count"), "alerts": [{"src": x.get("src"), "status": x.get("status")} for x in (a.get("alerts") or [])[:4]],
                "checked": rows[-1][1] if rows else None, "t": a.get("polled"), "series": ser}
    out["net"] = _r(None, net_card)
    def wire_card():
        c = sqlite3.connect(f"file:{BASE}/blackout.db?mode=ro", uri=True, timeout=5)
        try:
            cut = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 8 * 86400))
            rows = c.execute("""SELECT date(first_seen, '-5 hours') d, SUM(rank>=7) hi, SUM(rank BETWEEN 4 AND 6) mid, SUM(rank<4) lo
                                FROM clusters WHERE watchlist=0 AND first_seen>=? GROUP BY d ORDER BY d""", (cut,)).fetchall()
        finally: c.close()
        days = [[r[0], r[1] or 0, r[2] or 0, r[3] or 0] for r in rows][-7:]   # ET calendar days (EST offset), today last
        return {"days": days, "total": sum(d[1] + d[2] + d[3] for d in days), "hi": sum(d[1] for d in days)}
    out["wire"] = _r(None, wire_card)
    out["el"] = _r(None, lambda: elections_card(now))
    out.update(_r(None, lambda: wire_groups(now)) or {})
    out["comms"] = _r(None, comms_card)
    out["spec"] = _r(None, lambda: special_cards(now))
    if out.get("quake") and (out["quake"].get("sig") or {}).get("lat") is not None: out["quake"]["map"] = _r(None, lambda: quake_map(out["quake"]["sig"]))
    return out

# Snapshot refresher: one background thread rebuilds the homepage snapshot every ~100 s from the same in-process data the APIs use.
# Requests never compute: "/" embeds the last snapshot (no empty state) and /api/apple/home|dash return it.
_bg = {"on": False}
def _bg_loop():
    while True:
        for f in (home_data, dash_data):
            try: f()
            except Exception: pass
        time.sleep(100)
def _ensure_bg():
    return   # background refresher disabled: on Render it never refreshed (snapshot froze); the API's own 60/90 s caches refresh on demand
    if _bg["on"]: return
    with _lock:
        if _bg["on"]: return
        _bg["on"] = True
    threading.Thread(target=_bg_loop, daemon=True, name="bna-snapshot").start()
_cold = {"t": None}
def _cold_kick():
    """One-shot cold build (at most one thread ever running); the page never waits on it for more than 2 s."""
    t = _cold["t"]
    if t is not None and t.is_alive(): return t
    def run():
        for f in (home_data, dash_data):
            try: f()
            except Exception: pass
    t = threading.Thread(target=run, name="bna-snap-cold", daemon=True); _cold["t"] = t; t.start()
    return t
def _snap_js():
    # Cold start (first "/" after a deploy): kick the single-flight build and wait at most 2 s; if it is not ready the page
    # ships without a snapshot and bn-apple-home.js fills it from /api/apple/home (never blocks on data).
    if not _cache["v"] or not _dcache["v"]:
        try: _cold_kick().join(2.0)
        except Exception: pass
    try: js = open(os.path.join(BASE, "static", "bn-apple-home.js"), encoding="utf-8").read()
    except Exception: return ""
    dump = lambda v: json.dumps(v, separators=(",", ":"), default=str).replace("</", "<\\/") if v else "null"
    return f'<script>{js}</script><script>window.BNA&&BNA.render({dump(_cache["v"])},{dump(_dcache["v"])})</script>'

def head_tag():
    """Early, render-blocking switch: '/' with no hash (or #home) shows the new homepage; any tab hash shows the dashboard."""
    # bna-home: the new homepage (dashboard path "/" with no tab hash). bna-pg: the page groups restyled so far
    # (The Wire, Threats tabs, /crime, /network, /wire/<id> event pages); every other page keeps its current look.
    return (b'<script>(function(){var d=document.documentElement,p=location.pathname;function f(){var h=location.hash.replace(/^#/,""),home=p=="/"&&(!h||h=="home");'
            b'd.classList.toggle("bna-home",home);d.classList.toggle("bna-pg",!home)}'
            b'f();addEventListener("hashchange",f)})()</script>'
            b'<link rel="stylesheet" href="/bn-apple.css">')

def _map_section():
    """Global signal map card. Failure here must not take the homepage down."""
    try:
        import signal_map
        return signal_map.home_section()
    except Exception:
        return ""

def home_html(sn):
    """Server-rendered homepage shell (static text + real links). Live numbers fill in from /api/apple/home."""
    try:
        import sitenav_ui as UI; groups = UI.menu3_sections(sn)
    except Exception: groups = []
    cols = ""
    for g in groups:
        sid, label, items = g[0], g[1], g[-1]
        lis = "".join((f'<li><a href="{E(h)}">{E(l)}</a></li>' if h else f'<li class="bna-soon">{E(l)} <em>Soon</em></li>') for _k, l, h in items)
        cols += f'<div><h2>{E(label)}</h2><ul>{lis}</ul></div>'
    return f'''<div id="bna_home" class="bna" aria-label="Home">
<h1 class="bna-vh">BLACKOUT.NETWORK</h1>
{_board_html()}
<section class="bna-sec" aria-labelledby="bna_h_latest"><div class="bna-wrap bna-sech"><h2 id="bna_h_latest">The latest. <span>Ranked as it happens.</span></h2>
<div class="bna-arrows"><button type="button" class="bna-arw" data-dir="-1" aria-label="Scroll back" aria-controls="bna_row_latest">&lsaquo;</button><button type="button" class="bna-arw" data-dir="1" aria-label="Scroll forward" aria-controls="bna_row_latest">&rsaquo;</button></div></div>
<div class="bna-row" id="bna_row_latest" tabindex="0" aria-label="Top of the Wire"></div>
<p class="bna-wrap bna-more"><a class="bna-lnk" href="/#wire">Open The Wire</a></p></section>
{_map_section()}
{_snap_js()}
<section class="bna-sec bna-wrap"><div class="bna-brief"><div><h2>The Free brief. <span>The day, ranked.</span></h2><p>The highest-ranked events of the day, in one email.</p></div>
<a class="bna-btn" href="/newsletter">Get the Free brief</a></div><p class="bna-asof" data-bna="asof"></p></section>
<footer class="bna-foot"><div class="bna-wrap"><nav class="bna-cols" aria-label="Site">{cols}</nav>
<div class="bna-bot"><p class="bna-fol">Follow <a href="{E(sn.YT_URL)}" target="_blank" rel="noopener me">YouTube</a><a href="{E(sn.X_URL)}" target="_blank" rel="noopener me">X</a></p>
<p class="bna-legal"><a href="/scoring">How we score</a><a href="/privacy">Privacy</a><a href="/tos">Terms</a><a href="/stats">Stats</a><a href="/report-status">Report status</a></p></div>
<p class="bna-copy">BLACKOUT.NETWORK. Signal over noise.&trade;</p></div></footer></div>'''

def _static(name, ctype):
    with open(os.path.join(BASE, "static", name), "rb") as f: return 200, f.read(), ctype

def handle_get(path, qs):
    if not ENABLED(): return 404, {"error": "not found"}
    if path == "/bn-apple.css": return _static("bn-apple.css", "text/css")
    if path == "/bn-apple.js": return _static("bn-apple.js", "application/javascript")
    if path in ("/api/apple/home", "/api/apple/dash"):
        return 200, home_data() if path.endswith("home") else dash_data()   # cached 60 s / 90 s; "/" embeds the last result
    return 404, {"error": "not found"}
