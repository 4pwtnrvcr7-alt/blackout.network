"""Every Wire item on the map (Nov 20 2026, Matt pt1672u: "Everything that's coming through on the wire should be on the map").

build(days=7) returns the exact item set the Wire (/api/wire_tl) shows: blackout.db clusters with watchlist 0/1 plus the
trends_history.db archive stories, windowed by the Wire's own time (last activity, COALESCE(updated, first_seen)).
Each item gets the best honest map position, with its precision spelled out:
  exact    geo.db located it to a point, city, county or state, or the cluster carries source coordinates
  approx   approximate: geo.db country-level, or a fallback (one of several places named, a nationality, the classic map's offline
           place match while the exact geocode is pending). Drawn as hollow rings and labeled approximate.
  region   only a broad region is known (Middle East, Pacific ...): drawn as a labeled region ring, never a fake precise spot
  global   no place at all (cyber, markets, "Global (software)" ...): listed in the map's "No location" tray, not drawn
Nothing here geocodes online, writes a database, or touches scores. All databases are opened read-only."""
import json, os, re, sqlite3, threading, time
from datetime import datetime, timedelta, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "blackout.db"); HDB = os.path.join(BASE, "trends_history.db"); GDB = os.path.join(BASE, "geo.db")
DATA = os.path.join(BASE, "heatmap_data")
WINDOWS = (24, 72, 168)

def on(): return os.environ.get("BN_MAP_ALL", "1") != "0"
def _now(): return datetime.now(timezone.utc)
def _iso(d): return d.strftime("%Y-%m-%dT%H:%M:%SZ")

def _ro(p):
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=15); c.row_factory = sqlite3.Row; return c

# ------------------------------------------------------------------ reference data (small, offline)
_C = {}
def countries():
    if "c" not in _C:
        try: _C["c"] = json.load(open(os.path.join(DATA, "countries.json")))
        except Exception: _C["c"] = {}
        names = {}
        for iso2, c in _C["c"].items():
            for n in {c.get("name") or "", *(c.get("ne_names") or [])}:
                if n: names[_k(n)] = iso2
        try:
            import geo
            for iso2, al in geo.COUNTRY_ALIASES.items():
                for n in al: names.setdefault(_k(n), iso2)
            _C["dem"] = dict(geo.DEMONYMS)
        except Exception: _C["dem"] = {}
        _C["names"] = names
    return _C["c"]

def _k(s):
    import unicodedata
    s = unicodedata.normalize("NFKD", s or ""); s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()

def cc_of_name(name):
    countries(); return _C["names"].get(_k(name))

def country_pos(cc):
    c = countries().get((cc or "").upper()) or {}
    lab = c.get("label")
    if not lab: return None
    return {"lat": round(float(lab[0]), 4), "lon": round(float(lab[1]), 4), "cc": cc.upper(), "cn": c.get("name") or cc}

# Broad regions geo.py recognises (geo.BROAD_REGIONS) -> rough visual centre. Drawn as region rings, labeled "region only".
BROAD = {"middle east": (29.0, 45.0), "europe": (50.0, 15.0), "european union": (50.0, 10.0), "africa": (5.0, 20.0), "asia": (35.0, 95.0),
         "latin america": (-10.0, -60.0), "south america": (-15.0, -60.0), "north america": (45.0, -100.0), "central america": (14.0, -87.0),
         "caribbean": (17.0, -72.0), "balkans": (43.0, 21.0), "sahel": (15.0, 5.0), "horn of africa": (8.5, 47.0), "persian gulf": (27.0, 51.5),
         "the gulf": (26.0, 51.0), "gulf states": (25.0, 51.0), "southeast asia": (10.0, 108.0), "east asia": (35.0, 120.0), "central asia": (45.0, 65.0),
         "south asia": (22.0, 78.0), "scandinavia": (63.0, 15.0), "baltics": (57.0, 24.0), "baltic states": (57.0, 24.0), "eastern europe": (50.0, 30.0),
         "western europe": (48.0, 5.0), "west africa": (10.0, -5.0), "east africa": (0.0, 37.0), "southern africa": (-25.0, 25.0), "central africa": (2.0, 20.0),
         "north africa": (28.0, 10.0), "pacific": (0.0, -160.0), "indo pacific": (5.0, 110.0), "arctic": (78.0, 10.0), "antarctica": (-80.0, 0.0),
         "midwest": (42.0, -90.0), "midwestern": (42.0, -90.0), "west coast": (40.0, -122.0), "east coast": (38.0, -76.0), "gulf coast": (29.5, -91.0),
         "red sea": (20.0, 38.5), "black sea": (43.5, 34.5)}
BROAD_LABEL = {"midwestern": "Midwest", "the gulf": "Persian Gulf", "baltic states": "Baltics", "indo pacific": "Indo-Pacific"}
# The Wire's own display regions (wire_timeline.REGIONS). "sea" (oceans & poles) and "gl" have no single centre: those go to the tray.
WIRE_REG = {"na": (39.5, -98.5, "North America"), "la": (-12.0, -60.0, "Latin America"), "eu": (50.0, 15.0, "Europe"), "me": (29.0, 45.0, "Middle East"),
            "af": (5.0, 20.0, "Africa"), "as": (35.0, 95.0, "Asia"), "oc": (-25.0, 140.0, "Oceania")}

def _region(key, label, lat, lon):
    return {"lat": lat, "lon": lon, "prec": "region", "tier": "region", "place": label, "rid": key}

# ------------------------------------------------------------------ fallbacks for geo.db's unlocated reasons
_CAND = re.compile(r"\(([^()]*)\)\s*$")
def _cands_cc(cands):
    """['Qatar (Qatar)', 'Peoria (Illinois, US)', 'Georgia (US state)'] -> ['QA', 'US', 'US'] (None where unknown)."""
    out = []
    for s in cands or []:
        m = _CAND.search(s or ""); inner = (m.group(1) if m else "").strip()
        cc = None
        if inner.lower() == "us state": cc = "US"
        elif inner.lower() == "country": cc = cc_of_name(_CAND.sub("", s))
        elif inner:
            last = inner.split(",")[-1].strip()
            if re.fullmatch(r"[A-Z]{2}", last): cc = last
            else: cc = cc_of_name(last) or cc_of_name(inner)
        out.append(cc)
    return out

_FLAG = re.compile(r"flag ([A-Z]{2})")
def _nationality_ccs(reason, title):
    """Countries behind 'only nationality words or flags: Israeli, Palestinian, flag RU' in order of first appearance in the title."""
    countries(); dem = _C.get("dem") or {}
    bits = re.sub(r"\(these say who.*$", "", (reason or "").split(":", 1)[-1]).split(",")
    found = []
    tl = (title or "").lower()
    for b in bits:
        b = b.strip(); cc = None; pos = 10 ** 6
        m = _FLAG.match(b)
        if m:
            cc = m.group(1)
            flag = "".join(chr(0x1F1E6 + ord(ch) - 65) for ch in cc)
            p = (title or "").find(flag); pos = p if p >= 0 else pos
        elif b:
            cc = dem.get(b.lower())
            p = tl.find(b.lower()); pos = p if p >= 0 else pos
        if cc: found.append((pos, cc))
    found.sort(key=lambda x: x[0])
    return list(dict.fromkeys(cc for _, cc in found))

def _broad(reason):
    m = re.search(r"broad region \((.+?)\)", reason or "")
    if not m: return None
    for name in m.group(1).split(","):
        k = _k(name)
        if k in BROAD: return k, BROAD_LABEL.get(k, name.strip())
    return None

_INF = {}
def _infer(item):
    """signal_place's conservative offline match (the classic /map's), cached per item text. None when unsure or unavailable."""
    key = (item["id"], item["title"], item.get("loc"))
    if key in _INF: return _INF[key]
    hit = None
    try:
        import signal_place as SP
        hit = SP.infer(SP.story_text(item["title"], item.get("loc") or "", item.get("brief") or ""))
    except Exception:
        hit = None
    if len(_INF) > 20000: _INF.clear()
    _INF[key] = hit
    return hit

def _generic(place):
    """Reject offline matches on bare direction words ("South" from "Kwara South")."""
    head = _k((place or "").split(",")[0])
    if not head: return True
    try:
        import geo
        return head in geo.GENERIC
    except Exception:
        return head in {"north", "south", "east", "west", "central"}

def _infer_agrees(item, hit):
    """The classic offline match must agree with the story: its country is one the text names (when it names any), it matches the
    sources' own country (local US TV is not China), and its name is not one half of a hyphenated name."""
    cc = (hit.get("cc") or "").upper()
    if not cc: return True
    try:
        import geo
        named = geo._named_countries(item.get("title") or "") | geo._named_countries(item.get("loc") or "")     # countries/states named outright
        try: links = json.loads(item.get("links") or "[]") if isinstance(item.get("links"), str) else (item.get("links") or [])
        except Exception: links = []
        prior = geo.source_cc([{"source": (l or {}).get("source") or (l or {}).get("s"), "source_url": (l or {}).get("url") or (l or {}).get("u")} for l in links if isinstance(l, dict)])
    except Exception:
        return True
    if named and cc not in named: return False
    if prior and cc != prior and cc not in named and not (prior == "US" and cc in ("PR", "GU", "VI", "AS", "MP", "UM")): return False
    head = (hit.get("place") or "").split(",")[0].strip()
    if head and re.search(r"(?:[A-Za-z]-" + re.escape(head) + r"\b|\b" + re.escape(head) + r"-[A-Za-z])", item.get("title") or "", re.I) and \
            not re.search(r"(?<![-A-Za-z])" + re.escape(head) + r"(?![-A-Za-z])", item.get("title") or "", re.I):
        return False
    return True

def _wire_region(item):
    try:
        import wire_timeline as W
        return W.region_key(item.get("loc"), item["title"], item.get("lat"), item.get("lon"))
    except Exception:
        return "gl"

_EMO = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200D]")   # same strip as the Wire's headlines (wire_timeline._clean)
def _title(t): return re.sub(r"\s{2,}", " ", _EMO.sub("", re.sub(r"\s+", " ", t or ""))).strip()[:220]

def _ok(lat, lon):
    try: lat, lon = float(lat), float(lon)
    except (TypeError, ValueError): return False
    return -90 <= lat <= 90 and -180 <= lon <= 180 and not (lat == 0 and lon == 0)

PREC_EXACT = {"point", "city", "county", "state", "facility"}

def place(item, g):
    """-> dict(lat, lon, prec, tier, place, cc, how, rid). lat/lon None only for tier 'global'."""
    if g and g.get("located") and _ok(g.get("lat"), g.get("lon")):
        prec = g.get("precision") or "point"
        # Nov 21 2026 (pt1682u): a low-confidence match (weak town name, or coordinates that contradict the story's country) is drawn as approximate
        exact = prec in PREC_EXACT and (g.get("confidence") or "") != "low"
        return {"lat": round(float(g["lat"]), 4), "lon": round(float(g["lon"]), 4), "prec": prec, "tier": "exact" if exact else "approx",
                "place": g.get("place") or g.get("country_name") or "", "cc": g.get("country") or "", "how": "geo"}
    if _ok(item.get("lat"), item.get("lon")):
        return {"lat": round(float(item["lat"]), 4), "lon": round(float(item["lon"]), 4), "prec": "point", "tier": "exact",
                "place": item.get("loc") or "", "cc": "", "how": "source coordinates"}
    rc = (g or {}).get("reason_code") or ("archive" if item.get("a") else "pending")
    reason = (g or {}).get("reason_unlocated") or ""
    cands = []
    if g and g.get("candidates"):
        try: cands = json.loads(g["candidates"]) or []
        except Exception: cands = []
    def at_country(cc, how, label=None):
        p = country_pos(cc)
        if not p: return None
        return {"lat": p["lat"], "lon": p["lon"], "prec": "country", "tier": "approx", "place": label or p["cn"], "cc": p["cc"], "how": how}
    if rc == "multi_place":
        ccs = [c for c in _cands_cc(cands) if c]
        if ccs:
            names = [re.sub(r"\s*\(.*$", "", s) for s in cands]
            others = [n for n in names[1:] if n][:3]
            r = at_country(ccs[0], "several places named" + (" (also " + ", ".join(others) + ")" if others else ""))
            if r: return r
    if rc == "nationality_only":
        ccs = _nationality_ccs(reason, item["title"])
        if ccs:
            r = at_country(ccs[0], "nationality named, not a place" + (" (also " + ", ".join(ccs[1:4]) + ")" if len(ccs) > 1 else ""))
            if r: return r
    if rc == "ambiguous":
        ccs = set(c for c in _cands_cc(cands) if c)
        if len(ccs) == 1:
            r = at_country(ccs.pop(), "place name matches several spots in one country")
            if r: return r
    if rc == "broad_region":
        b = _broad(reason)
        if b:
            k, label = b; lat, lon = BROAD[k]
            return dict(_region("b:" + k, label, lat, lon), cc="", how="only a broad region is named")
    if rc not in ("global", "ambiguous"):
        hit = _infer(item)
        if hit and _generic(hit.get("place")): hit = None
        if hit and not _infer_agrees(item, hit): hit = None     # v10 (pt1686u): "Miami-Dade" is not Dade, China
        if hit and _ok(hit.get("lat"), hit.get("lon")):
            prec = hit.get("precision") or "country"
            if prec == "country" and hit.get("cc"):
                r = at_country(hit["cc"], "offline place match" + (" (exact geocode pending)" if rc == "pending" else ""), None)
                if r: return r
            if prec == "region":
                return dict(_region("p:" + _k(hit.get("place") or ""), hit.get("place") or "Region", round(float(hit["lat"]), 4), round(float(hit["lon"]), 4)),
                            cc=hit.get("cc") or "", how="offline place match")
            return {"lat": round(float(hit["lat"]), 4), "lon": round(float(hit["lon"]), 4), "prec": prec, "tier": "approx",
                    "place": hit.get("place") or "", "cc": hit.get("cc") or "", "how": "offline place match" + (" (exact geocode pending)" if rc == "pending" else "")}
    # ambiguous across countries, not found, no place: the Wire's own region (both Rafahs are Middle East), else the tray
    wr = _wire_region(item)
    if wr in WIRE_REG:
        lat, lon, label = WIRE_REG[wr]
        return dict(_region("w:" + wr, label, lat, lon), cc="", how="only the region is known")
    return {"lat": None, "lon": None, "prec": "global", "tier": "global", "place": "", "cc": "", "rid": "", "how": {
        "global": "the source marks it as global", "non_geo": "non-geographic topic", "no_place": "no place named"}.get(rc, "no place found")}

# ------------------------------------------------------------------ the Wire's item set
_LIVE = ("SELECT cluster_id id, COALESCE(updated, first_seen) t, first_seen fs, title, category, location loc, lat, lon, rank, watchlist, links, "
         "n_families, eff_families, brief, 0 a FROM clusters WHERE watchlist IN (0,1) AND COALESCE(updated, first_seen)>=?")
_ARCH = ("SELECT id, t, t fs, title, category, location loc, lat, lon, rank, watchlist, links, NULL n_families, NULL eff_families, NULL brief, 1 a "
         "FROM stories WHERE watchlist IN (0,1) AND t>=?")

def wire_counts(now=None):
    """The Wire's own count per map window (same tables, same filter, same time column as /api/wire_tl)."""
    now = now or _now(); out = {}
    c = _ro(DB)
    try:
        for h in WINDOWS:
            out[str(h)] = c.execute("SELECT COUNT(*) FROM clusters WHERE watchlist IN (0,1) AND COALESCE(updated, first_seen)>=?", (_iso(now - timedelta(hours=h)),)).fetchone()[0]
    finally: c.close()
    if os.path.exists(HDB):
        try:
            hd = _ro(HDB)
            try:
                for h in WINDOWS:
                    out[str(h)] += hd.execute("SELECT COUNT(*) FROM stories WHERE watchlist IN (0,1) AND t>=?", (_iso(now - timedelta(hours=h)),)).fetchone()[0]
            finally: hd.close()
        except sqlite3.Error: pass
    return out

def _geo_rows(ids):
    if not os.path.exists(GDB): return {}
    try: c = _ro(GDB)
    except sqlite3.Error:
        try: import geo; c = geo.gdb()
        except Exception: return {}
    try:
        out = {}
        ids = list(ids)
        for k in range(0, len(ids), 500):
            q = ids[k:k + 500]
            for r in c.execute(f"SELECT * FROM geo WHERE id IN ({','.join('?' * len(q))})", q): out[r["id"]] = dict(r)
        return out
    except sqlite3.Error: return {}
    finally: c.close()

def build(days=7, now=None):
    now = now or _now(); cut = _iso(now - timedelta(days=days))
    c = _ro(DB)
    try: items = [dict(r) for r in c.execute(_LIVE, (cut,))]
    finally: c.close()
    if os.path.exists(HDB):
        try:
            hd = _ro(HDB)
            try: items += [dict(r) for r in hd.execute(_ARCH, (cut,))]
            finally: hd.close()
        except sqlite3.Error: pass
    geo_rows = _geo_rows(i["id"] for i in items if not i["a"])
    rows, tiers, reasons = [], {"exact": 0, "approx": 0, "region": 0, "global": 0}, {}
    for it in items:
        g = geo_rows.get(it["id"])
        p = place(it, g)
        tiers[p["tier"]] += 1
        if p["how"] != "geo": reasons[p["how"].split(" (")[0]] = reasons.get(p["how"].split(" (")[0], 0) + 1
        try: links = json.loads(it["links"] or "[]")
        except Exception: links = []
        ln = (links[0] if links and isinstance(links[0], dict) else {}) or {}
        rk = it["rank"]
        try: rk = int(rk or 0)
        except (TypeError, ValueError): rk = 0
        rows.append([it["id"], p["lat"], p["lon"], rk, it["category"] or "", it["t"] or "", _title(it["title"]),
                     p.get("place") or "", p["prec"], int(it["watchlist"] or 0), (ln.get("source") or "")[:60], (ln.get("url") or "")[:500],
                     p.get("cc") or "", int(it["eff_families"] or it["n_families"] or 0), p["tier"], p["how"], p.get("rid") or "", int(it["a"] or 0)])
    rows.sort(key=lambda r: r[5], reverse=True)
    wc = wire_counts(now)
    n = len(rows)
    return {"generated": _iso(now), "source": "wire", "window_days": days,
            "coverage": {"total": n, "located": tiers["exact"] + tiers["approx"], "pct": round(100 * (n - tiers["global"]) / n, 1) if n else 0,
                         "tiers": tiers, "fallbacks": dict(sorted(reasons.items(), key=lambda kv: -kv[1])), "wire_counts": wc},
            "cols": ["id", "lat", "lon", "rank", "cat", "t", "title", "place", "prec", "watch", "src", "url", "cc", "fam", "tier", "how", "rid", "arch"],
            "rows": rows}
