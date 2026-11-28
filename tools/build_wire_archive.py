#!/usr/bin/env python3
"""Wire archive builder, phase 1 (Nov 27 2026, Matt pt1974u: history back to January 1, 2000).

Builds app/archive_wire_data/<year>.ndjson.gz.b64 (base64 of a gzip): one Wire row per real record from free authoritative datasets, ready to load into the
read-only archive SQLite (app/archive_wire.py, built at Docker build time). Run on the box (network needed); the shards are committed.

Phase 1 sources (2000-01-01 .. 2024-10-28, the day before the existing archive backfill / live Wire starts):
  USGS ComCat   M5+ worldwide, M4+ contiguous US and Hawaii        https://earthquake.usgs.gov/fdsnws/event/1/
  NHC HURDAT2   Atlantic + East/Central Pacific tropical storms and hurricanes (one row per storm, at peak intensity)
  OpenFEMA      DisasterDeclarationsSummaries, one row per declaration number (all states/counties merged)
  WHO DON       Disease Outbreak News (the API serves 2004 onward)
Every row has a headline, category, place, hashtags and ONE direct link to its own record page. Rows without a working link are dropped.
Ranking: the scanner's own code (scanner.item -> rebuild_cluster -> rank_cluster) on a scratch SQLite file; scanner.py is imported
read-only and never modified. Free templates only: no model, no paid writer.
Usage: python3 tools/build_wire_archive.py [--raw /path/to/cache] [--out app/archive_wire_data]"""
import os, sys, re, json, gzip, glob, math, time, sqlite3, tempfile, argparse, collections, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "app"); sys.path.insert(0, APP)
START = "2000-01-01T00:00:00Z"
END = "2024-10-29T00:00:00Z"       # exclusive: trends_history.db (the earlier archive backfill) starts at this instant
UA = {"User-Agent": "BLACKOUT.NETWORK archive build (blackout.network)"}

def log(*a): print(time.strftime("%H:%M:%S"), *a, flush=True)
def http(url, tries=3, to=120):
    for i in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=to).read()
        except Exception as ex:
            if i == tries - 1: raise
            time.sleep(4 * (i + 1))
def cached(raw, name, url):
    p = os.path.join(raw, name)
    if not (os.path.exists(p) and os.path.getsize(p) > 0):
        log("fetch", url[:110]); open(p, "wb").write(http(url))
    return p

STATES = {"AL": ("Alabama", 32.8, -86.8), "AK": ("Alaska", 64.0, -152.0), "AZ": ("Arizona", 34.3, -111.7), "AR": ("Arkansas", 34.9, -92.4),
 "CA": ("California", 37.2, -119.5), "CO": ("Colorado", 39.0, -105.5), "CT": ("Connecticut", 41.6, -72.7), "DE": ("Delaware", 39.0, -75.5),
 "DC": ("Washington, D.C.", 38.9, -77.0), "FL": ("Florida", 28.6, -82.4), "GA": ("Georgia", 32.7, -83.4), "HI": ("Hawaii", 20.8, -156.3),
 "ID": ("Idaho", 44.4, -114.6), "IL": ("Illinois", 40.0, -89.2), "IN": ("Indiana", 39.9, -86.3), "IA": ("Iowa", 42.1, -93.5),
 "KS": ("Kansas", 38.5, -98.4), "KY": ("Kentucky", 37.5, -85.3), "LA": ("Louisiana", 31.0, -92.0), "ME": ("Maine", 45.4, -69.2),
 "MD": ("Maryland", 39.0, -76.8), "MA": ("Massachusetts", 42.3, -71.8), "MI": ("Michigan", 44.3, -85.4), "MN": ("Minnesota", 46.3, -94.3),
 "MS": ("Mississippi", 32.7, -89.7), "MO": ("Missouri", 38.4, -92.5), "MT": ("Montana", 47.0, -109.6), "NE": ("Nebraska", 41.5, -99.8),
 "NV": ("Nevada", 39.3, -116.6), "NH": ("New Hampshire", 43.7, -71.6), "NJ": ("New Jersey", 40.1, -74.7), "NM": ("New Mexico", 34.4, -106.1),
 "NY": ("New York", 42.9, -75.5), "NC": ("North Carolina", 35.5, -79.4), "ND": ("North Dakota", 47.5, -100.5), "OH": ("Ohio", 40.3, -82.8),
 "OK": ("Oklahoma", 35.6, -97.5), "OR": ("Oregon", 43.9, -120.6), "PA": ("Pennsylvania", 40.9, -77.8), "RI": ("Rhode Island", 41.7, -71.5),
 "SC": ("South Carolina", 33.9, -80.9), "SD": ("South Dakota", 44.4, -100.2), "TN": ("Tennessee", 35.8, -86.3), "TX": ("Texas", 31.5, -99.3),
 "UT": ("Utah", 39.3, -111.7), "VT": ("Vermont", 44.0, -72.7), "VA": ("Virginia", 37.5, -78.8), "WA": ("Washington", 47.4, -120.5),
 "WV": ("West Virginia", 38.6, -80.6), "WI": ("Wisconsin", 44.6, -89.9), "WY": ("Wyoming", 43.0, -107.5),
 "PR": ("Puerto Rico", 18.2, -66.5), "VI": ("U.S. Virgin Islands", 18.3, -64.8), "GU": ("Guam", 13.4, 144.8), "AS": ("American Samoa", -14.3, -170.7),
 "MP": ("Northern Mariana Islands", 15.2, 145.7), "FM": ("Micronesia", 6.9, 158.2), "MH": ("Marshall Islands", 7.1, 171.2), "PW": ("Palau", 7.5, 134.6)}

# ------------------------------------------------------------------ scoring (the scanner's own code, read-only)
import scanner as S

class Scorer:
    """Scores single-record stories with scanner.rebuild_cluster on a scratch DB (cluster id = item id)."""
    def __init__(self):
        self.tmpd = tempfile.mkdtemp(prefix="bn_arch_"); S.DB = os.path.join(self.tmpd, "scratch.db")
        self.c = S.db(); self.c.execute("PRAGMA journal_mode=OFF"); self.c.execute("PRAGMA synchronous=OFF")
    def score(self, it):
        c = self.c
        c.execute("DELETE FROM alerts"); c.execute("DELETE FROM clusters")
        c.execute("INSERT INTO alerts VALUES(:id,:source,:family,:title,:category,:source_url,:event_time,:lat,:lon,:location,:base,:official,:extra,:event_time,:event_time,:id)", it)
        S.rebuild_cluster(c, it["id"])
        r = c.execute("SELECT score, rank, confidence FROM clusters WHERE cluster_id=?", (it["id"],)).fetchone()
        return int(r["score"]), int(r["rank"]), r["confidence"]

def iso(dt): return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def keep_t(t): return START <= t < END

def fema_clean(s):
    s = re.sub(r"\s+", " ", s or "").strip()
    # fire-management titles are free text ("AZ-RYAN-WILDFIRE-4/30/2002", "WILDFIRE -GREEN KNOLL- JULY 23, 2001"): drop the dates and the state code
    s = re.sub(r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b", "", s)
    s = re.sub(r"\b(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\.? \d{1,2},? \d{4}\b", "", s, flags=re.I)
    if re.search(r"fire", s, re.I) and re.search(r"[A-Za-z]-|-[A-Za-z]| - ", s):
        parts = [x.strip(" ,()") for x in re.split(r"\s*-\s*|-", s) if x.strip(" ,()")]
        if parts and re.fullmatch(r"[A-Za-z]{2}", parts[0]): parts = parts[1:]
        gen = [x for x in parts if re.fullmatch(r"(wild)?fires?", x, re.I)]
        rest = [x for x in parts if x not in gen]
        s = " ".join(rest + gen[:1]) if rest else (gen[0] if gen else s)
    s = re.sub(r"^[A-Za-z]{2} (?=.*fire)", "", s) if re.match(r"^(NV|CA|AZ|AK|OR|WA|ID|MT|NM|UT|CO|WY|TX|OK|FL|NC|SC|HI|AL|MN|SD|ND|NE|KS|AR|LA|TN|GA|VA|NY)\s", s) else s
    s = re.sub(r"^[A-Za-z]{2},\s+", "", s).strip(" -,")
    for a, b in ((r"\bASSOC\.?\s*W/?\s*TD\b", "ASSOCIATED WITH TROPICAL DEPRESSION"), (r"\bASSOC\.?\s*W/?\s*TS\b", "ASSOCIATED WITH TROPICAL STORM"),
                 (r"\bASSOCIATED W/?\s*TD\b", "ASSOCIATED WITH TROPICAL DEPRESSION"), (r"\bASSOC\.?\s*W/?\s*", "ASSOCIATED WITH "), (r"\bASSOCIATED W\b", "ASSOCIATED WITH"),
                 (r"\bW/\s*TYPH\b|\bWITH TYPH\b|\bW TYPH\b", "WITH TYPHOON"), (r"\bTYPH\b", "TYPHOON"), (r"\bTROPCIAL\b", "TROPICAL"), (r"\bNOR'EAST\b", "NOR'EASTER"), (r"\bTD\b", "TROPICAL DEPRESSION")):
        s = re.sub(a, b, s, flags=re.I)
    return s

def smart(s):
    """FEMA/NOAA upper-case titles -> Title Case with small words and acronyms handled."""
    small = {"and", "or", "of", "the", "in", "for", "to", "a", "an", "on", "at", "by", "from", "with"}
    keep = {"COVID-19", "COVID", "FEMA", "USA", "II", "III", "IV", "TS", "DR", "EM", "FM", "NYC", "PR", "US", "U.S.", "D.C."}
    out = []
    for i, w in enumerate(re.split(r"(\s+)", s.strip())):
        if not w or w.isspace(): out.append(w); continue
        if w.upper() in keep: out.append(w.upper())
        elif w.lower() in small and i: out.append(w.lower())
        else: out.append("-".join(re.sub(r"^([^A-Za-z]*)([A-Za-z])", lambda mm: mm.group(1) + mm.group(2).upper(), x.lower()) for x in w.split("-")) if (w.isupper() or w.islower() or w[0] == "(") else w)
    return re.sub(r"\s{2,}", " ", "".join(out)).strip()

def tag(s):
    s = re.sub(r"[^A-Za-z0-9 ]+", " ", s or "").title().replace(" ", "")
    return ("#" + s) if 3 <= len(s) <= 26 else ""

# ------------------------------------------------------------------ USGS
DROPPED = collections.Counter()

def usgs(raw):
    rows, seen = [], set()
    for y in range(2000, 2025):
        for k in ("w", "us", "hi"):
            p = os.path.join(raw, f"usgs_{k}_{y}.json")
            if not os.path.exists(p):
                q = {"w": "minmagnitude=5", "us": "minmagnitude=4&minlatitude=24&maxlatitude=50&minlongitude=-125.5&maxlongitude=-66",
                     "hi": "minmagnitude=4&minlatitude=18&maxlatitude=23&minlongitude=-161&maxlongitude=-154"}[k]
                cached(raw, os.path.basename(p), f"https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime={y}-01-01&endtime={y+1}-01-01&{q}&orderby=time-asc")
            for f in json.load(open(p))["features"]:
                pr = f["properties"]; m = pr.get("mag")
                if m is None or f["id"] in seen: continue
                lon, lat, depth = f["geometry"]["coordinates"][:3]
                place = (pr.get("place") or "").strip()
                if k in ("us", "hi"):   # the box also catches Mexico/Canada: keep U.S. places only
                    mm = re.search(r",\s*([A-Z]{2})$", place)
                    if not (mm and mm.group(1) in STATES) and not any(place.endswith(", " + v[0]) for v in STATES.values()): continue
                seen.add(f["id"]); rows.append((f, pr, m, lat, lon, depth, place))
    log("usgs raw rows", len(rows))
    return rows

def usgs_items(rows):
    out = []
    for f, pr, m, lat, lon, depth, place in rows:
        t = datetime.fromtimestamp(pr["time"] / 1000, timezone.utc)
        if not keep_t(iso(t)): continue
        loc = place
        ym = re.match(r"^(?:19|20)\d{2}\s+(.+)$", place)         # USGS names a few events ("2009 Samoa Earthquake"): keep the place, drop the label
        if ym: loc = re.sub(r"\s*(Earthquake|Aftershock)\b", "", ym.group(1)).strip(" ,")
        elif place and place[0].islower(): loc = place[0].upper() + place[1:]
        mm = re.match(r"^(.*?),\s*([A-Z]{2})$", place)
        if mm and mm.group(2) in STATES: loc = f"{mm.group(1)}, {STATES[mm.group(2)][0]}"
        if not loc: loc = "Unnamed region (%.1f, %.1f)" % (lat, lon)
        base = 20 + max(0, (m - 4.5)) * 18
        base += {"green": 0, "yellow": 10, "orange": 20, "red": 30}.get(pr.get("alert") or "", 0)
        if pr.get("tsunami"): base += 10
        # score on the scanner's own live title format; the display headline is written below
        it = S.item("USGS", "USGS", f["id"], f"M {m:.1f} - {place or loc}", "natural disaster", f"https://earthquake.usgs.gov/earthquakes/eventpage/{f['id']}",
                    t, lat, lon, loc, base, extra={"mag": m, "depth_km": depth, "pager": pr.get("alert"), "tsunami": pr.get("tsunami"), "felt": pr.get("felt")})
        extra = []
        if pr.get("tsunami"): extra.append("tsunami alert issued")
        if pr.get("alert") in ("orange", "red"): extra.append("USGS PAGER " + pr["alert"])
        head = f"M{m:.1f} earthquake: {loc}" + (f" ({', '.join(extra)})" if extra else "")
        country = loc.rsplit(",", 1)[-1].strip() if "," in loc else loc
        tags = ["#Earthquake", tag(country) or "#Seismic", "#USGS"]
        out.append(dict(it=it, title=head, loc=loc, tags=tags, link=it["source_url"], src="USGS ComCat", kind="quake", cat="natural disaster"))
    return out

# ------------------------------------------------------------------ HURDAT2
def _ll(s):
    v = float(s[:-1]); return -v if s[-1] in "SW" else v

def basin_name(basin, lat, lon):
    if basin == "AL":
        if 18 <= lat <= 31 and -98 <= lon <= -80.5: return "Gulf of Mexico"
        if 8 <= lat < 22 and -88 <= lon <= -60: return "Caribbean Sea"
        if lon < -60: return "western North Atlantic"
        if lon < -40: return "central North Atlantic"
        return "eastern North Atlantic"
    if basin == "CP" or lon <= -140 or lon > 0: return "central North Pacific"
    return "eastern North Pacific"

def hurdat(raw):
    out = []
    for fn in ("hurdat2.txt", "hurdat2_nepac.txt"):
        cur = None; recs = []
        def flush():
            if cur and recs: yield_storm(cur, recs)
        storms = []
        for line in open(os.path.join(raw, fn)):
            p = [x.strip() for x in line.strip().split(",")]
            if re.match(r"^(AL|EP|CP)\d{6}$", p[0]):
                if cur and recs: storms.append((cur, recs))
                cur, recs = p, []
            elif cur and len(p) > 7 and re.match(r"^\d{8}$", p[0]): recs.append(p)
        if cur and recs: storms.append((cur, recs))
        for hd, recs in storms:
            sid, name = hd[0], hd[1]; yr = int(sid[4:])
            if yr < 2000 or yr > 2025: continue
            best = None
            for p in recs:   # first time the storm reaches its highest sustained wind
                w = int(p[6]);
                if best is None or w > best[0]: best = (w, p)
            wind, p = best
            if wind < 34: continue
            t = datetime.strptime(p[0] + p[1], "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
            lat, lon = _ll(p[4]), _ll(p[5])
            cat = 5 if wind >= 137 else 4 if wind >= 113 else 3 if wind >= 96 else 2 if wind >= 83 else 1 if wind >= 64 else 0
            mph = int(round(wind * 1.15078 / 5.0) * 5)
            basin = sid[:2]; place = basin_name(basin, lat, lon)
            nm = name.title() if name != "UNNAMED" else None
            if cat:
                kind = "Hurricane"; rank_txt = f"Category {cat}"
            else:
                kind = "Tropical Storm"; rank_txt = "tropical storm strength"
            label = f"{kind} {nm}" if nm else f"Unnamed {'hurricane' if cat else 'tropical storm'} ({sid})"
            head = f"{label} peaks at {rank_txt} with {mph} mph winds over the {place}" if cat else f"{label} reaches {mph} mph winds over the {place}"
            base = {0: 30, 1: 42, 2: 52, 3: 62, 4: 72, 5: 85}[cat]
            ocean = "Atlantic" if basin == "AL" else "Pacific"
            nhc_url = (f"https://www.nhc.noaa.gov/data/tcr/{sid}_{name.title()}.pdf" if nm else
                       f"https://www.nhc.noaa.gov/data/tcr/index.php?season={yr}&basin={'atl' if basin == 'AL' else 'pac'}")
            it = S.item("NOAA NHC HURDAT2", "NOAA", f"{sid}", head, "natural disaster", nhc_url, t, lat, lon, f"{place[0].upper()+place[1:]}", base,
                        extra={"hurdat2": sid, "peak_wind_kt": wind, "saffir_simpson": cat})
            tags = [f"#{'Hurricane' if cat else 'TropicalStorm'}", tag(nm) if nm else "#Cyclone", f"#{ocean}"]
            out.append(dict(it=it, title=head, loc=place[0].upper() + place[1:], tags=tags, link=nhc_url, src="NOAA NHC HURDAT2", kind="storm", cat="natural disaster",
                            season=f"https://www.nhc.noaa.gov/data/tcr/index.php?season={yr}&basin={'atl' if basin == 'AL' else 'pac'}"))
    out = [x for x in out if keep_t(x["it"]["event_time"])]
    check_nhc_links(raw, out)
    log("hurdat storms", len(out)); return out

def check_nhc_links(raw, out):
    """HEAD every storm's Tropical Cyclone Report PDF once (cached); a storm whose PDF is not there links to its season index page."""
    import concurrent.futures as cf
    cp = os.path.join(raw, "nhc_links.json")
    try: ok = json.load(open(cp))
    except Exception: ok = {}
    def head(u):
        for i in range(3):
            try:
                r = urllib.request.urlopen(urllib.request.Request(u, headers=UA, method="HEAD"), timeout=40); return u, r.status == 200
            except urllib.error.HTTPError as ex:
                if ex.code in (403, 404, 410): return u, False
            except Exception: pass
            time.sleep(2)
        return u, None
    todo = sorted({x["link"] for x in out} | {x["season"] for x in out} - set(k for k, v in ok.items() if v is not None))
    with cf.ThreadPoolExecutor(12) as ex:
        for u, v in ex.map(head, todo): ok[u] = v
    json.dump(ok, open(cp, "w"))
    bad = 0
    for x in out:
        if ok.get(x["link"]) is not True:
            bad += 1
            if ok.get(x["season"]) is True: x["link"] = x["season"]; x["it"]["source_url"] = x["season"]
            else: x["link"] = ""
    log("nhc links: fell back to season page for", bad)

# ------------------------------------------------------------------ FEMA
def fema_items(raw):
    rows = json.load(open(os.path.join(raw, "fema.json")))
    g = collections.OrderedDict()
    for r in rows: g.setdefault(r["disasterNumber"], []).append(r)
    out = []
    for n, rs in g.items():
        r0 = rs[0]; t = r0["declarationDate"][:10] + "T00:00:00Z"
        if not keep_t(t): continue
        sts = sorted({r["state"] for r in rs}, key=lambda s: -sum(1 for r in rs if r["state"] == s))
        names = [STATES.get(s, (s,))[0] for s in sts]
        typ, inc = r0["declarationType"], r0["incidentType"]
        title = smart(fema_clean(r0["declarationTitle"] or inc))
        kind = {"DR": "Major disaster", "EM": "Federal emergency", "FM": "Fire management assistance"}.get(typ, "Disaster")
        where = names[0] if len(names) == 1 else (", ".join(names[:3]) + (f" and {len(names) - 3} more" if len(names) > 3 else ""))
        head = f"{kind} declared in {where}: {title}"
        if len(head) > 150: head = f"{kind} declared in {names[0]} and {len(names) - 1} more: {title}"
        cat = "disease" if inc == "Biological" else "war/conflict" if inc == "Terrorist" else "natural disaster"
        base = {"DR": 45, "EM": 35, "FM": 25}.get(typ, 30)
        if len(sts) >= 3: base += 5
        if len(sts) >= 10: base += 5
        if inc in ("Earthquake", "Tsunami", "Terrorist", "Volcanic Eruption", "Dam/Levee Break", "Chemical", "Typhoon") or (inc == "Hurricane" and typ == "DR"): base += 10
        st0 = STATES.get(sts[0]); lat, lon = (st0[1], st0[2]) if st0 else (None, None)
        url = f"https://www.fema.gov/disaster/{n}"
        it = S.item("FEMA", "FEMA", f"{typ}-{n}", head, cat, url, datetime.strptime(t, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc), lat, lon,
                    where if len(names) <= 3 else f"{names[0]} and {len(names) - 1} more", base, extra={"fema": f"{typ}-{n}", "incident": inc})
        itag = {"Severe Storm": "#SevereStorm", "Severe Ice Storm": "#IceStorm", "Snowstorm": "#Snowstorm", "Coastal Storm": "#CoastalStorm", "Mud/Landslide": "#Landslide",
                "Dam/Levee Break": "#DamFailure", "Volcanic Eruption": "#Volcano", "Biological": "#PublicHealth", "Fire": "#Wildfire", "Tropical Storm": "#TropicalStorm",
                "Straight-Line Winds": "#Windstorm"}.get(inc) or tag(inc) or "#Disaster"
        tags = ["#FEMA", tag(names[0]) or "#USA", itag]
        out.append(dict(it=it, title=head, loc=it["location"], tags=tags, link=url, src="OpenFEMA", kind="fema", cat=cat))
    log("fema declarations", len(out)); return out

# ------------------------------------------------------------------ WHO DON
def who_items(raw):
    vals = json.load(open(os.path.join(raw, "who.json")))
    try:
        import x_share
        names = sorted({k for k in x_share._COUNTRIES if len(k) > 3} | {"viet nam", "russian federation", "republic of korea", "occupied palestinian territory", "hong kong"},
                       key=len, reverse=True)
    except Exception: names = []
    out = []
    for v in vals:
        url_name = v.get("UrlName") or ""
        if not url_name: continue
        m = re.match(r"^(\d{4})_(\d{2})_(\d{2})", url_name)       # migrated old reports were re-published in 2021: the item's own date is in its URL
        pdt = (v.get("PublicationDate") or "")[:19] + "Z"
        if not m:   # no date in the URL: the API date is only trusted when it agrees with the year in the URL and is not a site-migration batch date
            ym = re.match(r"^(\d{4})", url_name)
            if (ym and ym.group(1) != pdt[:4]) or ("2021-06-02" <= pdt[:10] <= "2021-06-09") or ("2024-03-05" <= pdt[:10] <= "2024-03-15" and not url_name.startswith("2024")):
                DROPPED["who_undated"] += 1; continue
        t = f"{m.group(1)}-{m.group(2)}-{m.group(3)}T00:00:00Z" if m else pdt
        if len(t) < 20 or not keep_t(t): continue
        try: datetime.strptime(t, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError: continue
        title = re.sub(r"\s+", " ", (v.get("OverrideTitle") or v.get("Title") or "").replace("\u2013", "-").replace("\u2014", "-").strip())
        title = re.sub(r"^(19|20)\d{2}\s*-\s*", "", title)
        if not title: continue
        core = re.sub(r"\s*-\s*(update|situation update|follow-up).*$", "", title, flags=re.I)
        loc = None; low = core.lower()
        for nme in names:
            if re.search(r"\b" + re.escape(nme) + r"\b", low):
                loc = {"viet nam": "Viet Nam"}.get(nme, nme.title()); break
        if not loc and " - " in core:
            seg = core.rsplit(" - ", 1)[-1].strip()
            if len(seg) <= 40 and not re.search(r"\d|update|situation", seg, re.I): loc = seg
        loc = loc or "Worldwide"
        base = 45
        if re.search(r"ebola|marburg|bundibugyo|novel|h5n1|avian|mers|plague|nipah|pandemic|lassa|sars", title, re.I): base += 20
        if " - " in title and len(re.split(r",| and | - ", title.split(",", 1)[-1])) >= 2: base += 10
        url = "https://www.who.int/emergencies/disease-outbreak-news/item/" + url_name
        head = "WHO outbreak report: " + title
        it = S.item("WHO Disease Outbreak News", "WHO", v["Id"], title, "disease", url, datetime.strptime(t, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc),
                    location=loc, base=base, extra={"don_id": v.get("DonId")})
        dis = re.split(r" - |, ", core)[0]
        tags = ["#WHO", "#Outbreak", tag(loc) if loc != "Worldwide" else (tag(dis) or "#Health")]
        out.append(dict(it=it, title=head, loc=loc, tags=tags, link=url, src="WHO Disease Outbreak News", kind="who", cat="disease"))
    log("who don", len(out), "dropped (no reliable date)", DROPPED["who_undated"]); return out

# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--raw", default="/workspace/archive2000/raw"); ap.add_argument("--out", default=os.path.join(APP, "archive_wire_data"))
    ap.add_argument("--only", default="")
    a = ap.parse_args(); os.makedirs(a.raw, exist_ok=True); os.makedirs(a.out, exist_ok=True)
    cached(a.raw, "hurdat2.txt", "https://www.nhc.noaa.gov/data/hurdat/hurdat2-1851-2025-092326.txt")
    cached(a.raw, "hurdat2_nepac.txt", "https://www.nhc.noaa.gov/data/hurdat/hurdat2-nepac-1949-2025-092926.txt")
    items = []
    only = set(filter(None, a.only.split(",")))
    if not only or "quake" in only: items += usgs_items(usgs(a.raw))
    if not only or "storm" in only: items += hurdat(a.raw)
    if not only or "fema" in only: items += fema_items(a.raw)
    if not only or "who" in only: items += who_items(a.raw)
    log("items", len(items))
    sc = Scorer(); by_year = collections.defaultdict(list); bad = 0
    for i, x in enumerate(items):
        it = x["it"]
        if not re.match(r"^https?://", x["link"] or ""): bad += 1; continue
        score, rank, conf = sc.score(it)
        t = it["event_time"]
        by_year[t[:4]].append([it["id"], t, x["title"][:240], x["cat"], x["loc"][:120], it["lat"], it["lon"], score, rank, conf, x["tags"], x["src"], x["link"], x["kind"]])
        if i % 5000 == 0: log("scored", i)
    for y, rows in by_year.items():
        rows.sort(key=lambda r: (r[1], r[0]))
        # shards are committed as base64 text of a gzip (mtime 0, so a rebuild with the same data is byte-identical): the repo tooling moves text only
        blob = "".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n" for r in rows).encode("utf-8")
        import base64, io
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=9, mtime=0) as f: f.write(blob)
        open(os.path.join(a.out, f"{y}.ndjson.gz.b64"), "w").write(base64.b64encode(buf.getvalue()).decode("ascii") + "\n")
    log("dropped (no link)", bad, "years", len(by_year), "rows", sum(len(v) for v in by_year.values()))

if __name__ == "__main__": main()
