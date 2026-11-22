"""Open-Meteo request budget, shared by the weather map grids (wxmap.py) and the place card (weather.py). Nov 22 2026 (pt1745u).

Why: the free Open-Meteo API allows 600 location-calls a minute, 5,000 an hour and 10,000 a day per IP. Each deploy used to refill the
map grids from scratch (~2,500 calls), so a day with several deploys ran into HTTP 429 and Temp/Rain/Snow greyed out.
This module counts what this instance sends (location-calls, weighted the way Open-Meteo weights them), keeps the grids to their own
share, and remembers a 429 back-off (Retry-After when given, else until the hour or the UTC day turns, depending on the reason).
The state is small and public-safe (counts and a time), is saved next to the grid cache and handed to the next deploy.
"""
import json, re, threading, time
from datetime import datetime, timedelta, timezone

HOUR_CAP = 3500        # all callers, per rolling hour (Open-Meteo: 5,000)
DAY_CAP = 8000         # all callers, per rolling 24 h (Open-Meteo: 10,000)
GRID_HOUR_CAP = 2600   # the map grids alone, so place cards always have room
GRID_DAY_CAP = 5200
_L = threading.Lock()
_S = {"log": [], "until": 0.0, "why": None, "last429": 0.0}   # log: [ts, n, kind]

def _trim(now):
    _S["log"] = [e for e in _S["log"] if now - e[0] < 86400][-5000:]

def used(window, kind=None, now=None):
    now = now or time.time()
    with _L: return sum(e[1] for e in _S["log"] if now - e[0] < window and (kind is None or e[2] == kind))

def note(n, kind):
    now = time.time()
    with _L: _S["log"].append([now, n, kind]); _trim(now)

def limited():
    """(True, reason, until) while backing off after a 429."""
    with _L:
        if time.time() < _S["until"]: return True, _S["why"], _S["until"]
    return False, None, 0.0

def wait_s(n, kind):
    """Seconds until n more calls of this kind fit the budget (0 = go now). Large values mean: give up for now and retry later."""
    now = time.time()
    lim, _, until = limited()
    if lim: return until - now
    with _L:
        log = list(_S["log"])
    def need(window, cap, k):
        rows = sorted((e for e in log if now - e[0] < window and (k is None or e[2] == k)), key=lambda e: e[0])
        tot = sum(e[1] for e in rows)
        if tot + n <= cap: return 0.0
        for e in rows:   # wait until enough old calls age out of the window
            tot -= e[1]
            if tot + n <= cap: return e[0] + window - now + 1
        return window
    w = max(need(3600, HOUR_CAP, None), need(86400, DAY_CAP, None))
    if kind == "grid": w = max(w, need(3600, GRID_HOUR_CAP, "grid"), need(86400, GRID_DAY_CAP, "grid"))
    return w

def on_429(ex):
    """Record a 429 from Open-Meteo (urllib HTTPError). Honour Retry-After; else back off by the reason Open-Meteo gives."""
    now = time.time(); ra = None; reason = ""
    try: ra = ex.headers.get("Retry-After")
    except Exception: pass
    try: reason = json.loads(ex.read(2000).decode("utf-8", "replace")).get("reason") or ""
    except Exception: pass
    secs = None
    if ra:
        try: secs = float(ra)
        except ValueError: secs = None
    if secs is None:
        u = datetime.now(timezone.utc); low = reason.lower()
        if "daily" in low: secs = (u.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1) - u).total_seconds() + 120
        elif "hourly" in low: secs = (u.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1) - u).total_seconds() + 60
        elif "minutely" in low: secs = 75
        else:
            with _L: prev = _S["until"] - _S["last429"] if _S["last429"] else 0
            secs = min(6 * 3600, max(600, prev * 2))   # unknown reason: 10 min, doubling up to 6 h
    with _L:
        _S["until"] = max(_S["until"], now + secs); _S["last429"] = now
        _S["why"] = (reason or "Open-Meteo answered HTTP 429 (too many requests)")[:200]
    return secs

def state():
    """Public-safe snapshot: counts and the back-off time (no request details)."""
    now = time.time()
    with _L:
        log = [e for e in _S["log"] if now - e[0] < 86400]
        return {"until": _S["until"], "why": _S["why"], "last429": _S["last429"], "log": [[round(e[0], 1), e[1], e[2]] for e in log][-3000:]}

def adopt(st):
    """Take over the previous instance's counts and back-off (deploy handoff), keeping whichever is stricter."""
    if not isinstance(st, dict): return False
    now = time.time()
    with _L:
        try:
            if float(st.get("until") or 0) > _S["until"]: _S["until"] = float(st["until"]); _S["why"] = str(st.get("why") or "")[:200] or _S["why"]
            _S["last429"] = max(_S["last429"], float(st.get("last429") or 0))
            seen = {(round(e[0], 1), e[1], e[2]) for e in _S["log"]}
            for e in st.get("log") or []:
                if isinstance(e, list) and len(e) == 3 and now - float(e[0]) < 86400 and (round(float(e[0]), 1), int(e[1]), str(e[2])) not in seen:
                    _S["log"].append([float(e[0]), int(e[1]), str(e[2])[:8]])
            _S["log"].sort(key=lambda e: e[0]); _trim(now)
        except Exception: return False
    return True

def summary():
    lim, why, until = limited()
    return {"limited": lim, "reason": why if lim else None, "until": datetime.fromtimestamp(until, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if lim else None,
            "last_hour": used(3600), "last_day": used(86400), "grid_last_day": used(86400, "grid"), "caps": {"hour": HOUR_CAP, "day": DAY_CAP}}

def weight(n_vars, days=7):
    """Open-Meteo counts a call with more than 10 variables or more than 2 weeks as several (fractional) calls."""
    return max(1.0, n_vars / 10.0) * max(1.0, days / 14.0)
