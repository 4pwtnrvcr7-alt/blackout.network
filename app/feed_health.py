"""Wire / homepage feed freshness (Nov 23 2026, pt1771u–pt1773u).

A 60-second tick on the public Render node records whether the last finished
scan or the last Mac push is more than 20 minutes old. The result is served at
GET /api/signal/feed-health (also /api/feed-health). The homepage Updated line
and The Wire show a small notice while stale; it clears on its own when a new
scan arrives.

A boot grace period ignores a missing last_push on a brand-new instance so a
zero-downtime deploy, which resets in-memory push counters, cannot flash a
false delay notice while handed-off last_scan data is still fresh.

Never touches scanner scoring, push.py, jets.py, aviation_watch.py, or the
geocoder / map_pins files.
"""
from __future__ import annotations

import os, time, threading
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

STALE_S = 20 * 60
SEVERE_S = 2 * 60 * 60
GRACE_S = int(os.environ.get("BN_FEED_HEALTH_GRACE_S", "300"))
ET = ZoneInfo("America/New_York")

_lock = threading.Lock()
ST = {"stale": False, "severe": False, "logged": None, "checked": 0.0, "info": None}


def _ts(v):
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v) if v > 0 else None
    s = str(v).strip().replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.timestamp()
    except Exception:
        return None


def _iso(ts):
    if not ts:
        return None
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def _et(ts):
    if not ts:
        return ""
    return datetime.fromtimestamp(ts, ET).strftime("%-I:%M %p ET")


def _age(now, ts):
    return None if not ts else int(round(now - ts))


def notice_text(since_et):
    if since_et:
        return "Live updates delayed since " + since_et
    return "Live updates delayed"


def collect(now=None, booted=None, last_scan=None, last_push=None,
            mac_connected=False, grace_s=None):
    """Pure snapshot. last_scan / last_push may be unix seconds or ISO-8601."""
    now = time.time() if now is None else float(now)
    grace_s = GRACE_S if grace_s is None else int(grace_s)
    booted_ts = _ts(booted) or 0.0
    scan_ts = _ts(last_scan)
    push_ts = _ts(last_push)
    in_grace = booted_ts > 0 and (now - booted_ts) < grace_s
    # During boot grace, a missing push is a deploy artifact, not a stall.
    candidates = [t for t in (scan_ts, push_ts) if t]
    if in_grace and push_ts is None:
        candidates = [t for t in (scan_ts,) if t]
    freshest = max(candidates) if candidates else None
    if in_grace and freshest is None:
        stale = False
    else:
        stale = freshest is None or (now - freshest) > STALE_S
    since = freshest
    since_et = _et(since)
    severe = bool(stale and since and (now - since) > SEVERE_S)
    if stale and since is None:
        severe = (not in_grace) and (now - booted_ts) > SEVERE_S if booted_ts else True
    return {
        "ok": True,
        "stale": stale,
        "severe": severe,
        "notice": notice_text(since_et) if stale else "",
        "last_scan": _iso(scan_ts),
        "last_scan_et": _et(scan_ts),
        "last_scan_age_s": _age(now, scan_ts),
        "last_push": _iso(push_ts),
        "last_push_age_s": _age(now, push_ts),
        "mac_connected": bool(mac_connected),
        "since": _iso(since),
        "since_et": since_et,
        "since_age_s": _age(now, since),
        "boot_grace": in_grace,
        "grace_remaining_s": max(0, int(round(grace_s - (now - booted_ts)))) if in_grace else 0,
        "now": _iso(now),
    }


def _live_inputs():
    last_scan = last_push = booted = None
    mac = False
    try:
        import server
        last_scan = server.state.get("last_scan")
    except Exception:
        pass
    times = []
    try:
        import render_app as RA
        booted = getattr(RA, "BOOTED", None)
        lp = (getattr(RA, "SYNC", None) or {}).get("last_push")
        if lp:
            times.append(float(lp))
    except Exception:
        pass
    try:
        import realtime
        st = getattr(realtime, "ST", {}) or {}
        li = st.get("last_ingest")
        if li:
            times.append(float(li))
        pub = realtime.public()
        mac = bool(pub.get("mac_connected"))
    except Exception:
        pass
    if times:
        last_push = max(times)
    return dict(booted=booted, last_scan=last_scan, last_push=last_push, mac_connected=mac)


def snapshot():
    return collect(**_live_inputs())


def tick():
    info = snapshot()
    with _lock:
        prev = ST.get("stale")
        ST.update(stale=info["stale"], severe=info["severe"], checked=time.time(), info=info)
        if info["stale"] and not prev:
            ST["logged"] = "stale"
            print(
                "feed-health: stale since {since} (scan age {age}s, mac_connected={mac})".format(
                    since=info.get("since_et") or "unknown",
                    age=info.get("last_scan_age_s") if info.get("last_scan_age_s") is not None else "n/a",
                    mac=info.get("mac_connected"),
                ),
                flush=True,
            )
        elif prev and not info["stale"]:
            ST["logged"] = "recovered"
            print("feed-health: recovered; live updates resumed", flush=True)
    return info


def handle_get(path, qs):
    if path in ("/api/signal/feed-health", "/api/feed-health"):
        return 200, snapshot()
    return 404, {"error": "not found"}
