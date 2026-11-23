"""Network outage report for the 7 AM / 7 PM brief (Matt, pt1755u, Nov 23 2026). Opt-in per reader (subscribers.net_brief).

for_sub(sub, c) -> dict or None. Data is the same snapshot as /network (netmap.py): official provider status pages,
IODA internet outage signals and ODIN power outages. Uses the in-process copy when this process already has one,
otherwise reads the public /api/netmap/data endpoint once (cached 10 min).
Never raises: any failure returns None and the issue simply has no network section.
Kill switch: env BN_NL_NETWORK=0 or newsletter_config.json "network_section": false."""
import json, os, threading, time, urllib.request

UA = "blackout.network-newsletter/1.0 (network section; contact via blackout.network)"
TIMEOUT = 12
_C = {}; _LK = threading.Lock()

def _on(c=None):
    if os.environ.get("BN_NL_NETWORK", "").strip() == "0": return False
    return (c or {}).get("network_section", True) is not False

def _opted(sub):
    try: return bool(int((dict(sub) if sub is not None else {}).get("net_brief") or 0))
    except Exception: return False

def _base(c): return str((c or {}).get("base_url") or "https://blackout.network").rstrip("/")

def _snapshot(c=None):
    with _LK:
        hit = _C.get("d")
        if hit and time.time() - hit[0] < 600: return hit[1]
    d = None
    try:
        import netmap
        h = netmap._C.get("data")          # only an existing in-process copy; never start a 30 s build from the mail path
        if h and time.time() - h[0] < 1800: d = h[1]
    except Exception:
        d = None
    if d is None:
        try:
            req = urllib.request.Request(_base(c) + "/api/netmap/data", headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                d = json.loads(r.read(5_000_000).decode("utf-8", "replace"))
        except Exception:
            d = None
    if not isinstance(d, dict) or not isinstance(d.get("nets"), list) or not d.get("summary"):
        with _LK: hit = _C.get("d")
        return hit[1] if hit and time.time() - hit[0] < 3 * 3600 else None
    with _LK: _C["d"] = (time.time(), d)
    return d

def build(d, c=None):
    """Section dict from a /api/netmap/data payload, or None when it is unusable."""
    try:
        s = d["summary"]; nets = [n for n in d["nets"] if not n.get("link_only")]
        bad = sorted([n for n in nets if int(n.get("level", -1)) >= 2], key=lambda n: (-int(n["level"]), n.get("name") or ""))
        minor = [n for n in nets if int(n.get("level", -1)) == 1]
        cs = [x for x in (d.get("outages") or {}).get("countries") or [] if x.get("cur") and x.get("name")]
        cs.sort(key=lambda x: (not x.get("major"), x.get("name")))
        pw = int(s.get("power_customers") or 0)
        rows = []
        for n in bad[:5]:
            inc = (n.get("incidents") or [{}])[0].get("t") or n.get("status") or ""
            rows.append(dict(name=str(n.get("name") or "")[:80], level=int(n["level"]), what="Major outage" if int(n["level"]) >= 3 else "Disruption",
                             note=str(inc)[:150], url=n.get("status_url") or (_base(c) + "/network")))
        total = int(s.get("networks") or len(nets)); ok = int(s.get("ok") or 0)
        if bad: head = f"{len(bad)} of {total} tracked networks disrupted right now"
        else: head = f"No major U.S. network outages right now · {ok} of {total} tracked networks normal"
        lines = []
        if minor and not bad: lines.append(f"{len(minor)} with minor issues reported by the provider.")
        if cs: lines.append("Internet outage signals now in " + ", ".join(x["name"] for x in cs[:4]) + (f" and {len(cs) - 4} more" if len(cs) > 4 else "") + " (IODA).")
        if pw >= 10000: lines.append(f"{pw:,} U.S. power customers out (ODIN).")
        lines = _log_lines(d) + lines   # pt1758u: the /network incident timeline, recovered problems first
        return dict(head=head, rows=rows, lines=lines[:3], url=_base(c) + "/network", generated=d.get("generated"), issues=len(bad))
    except Exception:
        return None

def _log_lines(d, hours=12):
    """Up to 2 plain-English lines from the /network incident timeline: real problems (level 2+) that recovered in the last `hours` hours."""
    try:
        from datetime import datetime, timezone, timedelta
        from zoneinfo import ZoneInfo
        et = ZoneInfo("America/New_York"); lim = datetime.now(timezone.utc) - timedelta(hours=hours); out = []
        for t in d.get("timeline") or []:
            if int(t.get("level") or 0) < 2 or not t.get("end"): continue
            s = datetime.fromisoformat(str(t["start"]).replace("Z", "+00:00")); e = datetime.fromisoformat(str(t["end"]).replace("Z", "+00:00"))
            if e < lim: continue
            f = lambda x: x.astimezone(et).strftime("%-I:%M %p")
            out.append(f"Recovered: {str(t.get('name') or '')[:60]}, {str(t.get('title') or '')[:90]} ({f(s)} to {f(e)} ET).")
            if len(out) >= 2: break
        return out
    except Exception:
        return []

def for_sub(sub, c=None):
    if not _on(c) or not _opted(sub): return None
    try:
        d = _snapshot(c)
        return build(d, c) if d else None
    except Exception:
        return None

def text_lines(n):
    if not n: return []
    T = ["NETWORK STATUS", n["head"]]
    for r in n.get("rows") or []: T.append(f"- {r['name']}: {r['what']}" + (f", {r['note']}" if r.get("note") else "") + f" {r['url']}")
    T += list(n.get("lines") or [])
    T += [f"Live outage map: {n['url']}", ""]
    return T
