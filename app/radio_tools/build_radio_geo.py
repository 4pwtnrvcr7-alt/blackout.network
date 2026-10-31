#!/usr/bin/env python3
"""Build radio_geo.json for the Radio tab's location picker (re-run any time; public data only):
 NOAA NWR transmitters (weather.gov CCL.js), WXRadio.org stream mounts, public KiwiSDR receivers (receiverbook.de map),
 airports with ICAO codes (jetdata/airports.csv, OurAirports), radio-browser.info country list, US state FIPS (from NWR SAME codes)."""
import csv, json, os, re, urllib.request
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(BASE, "radio_geo.json")
UA = {"User-Agent": "blackout.network radio catalog builder"}
get = lambda u, t=30: urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=t).read().decode("utf-8", "ignore")
# NOAA Weather Radio
js = get("https://www.weather.gov/source/nwr/JS/CCL.js"); F = {}
for name, i, v in re.findall(r'^(\w+)\[(\d+)\]\s*=\s*"(.*)";', js, re.M): F.setdefault(int(i), {})[name] = v
nwr, states = {}, {}
for r in F.values():
    cs = r.get("CALLSIGN"); st = r.get("ST")
    if not cs or not r.get("LAT"): continue
    if st and r.get("SAME"): states.setdefault(st, {"code": st, "name": r.get("STATE", st), "fips": r["SAME"][1:3]})
    if cs in nwr: nwr[cs]["counties"].add(r.get("COUNTY", "")); continue
    try: lat, lon = float(r["LAT"]), float(r["LON"])
    except ValueError: continue
    nwr[cs] = {"cs": cs, "f": r.get("FREQ"), "site": r.get("SITENAME"), "st": r.get("SITESTATE") or st, "lat": round(lat, 3), "lon": round(lon, 3),
               "status": r.get("STATUS"), "wfo": (r.get("WFO") or "").split("|")[0], "counties": {r.get("COUNTY", "")}}
for v in nwr.values(): v["counties"] = sorted(c for c in v["counties"] if c)[:6]
# WXRadio.org mounts -> callsign
wx = {}
try:
    d = json.loads(get("https://wxradio.org/status-json.xsl"))["icestats"]["source"]
    for s in (d if isinstance(d, list) else [d]):
        mnt = s.get("listenurl", "").rsplit("/", 1)[-1]; m = re.search(r"-([KW][A-Z]{1,3}\d{2,3})$", mnt)
        if m: wx[m.group(1)] = "https://wxradio.org/" + mnt
except Exception as ex: print("wxradio:", ex)
for cs, u in wx.items():
    if cs in nwr: nwr[cs]["wx"] = u
# KiwiSDR receivers
kiwis = []
try:
    h = get("https://www.receiverbook.de/map?type=kiwisdr"); m = re.search(r"var receivers = (\[.*?\]);\s*\n", h, re.S)
    for site in json.loads(m.group(1)):
        lon, lat = site["location"]["coordinates"]
        for r in site.get("receivers", []):
            if r.get("type") == "KiwiSDR" and r.get("url"): kiwis.append({"label": r["label"][:90], "url": r["url"], "lat": round(lat, 2), "lon": round(lon, 2)})
except Exception as ex: print("kiwis:", ex)
# Airports with ICAO codes and scheduled service (LiveATC search links)
aps = []
with open(os.path.join(BASE, "jetdata", "airports.csv"), newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if r["type"] in ("large_airport", "medium_airport") and r["scheduled_service"] == "yes" and re.match(r"^[A-Z]{4}$", r["icao_code"] or r["ident"]):
            aps.append({"icao": r["icao_code"] or r["ident"], "name": r["name"][:60], "city": r["municipality"][:40], "cc": r["iso_country"], "rg": r["iso_region"],
                        "lat": round(float(r["latitude_deg"]), 3), "lon": round(float(r["longitude_deg"]), 3), "big": r["type"] == "large_airport"})
# Countries (names + label point from the Heat Map's Natural Earth country table)
ct = json.load(open(os.path.join(BASE, "heatmap_data", "countries.json")))
countries = sorted([{"cc": k, "name": v["name"], "lat": round(v["label"][0], 2), "lon": round(v["label"][1], 2)} for k, v in ct.items() if v.get("label")], key=lambda x: x["name"])
out = {"built": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "nwr": list(nwr.values()), "states": sorted(states.values(), key=lambda s: s["name"]),
       "kiwis": kiwis, "airports": aps, "countries": countries,
       "sources": {"nwr": "https://www.weather.gov/nwr/station_listing", "wx": "https://wxradio.org/", "kiwis": "https://www.receiverbook.de/map?type=kiwisdr",
                   "airports": "https://ourairports.com/data/", "countries": "Natural Earth (heatmap_data/countries.json)"}}
json.dump(out, open(OUT, "w"), separators=(",", ":"))
print(f"nwr {len(nwr)} (wx streams {sum(1 for v in nwr.values() if 'wx' in v)}), states {len(states)}, kiwis {len(kiwis)}, airports {len(aps)}, countries {len(countries)}, {os.path.getsize(OUT)//1024} KB")
