"""Internet status by U.S. state, territory and country for the Internet layer on /grid (Nov 24 2026, Matt pt1810u).
Source: IODA (Georgia Tech Internet Intelligence Lab), public keyless API v2. Inputs: the entity lists (which places IODA
monitors) and the last 24 h of outage alerts for countries and regions. Per place and signal the latest alert wins:
a signal whose latest alert is not "normal" is down. Status: red (outage) if routing (BGP) or active probing is critical,
or two or more signals are down; amber (degraded) if any one signal is down; green if IODA monitors the place and no
signal is down (a dip to 95 % of baseline or more is ignored, and a down signal is re-read from IODA raw signals: if its latest value is back at 95 % or more of baseline it counts as recovered); grey (no data) if IODA does not monitor it or IODA did not answer. Cached 10 min server-side (netmap.swr),
no keys, no writes. Territories (PR, GU, VI, AS, MP) are country-level entities in IODA."""
import time
from datetime import datetime, timezone

IODA = "https://api.ioda.inetintel.cc.gatech.edu/v2"; UI = "https://ioda.inetintel.cc.gatech.edu"
SIG = {"bgp": "Routing (BGP)", "ping-slash24": "Active probing", "merit-nt": "Network telescope"}
STRONG = {"bgp", "ping-slash24"}
WINDOW = 24 * 3600
MINOR = 95

def _iso(t): return datetime.fromtimestamp(int(t), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if t else None

import json as _json, os as _os
_ENTS = {}
def entities(jget):
    """IODA's monitored places. Last good list is kept; if IODA does not answer, the bundled list (inet_ents.json, Nov 24 2026) is used."""
    try:
        e = _entities(jget); _ENTS.update(e); return e
    except Exception:
        if _ENTS: return dict(_ENTS)
        with open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "netmap_static", "inet_ents.json"), encoding="utf-8") as fh: return _json.load(fh)

def _entities(jget):
    c = jget(f"{IODA}/entities/query?entityType=country", timeout=40).get("data") or []
    r = jget(f"{IODA}/entities/query?entityType=region&relatedTo=country/US", timeout=40).get("data") or []
    return dict(c={e["code"]: e.get("name") for e in c if e.get("code")},
                r={e["name"]: e["code"] for e in r if e.get("name") and not str(e.get("name")).startswith("Unknown")})

def alerts(jget, et):
    n = int(time.time())
    return jget(f"{IODA}/outages/alerts?entityType={et}&from={n - WINDOW}&until={n}&limit=20000", timeout=40, cap=20_000_000).get("data") or []

def judge(al, cur=None):
    """al: IODA alerts for one place; cur: {datasource: latest raw value} for signals re-checked now. Returns (level 0/2/3, signals-down list, since, alert count)."""
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
        v = st.get("v"); live = False
        if cur and cur.get(ds) is not None: v = cur[ds]; live = True       # current value beats the alert's value
        pct = round(100 * v / st["h"]) if st.get("h") and v is not None else None
        if pct is not None and pct >= MINOR: continue      # a 1-4 % dip is noise, not an outage (IODA still lists it)
        down.append(dict(ds=ds, name=SIG[ds], level=st["lv"], pct=pct, value=v, live=live, baseline=st.get("h"), since=_iso(st["since"])))
    crit = any(d["level"] == "critical" and d["ds"] in STRONG and (d["pct"] is None or d["pct"] <= 75) for d in down)
    lvl = 3 if (crit or len(down) >= 2) else 2 if down else 0
    since = min((d["since"] for d in down if d["since"]), default=None)
    return lvl, sorted(down, key=lambda d: d["ds"]), since, len(al)

def current(jget, et, code, ds):
    """Latest non-empty raw value of one IODA signal in the last 2 h (None if IODA has none yet)."""
    n = int(time.time())
    d = jget(f"{IODA}/signals/raw/{et}/{code}?from={n - 7200}&until={n}&datasource={ds}", timeout=15).get("data") or []
    while d and isinstance(d[0], list): d = d[0]
    vals = [x for x in ((d[0] if d else {}).get("values") or []) if x is not None]
    return vals[-1] if vals else None

def recheck(jget, todo, cap=15):
    """todo: [(et, code, ds)] signals the alert window says are down. Returns {(et, code): {ds: value}}."""
    from concurrent.futures import ThreadPoolExecutor
    out = {}
    def one(t):
        try: return t, current(jget, *t)
        except Exception: return t, None
    with ThreadPoolExecutor(4) as ex:
        for (et, code, ds), v in ex.map(one, todo[:cap]):
            if v is not None: out.setdefault((et, code), {})[ds] = v
    return out

def seen_ok(ents, et, code):
    if et == "country": return {(et, code)} if code in ents["c"] and code != "US" else set()
    return {(et, code)} if code in ents["r"].values() else set()

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
    todo = []
    for (et, code), al in groups.items():
        if (et, code) in seen_ok(ents, et, code): todo += [(et, code, d["ds"]) for d in judge(al)[1]]
    cur = recheck(jget, todo)     # signals that recovered since their last alert show normal, not stuck amber/red
    chk = _iso(time.time())
    def row(key, name, et, code):
        feed = ok[et] is not None
        if not feed: return dict(k=key, name=name, level=-1, status="No data", signals=[], checked=chk, src=f"{UI}/{et}/{code}")
        lvl, down, since, n = judge(groups.get((et, code), []), cur.get((et, code)))
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


# ---------------------------------------------------------------- Nov 24 2026 (Matt): last good snapshot, box relay, news evidence
# Green unless there is evidence of a problem. Evidence = IODA (server call, or the box relay snapshot when Render cannot reach
# IODA) plus news headlines about an internet outage/shutdown naming the place. The last good snapshot is used, with its age,
# until every source has been unavailable for over 1 hour; only then is the map grey.
import re as _re
RELAY = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "data", "ioda_relay.json")
MAX_AGE = 3600
_LG = {}
NEWS_Q = '"internet outage" OR "internet shutdown" OR "internet blackout" OR "internet disruption"'

def _ts(s):
    try: return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except Exception: return 0.0

def _good(r): return bool(r and r.get("places") and any((r.get("feeds") or {}).values()))

def relay():
    try:
        with open(RELAY, encoding="utf-8") as fh: r = _json.load(fh)
        return r if _good(r) else None
    except Exception: return None

def news(rss):
    """Headlines from the last 2 days about an internet outage or shutdown (Google News RSS, same helper as the cable layer)."""
    return rss(NEWS_Q, 2)

def _news_hits(items, places):
    hits = {}
    pats = [(k, p["name"]) for k, p in places.items() if p.get("name") and len(p["name"]) >= 4]
    for it in items or []:
        t = it.get("t") or ""
        if not _re.search(r"internet|network|connectivity|online", t, _re.I) or not _re.search(r"outage|shutdown|blackout|disrupt|down\b", t, _re.I): continue
        for k, nm in pats:
            if _re.search(r"\b" + _re.escape(nm) + r"\b", t, _re.I):
                hits.setdefault(k, []).append(dict(t=t, src=it.get("src"), url=it.get("url"), at=it.get("at"), shutdown=bool(_re.search(r"shutdown|blackout|nationwide", t, _re.I))))
    return hits

def serve(server, news_items=None, now=None):
    """Pick the freshest good snapshot (server build, last good in memory, box relay) and add news evidence."""
    now = now or time.time()
    if _good(server): _LG["v"] = server
    cands = [dict(x, via=v) for x, v in ((server if _good(server) else None, "server"), (_LG.get("v"), "server-last-good"), (relay(), "box-relay")) if x]
    best = max(cands, key=lambda x: _ts(x.get("generated"))) if cands else None
    age = now - _ts(best.get("generated")) if best else None
    if not best or age > MAX_AGE:
        out = dict(server or {}, via="none", age_s=None, all_down=True)
        out["places"] = {k: dict(v) for k, v in ((server or {}).get("places") or {}).items()}
    else:
        out = dict(best, age_s=round(max(0, age)), all_down=False)
        out["places"] = {k: dict(v) for k, v in best["places"].items()}
        for v in out["places"].values():
            if v.get("level", -1) < 0: v.update(level=0, status="Normal", signals=[])   # no evidence of a problem
    for k, hs in _news_hits(news_items, out["places"]).items():
        p = out["places"][k]; lvl = 3 if any(h["shutdown"] for h in hs) else 2
        p["news"] = hs[:3]
        if lvl > p.get("level", -1): p.update(level=lvl, status="Outage" if lvl == 3 else "Degraded")
    lv = [p.get("level", -1) for p in out["places"].values()]
    out["counts"] = dict(places=len(lv), live=sum(1 for x in lv if x >= 0), outage=lv.count(3), degraded=lv.count(2), normal=lv.count(0), no_data=lv.count(-1))
    return out
