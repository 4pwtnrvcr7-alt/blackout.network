"""Box-side IODA relay, part 2 (Nov 24 2026): the IODA data behind /api/netmap/data (30-day ASN events cut to the ASNs the
site tracks, 30-day country events, 24 h region summary) -> data/ioda_relay_data.json. Same keyless polite client as collect.py."""
import json, os, sys, time
D = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, D)
from collect import jget
IODA = "https://api.ioda.inetintel.cc.gatech.edu/v2"; DAYS = 30
asns = {f"asn/{a}" for a in json.load(open(os.path.join(D, "asns.json")))}
n = int(time.time()); out = {"generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
out["asn"] = [e for e in (jget(f"{IODA}/outages/events?entityType=asn&from={n - DAYS * 86400}&until={n}&limit=30000", timeout=60).get("data") or []) if e.get("location") in asns]
time.sleep(5)
out["cev"] = jget(f"{IODA}/outages/events?entityType=country&from={n - DAYS * 86400}&until={n}&limit=5000", timeout=40).get("data") or []
time.sleep(5)
out["reg"] = jget(f"{IODA}/outages/summary?entityType=region&from={n - 86400}&until={n}&limit=3000", timeout=40).get("data") or []
p = os.path.join(D, "data", "ioda_relay_data.json")
with open(p + ".tmp", "w") as f: json.dump(out, f, separators=(",", ":"))
os.replace(p + ".tmp", p); print("relay data: ok asn", len(out["asn"]), "cev", len(out["cev"]), "reg", len(out["reg"]))
