"""Build app/signal_places.json from the bundled GeoNames cities + admin1 + countries.

Compact on purpose: one ascii name per city, at most three candidates (largest population),
admin1 and country labels. Curated conflict places are added in signal_place.py.
Run from the repo: python3 tools/build_signal_places.py
"""
import gzip, json, os, sys, unicodedata
APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")
sys.path.insert(0, APP)
import geo

def fold(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return " ".join(geo.nw(w) for w in geo.TOK.findall(s))

def main():
    G = geo.gaz()
    cities = {}
    for row in G.cities:
        name, ascii_name, lat, lon, cc, _a1, pop = row[0], row[1], row[2], row[3], row[4], row[5], row[6]
        if not pop or pop < 15000: continue
        key = fold(ascii_name or name)
        if len(key) < 4 or key in geo.COMMON_HARD or key in geo.MONTHS: continue
        cities.setdefault(key, []).append([round(lat, 4), round(lon, 4), cc, int(pop), (ascii_name or name)[:48]])
    for key, rows in list(cities.items()):
        rows.sort(key=lambda r: -r[3])
        # Unique small names stay. Common names keep the largest few so a country cue can pick.
        cities[key] = rows[:3]
    admin = {}
    for code, a in G.admin1.items():
        if not a.get("label"): continue
        key = fold(a.get("name") or "")
        if len(key) < 4 or key in geo.COMMON_HARD: continue
        lab = a["label"]
        row = [round(lab[0], 4), round(lab[1], 4), code.split(".")[0], (a.get("name") or key)[:48]]
        if key in admin and not code.startswith("US."): continue
        admin[key] = row
    countries = {}
    for iso, c in G.countries.items():
        lab = c.get("label")
        if not lab: continue
        names = {c.get("name") or ""}
        names.update(c.get("ne_names") or [])
        names.update(geo.COUNTRY_ALIASES.get(iso) or [])
        for n in names:
            key = fold(n)
            if len(key) < 3 or key in ("us",) and False: pass
            if len(key) < 4 and key not in ("usa", "uk", "uae"): continue
            if key in geo.MONTHS: continue
            countries[key] = [round(lab[0], 4), round(lab[1], 4), iso, (c.get("name") or n)[:48]]
    out = {"c": cities, "a": admin, "k": countries}
    dest = os.path.join(APP, "signal_places.json.gz")
    with gzip.open(dest, "wt", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"), ensure_ascii=False)
    print(dest, os.path.getsize(dest), "cities", len(cities), "admin", len(admin), "countries", len(countries))

if __name__ == "__main__":
    main()
