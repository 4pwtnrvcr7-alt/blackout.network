"""Build app/water_static/county_centroids.json from the U.S. Census Bureau 2023 Gazetteer (public domain).
{"<5-digit county FIPS>": [lat, lon, "County name", "ST"]}. Used only to place EPA drinking-water systems that carry a county FIPS
but no coordinates (EPA ECHO SDWA has none). Markers drawn from it are labelled "county centre", never a plant location.
Run: python3 tools/build_county_centroids.py"""
import io, json, os, urllib.request, zipfile
URL = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2023_Gazetteer/2023_Gaz_counties_national.zip"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "water_static", "county_centroids.json")
raw = urllib.request.urlopen(urllib.request.Request(URL, headers={"User-Agent": "BlackoutNetwork-build/1.0"}), timeout=60).read()
z = zipfile.ZipFile(io.BytesIO(raw)); txt = z.read(z.namelist()[0]).decode("utf-8", "replace").splitlines()
hdr = [h.strip() for h in txt[0].split("\t")]; ix = {h: i for i, h in enumerate(hdr)}
out = {}
for ln in txt[1:]:
    p = ln.split("\t")
    if len(p) < len(hdr): continue
    out[p[ix["GEOID"]].strip()] = [round(float(p[ix["INTPTLAT"]]), 4), round(float(p[ix["INTPTLONG"]]), 4), p[ix["NAME"]].strip(), p[ix["USPS"]].strip()]
with open(OUT, "w") as f: json.dump(out, f, separators=(",", ":"), sort_keys=True)
print(len(out), "counties ->", os.path.relpath(OUT))
