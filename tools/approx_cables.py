"""Add approximate routes for major undersea cables OSM does not map end-to-end.

Landing coordinates are Wikidata (CC0) or, where noted, OpenStreetMap (ODbL).
Landing place lists are from operator announcements compiled on Wikipedia (CC BY-SA).
TeleGeography / Submarine Cable Map data is not used.

Usage: python3 tools/approx_cables.py
Writes into app/netmap_static/cables.json (idempotent: replaces features with s=approx
and the OSM AAE-1 Hong Kong approach stub we add, leaves everything else alone).
"""
import json, math, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEO = os.path.join(ROOT, "app", "netmap_static", "cables.json")
OSM_RAW = "/workspace/launch/team/review/release/stage2/osm_cables.json"

# lon, lat. Sources: wd = Wikidata P625 (CC0); osm = OpenStreetMap (ODbL).
# Abu Talat (Egypt) is omitted: no Wikidata or OSM coordinate was found.
# Akwa Ibom State (2Africa) is omitted: Wikipedia names the state, not a landing town.
P = {
    "Toulon": (5.931, 43.125),
    "Catania": (15.090, 37.503),
    "Marmaris": (28.271, 36.856),
    "Yanbu": (38.062, 24.089),
    "Al Hudaydah": (42.951, 14.802),
    "Haramous": (43.148, 11.595),          # Djibouti City; Haramous CLS has no WD/OSM point
    "Qalhat": (59.370, 22.700),
    "Fujairah": (56.334, 25.122),
    "Karachi": (67.010, 24.860),
    "Matara": (80.533, 5.950),
    "Ngwe Saung": (94.392, 16.858),
    "Kuakata": (90.117, 21.817),
    "Medan": (98.674, 3.589),
    "Malacca": (102.251, 2.200),
    "Tuas": (103.650, 1.317),
    "Marseille": (5.376, 43.297),
    "Bari": (16.867, 41.125),
    "Chania": (24.017, 35.517),
    "Jeddah": (39.161, 21.529),
    "Djibouti": (43.148, 11.595),
    "Aden": (45.033, 12.800),
    "Al Bustan": (58.612, 23.566),
    "Doha": (51.529, 25.286),
    "Mumbai": (72.878, 19.076),
    "Satun": (100.068, 6.615),
    "Songkhla": (100.597, 7.206),
    "Butterworth": (100.366, 5.394),
    "Sihanoukville": (103.500, 10.633),
    "Vung Tau": (107.070, 10.351),
    "Cape D Aguilar": (114.261, 22.208),
    "Mombasa": (39.667, -4.050),
    "Victoria": (55.454, -4.624),
    "Berbera": (45.013, 10.440),
    "Mogadishu": (45.342, 2.039),
    "Bosaso": (49.183, 11.283),
    "Kulhudhuffushi": (73.070, 6.623),
    "Barcelona": (2.177, 41.383),
    "Genoa": (8.934, 44.407),
    "Tympaki": (24.768, 35.072),
    "Port Said": (32.306, 31.263),
    "Ras Gharib": (33.078, 28.360),
    "Duba": (35.696, 27.349),
    "Nacala": (40.683, -14.550),
    "Mahajanga": (46.317, -15.717),
    "Maputo": (32.573, -25.969),
    "Amanzimtoti": (30.883, -30.050),
    "Gqeberha": (25.600, -33.958),
    "Yzerfontein": (18.150, -33.351),
    "Duynefontein": (18.431, -33.668),     # OSM CLS also exists; WD settlement used if not swapped
    "Luanda": (13.230, -8.815),
    "Moanda": (12.350, -5.930),
    "Pointe-Noire": (11.850, -4.798),
    "Libreville": (9.440, 0.408),
    "Lagos": (3.394, 6.456),
    "Accra": (-0.197, 5.556),
    "Abidjan": (-4.027, 5.336),
    "Dakar": (-17.432, 14.673),
    "Telde": (-15.417, 27.998),
    "Carcavelos": (-9.334, 38.687),
    "Bude": (-4.542, 50.824),
    "Manama": (50.583, 26.217),            # Wikidata P559 terminus of 2Africa
    "Moroni": (43.254, -11.704),           # Wikidata P559 terminus of 2Africa
    "Dar es Salaam": (39.280, -6.816),
}

# Mtwapa was not in the WD resolve batch as its own item in coords_by_q... I need to check.
# I didn't include Mtwapa in the resolve list! I had Mtwapa in the 2Africa place list but
# forgot to add it to titles. Let me not use a guessed Mtwapa. Wikipedia lists both Mtwapa
# and Mombasa; Mombasa is enough if Mtwapa coords are missing.

# Water waypoints (public-domain geography, not a commercial cable map).
W = {
    "w_med_s": (10.0, 38.2),
    "w_ionian": (18.0, 36.5),
    "w_aegean_s": (25.0, 34.8),
    "w_port_said": (32.40, 31.40),
    "w_suez_s": (32.40, 29.80),
    "w_gulf_suez": (33.60, 27.40),
    "w_red_n": (36.00, 24.50),
    "w_red_m": (38.50, 20.00),
    "w_red_s": (41.50, 16.50),
    "w_bab": (43.40, 12.55),
    "w_aden": (46.50, 12.80),
    "w_aden_e": (52.00, 15.50),
    "w_oman": (60.00, 21.50),
    "w_arabian": (64.00, 23.00),
    "w_ind_w": (70.00, 16.00),
    "w_ind_s": (76.00, 7.20),
    "w_lanka_s": (81.50, 5.40),
    "w_bob_s": (88.00, 6.50),
    "w_malacca_w": (95.50, 6.00),
    "w_malacca": (100.50, 3.00),
    "w_sing": (104.20, 1.20),
    "w_scs_s": (107.00, 6.00),
    "w_scs": (110.50, 15.00),
    "w_hk": (114.00, 21.80),
    "w_gulf": (57.50, 25.00),
    "w_cape": (18.00, -35.20),
    "w_waf_s": (10.00, -10.00),
    "w_waf_m": (3.00, 0.50),
    "w_waf_n": (-15.00, 12.00),
    "w_canary": (-16.00, 25.00),
    "w_gibraltar": (-7.00, 35.90),
    "w_mozambique": (40.00, -18.00),
    "w_horn": (52.00, 10.00),
}

def r3(p):
    return [round(float(p[0]), 3), round(float(p[1]), 3)]

def pts(*names):
    out = []
    for n in names:
        if n in P:
            out.append(r3(P[n]))
        elif n in W:
            out.append(r3(W[n]))
        else:
            raise KeyError(n)
    # drop exact consecutive duplicates
    tight = []
    for p in out:
        if not tight or p != tight[-1]:
            tight.append(p)
    return tight

def feat(name, coords, kind="trunk"):
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": coords},
        "properties": {
            "n": name,
            "op": "",
            "s": "approx",
            "approx": True,
            "leg": kind,
        },
    }

# Mtwapa skipped until we confirm coords; Mombasa covers Kenya on the trunk.
CABLES = {
    "SEA-ME-WE 5": {
        "trunk": [
            "Toulon", "w_med_s", "Catania", "w_ionian", "Marmaris",
            "w_port_said", "w_suez_s", "w_gulf_suez", "w_red_n", "Yanbu",
            "w_red_m", "w_red_s", "Al Hudaydah", "w_bab", "Haramous",
            "w_aden", "w_aden_e", "Qalhat", "w_arabian", "Karachi",
            "w_ind_w", "w_ind_s", "Matara", "w_lanka_s", "w_bob_s",
            "w_malacca_w", "w_malacca", "Malacca", "Tuas",
        ],
        "branches": [
            ["Qalhat", "w_gulf", "Fujairah"],
            ["w_bob_s", "Kuakata"],
            ["w_malacca_w", "Ngwe Saung"],
            ["Malacca", "Medan"],
        ],
    },
    "AAE-1": {
        "trunk": [
            "Marseille", "w_med_s", "Bari", "w_ionian", "Chania",
            "w_port_said", "w_suez_s", "w_gulf_suez", "w_red_n", "Jeddah",
            "w_red_m", "w_red_s", "w_bab", "Djibouti", "w_aden", "w_aden_e",
            "Al Bustan", "w_arabian", "Karachi", "Mumbai", "w_ind_s",
            "w_lanka_s", "w_bob_s", "w_malacca_w", "Satun", "Songkhla",
            "Butterworth", "w_scs_s", "w_scs", "w_hk", "Cape D Aguilar",
        ],
        "branches": [
            ["w_aden", "Aden"],
            ["Al Bustan", "w_gulf", "Fujairah"],
            ["w_gulf", "Doha"],
            ["w_malacca_w", "Ngwe Saung"],
            ["Butterworth", "Sihanoukville"],
            ["w_scs_s", "Vung Tau"],
        ],
    },
    "PEACE Cable": {
        "trunk": [
            "Marseille", "w_med_s", "w_port_said", "w_suez_s", "w_gulf_suez",
            "w_red_n", "w_red_m", "w_red_s", "w_bab", "Haramous",
            "w_aden", "w_horn", "Mombasa", "w_ind_s", "w_lanka_s",
            "Kulhudhuffushi", "w_malacca_w", "w_malacca", "Tuas",
        ],
        "branches": [
            ["Haramous", "Berbera"],
            ["w_horn", "Bosaso"],
            ["w_horn", "Mogadishu"],
            ["Mombasa", "Victoria"],
            ["w_ind_w", "Karachi"],
        ],
    },
    "2Africa": {
        # Europe / Med / Red Sea / east Africa / south / west Africa / back to Europe
        "trunk": [
            "Barcelona", "Marseille", "Genoa", "Tympaki", "Port Said",
            "Ras Gharib", "w_red_n", "Duba", "Yanbu", "Jeddah",
            "w_red_m", "w_red_s", "w_bab", "Djibouti", "Berbera",
            "Mogadishu", "Mombasa", "Dar es Salaam", "Nacala",
            "w_mozambique", "Maputo", "Amanzimtoti", "Gqeberha",
            "w_cape", "Yzerfontein", "Duynefontein", "Luanda", "Moanda",
            "Pointe-Noire", "Libreville", "Lagos", "Accra", "Abidjan",
            "Dakar", "w_canary", "Telde", "Carcavelos", "Bude",
        ],
        "branches": [
            ["Jeddah", "w_gulf", "Manama"],
            ["w_mozambique", "Mahajanga"],
            ["w_mozambique", "Moroni"],
        ],
    },
}


def rdp(pts, eps):
    if len(pts) < 3:
        return pts
    a, b = pts[0], pts[-1]
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = (dx * dx + dy * dy) or 1e-12
    i, dm = 0, -1
    for k in range(1, len(pts) - 1):
        p = pts[k]
        t = max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L))
        qx, qy = a[0] + t * dx - p[0], a[1] + t * dy - p[1]
        d = qx * qx + qy * qy
        if d > dm:
            i, dm = k, d
    if dm ** 0.5 <= eps:
        return [a, b]
    return rdp(pts[: i + 1], eps)[:-1] + rdp(pts[i:], eps)


def osm_aae1():
    """Hong Kong approach of AAE-1, already in the OSM extract (China MSA notice) but dropped by clean_cables."""
    if not os.path.exists(OSM_RAW):
        return []
    d = json.load(open(OSM_RAW))
    out = []
    for e in d.get("elements") or []:
        t = e.get("tags") or {}
        nm = (t.get("name") or t.get("seamark:name") or "").strip()
        if nm != "AAE-1" or e.get("type") != "way":
            continue
        g = [[p["lon"], p["lat"]] for p in e.get("geometry") or [] if p]
        g = [r3(p) for p in rdp(g, 0.02)]
        if len(g) < 2:
            continue
        out.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": g},
            "properties": {"n": "AAE-1", "op": "", "s": "osm", "id": f"w{e['id']}", "leg": "Hong Kong approach"},
        })
    return out


def build_features():
    feats = []
    for name, spec in CABLES.items():
        feats.append(feat(name, pts(*spec["trunk"]), "trunk"))
        for i, br in enumerate(spec["branches"], 1):
            feats.append(feat(name, pts(*br), f"branch {i}"))
    feats += osm_aae1()
    return feats


def main():
    d = json.load(open(GEO))
    # drop previously added approx / tagged AAE-1 stub so reruns are clean
    keep = []
    for f in d["features"]:
        p = f.get("properties") or {}
        if p.get("s") == "approx" or p.get("id") == "w969276639":
            continue
        keep.append(f)
    extra = build_features()
    d["features"] = keep + extra
    names = set(d.get("names") or [])
    for f in extra:
        n = (f.get("properties") or {}).get("n")
        if n:
            names.add(n)
    d["names"] = sorted(names)
    d["credit"] = (
        "Routes and landing stations (c) OpenStreetMap contributors (ODbL); "
        "U.S. cable areas: NOAA Office for Coastal Management; "
        "approximate routes for systems OSM does not map end-to-end connect official "
        "landing points using Wikidata coordinates (CC0)"
    )
    d["note"] = (
        "Most routes run landing-to-landing from OSM or NOAA (ends within 25 km of a "
        "landing station or the coast). A few major systems OSM does not map end-to-end "
        "are drawn as approximate routes connecting official landing points (city or "
        "settlement coordinates). Those popups are labelled 'approximate route'."
    )
    json.dump(d, open(GEO, "w"), separators=(",", ":"))
    print("wrote", GEO, "bytes", os.path.getsize(GEO), "added", len(extra), "features")


if __name__ == "__main__":
    # fix Mtwapa placeholder if I left a hack - P should not have a dummy
    main()
