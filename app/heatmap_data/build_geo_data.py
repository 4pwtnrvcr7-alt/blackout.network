"""One-off builder for the heat map's offline gazetteer (free data: GeoNames cities15000/countryInfo/admin1Codes, Natural Earth admin0/admin1).
Writes compact JSON into heatmap_data/. Source downloads live in /workspace/geodata."""
import json, os, zipfile, unicodedata
SRC = "/workspace/geodata"; OUT = os.path.dirname(os.path.abspath(__file__))
def asc(s): return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
countries = {}
for ln in open(f"{SRC}/countryInfo.txt", encoding="utf-8"):
    if ln.startswith("#"): continue
    p = ln.rstrip("\n").split("\t")
    countries[p[0]] = {"iso2": p[0], "iso3": p[1], "name": p[4], "capital": p[5], "pop": int(p[7] or 0), "neighbours": [x for x in p[17].split(",") if x]}
ne0 = json.load(open(f"{SRC}/ne_50m_admin_0_countries.geojson"))
for f in ne0["features"]:
    pr = f["properties"]; iso = pr["ISO_A2_EH"]
    if iso in countries:
        countries[iso]["label"] = [round(pr["LABEL_Y"], 4), round(pr["LABEL_X"], 4)]
        countries[iso]["ne_names"] = sorted({pr[k] for k in ("NAME", "NAME_LONG", "ADMIN", "NAME_EN", "FORMAL_EN") if pr.get(k)})
admin1 = {}
for ln in open(f"{SRC}/admin1CodesASCII.txt", encoding="utf-8"):
    code, name, ascii_, gid = ln.rstrip("\n").split("\t")
    admin1[code] = {"code": code, "name": name, "ascii": ascii_}
ne1 = json.load(open(f"{SRC}/ne_10m_admin_1_states_provinces.geojson"))
for f in ne1["features"]:
    pr = f["properties"]; c = pr.get("gn_a1_code")
    if not c or c not in admin1: continue
    a = admin1[c]; a["label"] = [round(pr["latitude"], 4), round(pr["longitude"], 4)]
    a["type"] = pr.get("type_en"); a["postal"] = pr.get("postal") if c.startswith("US.") else None
    alts = [x for x in (pr.get("name_alt") or "").split("|") if x]
    a["alts"] = sorted({x for x in alts + [pr.get("name"), pr.get("name_en")] if x})
cities = []
with zipfile.ZipFile(f"{SRC}/cities15000.zip") as z:
    for ln in z.open("cities15000.txt").read().decode("utf-8").splitlines():
        p = ln.split("\t")
        alts = [a for a in p[3].split(",") if a and a.isascii() and len(a) >= 4 and a[0].isupper() and " " not in a.strip()[:0]]
        cities.append([p[1], p[2], round(float(p[4]), 4), round(float(p[5]), 4), p[8], p[8] + "." + p[10], int(p[14] or 0), p[7], alts[:25]])
json.dump(countries, open(f"{OUT}/countries.json", "w"))
json.dump(admin1, open(f"{OUT}/admin1.json", "w"))
json.dump(cities, open(f"{OUT}/cities.json", "w"))
print(len(countries), len(admin1), len(cities))
