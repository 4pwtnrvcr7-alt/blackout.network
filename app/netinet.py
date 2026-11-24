"""Internet status by U.S. state, territory and country for the Internet layer on /grid (Nov 24 2026, Matt pt1810u).
Source: IODA (Georgia Tech Internet Intelligence Lab), public keyless API v2. Inputs: the entity lists (which places IODA
monitors) and the last 24 h of outage alerts for countries and regions. Per place and signal the latest alert wins:
a signal whose latest alert is not "normal" is down. Status: red (outage) if routing (BGP) or active probing is critical,
or two or more signals are down; amber (degraded) if any one signal is down; green if IODA monitors the place and no
signal is down (a dip to 95 % of baseline or more is ignored); grey (no data) if IODA does not monitor it or IODA did not answer. Cached 10 min server-side (netmap.swr),
no keys, no writes. Territories (PR, GU, VI, AS, MP) are country-level entities in IODA."""
import time
from datetime import datetime, timezone

IODA = "https://api.ioda.inetintel.cc.gatech.edu/v2"; UI = "https://ioda.inetintel.cc.gatech.edu"
SIG = {"bgp": "Routing (BGP)", "ping-slash24": "Active probing", "merit-nt": "Network telescope"}
STRONG = {"bgp", "ping-slash24"}
WINDOW = 24 * 3600
MINOR = 95

def _iso(t): return datetime.fromtimestamp(int(t), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if t else None

def entities(jget):
    c = jget(f"{IODA}/entities/query?entityType=country", timeout=40).get("data") or []
    r = jget(f"{IODA}/entities/query?entityType=region&relatedTo=country/US", timeout=40).get("data") or []
    return dict(c={e["code"]: e.get("name") for e in c if e.get("code")},
                r={e["name"]: e["code"] for e in r if e.get("name") and not str(e.get("name")).startswith("Unknown")})

def alerts(jget, et):
    n = int(time.time())
    return jget(f"{IODA}/outages/alerts?entityType={et}&from={n - WINDOW}&until={n}&limit=20000", timeout=40, cap=20_000_000).get("data") or []

def judge(al):
    """al: IODA alerts for one place. Returns (level 0/2/3, signals-down list, since, alert count)."""
    by = {}
    for a in sorted(al, key=lambda a: a.get("time") or 0):
        ds = a.get("datasource"); lv = a.get("level") or "normal"
        if ds not in SIG: continue
        st = by.setdefault(ds, {"lv": "normal", "since": None})
        if lv == "normal": st.update(lv="normal", since=None, v=None, h=None)
        else:
            if st["lv"] == "normal": st["since"] = a.get("time")
            st.update(lv=lv, v=a.get("value"), h=a.get("historyValue"))
    down = []
    for ds, st in by.items():
        if st["lv"] == "normal": continue
        pct = round(100 * st["v"] / st["h"]) if st.get("h") and st.get("v") is not None else None
        if pct is not None and pct >= MINOR: continue      # a 1-4 % dip is noise, not an outage (IODA still lists it)
        down.append(dict(ds=ds, name=SIG[ds], level=st["lv"], pct=pct, value=st.get("v"), baseline=st.get("h"), since=_iso(st["since"])))
    crit = any(d["level"] == "critical" and d["ds"] in STRONG and (d["pct"] is None or d["pct"] <= 75) for d in down)
    lvl = 3 if (crit or len(down) >= 2) else 2 if down else 0
    since = min((d["since"] for d in down if d["since"]), default=None)
    return lvl, sorted(down, key=lambda d: d["ds"]), since, len(al)

def build(jget):
    ents = entities(jget); out = {}
    ok = {}
    for et in ("country", "region"):
        try: ok[et] = alerts(jget, et)
        except Exception: ok[et] = None
    groups = {}
    for et in ("country", "region"):
        for a in ok[et] or []:
            e = a.get("entity") or {}
            if et == "region" and (e.get("attrs") or {}).get("country_code") != "US": continue
            groups.setdefault((et, e.get("code")), []).append(a)
    chk = _iso(time.time())
    def row(key, name, et, code):
        feed = ok[et] is not None
        if not feed: return dict(k=key, name=name, level=-1, status="No data", signals=[], checked=chk, src=f"{UI}/{et}/{code}")
        lvl, down, since, n = judge(groups.get((et, code), []))
        return dict(k=key, name=name, level=lvl, status={3: "Outage", 2: "Degraded", 0: "Normal"}[lvl], signals=down, since=since,
                    alerts_24h=n, checked=chk, src=f"{UI}/{et}/{code}")
    for code, name in ents["c"].items():
        if code == "US": continue
        out["C:" + code] = row("C:" + code, name, "country", code)
    for name, code in ents["r"].items():
        out["S:" + name] = row("S:" + name, name, "region", code)
    lv = [r["level"] for r in out.values()]
    return dict(generated=chk, source="IODA, Georgia Tech Internet Intelligence Lab", source_url=UI, window_h=WINDOW // 3600,
                feeds={k: v is not None for k, v in ok.items()},
                counts=dict(places=len(out), live=sum(1 for x in lv if x >= 0), outage=lv.count(3), degraded=lv.count(2), normal=lv.count(0)),
                places=out)
