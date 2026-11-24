"""Build app/netmap_static/hydro.json (pt1815u stage 2): hydroelectric plants of 25 MW and up, worldwide.
Source: WRI Global Power Plant Database v1.3.0 (2021), CC BY 4.0, keyless download:
  https://datasets.wri.org/dataset/globalpowerplantdatabase (globalpowerplantdatabasev130.zip -> global_power_plant_database.csv)
Hoover Dam's AZ and NV units are merged into one point. Usage: python3 tools/build_hydro.py CSV > app/netmap_static/hydro.json"""
import csv, json, sys
rows = [x for x in csv.DictReader(open(sys.argv[1], encoding="utf-8")) if x["primary_fuel"] == "Hydro" and float(x["capacity_mw"] or 0) >= 25]
p = []; hoover = None
for x in rows:
    try: yr = int(float(x["commissioning_year"])) if x["commissioning_year"] else 0
    except ValueError: yr = 0
    r = [round(float(x["longitude"]), 3), round(float(x["latitude"]), 3), x["name"][:70], round(float(x["capacity_mw"])), (x["owner"] or "")[:60], yr, x["country_long"][:40], x["gppd_idnr"]]
    if x["name"].startswith("Hoover Dam ("):
        if hoover: hoover[3] += r[3]; hoover[5] = min(hoover[5], yr) if yr else hoover[5]; continue
        r[2] = "Hoover Dam"; r[7] = "USA-HOOVER"; hoover = r
    p.append(r)
p.sort(key=lambda r: -r[3])
json.dump({"credit": "Hydropower plants: WRI Global Power Plant Database v1.3.0 (2021), CC BY 4.0", "cols": ["lon", "lat", "name", "mw", "owner", "year", "country", "id"],
           "min_mw": 25, "p": p}, sys.stdout, separators=(",", ":"), ensure_ascii=False)
