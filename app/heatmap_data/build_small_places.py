"""Builds small_places_0..4.tsv (towns of 1,000+): GeoNames cities500 populated places (https://download.geonames.org/export/dump/cities500.zip, CC BY 4.0)
that cities.json does not already have. Columns: name, ascii name (blank when the same), lat, lon, country, admin1 code, population.
Used only by geo.small_place() for a town a story marks as a place ("in Riverhead"), inside the story's country (v11, Nov 21 2026).
Run: python3 build_small_places.py /path/to/cities500.txt"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import geo
G = geo.gaz(); have = {(geo.key_of(c[0]), c[4]) for c in G.cities}
out = []
for line in open(sys.argv[1], encoding="utf-8"):
    f = line.rstrip("\n").split("\t")
    if f[6] != "P" or f[7] in ("PPLH", "PPLQ", "PPLW", "PPLX"): continue
    k = geo.key_of(f[1])
    if len(k) < 4 or (k, f[8]) in have or int(f[14] or 0) < 1000: continue
    out.append(f"{f[1]}\t{f[2] if f[2] != f[1] else ''}\t{float(f[4]):.3f}\t{float(f[5]):.3f}\t{f[8]}\t{f[10]}\t{int(f[14] or 0)}")
D = os.path.dirname(os.path.abspath(__file__)); N = 5
for j in range(N):      # shards under 1 MB each (GitHub API pushes)
    open(os.path.join(D, f"small_places_{j}.tsv"), "w", encoding="utf-8").write("\n".join(out[j::N]) + "\n")
print(len(out))
