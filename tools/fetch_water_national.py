#!/usr/bin/env python3
"""Download open national wastewater inventories and normalise them to JSON rows for build_water_db.py.

  CA  Environment and Climate Change Canada, Wastewater Systems Effluent Regulations (WSER) reported data. Open Government Licence - Canada.
      Location is the reported final discharge point (not the plant fence line); the row note says so.
  AU  Geoscience Australia, National Wastewater Treatment Facilities (2026). CC BY 4.0. FileGDB, read with pyogrio.

Usage: python3 tools/fetch_water_national.py --cache /tmp/water_plants_build      (needs: pip install pyogrio, in a venv)
"""
import argparse, csv, json, re, subprocess, zipfile
from pathlib import Path

CA_URL = "https://data-donnees.az.ec.gc.ca/api/file?path=%2Fsubstances%2Fplaninfrastruture%2Fwastewater-systems-effluent-regulations-reported-data%2FResaeu-Wser-identification.csv"
AU_URL = "https://d28rz98at9flks.cloudfront.net/151185/151185_01_2.zip"
UA = "BLACKOUT.NETWORK/water-plants (+https://blackout.network)"
PROV = {"Alberta": "AB", "British Columbia": "BC", "Manitoba": "MB", "New Brunswick": "NB", "Newfoundland and Labrador": "NL", "Nova Scotia": "NS",
        "Ontario": "ON", "Prince Edward Island": "PE", "Quebec": "QC", "Saskatchewan": "SK", "Yukon": "YT", "Northwest Territories": "NT", "Nunavut": "NU"}

def curl(url, dest):
    subprocess.check_call(["curl", "-sSL", "-m", "120", "-A", UA, "-o", str(dest), url])

def ca(cache):
    f = cache / "ca_wser.csv"
    if not f.exists():
        curl(CA_URL, f)
    rows = list(csv.reader(open(f, encoding="latin-1")))
    out = []
    for r in rows[1:]:
        try:
            lat, lon = float(r[30]), float(r[31])
        except ValueError:
            continue
        if r[42].strip().lower() != "operational" or not (41 < lat < 84 and -142 < lon < -52):
            continue
        city = r[3].strip().title(); prov = PROV.get(r[4].strip(), r[4].strip())
        out.append({"id": "ca" + re.sub(r"\W", "", r[0]), "name": (r[2].strip() or "Wastewater system")[:120], "lat": round(lat, 5), "lon": round(lon, 5),
                    "kind": "ww", "cc": "CA", "st": "", "note": ", ".join(x for x in (city, prov) if x) + " · reported discharge-point location"})
    return out

def au(cache):
    import pyogrio
    z = cache / "au.zip"
    if not z.exists():
        curl(AU_URL, z)
    d = cache / "au_gdb"
    if not d.exists():
        zipfile.ZipFile(z).extractall(d)
    gdb = next(d.glob("*.gdb"))
    meta, _f, _g, cols = pyogrio.raw.read(str(gdb), read_geometry=False)
    ix = {n: i for i, n in enumerate(meta["fields"])}
    out = []
    for i in range(len(cols[0])):
        g = lambda k: cols[ix[k]][i]
        if str(g("STATUS") or "").strip().lower() in ("decommissioned", "closed", "abandoned", "demolished"):
            continue
        lat, lon = g("LATITUDE"), g("LONGITUDE")
        if lat is None or lon is None or not (-45 < float(lat) < -8 and 110 < float(lon) < 160):
            continue
        gid = re.sub(r"[^0-9a-fA-F]", "", str(g("GlobalID") or ""))[:16] or str(i)
        out.append({"id": "au" + gid, "name": str(g("FEATURE_NAME") or "Wastewater treatment facility").strip()[:120], "lat": round(float(lat), 5), "lon": round(float(lon), 5),
                    "kind": "ww", "cc": "AU", "st": "", "note": ", ".join(x for x in (str(g("LOCALITY") or "").title(), str(g("STATE") or "")) if x)})
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--cache", default="/tmp/water_plants_build"); a = ap.parse_args()
    cache = Path(a.cache) / "national"; cache.mkdir(parents=True, exist_ok=True)
    for name, fn in (("ca", ca), ("au", au)):
        rows = fn(cache)
        (cache / f"{name}.json").write_text(json.dumps(rows, separators=(",", ":"), ensure_ascii=False))
        print(name, len(rows))

if __name__ == "__main__":
    main()
