"""Builds heatmap_data/nws_zones.json for geo.py (Nov 21 2026): NWS GIS public-zone (z_*), county (c_*) and marine (mz*) shapefiles
from https://www.weather.gov/gis/ (unzipped into z/, c/, mz/) plus office names from api.weather.gov/offices/<CWA>. Needs pyshp."""
import shapefile, json, urllib.request, collections, time, re
Z=collections.defaultdict(list)
r=shapefile.Reader('z/z_16ap26')
for s,cwa,tz,fe,zone,name,sz,lon,lat,short in r.iterRecords():
    for c in cwa.split():  # some zones list several CWAs? keep first 3 letters each
        Z[c[:3]].append([name.strip(), s, round(lat,3), round(lon,3), "Z"+sz, fe.strip()])
r=shapefile.Reader('c/c_16ap26')
for s,cwa,cn,fips,tz,fe,lon,lat in r.iterRecords():
    for c in re.findall(r"[A-Z]{3}", cwa):
        Z[c].append([cn.strip(), s, round(lat,3), round(lon,3), "C"+fips, fe.strip()])
r=shapefile.Reader('mz/mz16ap26')
for zid,wfo,gl,name,lon,lat in r.iterRecords():
    Z[wfo].append([name.strip(), zid[:2], round(lat,3), round(lon,3), "M"+zid, ""])
off={}
for c in sorted(Z):
    try:
        d=json.load(urllib.request.urlopen(urllib.request.Request(f"https://api.weather.gov/offices/{c}",headers={"User-Agent":"blackout.network geodata build"}),timeout=20))
        off[c]=d["name"]
    except Exception as e: print("miss",c,e)
    time.sleep(0.15)
json.dump({"source":"NWS GIS zone (z_16ap26), county (c_16ap26), marine (mz16ap26) shapefiles + api.weather.gov/offices","offices":off,"zones":Z},open("nws_zones.json","w"),separators=(",",":"))
print(len(off),sum(len(v) for v in Z.values()))
