#!/usr/bin/env python3
"""Crime tab collector (t392, Nov 1 2026). BOX ONLY: builds crime.db, which render_sync pushes to the public node like every other *.db.
Render never calls these sources; it only reads crime.db (crime.py).

  python3 crime_collect.py static     # ZIP->county, county names/populations, World Bank homicide rates (once, and monthly)
  python3 crime_collect.py states     # FBI CDE state + national offense series (8 offense types + violent/property)
  python3 crime_collect.py agencies [ST ...]   # FBI CDE agency (city police / sheriff) violent + property series -> counties
  python3 crime_collect.py live       # near-real-time city open-data incident feeds -> 30-day grid + recent serious incidents
  python3 crime_collect.py loop       # live every 30 min, states daily, agencies weekly (resumable crawl)
  python3 crime_collect.py status

Privacy: incidents are reduced to (category, local hour, location snapped to a ~200 m grid). No names, case numbers, addresses,
victim or suspect details are requested ($select) or stored. Only a salted hash of the source record id is kept, to dedupe updates.
Sources, licenses and latency: /workspace/launch/crime/SOURCES.md and the /crime page credits. Never touches scanner.py, scoring,
push.py, jets.py, aviation_watch.py or config.json."""
import os, sys, json, time, re, sqlite3, hashlib, math, csv, threading, urllib.request, urllib.parse, urllib.error, traceback
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("BN_CRIME_DB", "/workspace/blackout/crime.db")
WORK = os.environ.get("BN_CRIME_WORK", "/workspace/blackout/crime_work")     # box-only raw store (not a top-level *.db, so never synced)
RAW_DIR = os.environ.get("BN_CRIME_RAW", "/workspace/launch/crime/raw")
UA = "BLACKOUT.NETWORK (+https://blackout.network; hello@blackout.network)"   # Boston CKAN returns 502 for UAs containing "collector"
CDE = "https://cde.ucr.cjis.gov/LATEST"          # same API paths as api.usa.gov/crime/fbi/cde (that gateway returned 503 during vetting)
GRID = 0.002                                      # ~220 m north-south; snaps every incident to a block-sized cell
os.makedirs(WORK, exist_ok=True)

def log(*a): print(time.strftime("%H:%M:%S"), *a, flush=True)

def get(url, timeout=45, tries=3, raw=False):
    last = None
    for i in range(tries):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"}), timeout=timeout)
            b = r.read()
            return b if raw else json.loads(b)
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (400, 401, 403, 404): break
        except Exception as e: last = e
        time.sleep(2 + 3 * i)
    raise RuntimeError(f"GET failed {url[:120]}: {last}")

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS zips(zip TEXT PRIMARY KEY, fips TEXT);
CREATE TABLE IF NOT EXISTS counties(fips TEXT PRIMARY KEY, name TEXT, state TEXT, st TEXT, pop INTEGER, lat REAL, lon REAL,
  year INTEGER, violent INTEGER, property INTEGER, cov_pop INTEGER, v_rate REAL, p_rate REAL, coverage REAL, n_agencies INTEGER, n_reporting INTEGER,
  series TEXT, ytd TEXT, updated TEXT);
CREATE TABLE IF NOT EXISTS states(st TEXT PRIMARY KEY, name TEXT, fips TEXT, series TEXT, cats TEXT, latest INTEGER, updated TEXT);
CREATE TABLE IF NOT EXISTS agencies(ori TEXT PRIMARY KEY, name TEXT, type TEXT, st TEXT, county TEXT, fips TEXT, lat REAL, lon REAL,
  pop INTEGER, series TEXT, ytd TEXT, latest INTEGER, v_rate REAL, p_rate REAL, fetched TEXT, status TEXT);
CREATE INDEX IF NOT EXISTS ag_fips ON agencies(fips);
CREATE INDEX IF NOT EXISTS ag_st ON agencies(st, name);
CREATE TABLE IF NOT EXISTS countries(iso3 TEXT PRIMARY KEY, iso2 TEXT, num TEXT, name TEXT, year INTEGER, rate REAL, series TEXT);
CREATE TABLE IF NOT EXISTS feeds(id TEXT PRIMARY KEY, city TEXT, st TEXT, tz TEXT, lat REAL, lon REAL, bbox TEXT, source TEXT, url TEXT, api TEXT,
  license TEXT, lag TEXT, newest TEXT, window_start TEXT, window_end TEXT, n_window INTEGER, n_prev INTEGER, cats TEXT, daily TEXT, last_ok TEXT, last_error TEXT);
CREATE TABLE IF NOT EXISTS grid(feed TEXT, glat REAL, glon REAL, v INTEGER, p INTEGER, o INTEGER);
CREATE INDEX IF NOT EXISTS grid_f ON grid(feed);
CREATE TABLE IF NOT EXISTS serious(id TEXT PRIMARY KEY, feed TEXT, ts_utc INTEGER, local TEXT, glat REAL, glon REAL, cat TEXT);
CREATE INDEX IF NOT EXISTS ser_f ON serious(feed, ts_utc);
"""
def out_db():
    c = sqlite3.connect(OUT, timeout=30, check_same_thread=False); c.executescript(SCHEMA); c.execute("PRAGMA journal_mode=DELETE"); return c
def setmeta(c, k, v): c.execute("INSERT OR REPLACE INTO meta(k,v) VALUES(?,?)", (k, json.dumps(v)))
def now_iso(): return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

ST_FIPS = {"01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT", "10": "DE", "11": "DC", "12": "FL", "13": "GA", "15": "HI",
           "16": "ID", "17": "IL", "18": "IN", "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME", "24": "MD", "25": "MA", "26": "MI", "27": "MN",
           "28": "MS", "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH", "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND", "39": "OH",
           "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA",
           "54": "WV", "55": "WI", "56": "WY", "72": "PR"}
ST_NAME = {}

# ------------------------------------------------------------------------------------------------ static: ZIPs, counties, countries
def _topo_centroids(path, obj):
    """Rough centroid (mean of decoded arc vertices) per TopoJSON geometry id."""
    t = json.load(open(path)); sc, tr = t["transform"]["scale"], t["transform"]["translate"]
    arcs = []
    for a in t["arcs"]:
        x = y = 0; pts = []
        for dx, dy in a: x += dx; y += dy; pts.append((x * sc[0] + tr[0], y * sc[1] + tr[1]))
        arcs.append(pts)
    out = {}
    for g in t["objects"][obj]["geometries"]:
        polys = g.get("arcs") or []
        if g["type"] == "Polygon": polys = [polys]
        best = None
        for poly in polys:
            ring = poly[0] if poly else []
            pts = [p for i in ring for p in arcs[i if i >= 0 else ~i]]
            if pts and (best is None or len(pts) > len(best)): best = pts
        if best: out[str(g.get("id"))] = (round(sum(p[1] for p in best) / len(best), 3), round(sum(p[0] for p in best) / len(best), 3))
    return out

def build_static():
    c = out_db()
    # ZIP (ZCTA) -> county with the largest land overlap (Census 2020 relationship file, public domain)
    best = {}
    with open(os.path.join(RAW_DIR, "zcta_county.txt"), encoding="utf-8-sig") as f:
        for row in csv.DictReader(f, delimiter="|"):
            z = row["GEOID_ZCTA5_20"]; fp = row["GEOID_COUNTY_20"]
            if not z or not fp: continue
            a = int(row["AREALAND_PART"] or 0)
            if z not in best or a > best[z][1]: best[z] = (fp, a)
    c.execute("DELETE FROM zips"); c.executemany("INSERT INTO zips VALUES(?,?)", [(z, v[0]) for z, v in best.items()])
    # counties: names + 2024 population (Census Vintage 2024, public domain); centroids from us-atlas geometry
    cen = _topo_centroids(os.path.join(RAW_DIR, "counties-10m.json"), "counties")
    with open(os.path.join(RAW_DIR, "co-est2024.csv"), encoding="latin-1") as f:
        for row in csv.DictReader(f):
            st = ST_FIPS.get(row["STATE"])
            if not st: continue
            if row["SUMLEV"] == "040": ST_NAME[st] = row["STNAME"]; continue
            fp = row["STATE"] + row["COUNTY"]; la, lo = cen.get(fp, (None, None))
            c.execute("""INSERT INTO counties(fips,name,state,st,pop,lat,lon) VALUES(?,?,?,?,?,?,?)
                         ON CONFLICT(fips) DO UPDATE SET name=excluded.name, state=excluded.state, st=excluded.st, pop=excluded.pop, lat=excluded.lat, lon=excluded.lon""",
                      (fp, row["CTYNAME"], row["STNAME"], st, int(row["POPESTIMATE2024"] or 0), la, lo))
    setmeta(c, "state_names", ST_NAME)
    # countries: World Bank WDI VC.IHR.PSRC.P5 (UNODC source), CC BY 4.0
    num = {}
    for ln in open("/workspace/geodata/countryInfo.txt", encoding="utf-8"):
        if ln.startswith("#"): continue
        p = ln.rstrip("\n").split("\t")
        if len(p) > 4: num[p[1]] = (p[0], p[2], p[4])
    d = get("https://api.worldbank.org/v2/country/all/indicator/VC.IHR.PSRC.P5?format=json&per_page=20000&date=2005:2026", timeout=90)
    ser = {}
    for r in d[1] or []:
        if r.get("value") is None or not r.get("countryiso3code") or r["countryiso3code"] not in num: continue
        ser.setdefault(r["countryiso3code"], {})[int(r["date"])] = round(float(r["value"]), 2)
    c.execute("DELETE FROM countries")
    for iso3, s in ser.items():
        y = max(s); i2, nm, name = num[iso3]
        c.execute("INSERT INTO countries VALUES(?,?,?,?,?,?,?)", (iso3, i2, nm, name, y, s[y], json.dumps({str(k): s[k] for k in sorted(s)})))
    setmeta(c, "countries_meta", {"source": "UNODC via World Bank WDI (VC.IHR.PSRC.P5)", "license": "CC BY 4.0", "lastupdated": d[0].get("lastupdated"),
                                  "fetched": now_iso(), "n": len(ser)})
    c.commit(); log(f"static: {len(best)} zips, counties, {len(ser)} countries"); c.close()

# ------------------------------------------------------------------------------------------------ FBI CDE helpers
OFFENSES = ["homicide", "rape", "robbery", "aggravated-assault", "burglary", "larceny", "motor-vehicle-theft", "arson"]
def _months(d):
    return {k: v for k, v in (d or {}).items() if re.fullmatch(r"\d\d-\d{4}", k)}
def _yearly(actual, pop):
    """monthly dicts -> {year: [count, months_reported, population]}; a month counts as reported when a value is present."""
    out = {}
    for k, v in _months(actual).items():
        m, y = k.split("-"); y = int(y)
        o = out.setdefault(y, [0, 0, 0])
        if v is not None: o[0] += v; o[1] += 1
    for k, v in _months(pop).items():
        y = int(k.split("-")[1])
        if y in out and v: out[y][2] = max(out[y][2], int(v))
    return out
def _key(d, suffix, exclude=()):
    for k in d or {}:
        if k.endswith(suffix) and not any(k.startswith(x) for x in exclude): return k
    return None
def cde_summary(kind, ident, offense, y0, y1):
    return get(f"{CDE}/summarized/{kind}/{ident}/{offense}?from=01-{y0}&to=12-{y1}", timeout=60)

def build_states():
    c = out_db(); y1 = datetime.now().year; y0 = 2019
    names = json.loads((c.execute("SELECT v FROM meta WHERE k='state_names'").fetchone() or ["{}"])[0])
    nat = {}
    for st in sorted(set(ST_FIPS.values()) - {"PR"}):
        sname = names.get(st, st); series = {}; cats = {}
        for off in ["violent-crime", "property-crime"] + OFFENSES:
            try: d = cde_summary("state", st, off, y0, y1)
            except Exception as e: log("state", st, off, e); continue
            act = d.get("offenses", {}).get("actuals", {}); pops = d.get("populations", {})
            k = _key(act, " Offenses", ("United States",))
            yr = _yearly(act.get(k), (pops.get("participated_population") or {}).get(k.replace(" Offenses", "")) if k else None)
            tot = _yearly(act.get(k), (pops.get("population") or {}).get(k.replace(" Offenses", "")) if k else None)
            for y, v in yr.items():
                series.setdefault(str(y), {})[off] = v[0]; series[str(y)]["months"] = max(series[str(y)].get("months", 0), v[1])
                series[str(y)]["cov_pop"] = v[2]; series[str(y)]["pop"] = (tot.get(y) or [0, 0, 0])[2]
            time.sleep(0.3)
        full = [int(y) for y, v in series.items() if v.get("months", 0) >= 12 and v.get("violent-crime") is not None]
        latest = max(full) if full else None
        c.execute("INSERT OR REPLACE INTO states VALUES(?,?,?,?,?,?,?)", (st, sname, next((f for f, s in ST_FIPS.items() if s == st), ""),
                  json.dumps(series), json.dumps({o: series.get(str(latest), {}).get(o) for o in OFFENSES}) if latest else "{}", latest, now_iso()))
        c.commit(); log("state", st, "latest", latest)
    build_national(c); c.close()

def build_national(c=None):
    """US totals from /summarized/national/{offense} (the state endpoint carries only US populations, not US offenses)."""
    own = c is None; c = c or out_db(); y1 = datetime.now().year; y0 = 2019; nat = {}
    for off in ["violent-crime", "property-crime"] + OFFENSES:
        try: d = get(f"{CDE}/summarized/national/{off}?from=01-{y0}&to=12-{y1}", timeout=60)
        except Exception as e: log("national", off, e); continue
        act = d.get("offenses", {}).get("actuals", {}); pops = d.get("populations", {})
        us = _yearly(act.get("United States Offenses"), (pops.get("participated_population") or {}).get("United States"))
        ust = _yearly(act.get("United States Offenses"), (pops.get("population") or {}).get("United States"))
        nat[off] = {str(y): [v[0], v[1], v[2], (ust.get(y) or [0, 0, 0])[2]] for y, v in us.items()}
        time.sleep(0.3)
    if not nat.get("violent-crime"):
        log("national: no data, keeping the previous US row")
        if own: c.close()
        return
    series = {}
    for off, d in nat.items():
        for y, (n, m, cp, p) in d.items():
            s = series.setdefault(y, {}); s[off] = n; s["months"] = max(s.get("months", 0), m); s["cov_pop"] = cp; s["pop"] = p
    full = [int(y) for y, v in series.items() if v.get("months", 0) >= 12]
    latest = max(full) if full else None
    c.execute("INSERT OR REPLACE INTO states VALUES(?,?,?,?,?,?,?)", ("US", "United States", "00", json.dumps(series),
              json.dumps({o: series.get(str(latest), {}).get(o) for o in OFFENSES}) if latest else "{}", latest, now_iso()))
    setmeta(c, "fbi_meta", {"source": "FBI Crime Data Explorer (UCR/NIBRS)", "api": CDE, "fetched": now_iso()})
    c.commit(); log("national latest", latest)
    if own: c.close()

def _norm_county(s):
    s = re.sub(r"[^A-Z ]", "", (s or "").upper().replace("SAINT", "ST").replace("ST.", "ST"))
    return re.sub(r"\s+(COUNTY|PARISH|BOROUGH|CENSUS AREA|MUNICIPALITY|CITY AND BOROUGH|CITY)$", "", s.strip()).strip()

def _agency_one(a, y0, y1):
    res = {}
    for off in ("violent-crime", "property-crime"):
        d = cde_summary("agency", a["ori"], off, y0, y1)
        act = d.get("offenses", {}).get("actuals", {}); pops = (d.get("populations") or {}).get("population") or {}
        k = _key(act, " Offenses", ("United States", ST_NAME.get(a["state_abbr"], "~~"), a.get("state_name") or "~~"))
        if not k: res[off] = {}; continue
        res[off] = _yearly(act.get(k), pops.get(k.replace(" Offenses", "")))
        res["_monthly_" + off] = _months(act.get(k))
        time.sleep(0.15)
    return res

def build_agencies(states=None, max_age_days=6, workers=3):
    c = out_db(); y1 = datetime.now().year; y0 = y1 - 5
    names = json.loads((c.execute("SELECT v FROM meta WHERE k='state_names'").fetchone() or ["{}"])[0]); ST_NAME.update(names)
    cmap = {}
    for fp, nm, st in c.execute("SELECT fips, name, st FROM counties"): cmap[(st, _norm_county(nm))] = fp
    states = states or sorted(set(ST_FIPS.values()) - {"PR"})
    lock = threading.Lock(); done = [0]
    cut = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for st in states:
        try: lst = get(f"{CDE}/agency/byStateAbbr/{st}", timeout=90)
        except Exception as e: log("agency list", st, e); continue
        todo = []
        for county, ags in lst.items():
            for a in ags:
                if a.get("agency_type_name") not in ("City", "County"): continue
                row = c.execute("SELECT fetched FROM agencies WHERE ori=?", (a["ori"],)).fetchone()
                if row and row[0] and row[0] >= cut: continue
                first = (a.get("counties") or county or "").split(",")[0]
                a["_fips"] = cmap.get((st, _norm_county(first))); todo.append(a)
        log(f"agencies {st}: {len(todo)} to fetch")
        def work(a):
            try: r = _agency_one(a, y0, y1); status = "ok"
            except Exception as e: r = {}; status = f"error: {str(e)[:120]}"
            vy, py_ = r.get("violent-crime", {}), r.get("property-crime", {})
            series = {}
            for y in sorted(set(vy) | set(py_)):
                v = vy.get(y, [0, 0, 0]); p = py_.get(y, [0, 0, 0])
                series[str(y)] = {"v": v[0], "p": p[0], "m": min(v[1], p[1]) if (y in vy and y in py_) else 0, "pop": max(v[2], p[2])}
            full = [int(y) for y, s in series.items() if s["m"] >= 10 and int(y) < y1 and s["pop"]]
            latest = max(full) if full else None
            vr = pr = None; pop = series.get(str(latest), {}).get("pop") if latest else None
            if latest and pop:
                s = series[str(latest)]; k12 = 12 / s["m"]
                vr = round(s["v"] * k12 / pop * 1e5, 1); pr = round(s["p"] * k12 / pop * 1e5, 1)
            # year-to-date: same months this year vs last year, only months present in both
            ytd = None; mv, mp = r.get("_monthly_violent-crime") or {}, r.get("_monthly_property-crime") or {}
            ms = [m for m in range(1, 13) if mv.get(f"{m:02d}-{y1}") is not None and mv.get(f"{m:02d}-{y1-1}") is not None and m != 12]
            if len(ms) >= 3:
                ytd = {"months": ms[-1], "n": len(ms), "v": sum(mv[f"{m:02d}-{y1}"] for m in ms), "v_prev": sum(mv[f"{m:02d}-{y1-1}"] for m in ms),
                       "p": sum((mp.get(f"{m:02d}-{y1}") or 0) for m in ms), "p_prev": sum((mp.get(f"{m:02d}-{y1-1}") or 0) for m in ms)}
            with lock:
                c.execute("INSERT OR REPLACE INTO agencies VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                          (a["ori"], a["agency_name"], a["agency_type_name"], st, (a.get("counties") or ""), a.get("_fips"), a.get("latitude"), a.get("longitude"),
                           pop, json.dumps(series), json.dumps(ytd) if ytd else None, latest, vr, pr, now_iso(), status))
                done[0] += 1; c.commit()     # commit each row: the live-feed job writes the same file and must not wait on a long transaction
                if done[0] % 50 == 0: log(f"  {done[0]} agencies done")
        with ThreadPoolExecutor(workers) as ex: list(ex.map(work, todo))
        c.commit(); aggregate_counties(c, st)
    c.close()

def aggregate_counties(c, st=None):
    y1 = datetime.now().year
    q = "SELECT fips, pop FROM counties" + (" WHERE st=?" if st else ""); args = (st,) if st else ()
    for fp, cpop in c.execute(q, args).fetchall():
        ags = c.execute("SELECT name, series, ytd, pop FROM agencies WHERE fips=? AND status='ok'", (fp,)).fetchall()
        if not ags: continue
        per = {}
        for nm, s, ytd, pop in ags:
            for y, v in json.loads(s or "{}").items():
                if v["m"] >= 10 and v["pop"]:
                    k12 = 12 / v["m"]; o = per.setdefault(y, [0, 0, 0, 0])
                    o[0] += v["v"] * k12; o[1] += v["p"] * k12; o[2] += v["pop"]; o[3] += 1
        series = {y: {"v": round(o[0]), "p": round(o[1]), "cov_pop": o[2], "n": o[3]} for y, o in sorted(per.items()) if int(y) < y1}
        cand = [int(y) for y, o in series.items() if cpop and o["cov_pop"] >= 0.6 * cpop] or [int(y) for y in series]
        latest = max(cand) if cand else None
        yt = [json.loads(x[2]) for x in ags if x[2]]
        ytd = None
        if yt:
            m = max(x["months"] for x in yt); yt = [x for x in yt if x["months"] == m]
            ytd = {"months": m, "v": sum(x["v"] for x in yt), "v_prev": sum(x["v_prev"] for x in yt), "p": sum(x["p"] for x in yt),
                   "p_prev": sum(x["p_prev"] for x in yt), "n_agencies": len(yt)}
        if latest:
            s = series[str(latest)]; cov = s["cov_pop"]
            c.execute("""UPDATE counties SET year=?, violent=?, property=?, cov_pop=?, v_rate=?, p_rate=?, coverage=?, n_agencies=?, n_reporting=?, series=?, ytd=?, updated=?
                         WHERE fips=?""", (latest, s["v"], s["p"], cov, round(s["v"] / cov * 1e5, 1) if cov else None, round(s["p"] / cov * 1e5, 1) if cov else None,
                                         round(min(1.0, cov / cpop), 3) if cpop else None, len(ags), s["n"], json.dumps(series), json.dumps(ytd) if ytd else None, now_iso(), fp))
        else:
            c.execute("UPDATE counties SET n_agencies=?, n_reporting=0, series=?, ytd=?, updated=? WHERE fips=?", (len(ags), json.dumps(series), json.dumps(ytd) if ytd else None, now_iso(), fp))
    c.commit()

# ------------------------------------------------------------------------------------------------ live city feeds
# kind: soda | arcgis | carto | ckan. Only category, time and coordinates are requested.
FEEDS = [
 dict(id="chi", city="Chicago", st="IL", tz="America/Chicago", kind="soda", host="data.cityofchicago.org", ds="ijzp-q8t2", date="date",
      sel="id,date,primary_type,description,latitude,longitude", idf="id", desc=["primary_type", "description"], lat="latitude", lon="longitude",
      source="City of Chicago Data Portal: Crimes 2001 to Present", url="https://data.cityofchicago.org/Public-Safety/Crimes-2001-to-Present/ijzp-q8t2",
      license="City of Chicago Data Portal Terms of Use", lag="about 7 days (Chicago publishes with a one-week delay)"),
 dict(id="nyc", city="New York City", st="NY", tz="America/New_York", kind="soda", host="data.cityofnewyork.us", ds="5uac-w243", date="cmplnt_fr_dt",
      sel="cmplnt_num,cmplnt_fr_dt,cmplnt_fr_tm,ofns_desc,pd_desc,latitude,longitude", idf="cmplnt_num", desc=["ofns_desc", "pd_desc"], lat="latitude", lon="longitude",
      timef="cmplnt_fr_tm", source="NYC Open Data: NYPD Complaint Data Current (Year To Date)", url="https://data.cityofnewyork.us/Public-Safety/NYPD-Complaint-Data-Current-Year-To-Date-/5uac-w243",
      license="NYC Open Data Terms of Use", lag="quarterly (NYPD posts each quarter, so the newest data is months old)"),
 dict(id="la", city="Los Angeles", st="CA", tz="America/Los_Angeles", kind="soda", host="data.lacity.org", ds="k7nn-b2ep", date="date_occ",
      sel="uniquenibrno,date_occ,time_occ,nibr_description,crime_against,hndrdth_lat,hndrdth_lon", idf="uniquenibrno", desc=["nibr_description"], lat="hndrdth_lat", lon="hndrdth_lon",
      timef="time_occ", source="Los Angeles Open Data: LAPD NIBRS Offenses", url="https://data.lacity.org/Public-Safety/LAPD-NIBRS-Offenses-Dataset/k7nn-b2ep",
      license="City of Los Angeles open data terms", lag="1 to 2 weeks"),
 dict(id="sf", city="San Francisco", st="CA", tz="America/Los_Angeles", kind="soda", host="data.sf.gov", ds="wg3w-h783", date="incident_datetime",
      sel="row_id,incident_datetime,incident_category,incident_subcategory,incident_description,report_type_code,latitude,longitude", idf="row_id",
      desc=["incident_category", "incident_subcategory", "incident_description"], lat="latitude", lon="longitude", where="report_type_code in('II','VI','IS','VS')",
      source="DataSF: Police Department Incident Reports 2018 to Present", url="https://data.sfgov.org/Public-Safety/Police-Department-Incident-Reports-2018-to-Present/wg3w-h783",
      license="ODC Public Domain Dedication (PDDL)", lag="1 to 3 days"),
 dict(id="sea", city="Seattle", st="WA", tz="America/Los_Angeles", kind="soda", host="data.seattle.gov", ds="tazs-3rd5", date="offense_date",
      sel="offense_id,offense_date,offense_sub_category,nibrs_offense_code_description,shooting_type_group,latitude,longitude", idf="offense_id",
      desc=["offense_sub_category", "nibrs_offense_code_description", "shooting_type_group"], lat="latitude", lon="longitude",
      source="Seattle Open Data: SPD Crime Data 2008 to Present", url="https://data.seattle.gov/Public-Safety/SPD-Crime-Data-2008-Present/tazs-3rd5",
      license="City of Seattle open data terms", lag="about 1 day"),
 dict(id="dal", city="Dallas", st="TX", tz="America/Chicago", kind="soda", host="www.dallasopendata.com", ds="qv6i-rri7", date="date1",
      sel="incidentnum,date1,time1,offincident,nibrs_crime_category,geocoded_column", idf=("incidentnum", "offincident"), desc=["offincident", "nibrs_crime_category"],
      geo="geocoded_column", timef="time1", source="Dallas OpenData: Police Incidents", url="https://www.dallasopendata.com/Public-Safety/Police-Incidents/qv6i-rri7",
      license="Open Data Commons Attribution License", lag="1 to 2 days"),
 dict(id="kc", city="Kansas City", st="MO", tz="America/Chicago", kind="soda", host="data.kcmo.org", ds="f7wj-ckmw", date="from_date",
      sel="report,ibrs,from_date,offense,description,firearmusedflag,location", idf=("report", "ibrs"), desc=["offense", "description"], geo="location",
      source="Open Data KC: KCPD Crime Data 2026", url="https://data.kcmo.org/Crime/KCPD-Crime-Data-2026/f7wj-ckmw",
      license="City of Kansas City open data terms", lag="about 1 week"),
 dict(id="cin", city="Cincinnati", st="OH", tz="America/New_York", kind="soda", host="data.cincinnati-oh.gov", ds="t9kw-3jfx", date="reportdate",
      sel="reportnumber,reportdate,starscategory,lat_x,lon_x", idf=("reportnumber", "starscategory"), desc=["starscategory"], lat="lat_x", lon="lon_x",
      source="CincyInsights: CPD Reported Crime", url="https://data.cincinnati-oh.gov/safety/Cincinnati-Police-Department-Reported-Crime-Dataset/t9kw-3jfx",
      license="Public domain (City of Cincinnati open data)", lag="about 1 week"),
 dict(id="mcmd", city="Montgomery County", st="MD", tz="America/New_York", kind="soda", host="data.montgomerycountymd.gov", ds="icn6-v9z3", date="start_date",
      sel="incident_id,offence_code,start_date,crimename1,crimename2,crimename3,latitude,longitude", idf=("incident_id", "offence_code"),
      desc=["crimename2", "crimename3"], lat="latitude", lon="longitude", source="dataMontgomery: Crime", url="https://data.montgomerycountymd.gov/Public-Safety/Crime/icn6-v9z3",
      license="Public domain (Montgomery County open data)", lag="about 1 day"),
 dict(id="oak", city="Oakland", st="CA", tz="America/Los_Angeles", kind="soda", host="data.oaklandca.gov", ds="ppgh-7dqv", date="datetime",
      sel="casenumber,datetime,crimetype,description,location", idf=("casenumber", "crimetype"), desc=["crimetype", "description"], geo="location",
      source="Oakland Open Data: CrimeWatch Data", url="https://data.oaklandca.gov/Public-Safety/CrimeWatch-Data/ppgh-7dqv",
      license="City of Oakland open data terms", lag="2 to 3 days"),
 dict(id="cam", city="Cambridge", st="MA", tz="America/New_York", kind="soda", host="data.cambridgema.gov", ds="xuad-73uj", date="date_of_report",
      sel="file_number,date_of_report,crime,reporting_area_lat,reporting_area_lon", idf=("file_number", "crime"), desc=["crime"], lat="reporting_area_lat", lon="reporting_area_lon",
      source="Cambridge Open Data: Crime Reports", url="https://data.cambridgema.gov/Public-Safety/Crime-Reports/xuad-73uj",
      license="City of Cambridge open data terms", lag="about 1 month"),
 dict(id="phl", city="Philadelphia", st="PA", tz="America/New_York", kind="carto", table="incidents_part1_part2", date="dispatch_date_time",
      sel="cartodb_id,dispatch_date_time,text_general_code,point_x,point_y", idf="cartodb_id", desc=["text_general_code"], lat="point_y", lon="point_x",
      source="OpenDataPhilly: Crime Incidents (Philadelphia Police Department)", url="https://opendataphilly.org/datasets/crime-incidents/",
      license="OpenDataPhilly terms (attribution)", lag="under 1 day"),
 dict(id="dc", city="Washington", st="DC", tz="America/New_York", kind="arcgis", base="https://maps2.dcgis.dc.gov/dcgis/rest/services/FEEDS/MPD/MapServer/39",
      date="START_DATE", sel="CCN,OFFENSE,METHOD,START_DATE,REPORT_DAT,LATITUDE,LONGITUDE", idf=("CCN", "OFFENSE"), desc=["OFFENSE", "METHOD"], lat="LATITUDE", lon="LONGITUDE",
      source="Open Data DC: Crime Incidents in the Last 30 Days (MPD)", url="https://opendata.dc.gov/datasets/DCGIS::crime-incidents-in-the-last-30-days",
      license="Creative Commons Attribution 4.0 (Open Data DC)", lag="under 1 day"),
 dict(id="det", city="Detroit", st="MI", tz="America/Detroit", kind="arcgis", base="https://services2.arcgis.com/qvkbeam7Wirps6zC/arcgis/rest/services/RMS_Crime_Incidents_2026/FeatureServer/0",
      date="incident_occurred_at", sel="incident_entry_id,incident_occurred_at,offense_category,offense_description,latitude,longitude", idf="incident_entry_id",
      desc=["offense_category", "offense_description"], lat="latitude", lon="longitude", source="Detroit Open Data: RMS Crime Incidents 2026",
      url="https://data.detroitmi.gov/datasets/rms-crime-incidents", license="City of Detroit open data terms", lag="about 1 day"),
 dict(id="den", city="Denver", st="CO", tz="America/Denver", kind="arcgis", base="https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/arcgis/rest/services/ODC_CRIME_OFFENSES_P/FeatureServer/324",
      date="FIRST_OCCURRENCE_DATE", sel="OFFENSE_ID,FIRST_OCCURRENCE_DATE,OFFENSE_CATEGORY_ID,OFFENSE_TYPE_ID,GEO_LAT,GEO_LON,IS_CRIME", idf="OFFENSE_ID",
      desc=["OFFENSE_CATEGORY_ID", "OFFENSE_TYPE_ID"], lat="GEO_LAT", lon="GEO_LON", where="IS_CRIME=1", source="Denver Open Data: Crime (NIBRS offenses)",
      url="https://opendata-geospatialdenver.hub.arcgis.com/datasets/geospatialdenver::crime", license="Denver Open Data terms (CC BY 3.0)", lag="1 to 3 days (updated weekdays)"),
 dict(id="bos", city="Boston", st="MA", tz="America/New_York", kind="ckan", host="data.boston.gov", res="b973d8cb-eeb2-4e7e-99da-c92938efc9c0", date="OCCURRED_ON_DATE",
      sel='"_id","INCIDENT_NUMBER","OFFENSE_CODE","OFFENSE_DESCRIPTION","SHOOTING","OCCURRED_ON_DATE","Lat","Long"', idf=("INCIDENT_NUMBER", "OFFENSE_CODE"),
      desc=["OFFENSE_DESCRIPTION", "SHOOTING"], lat="Lat", lon="Long", source="Analyze Boston: Crime Incident Reports (Boston Police Department)",
      url="https://data.boston.gov/dataset/crime-incident-reports-august-2015-to-date-source-new-system", license="ODC Public Domain Dedication (PDDL)", lag="1 to 2 days"),
]

# category normalization (applied to the joined description text, upper-case). Order matters: first match wins.
CATS = [
 ("Homicide", "v", r"HOMICIDE|MURDER|MANSLAUGHTER|CRIMINAL HOMICIDE"),
 ("Shooting", "v", r"SHOOTING|SHOT ?SPOTTER|DISCHARGE OF (A )?FIREARM|SHOTS FIRED|^.*\bGUN\b.*ASSAULT|ASSAULT.*\b(GUN|FIREARM)\b"),
 ("Robbery", "v", r"ROBBERY|CARJACK|HOLDUP|HOLD UP"),
 ("Sexual offense", "v", r"RAPE|SEX(UAL)? (ASSAULT|ABUSE|OFFENSE|BATTERY)|CRIM(INAL)? SEXUAL|SODOMY|FONDL|SEX OFFENSE|SEX CRIME|\bSEXUAL\b"),
 ("Aggravated assault", "v", r"AGG(RAVATED|\.)? ?(ASSAULT|ASLT|BATTERY)|ASSAULT W(ITH)?/? ?(A )?DEADLY|ADW|FELONY ASSAULT|ASSAULT 1|ASSAULT,? 1ST|BATTERY.*AGG|AGGRAVATED"),
 ("Kidnapping", "v", r"KIDNAP|ABDUCT|HUMAN TRAFFICKING"),
 ("Assault", "v", r"ASSAULT|BATTERY|INTIMIDATION|THREAT|STRANGULATION|SIMPLE ASSAULT|DOMESTIC"),
 ("Burglary", "p", r"BURGLARY|BREAKING AND ENTERING|BREAKING & ENTERING|B&E|HOME INVASION|BURG"),
 ("Vehicle theft", "p", r"MOTOR VEHICLE THEFT|VEHICLE THEFT|STOLEN VEHICLE|AUTO THEFT|THEFT OF (A )?(MOTOR )?VEHICLE|GTA|GRAND THEFT AUTO|LARCENY OF (A )?MOTOR VEHICLE|STOLEN AUTO|VEH(ICLE)?[- ]THEFT|UUV|AUTO-THEFT"),
 ("Arson", "p", r"ARSON"),
 ("Theft", "p", r"THEFT|LARCENY|SHOPLIFT|STEALING|PICKPOCKET|PURSE.?SNATCH|STOLEN PROPERTY|STOLEN"),
 ("Vandalism", "p", r"VANDALISM|CRIMINAL DAMAGE|CRIMINAL MISCHIEF|DESTRUCTION|DAMAGE TO PROPERTY|GRAFFITI|DEFAC|MALICIOUS"),
 ("Fraud", "p", r"FRAUD|FORGERY|COUNTERFEIT|IDENTITY|EMBEZZLE|SWINDL|CREDIT CARD|BAD CHECK|WHITE-COLLAR|IMPERSONAT|EXTORTION|BRIBERY"),
 ("Weapons", "o", r"WEAPON|FIREARM|GUN|CONCEALED|CARRYING"),
 ("Drugs", "o", r"NARCOTIC|DRUG|CONTROLLED SUB|MARIJUANA|CANNABIS|COCAINE|HEROIN|PARAPHERNALIA|OPIUM|METH"),
]
CATS_RE = [(n, g, re.compile(rx)) for n, g, rx in CATS]
SERIOUS = {"Homicide", "Shooting", "Robbery", "Aggravated assault", "Kidnapping"}   # alert-eligible (sexual offenses deliberately excluded to protect victims)
SKIP_RE = re.compile(r"NON-?CRIMINAL|LOST PROPERTY|FOUND PROPERTY|WARRANT|TRAFFIC|MISSING PERSON|SICK|DEATH INVESTIGATION|SUICIDE|NOT A CRIME|"
                     r"CASE CLOSURE|COURTESY|RECOVERED VEHICLE|VEHICLE RECOVERY|NATURAL DEATH|ACCIDENT|TOWED|INVESTIGATE PERSON|INVESTIGATE PROPERTY|SERVICE")
def classify(text):
    t = (text or "").upper()
    if SKIP_RE.search(t) and not re.search(r"ASSAULT|ROBBERY|HOMICIDE|SHOOT|BURGL|THEFT", t): return None, None
    for n, g, rx in CATS_RE:
        if rx.search(t): return n, g
    return "Other", "o"

def _num(x):
    try:
        v = float(x); return v if math.isfinite(v) and v != 0 else None
    except Exception: return None
def _snap(v): return round(round(v / GRID) * GRID, 4)

def _soda(f, since_local, until_local=None):
    rows, off, page = [], 0, 20000
    where = f"{f['date']} >= '{since_local}'" + (f" AND {f['date']} <= '{until_local}'" if until_local else "") + (f" AND {f['where']}" if f.get("where") else "")
    while True:
        q = urllib.parse.urlencode({"$select": f["sel"], "$where": where, "$order": f"{f['date']} DESC", "$limit": page, "$offset": off})
        b = get(f"https://{f['host']}/resource/{f['ds']}.json?{q}", timeout=120)
        rows += b; off += page
        if len(b) < page or off >= 120000: break
        time.sleep(1)
    return rows
def _arcgis(f, since_ms):
    rows, off = [], 0
    meta = get(f["base"] + "?f=json", timeout=60); n = int(meta.get("maxRecordCount") or 1000); n = min(n, 2000)
    where = f"{f['date']} >= {_arc_ts(since_ms)}" + (f" AND {f['where']}" if f.get("where") else "")
    while True:
        q = urllib.parse.urlencode({"where": where, "outFields": f["sel"], "returnGeometry": "false", "orderByFields": f"{f['date']} DESC",
                                    "resultOffset": off, "resultRecordCount": n, "f": "json"})
        b = get(f"{f['base']}/query?{q}", timeout=120)
        if "error" in b: raise RuntimeError(str(b["error"])[:200])
        feats = [x["attributes"] for x in b.get("features", [])]; rows += feats; off += len(feats)
        if not feats or (not b.get("exceededTransferLimit") and len(feats) < n) or off >= 120000: break
        time.sleep(0.5)
    return rows
def _arc_ts(ms): return "timestamp '" + datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + "'"
def _carto(f, since_utc):
    q = f"SELECT {f['sel']} FROM {f['table']} WHERE {f['date']} >= '{since_utc}' ORDER BY {f['date']} DESC LIMIT 100000"
    return get("https://phl.carto.com/api/v2/sql?" + urllib.parse.urlencode({"q": q}), timeout=120).get("rows", [])
def _ckan(f, since_utc):
    rows, off = [], 0
    while True:
        sql = f'SELECT {f["sel"]} FROM "{f["res"]}" WHERE "{f["date"]}" >= \'{since_utc}\' LIMIT 2000 OFFSET {off}'
        b = get(f"https://{f['host']}/api/3/action/datastore_search_sql?" + urllib.parse.urlencode({"sql": sql}), timeout=120)
        rec = b.get("result", {}).get("records", []); rows += rec; off += len(rec)   # pages of 2,000 (10,000 gets a 502 from Boston's CKAN)
        if len(rec) < 2000 or off >= 100000: break
        time.sleep(0.5)
    return rows

SALT = hashlib.sha256(b"bn-crime-v1").hexdigest()[:16]
def _uid(f, r):
    idf = f["idf"] if isinstance(f["idf"], tuple) else (f["idf"],)
    return hashlib.sha256((SALT + f["id"] + "|" + "|".join(str(r.get(k)) for k in idf)).encode()).hexdigest()[:20]

def _ts(f, r):
    """-> aware datetime in the feed's local zone."""
    tz = ZoneInfo(f["tz"]); v = r.get(f["date"])
    if v is None: return None
    if isinstance(v, (int, float)): return datetime.fromtimestamp(v / 1000, timezone.utc).astimezone(tz)
    s = str(v).strip()
    try:
        if s.endswith("Z") or re.search(r"[+-]\d\d(:?\d\d)?$", s):
            s2 = s.replace("Z", "+00:00");  s2 = re.sub(r"([+-]\d\d)$", r"\1:00", s2)
            return datetime.fromisoformat(s2.replace(" ", "T")).astimezone(tz)
        d = datetime.fromisoformat(s.replace(" ", "T")[:19])
        tf = f.get("timef")
        if tf and r.get(tf) and d.hour == 0 and d.minute == 0:
            t = re.sub(r"\D", "", str(r[tf]))[:4].zfill(4) if ":" not in str(r[tf]) else str(r[tf]).replace(":", "")[:4].zfill(4)
            try: d = d.replace(hour=min(23, int(t[:2])), minute=min(59, int(t[2:4])))
            except Exception: pass
        return d.replace(tzinfo=tz)
    except Exception: return None

def raw_db():
    k = sqlite3.connect(os.path.join(WORK, "raw.sqlite"), timeout=30)
    k.execute("CREATE TABLE IF NOT EXISTS inc(id TEXT PRIMARY KEY, feed TEXT, ts_utc INTEGER, local TEXT, glat REAL, glon REAL, cat TEXT, grp TEXT)")
    k.execute("CREATE INDEX IF NOT EXISTS inc_f ON inc(feed, ts_utc)"); return k

def fetch_feed(f, k):
    tz = ZoneInfo(f["tz"])
    last = k.execute("SELECT MAX(ts_utc) FROM inc WHERE feed=?", (f["id"],)).fetchone()[0]
    since = datetime.fromtimestamp(last, timezone.utc) - timedelta(days=4) if last else datetime.now(timezone.utc) - timedelta(days=100)
    if f["id"] == "nyc" and not last: since = datetime.now(timezone.utc) - timedelta(days=200)   # quarterly feed: newest data is months old
    sl = since.astimezone(tz).strftime("%Y-%m-%dT%H:%M:%S")
    if f["kind"] == "soda": rows = _soda(f, sl)
    elif f["kind"] == "arcgis": rows = _arcgis(f, since.timestamp() * 1000)
    elif f["kind"] == "carto": rows = _carto(f, since.strftime("%Y-%m-%dT%H:%M:%SZ"))
    else: rows = _ckan(f, since.strftime("%Y-%m-%d %H:%M:%S"))
    n_ok = 0; nowu = time.time() + 3600
    for r in rows:
        if f.get("geo"):
            g = r.get(f["geo"]) or {}
            if "coordinates" in g: lo, la = (_num(g["coordinates"][0]), _num(g["coordinates"][1]))
            else: la, lo = _num(g.get("latitude")), _num(g.get("longitude"))
        else: la, lo = _num(r.get(f["lat"])), _num(r.get(f["lon"]))
        if la is None or lo is None or abs(la) > 80 or abs(lo) > 180: continue
        text = " | ".join(str(r.get(x) or "") for x in f["desc"])
        if f["id"] == "bos" and str(r.get("SHOOTING") or "0").strip() in ("1", "Y"): text = "SHOOTING | " + text
        if f["id"] == "dc" and str(r.get("METHOD") or "").upper() == "GUN" and re.search(r"ASSAULT|HOMICIDE", text.upper()): text = "SHOOTING | " + text
        if f["id"] == "kc" and r.get("firearmusedflag") in (True, "true") and re.search(r"ASSAULT", text.upper()): text = "SHOOTING | " + text
        cat, grp = classify(text)
        if not cat: continue
        d = _ts(f, r)
        if not d or d.timestamp() > nowu: continue
        k.execute("INSERT OR REPLACE INTO inc VALUES(?,?,?,?,?,?,?,?)", (_uid(f, r), f["id"], int(d.timestamp()), d.strftime("%Y-%m-%dT%H:00"),
                                                                       _snap(la), _snap(lo), cat, grp)); n_ok += 1
    k.commit(); return len(rows), n_ok

def build_live(only=None):
    k = raw_db(); c = out_db()
    for f in FEEDS:
        if only and f["id"] not in only: continue
        err = None
        try:
            n, ok = fetch_feed(f, k); log(f"feed {f['id']}: {n} rows, {ok} kept")
        except Exception as e:
            err = str(e)[:300]; log(f"feed {f['id']} ERROR {err}")
        newest = k.execute("SELECT MAX(ts_utc) FROM inc WHERE feed=?", (f["id"],)).fetchone()[0]
        api = (f"https://{f['host']}/resource/{f['ds']}.json" if f["kind"] == "soda" else f.get("base") or
               ("https://phl.carto.com/api/v2/sql" if f["kind"] == "carto" else f"https://{f.get('host')}/api/3/action/datastore_search?resource_id={f.get('res')}"))
        if not newest:
            c.execute("""INSERT INTO feeds(id,city,st,tz,source,url,api,license,lag,last_error) VALUES(?,?,?,?,?,?,?,?,?,?)
                         ON CONFLICT(id) DO UPDATE SET last_error=excluded.last_error""", (f["id"], f["city"], f["st"], f["tz"], f["source"], f["url"], api, f["license"], f["lag"], err))
            c.commit(); continue
        w1 = newest; w0 = newest - 30 * 86400; p0 = w0 - 30 * 86400
        k.execute("DELETE FROM inc WHERE feed=? AND ts_utc<?", (f["id"], p0 - 86400)); k.commit()
        rows = k.execute("SELECT ts_utc, local, glat, glon, cat, grp, id FROM inc WHERE feed=? AND ts_utc>?", (f["id"], w0)).fetchall()
        # drop placeholder / geocoding-failure coordinates (e.g. Seattle's -1,-1): keep points within ~0.6 deg of the median point
        if rows:
            mla = sorted(r[2] for r in rows)[len(rows) // 2]; mlo = sorted(r[3] for r in rows)[len(rows) // 2]
            rows = [r for r in rows if abs(r[2] - mla) < 0.6 and abs(r[3] - mlo) < 0.8]
        earliest = k.execute("SELECT MIN(ts_utc) FROM inc WHERE feed=?", (f["id"],)).fetchone()[0]
        prev_days = k.execute("SELECT COUNT(DISTINCT substr(local,1,10)) FROM inc WHERE feed=? AND ts_utc>? AND ts_utc<=?", (f["id"], p0, w0)).fetchone()[0]
        if earliest and earliest <= p0 + 2 * 86400 and prev_days >= 27:   # only compare when the previous 30 days are fully stored (DC's layer keeps 30 days only)
            n_prev = k.execute("SELECT COUNT(*) FROM inc WHERE feed=? AND ts_utc>? AND ts_utc<=?", (f["id"], p0, w0)).fetchone()[0]
            prev_cats = dict(k.execute("SELECT cat, COUNT(*) FROM inc WHERE feed=? AND ts_utc>? AND ts_utc<=? GROUP BY cat", (f["id"], p0, w0)).fetchall())
        else: n_prev, prev_cats = None, {}
        cells, cats, daily = {}, {}, {}
        lats = sorted(r[2] for r in rows); lons = sorted(r[3] for r in rows)
        for ts, loc, la, lo, cat, grp, _ in rows:
            o = cells.setdefault((la, lo), [0, 0, 0]); o["vpo".index(grp)] += 1
            cats[cat] = cats.get(cat, 0) + 1
            dd = daily.setdefault(loc[:10], [0, 0, 0]); dd["vpo".index(grp)] += 1
        q = lambda a, p: a[min(len(a) - 1, int(len(a) * p))] if a else None
        bbox = [q(lons, .01), q(lats, .01), q(lons, .99), q(lats, .99)] if rows else None
        c.execute("DELETE FROM grid WHERE feed=?", (f["id"],))
        c.executemany("INSERT INTO grid VALUES(?,?,?,?,?,?)", [(f["id"], la, lo, v[0], v[1], v[2]) for (la, lo), v in cells.items()])
        c.execute("DELETE FROM serious WHERE feed=?", (f["id"],))
        c.executemany("INSERT OR REPLACE INTO serious VALUES(?,?,?,?,?,?,?)", [(r[6], f["id"], r[0], r[1], r[2], r[3], r[4]) for r in rows
                                                                              if r[4] in SERIOUS and r[0] > w1 - 14 * 86400])
        tz = ZoneInfo(f["tz"]); fmt = lambda t: datetime.fromtimestamp(t, timezone.utc).astimezone(tz).strftime("%Y-%m-%dT%H:%M")
        cl = sorted(({"cat": a, "n": b, "prev": prev_cats.get(a, 0)} for a, b in cats.items()), key=lambda x: -x["n"])
        c.execute("""INSERT OR REPLACE INTO feeds(id,city,st,tz,lat,lon,bbox,source,url,api,license,lag,newest,window_start,window_end,n_window,n_prev,cats,daily,last_ok,last_error)
                     VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (f["id"], f["city"], f["st"], f["tz"], q(lats, .5), q(lons, .5), json.dumps(bbox), f["source"], f["url"], api, f["license"], f["lag"],
                   fmt(newest), fmt(w0), fmt(w1), len(rows), n_prev, json.dumps(cl), json.dumps(sorted(daily.items())), now_iso() if not err else
                   (c.execute("SELECT last_ok FROM feeds WHERE id=?", (f["id"],)).fetchone() or [None])[0], err))
        c.commit()
    setmeta(c, "live_meta", {"built": now_iso(), "grid_deg": GRID}); c.commit(); c.close(); k.close()

def status():
    c = sqlite3.connect(f"file:{OUT}?mode=ro", uri=True)
    for t in ("zips", "counties", "states", "agencies", "countries", "feeds", "grid", "serious"):
        print(t, c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
    print("counties with data:", c.execute("SELECT COUNT(*) FROM counties WHERE year IS NOT NULL").fetchone()[0])
    for r in c.execute("SELECT id, newest, n_window, n_prev, last_error FROM feeds"): print(r)
    print("size MB", round(os.path.getsize(OUT) / 1e6, 2))

def _loop_state():
    try:
        c = sqlite3.connect(f"file:{OUT}?mode=ro", uri=True, timeout=30)
        r = c.execute("SELECT v FROM meta WHERE k='loop_state'").fetchone(); c.close()
        return json.loads(r[0]) if r else {}
    except Exception: return {}
def _save_loop_state(st):
    c = out_db(); setmeta(c, "loop_state", st); c.commit(); c.close()

def loop():
    """Live feeds every 30 min; FBI states daily; agency crawl weekly in a background thread (it takes hours) so live maps stay fresh;
    static files monthly. Last-run times persist in crime.db meta, so a restart does not redo finished work."""
    st = _loop_state(); ag = {"t": None}
    def agencies_job():
        try: build_agencies(["FL"] + [x for x in sorted(set(ST_FIPS.values()) - {"PR", "FL"})])
        except Exception: traceback.print_exc()
        finally:
            s2 = _loop_state(); s2["agencies"] = time.time(); _save_loop_state(s2)
    while True:
        t = time.time()
        try:
            st = _loop_state()
            if t - st.get("static", 0) > 30 * 86400: build_static(); st["static"] = t; _save_loop_state(st)
            build_live()
            if t - st.get("states", 0) > 86400: build_states(); st = _loop_state(); st["states"] = t; _save_loop_state(st)
            if t - st.get("agencies", 0) > 7 * 86400 and not (ag["t"] and ag["t"].is_alive()):
                ag["t"] = threading.Thread(target=agencies_job, daemon=True); ag["t"].start()
        except Exception: traceback.print_exc()
        time.sleep(max(60, 1800 - (time.time() - t)))

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "static": build_static()
    elif cmd == "states": build_states()
    elif cmd == "national": build_national()
    elif cmd == "agencies": build_agencies([s.upper() for s in sys.argv[2:]] or None)
    elif cmd == "aggregate":
        c = out_db(); aggregate_counties(c); c.close()
    elif cmd == "live": build_live(sys.argv[2:] or None)
    elif cmd == "loop": loop()
    else: status()
