"""Box-side IODA relay (Nov 24 2026, Matt pt1810u). Render cannot reach IODA, the box can. Builds the same snapshot as
app/netinet.build() with a polite keyless urllib client and writes data/ioda_relay.json. Read-only, no secrets, no posting."""
import json, os, sys, urllib.request
D = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, D)
import netinet
UA = "BlackoutNetwork-status/2.0 (+https://blackout.network/grid; box relay, cached, polite)"
def jget(url, timeout=40, cap=20_000_000, **k):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"}), timeout=timeout) as r:
        return json.loads(r.read(cap).decode("utf-8", "replace"))
r = netinet.build(jget)
if not any((r.get("feeds") or {}).values()): print("relay: IODA feeds failed, keep previous file"); sys.exit(1)
r["relay"] = True
out = os.path.join(D, "data", "ioda_relay.json"); tmp = out + ".tmp"
with open(tmp, "w") as f: json.dump(r, f, separators=(",", ":"))
os.replace(tmp, out); print("relay: ok", r["counts"], r["generated"])
