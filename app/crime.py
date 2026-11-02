"""Crime tab (t392, Nov 1 2026): GET /crime (HTML), /api/crime/search?q=, /api/crime/heat?feed=, /api/crime/counties, /api/crime/global,
/api/crime/feeds, /api/crime/static/<file>, /api/crime/app.js|app.css.

Reads ONLY crime.db (built on the box by crime_collect.py and pushed by the normal data sync) and two static TopoJSON files.
This node never calls the crime sources itself, so a page view costs one small SQLite read and memory stays flat (Render free: 512 MB).
Privacy and tone: incidents are shown only as ~200 m grid cells and category + hour; no names, case numbers, addresses or victim/suspect
details exist in crime.db. Neutral, factual wording; no demographic data is collected or shown.
Never touches scanner.py, scoring, push.py, jets.py, aviation_watch.py or config.json."""
import os, re, json, html, time, math, sqlite3, urllib.parse
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import sitenav

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "crime.db")
STATIC = os.path.join(BASE, "crime_static")
SITE = "https://blackout.network"; BRAND = "BLACKOUT.NETWORK"
ET = ZoneInfo("America/New_York")
E = lambda s: html.escape(str(s if s is not None else ""), quote=True)
TITLE = "Crime map and statistics near you: ZIP, city, county, country | BLACKOUT.NETWORK"
DESC = ("Look up crime for any US ZIP code, city, county or state, or any country: official FBI rates per 100,000 with trends, "
        "near-real-time incident heat maps for 16 US cities, a US county map and a world homicide map. Free, sourced, no sign-up.")
VCOL, PCOL, OCOL = "#FF4D4F", "#F5A524", "#8B95A3"

# ------------------------------------------------------------------------------------------------ data access
_C = {}
def _db():
    if not os.path.exists(DB): return None
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=10); c.row_factory = sqlite3.Row; return c
def _mt():
    try: return os.path.getmtime(DB)
    except OSError: return 0
def cached(key, fn):
    mt = _mt(); v = _C.get(key)
    if v and v[0] == mt: return v[1]
    r = fn(); _C[key] = (mt, r); return r
def q1(sql, args=()):
    c = _db()
    if not c: return None
    try: return c.execute(sql, args).fetchone()
    finally: c.close()
def qa(sql, args=()):
    c = _db()
    if not c: return []
    try: return c.execute(sql, args).fetchall()
    finally: c.close()
def meta(k):
    r = q1("SELECT v FROM meta WHERE k=?", (k,))
    try: return json.loads(r[0]) if r else {}
    except Exception: return {}

def feeds():
    def f():
        out = []
        for r in qa("SELECT * FROM feeds WHERE newest IS NOT NULL ORDER BY city"):
            d = dict(r)
            for k in ("bbox", "cats", "daily"):
                try: d[k] = json.loads(d[k] or "null")
                except Exception: d[k] = None
            out.append(d)
        return out
    return cached("feeds", f)

def _state_rates(st):
    r = q1("SELECT * FROM states WHERE st=?", (st,))
    if not r: return None
    s = json.loads(r["series"] or "{}"); y = r["latest"]
    if not y: return {"st": st, "name": r["name"], "year": None}
    v = s.get(str(y), {}); cp = v.get("cov_pop") or 0
    rate = lambda n: round(n / cp * 1e5, 1) if (cp and n is not None) else None
    trend = []
    for yy in sorted(s, key=int):
        x = s[yy]
        if x.get("months", 0) >= 12 and x.get("cov_pop"):
            trend.append({"year": int(yy), "v": rate_of(x.get("violent-crime"), x["cov_pop"]), "p": rate_of(x.get("property-crime"), x["cov_pop"])})
    cats = {k: rate(v.get(k)) for k in ("homicide", "rape", "robbery", "aggravated-assault", "burglary", "larceny", "motor-vehicle-theft", "arson")}
    return {"st": st, "name": r["name"], "year": y, "v_rate": rate(v.get("violent-crime")), "p_rate": rate(v.get("property-crime")),
            "violent": v.get("violent-crime"), "property": v.get("property-crime"), "coverage": round(cp / v["pop"], 3) if v.get("pop") else None,
            "cats": cats, "trend": trend[-6:]}
def rate_of(n, p): return round(n / p * 1e5, 1) if (n is not None and p) else None
def state(st): return cached("st:" + st, lambda: _state_rates(st))
def national(): return state("US")

def county(fips):
    r = q1("SELECT * FROM counties WHERE fips=?", (fips,))
    if not r: return None
    d = dict(r)
    for k in ("series", "ytd"):
        try: d[k] = json.loads(d[k] or "null")
        except Exception: d[k] = None
    tr = []
    for y, v in sorted((d.get("series") or {}).items(), key=lambda kv: int(kv[0])):
        if v.get("cov_pop"): tr.append({"year": int(y), "v": rate_of(v["v"], v["cov_pop"]), "p": rate_of(v["p"], v["cov_pop"]), "cov": round(v["cov_pop"] / d["pop"], 2) if d.get("pop") else None})
    d["trend"] = tr[-6:]
    return d

def agency_for_city(city, st):
    c = (city or "").strip()
    if not c or not st: return None
    pats = [f"{c} Police Department", f"{c} Police Dept%", f"{c} Police%", f"City of {c}%", f"{c} Metropolitan Police%", f"{c} Department of Public Safety%"]
    for p in pats:
        r = q1("SELECT * FROM agencies WHERE st=? AND type='City' AND name LIKE ? AND status='ok' ORDER BY pop DESC LIMIT 1", (st, p))
        if r: return _agency(r)
    return None
def _agency(r):
    d = dict(r)
    for k in ("series", "ytd"):
        try: d[k] = json.loads(d[k] or "null")
        except Exception: d[k] = None
    d["trend"] = [{"year": int(y), "v": rate_of(v["v"] * 12 / v["m"], v["pop"]) if v["m"] else None, "p": rate_of(v["p"] * 12 / v["m"], v["pop"]) if v["m"] else None}
                  for y, v in sorted((d.get("series") or {}).items(), key=lambda kv: int(kv[0])) if v.get("m", 0) >= 10 and v.get("pop")][-6:]
    return d

def country(iso2=None, iso3=None):
    r = q1("SELECT * FROM countries WHERE " + ("iso2=?" if iso2 else "iso3=?"), (iso2 or iso3,))
    if not r: return None
    d = dict(r); d["series"] = json.loads(d["series"] or "{}")
    allr = sorted(x[0] for x in qa("SELECT rate FROM countries WHERE year>=2015"))
    d["median"] = allr[len(allr) // 2] if allr else None
    d["rank"] = 1 + sum(1 for x in qa("SELECT rate FROM countries WHERE year>=2015 AND rate>?", (d["rate"],))); d["n_ranked"] = len(allr)
    return d

# ------------------------------------------------------------------------------------------------ geocoding (offline, reuses the newsletter geocoder)
def _nl():
    import newsletter; return newsletter
def zip_county(z): r = q1("SELECT fips FROM zips WHERE zip=?", (z,)); return r[0] if r else None
def nearest_zip(lat, lon):
    G = _nl()._geo_data()["zip"]; best = None
    for z, v in G.items():
        d = (v[0] - lat) ** 2 + ((v[1] - lon) * math.cos(math.radians(lat))) ** 2
        if best is None or d < best[0]: best = (d, z)
    return best[1] if best and best[0] < 0.25 else None
def nearest_county(lat, lon, max_km=60):
    best = None
    for r in qa("SELECT fips, lat, lon FROM counties WHERE lat IS NOT NULL"):
        d = _km(lat, lon, r["lat"], r["lon"])
        if best is None or d < best[0]: best = (d, r["fips"])
    return best[1] if best and best[0] <= max_km else None
def _km(a, b, c, d):
    p = math.pi / 180; x = 0.5 - math.cos((c - a) * p) / 2 + math.cos(a * p) * math.cos(c * p) * (1 - math.cos((d - b) * p)) / 2
    return 12742 * math.asin(math.sqrt(max(0, x)))
def feed_for(lat, lon):
    if lat is None or lon is None: return None
    best = None
    for f in feeds():
        bb = f.get("bbox")
        if not bb: continue
        pad = 0.01
        if bb[0] - pad <= lon <= bb[2] + pad and bb[1] - pad <= lat <= bb[3] + pad:
            d = _km(lat, lon, f["lat"], f["lon"])
            if d <= 45 and (best is None or d < best[0]): best = (d, f)
    return best[1] if best else None

ST_ABBR = {}
def state_lookup(q):
    if not ST_ABBR:
        for r in qa("SELECT st, name FROM states"): ST_ABBR[r["st"]] = r["name"]
    u = q.strip().upper().replace(".", "")
    if u in ST_ABBR and u != "US": return u
    for st, nm in ST_ABBR.items():
        if nm and nm.upper() == u and st != "US": return st
    return None

def resolve(q):
    """-> place dict {label, kind, lat, lon, st, fips, cc, city} or None."""
    q = re.sub(r"\s+", " ", str(q or "")).strip()[:80]
    if not q: return None
    if q.upper() in ("US", "USA", "UNITED STATES", "UNITED STATES OF AMERICA", "AMERICA"): return {"label": "United States", "kind": "national", "cc": "US"}
    m = re.fullmatch(r"(\d{5})(?:-\d{4})?", q)
    if m:
        z = m.group(1); fp = zip_county(z); g = _nl().geocode_place(z)
        if not fp and not g: return None
        if not fp and g and g.get("lat") is not None: fp = nearest_county(g["lat"], g["lon"])   # ZIP missing from the crosswalk copy
        st = None; cn = county(fp) if fp else None
        if cn: st = cn["st"]
        return {"label": (g or {}).get("label") or f"ZIP {z}", "kind": "zip", "zip": z, "lat": (g or {}).get("lat"), "lon": (g or {}).get("lon"), "fips": fp, "st": st, "cc": "US"}
    st = state_lookup(q)
    if st: return {"label": ST_ABBR.get(st, st), "kind": "state", "st": st, "cc": "US"}
    m = re.fullmatch(r"(.+?)\s+(county|parish|borough)\s*(?:,\s*([A-Za-z .]+))?", q, re.I)
    if m:
        nm, st2 = m.group(1).strip(), state_lookup(m.group(3) or "") if m.group(3) else None
        rows = qa("SELECT fips, name, st, lat, lon FROM counties WHERE lower(name) IN (?, ?)" + (" AND st=?" if st2 else "") + " ORDER BY pop DESC",
                  ((nm + " " + m.group(2)).lower(), nm.lower()) + ((st2,) if st2 else ()))
        if rows:
            r = rows[0]; return {"label": f"{r['name']}, {r['st']}", "kind": "county", "fips": r["fips"], "st": r["st"], "lat": r["lat"], "lon": r["lon"], "cc": "US"}
    g = _nl().geocode_place(q)
    if not g: return None
    if g["kind"] == "country":
        if g["cc"] == "US": return {"label": "United States", "kind": "national", "cc": "US"}
        return {"label": g["label"], "kind": "country", "cc": g["cc"], "lat": g["lat"], "lon": g["lon"]}
    if g["cc"] != "US": return {"label": g["label"], "kind": "intl_city", "cc": g["cc"], "lat": g["lat"], "lon": g["lon"]}
    z = nearest_zip(g["lat"], g["lon"]); fp = zip_county(z) if z else None; cn = county(fp) if fp else None
    st = (g["label"].split(", ")[-1] if ", " in g["label"] else None) or (cn or {}).get("st")
    return {"label": g["label"], "kind": "city", "city": g["label"].split(",")[0].strip(), "lat": g["lat"], "lon": g["lon"], "fips": fp, "st": st, "cc": "US"}

# ------------------------------------------------------------------------------------------------ lookup
def _feed_summary(f, days=30):
    d = dict(f); daily = d.get("daily") or []
    tot = [sum(x[1]) for x in daily]; viol = sum(x[1][0] for x in daily); prop = sum(x[1][1] for x in daily)
    tz = ZoneInfo(f["tz"]); d["violent"] = viol; d["property"] = prop; d["total"] = sum(tot)
    d["change"] = round((d["n_window"] - d["n_prev"]) / d["n_prev"] * 100) if d.get("n_prev") else None
    def _ab(loc):
        try: return datetime.fromisoformat(loc).replace(tzinfo=tz).strftime("%Z")
        except Exception: return datetime.now(tz).strftime("%Z")
    d["tzabbr"] = _ab(d.get("window_end") or "")
    d["recent_serious"] = [dict(r) for r in qa("SELECT local, glat, glon, cat FROM serious WHERE feed=? ORDER BY ts_utc DESC LIMIT 12", (f["id"],))]
    for r in d["recent_serious"]: r["tz"] = _ab(r.get("local") or "")
    d.pop("api", None)
    return d

def lookup(q):
    p = resolve(q)
    if not p: return {"ok": False, "q": q, "message": "We couldn't find that place. Try a US ZIP code (60614), a city (Chicago, IL), a county (Seminole County, FL), a state or a country."}
    out = {"ok": True, "q": q, "place": p, "national": national()}
    if p["kind"] in ("country", "intl_city"):
        out["country"] = country(iso2=p["cc"])
    else:
        if p.get("st"): out["state"] = state(p["st"])
        if p.get("fips"): out["county"] = county(p["fips"])
        if p["kind"] == "city": out["agency"] = agency_for_city(p.get("city"), p.get("st"))
        if p["kind"] == "county" and out.get("county") and out["county"].get("lat"):
            p.setdefault("lat", out["county"]["lat"]); p.setdefault("lon", out["county"]["lon"])
        f = feed_for(p.get("lat"), p.get("lon")) if p["kind"] in ("zip", "city", "county") else None
        if f: out["feed"] = _feed_summary(f)
    out["html"] = render_result(out)
    return out

# ------------------------------------------------------------------------------------------------ formatting
def n(v):
    if v is None: return "—"
    return f"{int(round(v)):,}"
def r1(v): return "—" if v is None else (f"{v:,.1f}" if v < 100 else f"{v:,.0f}")
def pct(v): return "—" if v is None else f"{v * 100:.0f}%"
def dfmt(s, f="%b %-d, %Y"):
    try: return datetime.fromisoformat(s).strftime(f)
    except Exception: return s or "—"
def chg(cur, prev):
    if not prev or cur is None: return None
    return round((cur - prev) / prev * 100)
def chg_html(c, noun="vs. same months last year"):
    if c is None: return ""
    cls = "up" if c > 0 else ("dn" if c < 0 else "eq")
    arrow = "▲" if c > 0 else ("▼" if c < 0 else "■")
    return f'<span class="cr-chg {cls}">{arrow} {abs(c)}% {E(noun)}</span>'

def bars_compare(rows, key):
    """rows: [(label, value, highlight)] -> horizontal comparison bars."""
    vals = [v for _, v, _ in rows if v is not None]
    if not vals: return ""
    mx = max(vals) or 1
    return '<ul class="cr-cmp">' + "".join(
        f'<li class="{"hi" if hi else ""}"><span class="l">{E(lab)}</span><span class="b"><i style="width:{max(2, v / mx * 100) if v is not None else 0:.1f}%;background:{key}"></i></span>'
        f'<b>{r1(v)}</b></li>' for lab, v, hi in rows) + "</ul>"

def trend_html(tr, title):
    tr = [t for t in tr if t.get("v") is not None]
    if len(tr) < 2: return ""
    mv = max(t["v"] for t in tr) or 1; mp = max((t["p"] or 0) for t in tr) or 1
    cols = "".join(f'<div class="cr-tc"><div class="cr-tb"><i class="v" style="height:{t["v"] / mv * 92:.0f}%" title="Violent {r1(t["v"])}"></i>'
                   f'<i class="p" style="height:{(t["p"] or 0) / mp * 92:.0f}%" title="Property {r1(t["p"])}"></i></div><span>{t["year"]}</span></div>' for t in tr)
    return (f'<div class="cr-card"><h3>{E(title)}</h3><div class="cr-trend">{cols}</div>'
            f'<div class="cr-leg"><span><i style="background:{VCOL}"></i>Violent per 100k (scaled)</span><span><i style="background:{PCOL}"></i>Property per 100k (scaled)</span></div></div>')

def cats_html(cats, title, note=""):
    cats = [c for c in (cats or []) if c.get("n")]
    if not cats: return ""
    mx = max(c["n"] for c in cats)
    col = lambda nm: VCOL if nm in ("Homicide", "Shooting", "Robbery", "Sexual offense", "Aggravated assault", "Kidnapping", "Assault") else (
        PCOL if nm in ("Burglary", "Vehicle theft", "Arson", "Theft", "Vandalism", "Fraud") else OCOL)
    li = "".join(f'<li><span class="fill" style="width:{c["n"] / mx * 100:.1f}%;background:{col(c["cat"])}33;border-right:3px solid {col(c["cat"])}"></span>'
                 f'<span class="in"><span>{E(c["cat"])}</span><b>{n(c["n"])}{" " + chg_html(chg(c["n"], c.get("prev")), "") if c.get("prev") else ""}</b></span></li>' for c in cats[:12])
    return f'<div class="cr-card"><h3>{E(title)}</h3><ul class="cr-bars">{li}</ul>{note}</div>'

def daily_html(daily):
    if not daily or len(daily) < 3: return ""
    daily = daily[-30:]; mx = max(sum(x[1]) for x in daily) or 1
    cols = "".join(f'<div class="cr-dc" title="{E(d)}: {sum(v)} reports, {v[0]} violent"><i class="t" style="height:{sum(v) / mx * 100:.0f}%"></i>'
                   f'<i class="v" style="height:{v[0] / mx * 100:.0f}%"></i></div>' for d, v in daily)
    return (f'<div class="cr-card"><h3>Reports per day</h3><div class="cr-daily">{cols}</div><div class="cr-axis"><span>{E(dfmt(daily[0][0], "%b %-d"))}</span>'
            f'<span>{E(dfmt(daily[-1][0], "%b %-d"))}</span></div><div class="cr-leg"><span><i style="background:{VCOL}"></i>Violent</span>'
            f'<span><i style="background:#3a4350"></i>All reported</span></div></div>')

def kpi(label, val, sub, col):
    return f'<div class="cr-k" style="--c:{col}"><small>{E(label)}</small><b>{val}</b><span>{sub}</span></div>'

def _src(text, url): return f'<a href="{E(url)}" target="_blank" rel="noopener">{E(text)}</a>'
FBI_URL = "https://cde.ucr.cjis.gov/LATEST/webapp/#/pages/explorer/crime/crime-trend"
WB_URL = "https://data.worldbank.org/indicator/VC.IHR.PSRC.P5"

def render_result(d):
    p = d["place"]; nat = d.get("national") or {}; st = d.get("state"); cn = d.get("county"); ag = d.get("agency"); f = d.get("feed"); co = d.get("country")
    h = []
    kind_lbl = {"zip": "ZIP code", "city": "City", "county": "County", "state": "State", "national": "Country", "country": "Country", "intl_city": "City"}.get(p["kind"], "")
    h.append(f'<div class="cr-place"><span class="cr-kick">{E(kind_lbl)}</span><h2>{E(p["label"])}</h2>')
    if p["kind"] in ("zip", "city") and cn: h.append(f'<p class="cr-mu">In {E(cn["name"])}, {E(cn["st"])}.' + (' Near-real-time city data available.' if f else '') + '</p>')
    h.append('</div>')
    if co is not None or p["kind"] in ("country", "intl_city"):
        if not co:
            h.append('<div class="cr-empty">No recent official homicide figure is published for this country in the UNODC / World Bank series.</div>')
        else:
            yrs = sorted(co["series"].items(), key=lambda kv: int(kv[0]))[-8:]
            h.append('<div class="cr-kpis">' + kpi("Homicides per 100k", r1(co["rate"]), f'{co["year"]}, latest official year', VCOL)
                     + kpi("World median", r1(co["median"]), f'{co["n_ranked"]} countries reporting since 2015', OCOL)
                     + kpi("Rank (highest = 1)", f'{co["rank"]}', f'of {co["n_ranked"]} countries', PCOL) + '</div>')
            mx = max(v for _, v in yrs) or 1
            cols = "".join(f'<div class="cr-tc"><div class="cr-tb"><i class="v" style="height:{v / mx * 100:.0f}%" title="{v}"></i></div><span>{y}</span></div>' for y, v in yrs)
            h.append(f'<div class="cr-grid2"><div class="cr-card"><h3>Homicide rate trend</h3><div class="cr-trend">{cols}</div></div>'
                     f'<div class="cr-card"><h3>How it compares</h3>{bars_compare([(co["name"], co["rate"], True), ("World median", co["median"], False), ("United States", (country(iso2="US") or {}).get("rate"), False)], VCOL)}'
                     '<p class="cr-mu">Intentional homicide is the most comparable crime measure between countries; theft and assault are defined and recorded too differently to rank fairly.</p></div></div>')
        h.append(f'<div class="cr-note"><b>No near-real-time feed here.</b> Live incident maps are available only for US cities whose police publish open incident data. '
                 f'Source: UNODC via {_src("World Bank WDI (VC.IHR.PSRC.P5)", WB_URL)}, CC BY 4.0.</div>')
        return "".join(h)
    # ---- US: pick the most local official level with data
    lvl, lname, vr, pr, yr, cov, tr, ytd = None, None, None, None, None, None, [], None
    if ag and ag.get("latest"):
        lvl, lname, vr, pr, yr, tr, ytd = "agency", ag["name"], ag["v_rate"], ag["p_rate"], ag["latest"], ag["trend"], ag.get("ytd")
    elif cn and cn.get("year"):
        lvl, lname, vr, pr, yr, cov, tr, ytd = "county", f'{cn["name"]}, {cn["st"]}', cn["v_rate"], cn["p_rate"], cn["year"], cn.get("coverage"), cn["trend"], cn.get("ytd")
    elif st and st.get("year"):
        lvl, lname, vr, pr, yr, tr = "state", st["name"], st["v_rate"], st["p_rate"], st["year"], st["trend"]
    elif p["kind"] == "national" and nat.get("year"):
        lvl, lname, vr, pr, yr, tr = "national", "United States", nat["v_rate"], nat["p_rate"], nat["year"], nat["trend"]
    if lvl:
        sub = {"agency": f"{yr} · FBI data for {E(lname)}", "county": f"{yr} · {E(lname)} (all reporting agencies)", "state": f"{yr} · statewide",
               "national": f"{yr} · nationwide"}[lvl]
        yv = chg(ytd["v"], ytd["v_prev"]) if ytd else None; ypc = chg(ytd["p"], ytd["p_prev"]) if ytd else None
        h.append('<div class="cr-kpis">' + kpi("Violent crime per 100k", r1(vr), sub, VCOL) + kpi("Property crime per 100k", r1(pr), sub, PCOL))
        if ytd: h.append(kpi(f"{datetime.now().year} so far (Jan–{datetime(2000, ytd['months'], 1).strftime('%b')})", (f'{"+" if yv and yv > 0 else ""}{yv}%' if yv is not None else "—"),
                             f'violent vs. same months {datetime.now().year - 1}; property {("+" if ypc and ypc > 0 else "") + str(ypc) + "%" if ypc is not None else "—"}', OCOL))
        h.append('</div>')
        if lvl == "county" and cov is not None and cov < 0.6:
            h.append(f'<div class="cr-note warn">Partial data: agencies that reported to the FBI cover about {pct(cov)} of {E(lname)}\'s population, so treat these rates as an estimate.</div>')
        rows_v = []; rows_p = []
        if lvl in ("agency",) and cn and cn.get("v_rate") is not None: rows_v.append((f'{cn["name"]}', cn["v_rate"], False)); rows_p.append((f'{cn["name"]}', cn["p_rate"], False))
        if lvl in ("agency", "county"): rows_v.insert(0, (lname, vr, True)); rows_p.insert(0, (lname, pr, True))
        if st and st.get("v_rate") is not None: rows_v.append((st["name"], st["v_rate"], lvl == "state")); rows_p.append((st["name"], st["p_rate"], lvl == "state"))
        if nat.get("v_rate") is not None: rows_v.append(("United States", nat["v_rate"], lvl == "national")); rows_p.append(("United States", nat["p_rate"], lvl == "national"))
        h.append(f'<div class="cr-grid2"><div class="cr-card"><h3>Violent crime per 100,000 people</h3>{bars_compare(rows_v, VCOL)}</div>'
                 f'<div class="cr-card"><h3>Property crime per 100,000 people</h3>{bars_compare(rows_p, PCOL)}</div></div>')
        cats_s = (st or nat or {}).get("cats") if lvl != "national" else nat.get("cats")
        ct = trend_html(tr, f"Trend, {lname}")
        if cats_s:
            lab = {"homicide": "Homicide", "rape": "Rape", "robbery": "Robbery", "aggravated-assault": "Aggravated assault", "burglary": "Burglary",
                   "larceny": "Larceny-theft", "motor-vehicle-theft": "Vehicle theft", "arson": "Arson"}
            nm = (st or {}).get("name") if lvl != "national" and st else "United States"
            rows = [{"cat": lab[k], "n": v} for k, v in cats_s.items() if v]
            rows.sort(key=lambda x: -x["n"])
            mx = max(r["n"] for r in rows) if rows else 1
            li = "".join(f'<li><span class="fill" style="width:{r["n"] / mx * 100:.1f}%;background:{(VCOL if r["cat"] in ("Homicide", "Rape", "Robbery", "Aggravated assault") else PCOL)}33;'
                         f'border-right:3px solid {(VCOL if r["cat"] in ("Homicide", "Rape", "Robbery", "Aggravated assault") else PCOL)}"></span><span class="in"><span>{E(r["cat"])}</span><b>{r1(r["n"])}</b></span></li>' for r in rows)
            h.append(f'<div class="cr-grid2">{ct or ""}<div class="cr-card"><h3>By offense, {E(nm)} ({(st or nat).get("year")}), per 100k</h3><ul class="cr-bars">{li}</ul></div></div>')
        elif ct: h.append(ct)
    else:
        h.append('<div class="cr-empty">The FBI has no complete recent year for this area yet (for example, agencies still moving to the new NIBRS system). '
                 'State and national figures are shown below when available.</div>')
    # ---- near-real-time
    if f:
        tzab = f["tzabbr"]
        h.append(f'<div class="cr-sec"><h2><span class="cr-live"><i></i>Near-real-time</span> {E(f["city"])}: last 30 days of reports</h2>'
                 f'<span class="cr-mu">Data window {E(dfmt(f["window_start"], "%b %-d"))} to {E(dfmt(f["window_end"], "%b %-d, %Y"))} ({E(tzab)}). Publishing lag: {E(f["lag"])}.</span></div>')
        h.append('<div class="cr-kpis">' + kpi("Reports, last 30 days", n(f["n_window"]), chg_html(f.get("change"), "vs. previous 30 days") or "&nbsp;", OCOL)
                 + kpi("Violent", n(f["violent"]), f'{(f["violent"] / f["total"] * 100 if f["total"] else 0):.0f}% of reports', VCOL)
                 + kpi("Property", n(f["property"]), f'{(f["property"] / f["total"] * 100 if f["total"] else 0):.0f}% of reports', PCOL) + '</div>')
        h.append(f'<div class="cr-mapwrap"><div class="cr-maptools" role="group" aria-label="Map filter"><button type="button" class="on" data-g="all">All</button>'
                 f'<button type="button" data-g="v">Violent</button><button type="button" data-g="p">Property</button><span class="cr-mu">Each glow is a ~200 m block; red dots are serious violent reports in the last 14 days of data.</span></div>'
                 f'<div class="cr-map" id="cr-heat" data-feed="{E(f["id"])}" data-lat="{p.get("lat") or f["lat"]}" data-lon="{p.get("lon") or f["lon"]}" role="img" aria-label="Heat map of reported crime in {E(f["city"])}, last 30 days"></div></div>')
        rs = f.get("recent_serious") or []
        rs_html = "".join(f'<li><b>{E(r["cat"])}</b><span>{E(dfmt(r["local"], "%a %b %-d, %-I %p"))} {E(r.get("tz") or tzab)}</span></li>' for r in rs[:8])
        h.append('<div class="cr-grid2">' + cats_html(f.get("cats"), "What was reported (with change vs. previous 30 days)") +
                 '<div>' + daily_html(f.get("daily")) +
                 (f'<div class="cr-card"><h3>Latest serious violent reports</h3><ul class="cr-recent">{rs_html}</ul><p class="cr-mu">Shown by category and hour only, never by address or person.</p></div>' if rs_html else "")
                 + '</div></div>')
        h.append(f'<div class="cr-note">Source: {_src(f["source"], f["url"])} ({E(f["license"])}). Reports are initial police reports and can be reclassified later. '
                 f'Counts follow BLACKOUT.NETWORK\'s category grouping, not legal charges. Last checked {E(_ago(f.get("last_ok")))}.</div>')
    elif p["kind"] != "national":
        names = ", ".join(x["city"] for x in feeds())
        h.append(f'<div class="cr-note"><b>No near-real-time public feed covers {E(p["label"])} yet.</b> Showing the latest official FBI statistics instead. '
                 f'Near-real-time maps are available for: {E(names)}.</div>')
    h.append(f'<div class="cr-note">Official statistics: {_src("FBI Crime Data Explorer (UCR/NIBRS)", FBI_URL)}, public domain. Rates are offenses per 100,000 residents covered by reporting agencies.</div>')
    return "".join(h)

def _ago(iso):
    try: t = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except Exception: return "recently"
    s = (datetime.now(timezone.utc) - t).total_seconds()
    if s < 3600: return f"{max(1, int(s // 60))} min ago"
    if s < 86400: return f"{int(s // 3600)} h ago"
    return t.astimezone(ET).strftime("%b %-d, %-I:%M %p ET")

# ------------------------------------------------------------------------------------------------ newsletter hooks
def brief_for(sub):
    """Local crime section for one subscriber's brief, or None. sub: dict with loc_label, loc_lat, loc_lon, loc_cc, loc_kind."""
    try:
        if not sub or not sub.get("loc_label"): return None
        lab = sub["loc_label"]; url = f"{SITE}/crime?place={urllib.parse.quote(lab)}"
        if sub.get("loc_cc") and sub["loc_cc"] != "US":
            co = country(iso2=sub["loc_cc"])
            if not co: return None
            return {"label": co["name"], "url": url, "lines": [f"Intentional homicide rate: {r1(co['rate'])} per 100,000 people ({co['year']}), against a world median of {r1(co['median'])}."],
                    "source": "UNODC via World Bank"}
        q = lab.split(" ")[-1] if sub.get("loc_kind") == "zip" else lab
        d = lookup(q) if q else None
        if not d or not d.get("ok"): return None
        lines = []; f = d.get("feed")
        if f and f.get("daily"):
            last7 = f["daily"][-8:-1]; prev7 = f["daily"][-15:-8]   # skip the newest day: it is usually only partly published
            t7 = sum(sum(x[1]) for x in last7); v7 = sum(x[1][0] for x in last7); tp = sum(sum(x[1]) for x in prev7)
            c = chg(t7, tp)
            lines.append(f"{f['city']}, latest 7 days of police data (through {dfmt(last7[-1][0] if last7 else f['window_end'], '%b %-d')}): {t7:,} reports, {v7:,} of them violent"
                         + (f" ({'+' if c > 0 else ''}{c}% vs. the week before)." if c is not None else "."))
            top = ", ".join(f"{x['cat'].lower()} {x['n']:,}" for x in (f.get("cats") or [])[:3])
            if top: lines.append(f"Most reported in the last 30 days: {top}.")
        cn = d.get("county"); st = d.get("state"); nat = d.get("national") or {}
        if cn and cn.get("year") and cn.get("v_rate") is not None:
            lines.append(f"{cn['name']}, {cn['st']} ({cn['year']}, FBI): violent crime {r1(cn['v_rate'])} and property crime {r1(cn['p_rate'])} per 100,000"
                         + (f"; {st['name']} {r1(st['v_rate'])} and {r1(st['p_rate'])}" if st and st.get("v_rate") else "") + (f"; US {r1(nat['v_rate'])} and {r1(nat['p_rate'])}." if nat.get("v_rate") else "."))
        elif st and st.get("v_rate") is not None:
            lines.append(f"{st['name']} ({st['year']}, FBI): violent crime {r1(st['v_rate'])} and property crime {r1(st['p_rate'])} per 100,000" + (f" (US {r1(nat['v_rate'])} and {r1(nat['p_rate'])})." if nat.get("v_rate") else "."))
        return {"label": d["place"]["label"], "url": url, "lines": lines, "source": "Police open data and FBI Crime Data Explorer"} if lines else None
    except Exception:
        return None

ALERT_KM = 5.0          # within 5 km of the subscriber's area centre (their stored location is itself rounded to ~10 km)
ALERT_KM_CITY = 8       # city-level locations are geocoded to the city centre, so allow a slightly wider radius
ALERT_MAX_AGE_H = 24    # the incident must have occurred within the last 24 hours (most feeds lag more than that, so alerts are rare)
def alert_candidates(sub, now_ts=None, exclude=()):
    """Serious violent reports (homicide, shooting, robbery, aggravated assault, kidnapping) near a ZIP/city subscriber, newest first."""
    if not sub or sub.get("loc_lat") is None or sub.get("loc_kind") not in ("zip", "city") or sub.get("loc_cc") != "US": return []
    now_ts = now_ts or time.time(); la, lo = sub["loc_lat"], sub["loc_lon"]
    f = feed_for(la, lo)
    if not f: return []
    out = []
    for r in qa("SELECT id, feed, ts_utc, local, glat, glon, cat FROM serious WHERE feed=? AND ts_utc>=? ORDER BY ts_utc DESC LIMIT 200", (f["id"], int(now_ts - ALERT_MAX_AGE_H * 3600))):
        if r["id"] in exclude: continue
        d = _km(la, lo, r["glat"], r["glon"])
        if d <= (ALERT_KM if sub.get("loc_kind") == "zip" else ALERT_KM_CITY): out.append({**dict(r), "km": round(d, 1), "city": f["city"], "tz": f["tz"], "source": f["source"], "src_url": f["url"]})
    return out[:5]

# ------------------------------------------------------------------------------------------------ JSON APIs
def heat(feed):
    def f():
        cells = [[r[0], r[1], r[2], r[3], r[4]] for r in qa("SELECT glat, glon, v, p, o FROM grid WHERE feed=?", (feed,))]
        ser = [[r[0], r[1], r[2], r[3]] for r in qa("SELECT glat, glon, cat, local FROM serious WHERE feed=? ORDER BY ts_utc DESC LIMIT 400", (feed,))]
        fd = next((x for x in feeds() if x["id"] == feed), None)
        return {"feed": feed, "cells": cells, "serious": ser, "bbox": (fd or {}).get("bbox"), "city": (fd or {}).get("city")}
    return cached("heat:" + feed, f)
def counties_json():
    return cached("counties", lambda: {r["fips"]: [r["v_rate"], r["p_rate"], r["year"], r["coverage"], r["name"], r["st"]]
                                       for r in qa("SELECT fips, v_rate, p_rate, year, coverage, name, st FROM counties WHERE v_rate IS NOT NULL")})
def global_json():
    return cached("global", lambda: [[r["num"], r["iso3"], r["name"], r["rate"], r["year"]] for r in qa("SELECT num, iso3, name, rate, year FROM countries ORDER BY rate DESC")])
def feeds_json():
    return [{k: f.get(k) for k in ("id", "city", "st", "newest", "window_start", "window_end", "n_window", "n_prev", "lag", "source", "url", "license", "last_ok")} for f in feeds()]

# ------------------------------------------------------------------------------------------------ page
TILE = ('<svg class="cr-tile" viewBox="0 0 1024 1024" aria-hidden="true"><rect x="8" y="8" width="1008" height="1008" rx="192" fill="#0B0D10" stroke="#2f3742" stroke-width="16"/><path fill="#FFFFFF" d="M527.26 681.57V342.43H606.23L755.93 523.16V342.43H849.92V681.57H770.95L621.25 500.84V681.57ZM279.21 681.57V612.29H349.46Q374.17 612.29 387.01 603.81Q399.84 595.33 399.84 577.89Q399.84 560.45 387.01 551.97Q374.17 543.49 349.46 543.49H279.21V477.12H334.93Q359.15 477.12 371.26 468.88Q383.37 460.65 383.37 444.17Q383.37 427.7 371.26 419.71Q359.15 411.71 334.93 411.71H279.21V342.43H347.52Q414.38 342.43 447.32 366.9Q480.27 391.37 480.27 431.09Q480.27 457.25 466.46 476.88Q454.56 493.79 434.38 504.58Q437.52 505.68 440.54 506.91Q467.19 517.81 481.96 538.4Q496.74 558.99 496.74 588.55Q496.74 632.63 461.13 657.1Q425.52 681.57 357.21 681.57Z"/><path fill="#C8102E" d="M180.86 342.43H262.25C266 342.43 269.04 345.47 269.04 349.22V392.63C269.04 396.37 266 399.41 262.25 399.41H180.86C177.12 399.41 174.08 396.37 174.08 392.63V349.22C174.08 345.47 177.12 342.43 180.86 342.43Z"/><path fill="#FFC21A" d="M180.86 483.51H262.25C266 483.51 269.04 486.55 269.04 490.3V533.7C269.04 537.45 266 540.49 262.25 540.49H180.86C177.12 540.49 174.08 537.45 174.08 533.7V490.3C174.08 486.55 177.12 483.51 180.86 483.51ZM180.86 412.97H262.25C266 412.97 269.04 416.01 269.04 419.76V463.17C269.04 466.91 266 469.95 262.25 469.95H180.86C177.12 469.95 174.08 466.91 174.08 463.17V419.76C174.08 416.01 177.12 412.97 180.86 412.97Z"/><path fill="#3FAE80" d="M180.86 624.59H262.25C266 624.59 269.04 627.63 269.04 631.37V674.78C269.04 678.53 266 681.57 262.25 681.57H180.86C177.12 681.57 174.08 678.53 174.08 674.78V631.37C174.08 627.63 177.12 624.59 180.86 624.59ZM180.86 554.05H262.25C266 554.05 269.04 557.09 269.04 560.83V604.24C269.04 607.99 266 611.03 262.25 611.03H180.86C177.12 611.03 174.08 607.99 174.08 604.24V560.83C174.08 557.09 177.12 554.05 180.86 554.05Z"/></svg>')   # logo V2-final tile (Nov 1 2026)

def _file(name):
    p = os.path.join(STATIC, os.path.basename(name))
    if not os.path.isfile(p): return 404, {"error": "not found"}
    ct = {"js": "application/javascript", "css": "text/css", "json": "application/json"}.get(name.rsplit(".", 1)[-1], "application/octet-stream")
    with open(p, "rb") as fh: return 200, fh.read(), ct

def render_page(q=""):
    fs = feeds(); nat = national() or {}; d = None
    if q: d = lookup(q)
    fm = meta("fbi_meta"); cm = meta("countries_meta")
    newest = max((x["newest"] for x in fs), default=None)
    hero = (f'<section class="cr-hero"><div class="cr-row">{TILE}<div class="cr-ht"><div class="cr-live"><i></i>BLACKOUT.NETWORK · CRIME DATA</div>'
            '<h1>Crime near you, <em>in real numbers</em></h1>'
            '<p>Type a US ZIP code, city, county or state, or any country. You get official rates per 100,000 people, how they compare and how they are trending, '
            'plus a live heat map of recent police reports where the city publishes them.</p></div></div>'
            f'<form class="cr-search" action="/crime" method="get" role="search"><label for="cr-q" class="cr-vh">Place</label>'
            f'<input id="cr-q" name="place" type="search" value="{E(q)}" maxlength="80" autocomplete="off" placeholder="ZIP, city, county, state or country" enterkeyhint="search">'
            '<button type="submit">Look up</button></form>'
            '<div class="cr-chips">' + "".join(f'<a class="cr-chip" href="/crime?place={urllib.parse.quote(x)}" data-q="{E(x)}">{E(x)}</a>' for x in
                                                ("60614", "Chicago, IL", "Seminole County, FL", "Philadelphia", "Florida", "Canada")) + '</div>'
            f'<div class="cr-stats"><span><b>{len(fs)}</b> cities with near-real-time maps</span><span><b>{n(q1("SELECT COUNT(*) FROM counties WHERE year IS NOT NULL")[0] if _db() else 0)}</b> US counties with FBI rates</span>'
            f'<span><b>{n(q1("SELECT COUNT(*) FROM countries")[0] if _db() else 0)}</b> countries</span>'
            + (f'<span>Newest police report: <b>{E(dfmt(newest, "%b %-d"))}</b></span>' if newest else "") + '</div></section>')
    if d and d.get("ok"): res = d["html"]
    elif d: res = f'<div class="cr-empty">{E(d["message"])}</div>'
    else: res = (lookup("United States") or {}).get("html", "") if _db() else '<div class="cr-empty">Crime data is syncing. Please check back in a few minutes.</div>'
    result = f'<section class="cr-result" id="cr-result" aria-live="polite">{res}</section>'
    cards = "".join(f'<a class="cr-city" href="/crime?place={urllib.parse.quote(x["city"] + ", " + x["st"])}" data-q="{E(x["city"] + ", " + x["st"])}">'
                    f'<b>{E(x["city"])}, {E(x["st"])}</b><span>{n(x["n_window"])} reports · 30 days</span>'
                    f'<small>Through {E(dfmt(x["window_end"], "%b %-d"))} · lag {E(x["lag"].split(" (")[0])}</small>{chg_html(chg(x["n_window"], x["n_prev"]), "vs. prior 30 days")}</a>' for x in fs)
    cities = ('<div class="cr-sec"><h2>Cities with near-real-time police data</h2><span class="cr-mu">Updated every 30 minutes from each city\'s official open-data portal. '
              'Everywhere else falls back to the latest official FBI statistics.</span></div>' f'<div class="cr-cities">{cards}</div>')
    usmap = ('<div class="cr-sec"><h2>US counties: violent crime per 100,000</h2><span class="cr-mu">Latest full year each county\'s agencies reported to the FBI. '
             'Grey means no recent complete data (often an agency still moving to NIBRS). Tap a county for details.</span></div>'
             '<div class="cr-mapwrap"><div class="cr-map tall" id="cr-us" role="img" aria-label="Map of US counties shaded by violent crime rate"></div>'
             f'<div class="cr-scale"><span>Lower</span><i class="cr-grad"></i><span>Higher</span></div></div>')
    top = qa("SELECT name, rate, year FROM countries WHERE year>=2018 ORDER BY rate DESC LIMIT 10"); low = qa("SELECT name, rate, year FROM countries WHERE year>=2018 ORDER BY rate ASC LIMIT 10")
    tl = lambda rows: "".join(f'<li><a href="/crime?place={urllib.parse.quote(r["name"])}" data-q="{E(r["name"])}">{E(r["name"])}</a><b>{r1(r["rate"])}</b><small>{r["year"]}</small></li>' for r in rows)
    world = ('<div class="cr-sec"><h2>World: intentional homicides per 100,000</h2><span class="cr-mu">Latest official year per country (UNODC via World Bank). '
             'Homicide is the most comparable crime measure across borders.</span></div>'
             '<div class="cr-mapwrap"><div class="cr-map tall" id="cr-world" role="img" aria-label="World map of countries shaded by homicide rate"></div>'
             f'<div class="cr-scale"><span>0</span><i class="cr-grad"></i><span>30+</span></div></div>'
             f'<div class="cr-grid2"><div class="cr-card"><h3>Highest rates (2018 or later)</h3><ol class="cr-rank">{tl(top)}</ol></div>'
             f'<div class="cr-card"><h3>Lowest rates (2018 or later)</h3><ol class="cr-rank">{tl(low)}</ol></div></div>')
    nl = ('<section class="cr-cta"><div><div class="cr-kick">FREE · 7 AM &amp; 7 PM ET</div><h2>Get your area\'s crime numbers in the brief</h2>'
          '<p>Add your ZIP, city or country, then tick <b>Include local crime summary in my briefs</b> and, if you want them, '
          '<b>Real-time crime alerts for my area</b>. Both start off and you can change them any time in Manage preferences. Nothing is sent until you confirm by email.</p></div>'
          '<div class="bng-inline-slot" data-src="crime"><a class="cr-btn red" href="/newsletter?utm_source=crime&amp;utm_medium=cta&amp;utm_campaign=crime">✉ Get the free brief</a></div>'
          '<p class="cr-mu">Follow us on YouTube and X too. Links are at the top of every page on blackout.network.</p></section>')
    how = ('<section class="cr-card cr-how"><h3>How this works, and what we never show</h3><ul>'
           '<li><b>Official rates</b> come from the FBI Crime Data Explorer (UCR/NIBRS): offenses reported by city police and sheriffs, divided by the population those agencies cover. '
           'County figures add up every reporting agency in the county; when they cover less than 60% of residents we say so. The FBI publishes monthly data about 1 to 3 months behind.</li>'
           '<li><b>Near-real-time maps</b> use each city\'s own open-data incident feed, checked every 30 minutes. Most cities publish with a lag of 1 to 7 days, New York quarterly; '
           'every map shows its exact data window.</li>'
           '<li><b>Privacy:</b> we keep only the category, the hour and a location rounded to a block-sized (~200 m) grid. No names, case numbers, addresses, or victim or suspect details are collected or shown, '
           'and we never show demographic breakdowns.</li>'
           '<li><b>Context:</b> reports are not convictions, cities define offenses differently, and a busy downtown or tourist area shows more reports because more people are there. '
           'Use these numbers to stay informed, not to judge a neighborhood or its residents.</li>'
           f'<li><b>Sources:</b> {_src("FBI Crime Data Explorer", FBI_URL)} (public domain) · {_src("UNODC homicide data via World Bank", WB_URL)} (CC BY 4.0) · '
           'US Census ZIP-to-county and population files (public domain) · city portals listed on each map. Map tiles: '
           f'{_src("OpenFreeMap", "https://openfreemap.org/")} © {_src("OpenMapTiles", "https://www.openmaptiles.org/")} data © {_src("OpenStreetMap contributors", "https://www.openstreetmap.org/copyright")}. '
           f'FBI data last refreshed {E(_ago(fm.get("fetched")))}; homicide data updated by the World Bank {E(cm.get("lastupdated") or "")}.</li>'
           '<li>Research only: BLACKOUT.NETWORK is not a police or emergency service. In an emergency call 911 (or your local number).</li></ul></section>')
    body = f'<main class="cr" id="main">{hero}{result}{cities}{usmap}{world}{nl}{how}</main>'
    foot = ('<footer class="cr-foot">BLACKOUT.NETWORK · <a href="/">The Wire</a> · <a href="/#weather">Weather</a> · <a href="/#preppers">Preppers</a> · '
            '<a href="/newsletter">Newsletter</a> · <a href="/sources">Sources</a> · <a href="/privacy">Privacy</a> · <a href="/tos">Terms</a></footer>')
    path = "/crime" + (f"?place={urllib.parse.quote(q)}" if q else "")
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "WebPage", "@id": f"{SITE}/crime#page", "url": f"{SITE}/crime", "name": TITLE, "description": DESC, "inLanguage": "en-US",
         "isPartOf": {"@type": "WebSite", "@id": f"{SITE}/#website", "url": SITE, "name": BRAND}, "about": [{"@type": "Thing", "name": "Crime statistics"}, {"@type": "Thing", "name": "Public safety"}],
         "breadcrumb": {"@id": f"{SITE}/crime#crumbs"}, "publisher": {"@id": f"{SITE}/#org"}},
        {"@type": "Organization", "@id": f"{SITE}/#org", "name": BRAND, "url": SITE, "logo": f"{SITE}/icons/icon-512.png", "email": "hello@blackout.network",
         "sameAs": ["https://x.com/BlkoutNtw", "https://www.youtube.com/@blkoutntw"]},
        {"@type": "BreadcrumbList", "@id": f"{SITE}/crime#crumbs", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": BRAND, "item": SITE + "/"}, {"@type": "ListItem", "position": 2, "name": "Crime", "item": f"{SITE}/crime"}]},
        {"@type": "Dataset", "name": "BLACKOUT.NETWORK crime statistics by US ZIP, city, county, state and country", "description": DESC, "url": f"{SITE}/crime",
         "creator": {"@id": f"{SITE}/#org"}, "isAccessibleForFree": True, "spatialCoverage": "United States; worldwide (homicide)",
         "isBasedOn": [FBI_URL, WB_URL] + [x["url"] for x in fs], "variableMeasured": ["Violent crime rate per 100,000", "Property crime rate per 100,000", "Intentional homicide rate per 100,000", "Reported incidents (30 days)"],
         "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": f"{SITE}/api/crime/global"},
                          {"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": f"{SITE}/api/crime/counties"}]}]}
    title = TITLE if not (d and d.get("ok")) else f"Crime in {d['place']['label']}: rates, trends and map | {BRAND}"
    head = (sitenav.head_html("crime", path) + '<meta name="robots" content="index,follow,max-image-preview:large">'
            '<meta name="keywords" content="crime map, crime rate by ZIP code, crime statistics, county crime rate, violent crime rate, property crime, crime near me, homicide rate by country, FBI crime data">'
            '<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False).replace("</", "<\\/") + '</script>'
            '<link rel="stylesheet" href="/api/crime/app.css">')
    if title != TITLE: head = head.replace(f"<title>{E(TITLE)}</title>", f"<title>{E(title)}</title>", 1)
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' + head +
            '<link rel="stylesheet" href="/theme.css"><link rel="icon" href="/favicon.ico" sizes="any">'
            '<style>body{margin:0;background:var(--bn-bg,#0B0D10);overflow-x:hidden}</style></head><body><a class="skip bn-skip" href="#main" style="position:absolute;left:-999px">Skip to content</a>'
            + sitenav.header_html("@crime") + body + foot + '<script src="/api/crime/app.js" defer></script></body></html>').encode("utf-8")

def handle_get(path, qs):
    qs = qs or {}
    g = lambda k: ((qs.get(k) or [""])[0] if isinstance(qs.get(k), list) else (qs.get(k) or ""))
    if path in ("/crime", "/crime/"): return 200, render_page((g("place") or g("q")).strip()[:80]), "text/html"
    if path == "/api/crime/search":
        d = lookup(g("q"))
        return (200 if d.get("ok") else 404), d
    if path == "/api/crime/heat":
        fid = re.sub(r"[^a-z]", "", g("feed"))[:8]
        return 200, heat(fid)
    if path == "/api/crime/counties": return 200, counties_json()
    if path == "/api/crime/global": return 200, global_json()
    if path == "/api/crime/feeds": return 200, feeds_json()
    if path == "/api/crime/app.js": return _file("app.js")
    if path == "/api/crime/app.css": return _file("app.css")
    if path.startswith("/api/crime/static/"): return _file(path.rsplit("/", 1)[-1])
    return 404, {"error": "not found"}
