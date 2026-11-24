"""Live grid status outside the U.S. from keyless grid-frequency feeds (pt1815u, Nov 24 2026).
A synchronous area's frequency is the one public, real-time health signal every operator shares: all countries in the area see the
same frequency, so it colours that whole area's 220 kV+ lines. No per-line status exists anywhere.
  - Continental Europe: Energy-Charts (Fraunhofer ISE) /frequency, CC BY 4.0, keyless. https://api.energy-charts.info
  - Great Britain: Elexon Insights Solution (BMRS) system frequency, keyless, Elexon BMRS data licence (free reuse with credit).
  - Nordic (NO, SE, FI): Statnett driftsdata, keyless, NLOD. https://driftsdata.statnett.no
Status, from the last 5 minutes (nominal 50 Hz): ok |df| <= 0.2 Hz (the operators' standard range); strain 0.2-0.8 Hz;
out > 0.8 Hz (below 49.2 Hz, where automatic under-frequency load shedding starts); na = feed silent or older than 15 min.
Outlines: app/netmap_static/syncareas.json from tools/build_syncareas.py (Natural Earth countries; Northern Ireland excluded from GB).
Read-only; no keys, accounts or writes.
"""
import json, os, time, functools
from datetime import datetime

AREAS = [
    {"id": "sa-ce", "name": "Continental Europe synchronous grid", "src": "Energy-Charts (Fraunhofer ISE), CC BY 4.0", "url": "https://www.energy-charts.info/charts/frequency/chart.htm",
     "cc": "AT BE BA BG HR CZ FR DE GR HU IT LU ME NL MK PL PT RO RS SK SI ES CH AL XK UA MD TR MA DZ TN LI".split()},
    {"id": "sa-gb", "name": "Great Britain grid (NESO)", "src": "Elexon BMRS system frequency", "url": "https://bmrs.elexon.co.uk/system-frequency", "cc": ["GB"]},
    {"id": "sa-nordic", "name": "Nordic synchronous grid", "src": "Statnett driftsdata, NLOD", "url": "https://driftsdata.statnett.no/Web/Map/frequency", "cc": ["NO", "SE", "FI"]},
]
STALE = 900

def status(vals):
    if not vals: return "na", None
    dev = max(abs(v - 50.0) for v in vals)
    return ("ok" if dev <= 0.2 else "strain" if dev <= 0.8 else "out"), round(dev * 1000)

@functools.lru_cache(maxsize=1)
def outlines(static):   # built by tools/build_syncareas.py (union of Natural Earth countries, buffered 0.1 deg, simplified)
    return json.load(open(os.path.join(static, "syncareas.json")))

def _ce(jget, now):
    d = jget("https://api.energy-charts.info/frequency?region=DE-Freiburg", timeout=25)
    u, f = d.get("unix_seconds") or [], d.get("data") or []
    pts = [(t, v) for t, v in zip(u, f) if v is not None and now - t <= 300 + 240]
    last = u[-1] if u else None
    return [v for t, v in pts if last and last - t <= 300], last

def _gb(jget, now):
    fr = datetime.utcfromtimestamp(now - 1200).strftime("%Y-%m-%dT%H:%MZ"); to = datetime.utcfromtimestamp(now + 60).strftime("%Y-%m-%dT%H:%MZ")
    d = jget(f"https://data.elexon.co.uk/bmrs/api/v1/system/frequency?format=json&from={fr}&to={to}", timeout=20).get("data") or []
    pts = [(datetime.fromisoformat(r["measurementTime"].replace("Z", "+00:00")).timestamp(), r["frequency"]) for r in d if r.get("frequency") is not None]
    if not pts: return [], None
    last = max(t for t, _ in pts)
    return [v for t, v in pts if last - t <= 300], last

def _nordic(jget, now):
    d = jget("https://driftsdata.statnett.no/restapi/Frequency/BySecond?From=" + datetime.utcfromtimestamp(now - 900).strftime("%Y-%m-%d"), timeout=20)
    m = [v for v in (d.get("Measurements") or []) if v]
    if not m: return [], None
    last = d["EndPointUTC"] / 1000.0
    return m[-300:], last

FEEDS = {"sa-ce": _ce, "sa-gb": _gb, "sa-nordic": _nordic}

def build(jget, static):
    now = time.time(); geo = outlines(static); areas = []
    for a in AREAS:
        st, dev, last, err = "na", None, None, None
        try:
            vals, last = FEEDS[a["id"]](jget, now)
            if last and now - last <= STALE: st, dev = status(vals)
            else: err = "feed is stale"
            fnow = round(vals[-1], 3) if vals else None
        except Exception as ex:
            err, fnow = type(ex).__name__, None
        areas.append({"id": a["id"], "name": a["name"], "status": st, "dev_mhz": dev, "hz": fnow, "last": int(last) if last else None,
                      "src": a["src"], "url": a["url"], "countries": a["cc"], "err": err, "g": geo[a["id"]]})
    return {"areas": areas, "checked": int(now),
            "method": "Synchronous-area grid frequency, last 5 min: within 0.2 Hz of 50 Hz normal; 0.2-0.8 Hz strained; beyond 0.8 Hz emergency (load shedding range); grey if the feed is silent."}
