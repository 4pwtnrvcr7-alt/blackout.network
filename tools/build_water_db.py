#!/usr/bin/env python3
"""Build the Water layer plant database (read-only SQLite) from downloaded public inventories.

Sources (licensed / open, cited per row; coordinates come from the source, never guessed):
  - EPA ECHO facility search, active SIC 4941 (water supply) and SIC 4952 (sewerage)
  - EEA Waterbase UWWTD treatment plants (CC BY 4.0), if a UWWTPS.csv is in the cache
  - OpenStreetMap man_made=water_works / wastewater_plant (ODbL), country extracts

Usage:
  python3 tools/build_water_db.py --cache /tmp/water_plants_build --out /tmp/water_plants.sqlite --ship app/netmap_static
"""
from __future__ import annotations
import argparse, csv, json, math, os, re, sys
from collections import Counter, defaultdict
from pathlib import Path

COLS = ["lon", "lat", "name", "kind", "cc", "st", "src", "id", "url", "note"]
ITEM_RE = re.compile(r"^[A-Za-z][A-Za-z0-9._-]{3,40}$")
TERR = {"GU", "AS", "PR", "VI", "MP"}   # U.S. territories carry their own ISO country code
US_STATES = set("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split())

# Tight-enough bboxes for assigning a U.S. state when OSM has no addr:state.
# Overlaps (e.g. VA/DC, TN/GA) pick the smallest box that contains the point.
_US_BOXES = [
    ("RI", 41.14, -71.89, 42.02, -71.12), ("DE", 38.45, -75.79, 39.84, -75.05),
    ("CT", 40.98, -73.73, 42.05, -71.79), ("NJ", 38.93, -75.56, 41.36, -73.89),
    ("NH", 42.70, -72.56, 45.31, -70.70), ("VT", 42.73, -73.44, 45.02, -71.47),
    ("MA", 41.23, -73.51, 42.89, -69.93), ("HI", 18.91, -160.25, 22.24, -154.80),
    ("MD", 37.89, -79.49, 39.72, -75.05), ("DC", 38.79, -77.12, 38.99, -76.91),
    ("WV", 37.20, -82.64, 40.64, -77.72), ("ME", 43.06, -71.08, 47.46, -66.95),
    ("SC", 32.05, -83.35, 35.22, -78.54), ("KY", 36.50, -89.57, 39.15, -81.96),
    ("IN", 37.77, -88.10, 41.76, -84.78), ("VA", 36.54, -83.68, 39.47, -75.24),
    ("OH", 38.40, -84.82, 42.33, -80.52), ("TN", 34.98, -90.31, 36.68, -81.65),
    ("PA", 39.72, -80.52, 42.27, -74.69), ("MS", 30.17, -91.66, 35.00, -88.10),
    ("LA", 28.93, -94.04, 33.02, -88.82), ("AL", 30.14, -88.47, 35.01, -84.89),
    ("AR", 33.00, -94.62, 36.50, -89.64), ("NC", 33.84, -84.32, 36.59, -75.46),
    ("NY", 40.50, -79.76, 45.01, -71.86), ("IA", 40.38, -96.64, 43.50, -90.14),
    ("IL", 36.97, -91.51, 42.51, -87.50), ("WI", 42.49, -92.89, 47.08, -86.25),
    ("MO", 35.99, -95.77, 40.61, -89.10), ("FL", 24.52, -87.63, 31.00, -80.03),
    ("GA", 30.36, -85.61, 35.00, -80.84), ("OK", 33.62, -103.00, 37.00, -94.43),
    ("KS", 36.99, -102.05, 40.00, -94.59), ("NE", 40.00, -104.05, 43.00, -95.31),
    ("SD", 42.48, -104.06, 45.95, -96.44), ("ND", 45.94, -104.05, 49.00, -96.55),
    ("MN", 43.50, -97.24, 49.38, -89.49), ("MI", 41.70, -90.42, 48.19, -82.41),
    ("TX", 25.84, -106.65, 36.50, -93.51), ("NM", 31.33, -109.05, 37.00, -103.00),
    ("AZ", 31.33, -114.82, 37.00, -109.05), ("CO", 37.00, -109.06, 41.00, -102.04),
    ("WY", 41.00, -111.05, 45.00, -104.05), ("UT", 37.00, -114.05, 42.00, -109.04),
    ("NV", 35.00, -120.01, 42.00, -114.04), ("ID", 42.00, -117.24, 49.00, -111.04),
    ("MT", 44.36, -116.05, 49.00, -104.04), ("OR", 41.99, -124.57, 46.27, -116.46),
    ("WA", 45.54, -124.73, 49.00, -116.92), ("CA", 32.53, -124.48, 42.01, -114.13),
    ("AK", 51.22, -179.15, 71.44, -129.98),
]

def us_state(lat, lon, tagged=""):
    t = (tagged or "").strip().upper()
    if t in US_STATES or t in ("DC", "PR", "VI", "GU"):
        return t
    hits = []
    for st, s, w, n, e in _US_BOXES:
        if s <= lat <= n and w <= lon <= e:
            hits.append(( (n-s)*(e-w), st))
    hits.sort()
    return hits[0][1] if hits else ""


def _pt(lat, lon):
    try:
        a, b = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    if abs(a) < 0.2 or abs(b) < 0.2 or abs(a) > 90 or abs(b) > 180:
        return None
    return (round(b, 5), round(a, 5))  # lon, lat

_KEEP = {"LLC", "LP", "INC", "WWTP", "WWTF", "WPCP", "WPCF", "WRF", "WRRF", "STP", "POTW", "PWS", "MHP", "WTP", "WTF", "WSD", "MUD", "PUD", "SD", "II", "III", "IV", "NE", "NW", "SE", "SW", "USA", "US", "AFB", "RV", "NYC", "DC", "WWT", "STW"}
_SMALL = {"of", "the", "and", "at", "for", "in", "on", "to", "a", "an"}

def _smart(s):
    out = []
    for i, w in enumerate(re.split(r"(\s+)", s)):
        if not w.strip():
            out.append(w); continue
        core = re.sub(r"[^A-Za-z]", "", w)
        if core.upper() in _KEEP:
            out.append(w.upper() if core.isupper() else w)
        elif i and w.lower() in _SMALL:
            out.append(w.lower())
        else:
            out.append(re.sub(r"[A-Za-z]+", lambda m: m.group(0)[:1].upper() + m.group(0)[1:].lower(), w))
    return "".join(out)

def _name(s):
    s = re.sub(r"\s+", " ", str(s or "").strip())
    letters = [c for c in s if c.isalpha()]
    if letters and sum(c.isupper() for c in letters) / len(letters) > 0.8:   # EPA lists are ALL CAPS
        s = _smart(s)
    return s[:120] if s else "Unnamed plant"

def _id(prefix, raw):
    s = re.sub(r"[^A-Za-z0-9._-]+", "", str(raw or ""))
    cid = (prefix + s)[:41]
    if ITEM_RE.fullmatch(cid):
        return cid
    # fallback: prefix + hex of raw
    h = format(abs(hash(str(raw))) % (16**10), "x")
    cid = (prefix + h)[:41]
    return cid if ITEM_RE.fullmatch(cid) else None

def load_echo(path, kind, src, url_for):
    out = []
    if not path.is_file():
        return out
    data = json.loads(path.read_text())
    for w in data.get("facilities") or []:
        pt = _pt(w.get("FacLat"), w.get("FacLong"))
        if not pt:
            continue
        rid = str(w.get("RegistryID") or "").strip()
        cid = _id("ef", rid or w.get("FacName"))
        if not cid:
            continue
        st = (w.get("FacState") or "").strip().upper()[:2]
        place = ", ".join(x for x in ((w.get("FacCity") or "").title(), st) if x)
        name = _name(w.get("FacName"))
        note = place
        out.append({
            "lon": pt[0], "lat": pt[1], "name": name, "kind": kind, "cc": st if st in TERR else "US", "st": "" if st in TERR else st,
            "src": src, "id": cid, "url": url_for(rid), "note": note, "rid": rid,
        })
    return out

def osm_el_pt(el):
    if "lat" in el and "lon" in el:
        return _pt(el["lat"], el["lon"])
    c = el.get("center") or {}
    if "lat" in c:
        return _pt(c["lat"], c["lon"])
    return None

seen_osm = set()

# Rough outline of Northern Ireland (lon, lat); the Geofabrik Ireland extract covers both IE and GB-NIR.
_NI = [(-8.18,54.46),(-7.95,54.72),(-7.65,54.95),(-7.40,55.07),(-7.00,55.26),(-6.20,55.25),(-5.95,55.0),(-5.45,54.65),(-5.43,54.40),(-5.62,54.10),(-6.05,54.00),(-6.28,54.03),(-6.55,54.07),(-6.85,54.0),(-7.10,54.05),(-7.45,54.15),(-7.85,54.20),(-8.18,54.46)]
def in_ni(lat, lon):
    ins = False
    for (x1, y1), (x2, y2) in zip(_NI, _NI[1:]):
        if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            ins = not ins
    return ins


def _tag_cc(tags):
    t = (tags.get("addr:country") or tags.get("addr:country_code") or tags.get("is_in:country_code")
         or tags.get("ISO3166-1") or tags.get("ISO3166-1:alpha2") or "").strip().upper()
    t = t.replace("UAE", "AE").replace("PALESTINE", "PS").replace("ISR", "IL")
    if len(t) >= 2 and t[:2].isalpha():
        return t[:2]
    return ""

def gcc_cc(lat, lon, tags):
    c = _tag_cc(tags)
    if c in {"AE", "SA", "OM", "QA", "BH", "KW"}:
        return c
    if 25.7 <= lat <= 26.4 and 50.3 <= lon <= 50.85: return "BH"
    if 24.4 <= lat <= 26.25 and 50.7 <= lon <= 51.7: return "QA"
    if 28.45 <= lat <= 30.15 and 46.5 <= lon <= 48.55: return "KW"
    if 25.9 <= lat <= 26.7 and 56.05 <= lon <= 56.55: return "OM"   # Musandam
    if 22.6 <= lat <= 26.15 and 51.5 <= lon <= 56.6: return "AE"
    if 16.5 <= lat <= 26.6 and 51.8 <= lon <= 60.0: return "OM"
    return "SA"

def ilps_cc(lat, lon, tags):
    c = _tag_cc(tags)
    if c in {"IL", "PS"}:
        return c
    if 31.22 <= lat <= 31.62 and 34.20 <= lon <= 34.57: return "PS"   # Gaza
    if 31.33 <= lat <= 32.57 and 35.05 <= lon <= 35.58: return "PS"   # West Bank, untagged; western edge is approximate
    return "IL"

def sngm_cc(lat, lon, tags):
    c = _tag_cc(tags)
    if c in {"SN", "GM"}:
        return c
    if 13.05 <= lat <= 13.83 and -16.82 <= lon <= -13.80:
        if lon <= -16.55:
            return "GM" if 13.35 <= lat <= 13.55 else "SN"
        return "GM"
    return "SN"


def load_osm(folder):
    out = []
    if not folder.is_dir():
        return out
    for fp in sorted(folder.rglob("*.json")):
        try:
            data = json.loads(fp.read_text())
        except Exception:
            continue
        cc = (data.get("cc") or fp.stem).upper()
        for el in data.get("elements") or []:
            if (el.get("type"), el.get("id")) in seen_osm:
                continue
            seen_osm.add((el.get("type"), el.get("id")))
            tags = el.get("tags") or {}
            mm = tags.get("man_made")
            kind = "ww" if mm == "wastewater_plant" else "dw" if mm == "water_works" else None
            if not kind:
                continue
            pt = osm_el_pt(el)
            if not pt:
                continue
            typ = {"node": "n", "way": "w", "relation": "r"}.get(el.get("type"), "n")
            oid = el.get("id")
            cid = _id("ow", f"{typ}{oid}")
            if not cid:
                continue
            name = _name(tags.get("name") or tags.get("official_name") or ("Wastewater plant" if kind == "ww" else "Water works"))
            st = us_state(pt[1], pt[0], (tags.get("addr:state") or tags.get("is_in:state") or ""))
            url = f"https://www.openstreetmap.org/{el.get('type')}/{oid}"
            ecc = "GB" if (cc == "IE" and in_ni(pt[1], pt[0])) else cc
            if cc == "MY":   # the Geofabrik extract covers Malaysia, Singapore and Brunei
                ecc = "SG" if (1.15 <= pt[1] <= 1.48 and 103.6 <= pt[0] <= 104.1) else "BN" if (4.0 <= pt[1] <= 5.1 and 114.0 <= pt[0] <= 115.4) else "MY"
            if cc in {"GCC", "ILPS", "SNGM"}:
                lat, lon = pt[1], pt[0]
                tags = el.get("tags") or {}
                ecc = gcc_cc(lat, lon, tags) if cc == "GCC" else ilps_cc(lat, lon, tags) if cc == "ILPS" else sngm_cc(lat, lon, tags)
            op = _name(tags.get("operator")) if tags.get("operator") else ""
            out.append({
                "lon": pt[0], "lat": pt[1], "name": name, "kind": kind, "cc": ecc, "st": st if ecc == "US" else "",
                "src": "OpenStreetMap (ODbL)", "id": cid, "url": url, "note": op[:80],
            })
    return out

NAT_SRC = {
    "ca": ("Environment and Climate Change Canada, WSER reported data (Open Government Licence - Canada)", "https://open.canada.ca/data/en/dataset/9e11e114-ef0d-4814-8d93-24af23716489"),
    "au": ("Geoscience Australia, National Wastewater Treatment Facilities (CC BY 4.0)", "https://data.gov.au/data/dataset/wastewater-treatment-facilities"),
}

def load_national(folder):
    out = []
    for k, (src, url) in NAT_SRC.items():
        f = Path(folder) / f"{k}.json"
        if not f.is_file():
            continue
        for r in json.loads(f.read_text()):
            pt = _pt(r["lat"], r["lon"])
            if not pt:
                continue
            out.append({"lon": pt[0], "lat": pt[1], "name": _name(r["name"]), "kind": r["kind"], "cc": r["cc"], "st": "", "src": src,
                        "id": r["id"], "url": url, "note": r.get("note", "")})
    return out

def load_uwwtd(csv_path):
    out = []
    if not csv_path or not Path(csv_path).is_file():
        return out
    with open(csv_path, newline="", encoding="utf-8", errors="replace") as fh:
        r = csv.DictReader(fh)
        for row in r:
            # skip collecting systems that are not a plant, and inactive
            cs = (row.get("uwwCollectingSystem") or row.get("UWWCOLLECTINGSYSTEM") or "").upper()
            state = str(row.get("uwwState") or row.get("UWWSTATE") or "1")
            if cs == "NOTCON":
                continue
            if state not in ("1", "1.0", "active", ""):
                continue
            lat = row.get("uwwLatitude") or row.get("UWWLATITUDE") or row.get("lat")
            lon = row.get("uwwLongitude") or row.get("UWWLONGITUDE") or row.get("lon")
            pt = _pt(lat, lon)
            if not pt:
                continue
            cc = (row.get("rptMStateKey") or row.get("RPTMSTATEKEY") or row.get("country") or "").upper()[:2]
            pid = row.get("uwwCode") or row.get("UWWCODE") or row.get("thematicId") or ""
            cid = _id("eu", f"{cc}{pid}")
            if not cid:
                continue
            name = _name(row.get("uwwName") or row.get("UWWNAME") or "Urban wastewater plant")
            out.append({
                "lon": pt[0], "lat": pt[1], "name": name, "kind": "ww", "cc": cc, "st": "",
                "src": "EEA Waterbase UWWTD (CC BY 4.0)", "id": cid,
                "url": "https://www.eea.europa.eu/en/datahub/datahubitem-view/6244937d-1c2c-47f5-bdf1-33ca01ff1715",
                "note": "",
            })
    return out

def close(a, b, meters=400):
    if a.get("cc") == "CA":
        meters = 1500   # Canadian WSER points are effluent discharge points, usually up to ~1 km from the plant
    # rough degrees: 1 deg lat ~ 111km
    dlat = (a["lat"] - b["lat"]) * 111_000
    dlon = (a["lon"] - b["lon"]) * 111_000 * math.cos(math.radians(a["lat"]))
    return (dlat * dlat + dlon * dlon) ** 0.5 <= meters

def merge(primary, extra):
    """Keep primary; add extra points not within 400 m of a same-kind primary point."""
    grid = defaultdict(list)
    for p in primary:
        key = (round(p["lat"] * 50), round(p["lon"] * 50), p["kind"])  # ~2km cells
        grid[key].append(p)
    out = list(primary)
    ids = {p["id"] for p in out}
    for e in extra:
        if e["id"] in ids:
            # id clash: re-stamp extra
            e = dict(e); e["id"] = _id("ox", e["id"])
            if not e["id"] or e["id"] in ids:
                continue
        cell = (round(e["lat"] * 50), round(e["lon"] * 50), e["kind"])
        neigh = []
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                neigh.extend(grid.get((cell[0] + di, cell[1] + dj, e["kind"])) or [])
        if any(close(e, n) for n in neigh):
            continue
        out.append(e)
        ids.add(e["id"])
        grid[cell].append(e)
    return out


SRC_TPL = {
    "U.S. EPA ECHO / FRS, SIC 4941 (water supply)": "https://echo.epa.gov/detailed-facility-report?fid={ref}",
    "U.S. EPA ECHO / FRS, SIC 4952 (sewerage systems)": "https://echo.epa.gov/detailed-facility-report?fid={ref}",
    "OpenStreetMap (ODbL)": "https://www.openstreetmap.org/{ref}",
    "EEA Waterbase UWWTD (CC BY 4.0)": "https://www.eea.europa.eu/en/datahub/datahubitem-view/6244937d-1c2c-47f5-bdf1-33ca01ff1715",
    "Environment and Climate Change Canada, WSER reported data (Open Government Licence - Canada)": "https://open.canada.ca/data/en/dataset/9e11e114-ef0d-4814-8d93-24af23716489",
    "Geoscience Australia, National Wastewater Treatment Facilities (CC BY 4.0)": "https://data.gov.au/data/dataset/wastewater-treatment-facilities",
}
TIERS = [8.0, 2.0, 0.5, 0.125]   # cluster cell size in degrees, picked by map zoom on the server

def ref_of(r):
    u = r["url"]
    if "openstreetmap.org/" in u:
        t, i = u.rsplit("/", 2)[-2:]
        return f"{t}/{i}"
    if "fid=" in u:
        return u.split("fid=")[1]
    return ""

def write_db(rows, dest):
    import sqlite3
    dest = Path(dest)
    if dest.exists():
        dest.unlink()
    db = sqlite3.connect(dest)
    db.executescript("""
    PRAGMA page_size=4096; PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;
    CREATE TABLE s(id INTEGER PRIMARY KEY, label TEXT NOT NULL, tpl TEXT NOT NULL);
    CREATE TABLE p(cy INT NOT NULL, cx INT NOT NULL, uid TEXT NOT NULL, lon REAL NOT NULL, lat REAL NOT NULL, name TEXT NOT NULL,
                   k INT NOT NULL, cc TEXT NOT NULL, st TEXT NOT NULL, src INT NOT NULL, ref TEXT NOT NULL, note TEXT NOT NULL,
                   PRIMARY KEY(cy, cx, uid)) WITHOUT ROWID;
    CREATE UNIQUE INDEX p_uid ON p(uid);
    CREATE TABLE cl(t INT NOT NULL, gy INT NOT NULL, gx INT NOT NULL, n INT NOT NULL, nw INT NOT NULL, lat REAL NOT NULL, lon REAL NOT NULL,
                    PRIMARY KEY(t, gy, gx)) WITHOUT ROWID;
    CREATE TABLE m(k TEXT PRIMARY KEY, v TEXT NOT NULL);
    """)
    srcs = {}
    for r in rows:
        if r["src"] not in srcs:
            srcs[r["src"]] = len(srcs) + 1
            db.execute("INSERT INTO s VALUES(?,?,?)", (srcs[r["src"]], r["src"], SRC_TPL.get(r["src"], "")))
    cl = [defaultdict(lambda: [0, 0, 0.0, 0.0]) for _ in TIERS]
    for r in rows:
        cy, cx = int((r["lat"] + 90) * 8), int((r["lon"] + 180) * 8)
        db.execute("INSERT INTO p VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (cy, cx, r["id"], r["lon"], r["lat"], r["name"], 1 if r["kind"] == "ww" else 0,
                   r["cc"], r["st"], srcs[r["src"]], ref_of(r), r["note"]))
        for t, size in enumerate(TIERS):
            c = cl[t][(int((r["lat"] + 90) / size), int((r["lon"] + 180) / size))]
            c[0] += 1; c[1] += 1 if r["kind"] == "ww" else 0; c[2] += r["lat"]; c[3] += r["lon"]
    for t in range(len(TIERS)):
        db.executemany("INSERT INTO cl VALUES(?,?,?,?,?,?,?)",
                       [(t, gy, gx, v[0], v[1], round(v[2] / v[0], 4), round(v[3] / v[0], 4)) for (gy, gx), v in cl[t].items()])
    db.commit()
    db.execute("INSERT INTO m VALUES('rows',?)", (str(len(rows)),))
    db.execute("INSERT INTO m VALUES('countries',?)", (str(len({r["cc"] for r in rows})),))
    db.commit()
    db.execute("VACUUM")
    db.close()

def ship(dbpath, outdir, part=2_600_000):
    """zip -> base64 text parts (the repo ships large binaries as text parts, like gridtiles.b64.N)."""
    import base64, zipfile, io
    outdir = Path(outdir)
    for f in outdir.glob("water.db.b64.*"):
        f.unlink()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.write(dbpath, "water.sqlite")
    b = base64.b64encode(buf.getvalue())
    n = 0
    for i in range(0, len(b), part):
        (outdir / f"water.db.b64.{n}").write_bytes(b[i:i + part]); n += 1
    return len(buf.getvalue()), len(b), n

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default="/tmp/water_plants_build")
    ap.add_argument("--out", default="/tmp/water_plants.sqlite")
    ap.add_argument("--ship", default="")
    ap.add_argument("--report", default="docs/water-plants-coverage.md")
    a = ap.parse_args()
    cache = Path(a.cache)
    echo_dw = load_echo(cache / "us_water_supply_sic4941.json", "dw", "U.S. EPA ECHO / FRS, SIC 4941 (water supply)", lambda rid: f"https://echo.epa.gov/detailed-facility-report?fid={rid}")
    echo_ww = load_echo(cache / "us_sewerage_sic4952.json", "ww", "U.S. EPA ECHO / FRS, SIC 4952 (sewerage systems)", lambda rid: f"https://echo.epa.gov/detailed-facility-report?fid={rid}")
    eu = []
    for cand in cache.rglob("UWWTPS.csv"):
        eu = load_uwwtd(cand); break
    osm = load_osm(cache / "osm") + load_osm(cache / "osm_gf")
    # authoritative first: EPA in the U.S., EEA in Europe; OpenStreetMap fills gaps everywhere (400 m same-kind dedupe)
    us = merge(echo_dw + echo_ww, [r for r in osm if r["cc"] == "US"])
    nat = load_national(cache / "national")
    rest = merge(eu + nat, [r for r in osm if r["cc"] != "US"])
    rows = pack_rows(us + rest)
    write_db(rows, a.out)
    cov = coverage(rows)
    print("db", a.out, Path(a.out).stat().st_size, "rows", len(rows))
    if a.ship:
        z, b, n = ship(a.out, a.ship)
        print("zip", z, "b64", b, "parts", n)
    lines = ["# Water plant coverage", "", cov["note"], "", f"{cov['countries']} countries/territories.", "", "## By country (ISO 3166-1 alpha-2)", ""]
    lines += [f"- {cc}: {n:,}" for cc, n in cov["by_cc"].items()]
    lines += ["", "## U.S. by state", ""] + [f"- {st}: {n:,}" for st, n in cov["us_by_state"].items()]
    if cov["us_states_missing"]:
        lines += ["", "States with no EPA or OSM point in this build: " + ", ".join(cov["us_states_missing"])]
    lines += ["", "## By source", ""] + [f"- {s}: {n:,}" for s, n in cov["by_source"].items()]
    Path(a.report).write_text("\n".join(lines) + "\n")
    print(json.dumps({k: cov[k] for k in ("plants", "countries", "by_kind", "by_source", "us_states_present", "us_states_missing")}, indent=1))

def pack_rows(rows):
    rows = sorted(rows, key=lambda r: (r["cc"], r["st"] or "", r["name"].lower()))
    seen, out = set(), []
    for r in rows:
        if r["id"] in seen:
            continue
        seen.add(r["id"]); out.append(r)
    return out

def coverage(rows):
    by_cc = Counter(r["cc"] for r in rows)
    us = Counter(r["st"] for r in rows if r["cc"] == "US" and r["st"] in US_STATES)
    return {"plants": len(rows), "countries": len(by_cc), "by_kind": dict(Counter(r["kind"] for r in rows)), "by_cc": dict(by_cc.most_common()),
            "us_by_state": dict(sorted(us.items())), "us_states_present": len(us), "us_states_missing": sorted(US_STATES - set(us)),
            "by_source": dict(Counter(r["src"] for r in rows)),
            "note": f"{len(rows):,} plants with source-cited coordinates; U.S. {sum(by_cc[c] for c in ('US',)):,}."}

if __name__ == "__main__":
    main()
