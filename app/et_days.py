"""Eastern Time calendar-day windows for day-bucketed charts.

Charts labeled "7 days" must end on today in America/New_York and span exactly
that many calendar days (today and the previous n-1 days). They must not use a
rolling 168-hour UTC window, UTC date prefixes, or future-dated event times.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


def _aware(now):
    if now is None:
        return datetime.now(timezone.utc)
    if isinstance(now, (int, float)):
        return datetime.fromtimestamp(now, timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now


def et_today(now=None):
    return _aware(now).astimezone(ET).date()


def et_last_days(n=7, now=None):
    """n ET calendar dates ending today, oldest first, as YYYY-MM-DD strings."""
    end = et_today(now)
    return [(end - timedelta(days=i)).isoformat() for i in range(n - 1, -1, -1)]


def et_day(ts):
    """YYYY-MM-DD in Eastern Time for an ISO timestamp, datetime, or Unix seconds."""
    if ts is None or ts == "":
        return None
    if isinstance(ts, (int, float)):
        d = _aware(ts)
    elif isinstance(ts, datetime):
        d = _aware(ts)
    else:
        s = str(ts).strip().replace("Z", "+00:00")
        try:
            d = datetime.fromisoformat(s)
        except ValueError:
            return None
        d = _aware(d)
    return d.astimezone(ET).strftime("%Y-%m-%d")


def et_window_start(n=7, now=None):
    """Timezone-aware datetime for 00:00 ET on the first day of the window."""
    first = et_last_days(n, now)[0]
    return datetime.strptime(first, "%Y-%m-%d").replace(tzinfo=ET)


def bucket_volume_trend(rows, days, high_threshold):
    """Aggregate cluster rows into volume + severity-trend series for `days`.

    rows: iterable of dicts with t (timestamp), category, score, watchlist.
    Future days and dates outside `days` are dropped. Every day in `days` appears
    in the trend list (zeros if empty). Volume lists only non-zero category counts.
    """
    days = list(days)
    allowed = set(days)
    vol_map = {}
    trend = {d: {"d": d, "mx": 0, "sum": 0, "n": 0, "high": 0} for d in days}
    for r in rows:
        d = et_day(r.get("t"))
        if d not in allowed:
            continue
        cat = r.get("category") or "other"
        vol_map[(d, cat)] = vol_map.get((d, cat), 0) + 1
        if not r.get("watchlist"):
            sc = r.get("score") or 0
            tr = trend[d]
            tr["mx"] = max(tr["mx"], sc)
            tr["sum"] += sc
            tr["n"] += 1
            if sc >= high_threshold:
                tr["high"] += 1
    vol = [{"d": d, "category": c, "n": n} for (d, c), n in sorted(vol_map.items())]
    out = []
    for d in days:
        tr = trend[d]
        avg = round(tr["sum"] / tr["n"], 1) if tr["n"] else 0
        out.append({"d": d, "mx": tr["mx"] if tr["n"] else 0, "avg": avg, "high": tr["high"]})
    return vol, out
