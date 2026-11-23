"""Build us_census_places_0..3.tsv and us_counties.tsv from the Census Bureau 2024 national gazetteers
(https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/, public domain) and drop names
already in cities.json or small_places_*.tsv.
Run: python3 build_us_census.py /path/to/2024_Gaz_place_national.txt /path/to/2024_Gaz_counties_national.txt
"""
import os, sys, json, re, unicodedata, glob
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import geo

def clean_place(n):
    n = (n or "").strip()
    suf = re.compile(r"\s+(city|town|village|CDP|municipality|borough|unified government|consolidated government|metro government|urban county|city and borough|city and county|charter township|charter municipality|comunidad|zona urbana|plantation|gore|grant|location|township)$", re.I)
    while True:
        m = suf.search(n)
        if not m:
            break
        n = n[:m.start()].strip()
    return n

DATA = os.path.dirname(os.path.abspath(__file__))
have = set()
for c in geo.gaz().cities:
    if c[4] == "US":
        have.add((geo.key_of(c[0]), (c[5] or "").split(".")[-1]))
        if c[1]:
            have.add((geo.key_of(c[1]), (c[5] or "").split(".")[-1]))
for src in glob.glob(os.path.join(DATA, "small_places_*.tsv")):
    for line in open(src, encoding="utf-8"):
        f = line.rstrip("\n").split("\t")
        if len(f) >= 6 and f[4] == "US":
            have.add((geo.key_of(f[0]), f[5]))

places = []
with open(sys.argv[1], encoding="latin-1") as fh:
    next(fh)
    for line in fh:
        p = line.rstrip("\n").split("\t")
        if len(p) < 12:
            continue
        st, nm = p[0].strip(), clean_place(p[3])
        k = geo.key_of(nm)
        if len(k) < 3 or (k, st) in have:
            continue
        try:
            lat, lon = float(p[-2].strip()), float(p[-1].strip())
        except ValueError:
            continue
        places.append("%s\t\t%.4f\t%.4f\tUS\t%s\t0" % (nm, lat, lon, st))
        have.add((k, st))
counties = []
with open(sys.argv[2], encoding="latin-1") as fh:
    next(fh)
    for line in fh:
        p = line.rstrip("\n").split("\t")
        if len(p) < 10:
            continue
        st, raw = p[0].strip(), p[3].strip()
        nm = re.sub(r"\s+(County|Parish|Borough|Census Area|Municipality|city|City and Borough)$", "", raw, flags=re.I).strip()
        if not nm:
            continue
        try:
            lat, lon = float(p[-2].strip()), float(p[-1].strip())
        except ValueError:
            continue
        counties.append("%s\t%s\t%.4f\t%.4f\tUS\t%s\t0" % (nm, raw, lat, lon, st))
N = 4
for j in range(N):
    chunk = places[j::N]
    open(os.path.join(DATA, "us_census_places_%s.tsv" % j), "w", encoding="utf-8").write("\n".join(chunk) + ("\n" if chunk else ""))
open(os.path.join(DATA, "us_counties.tsv"), "w", encoding="utf-8").write("\n".join(counties) + "\n")
print(len(places), "places", len(counties), "counties")
