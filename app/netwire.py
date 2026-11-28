"""Wire internet and power outage stories for The Grid (Nov 27 2026).

When IODA does not answer Render, /grid was painting every country "No data" and
reporting zero outages worldwide, even though The Wire already had the same IODA
(and power outage) stories. This module reads those stories, read-only, and turns
them into the records the grid APIs and pages already use.

Never opens blackout.db except through wire_timeline's existing read-only helper
(or the already-cached heat_payload). No new paid or Render services.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

INET_RX = re.compile(
    r"internet outage|internet shutdown|internet blackout|internet disruption",
    re.I,
)
IODA_H = re.compile(r"internet outage,\s*([\d.]+)\s*h\s*\(IODA\)", re.I)
# Provider status-page incidents (Anthropic, Cloudflare dashboard, etc.) already
# appear on the network board; they are not country/region internet outages.
STATUS_RX = re.compile(r"\bstatus\b.*\b(incident|degraded|major impact)\b|\(major impact", re.I)
POWER_RX = re.compile(
    r"\b(?:power outage|power outages|without power|blackout|electrical grid|"
    r"power plant|power station|power grid|customers without power)\b",
    re.I,
)
SHUTDOWN_RX = re.compile(r"\b(?:shutdown|blackout|nationwide)\b", re.I)
DAYS = 7
CUR_GRACE = timedelta(minutes=75)


def _now():
    return datetime.now(timezone.utc)


def _ts(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def _iso(d):
    if not d:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _src_url(links):
    if isinstance(links, str):
        try:
            links = json.loads(links)
        except Exception:
            links = []
    if not isinstance(links, list):
        return "", ""
    for x in links:
        if not isinstance(x, dict):
            continue
        name = x.get("s") or x.get("source") or ""
        url = x.get("u") or x.get("url") or ""
        if name or url:
            return name, url
    return "", ""


def is_internet(title, src=""):
    t, s = title or "", src or ""
    if STATUS_RX.search(t):
        return False
    if IODA_H.search(t) or re.search(r"\bIODA\b", s) or "IODA internet" in s:
        return True
    if INET_RX.search(t):
        return True
    if re.search(r"cloudflare radar", t + " " + s, re.I) and re.search(r"outage|shutdown|disrupt", t, re.I):
        return True
    return False


def is_power(title, src=""):
    t = title or ""
    if is_internet(t, src):
        return False
    return bool(POWER_RX.search(t))


def parse_window(title, t, now=None):
    """Return (start, end, cur, hours) from a Wire headline and its event time."""
    now = now or _now()
    start = _ts(t)
    m = IODA_H.search(title or "")
    hours = float(m.group(1)) if m else None
    end = (start + timedelta(hours=hours)) if start is not None and hours is not None else None
    if end is not None:
        cur = end >= now - CUR_GRACE
    elif start is not None and IODA_H.search(title or ""):
        cur = start >= now - timedelta(hours=24)
    elif start is not None and INET_RX.search(title or ""):
        cur = start >= now - timedelta(hours=24)
    else:
        cur = False
    return start, end, cur, hours


def story_from(row, now=None):
    """Normalize a heat_payload or SQL row into a grid outage story, or None."""
    now = now or _now()
    if not isinstance(row, dict):
        return None
    title = (row.get("title") or "").split("\n")[0].strip()
    if not title:
        return None
    src = row.get("src") or ""
    url = row.get("url") or ""
    if not src:
        src, url = _src_url(row.get("links") or row.get("l") or [])
    kind = "internet" if is_internet(title, src) else "power" if is_power(title, src) else None
    if not kind:
        return None
    t = row.get("t") or row.get("et") or row.get("event_time") or row.get("fs") or row.get("first_seen")
    start, end, cur, hours = parse_window(title, t, now)
    if start and start < now - timedelta(days=DAYS) and not cur:
        return None
    cid = row.get("id") or row.get("cluster_id") or ""
    href = f"/wire/{cid}" if re.fullmatch(r"[0-9a-f]{16}", str(cid)) else ""
    place = row.get("place") or row.get("loc") or row.get("location") or ""
    return dict(
        id=str(cid),
        title=title[:220],
        kind=kind,
        rank=int(row.get("rank") or 0),
        lat=row.get("lat"),
        lon=row.get("lon"),
        place=place,
        cc=(row.get("cc") or "") or None,
        prec=row.get("prec"),
        t=_iso(start) if start else (t if isinstance(t, str) else None),
        end=_iso(end),
        cur=bool(cur),
        hours=hours,
        src=src,
        url=url,
        href=href,
        shutdown=bool(SHUTDOWN_RX.search(title)),
    )


def stories_from_rows(rows, now=None):
    now = now or _now()
    internet, power = [], []
    seen = set()
    for row in rows or []:
        s = story_from(row, now)
        if not s or s["id"] in seen:
            continue
        seen.add(s["id"])
        (internet if s["kind"] == "internet" else power).append(s)
    key = lambda x: (not x["cur"], -( _ts(x["t"]).timestamp() if _ts(x["t"]) else 0))
    internet.sort(key=key)
    power.sort(key=key)
    return {"internet": internet, "power": power, "ok": True}


def _heat_rows():
    try:
        import signal_map
        p = signal_map.heat_payload()
    except Exception:
        return None
    if not isinstance(p, dict):
        return None
    cols = p.get("cols") or []
    ix = {k: i for i, k in enumerate(cols)}
    out = []
    for r in p.get("rows") or []:
        g = lambda k: r[ix[k]] if k in ix and ix[k] < len(r) else None
        out.append({
            "id": g("id"), "title": g("title"), "lat": g("lat"), "lon": g("lon"),
            "place": g("place"), "cc": g("cc"), "prec": g("prec"), "t": g("t"),
            "src": g("src"), "url": g("url"), "rank": g("rank"), "fs": g("fs"),
        })
    return out


def _sql_rows(days=DAYS):
    """Read-only fallback when the heat payload is not yet built."""
    try:
        import wire_timeline as W
    except Exception:
        return None
    cut = (_now() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        c = W._ro(W.DB)
    except Exception:
        return None
    try:
        q = (
            "SELECT cluster_id AS id, title, location AS place, lat, lon, "
            "COALESCE(event_time, first_seen) AS t, first_seen AS fs, rank, links "
            "FROM clusters WHERE watchlist IN (0, 1) "
            "AND COALESCE(updated, first_seen) >= ? "
            "AND (title LIKE '%internet outage%' OR title LIKE '%(IODA)%' "
            "OR title LIKE '%internet shutdown%' OR title LIKE '%internet blackout%' "
            "OR title LIKE '%without power%' OR title LIKE '%power outage%' "
            "OR title LIKE '%blackout%') "
            "ORDER BY t DESC LIMIT 400"
        )
        return [dict(r) for r in c.execute(q, [cut])]
    except Exception:
        return None
    finally:
        try:
            c.close()
        except Exception:
            pass


def load(now=None):
    """Return {internet, power, ok} or None if the Wire could not be read."""
    rows = _heat_rows()
    if rows is None:
        rows = _sql_rows()
    if rows is None:
        return None
    return stories_from_rows(rows, now=now)


def match_keys(story, places):
    """Place keys (C:MW, S:Florida, …) this story belongs to."""
    if not places:
        return []
    keys = []
    cc = (story.get("cc") or "").upper()
    place = (story.get("place") or "").strip()
    if cc and cc != "US" and f"C:{cc}" in places:
        keys.append(f"C:{cc}")
    if place:
        if "," in place:
            region, country = [x.strip() for x in place.split(",", 1)]
            if f"S:{region}" in places and (cc == "US" or re.search(r"united states|\bus\b", country, re.I)):
                keys.append(f"S:{region}")
            elif f"S:{region}" in places and cc == "US":
                keys.append(f"S:{region}")
        if f"S:{place}" in places:
            keys.append(f"S:{place}")
    # Name match, longest first, same disambiguation as netinet news headlines.
    try:
        import netinet
        hits = netinet._news_hits(
            [{"t": (story.get("title") or "") + " internet outage " + place, "src": story.get("src"), "url": story.get("href") or story.get("url"), "at": story.get("t")}],
            places,
        )
        keys.extend(hits.keys())
    except Exception:
        pats = sorted(
            [(k, p.get("name") or "") for k, p in places.items() if (p.get("name") or "") and len(p.get("name") or "") >= 4],
            key=lambda x: -len(x[1]),
        )
        blob = (story.get("title") or "") + " " + place
        for k, nm in pats:
            if re.search(r"(?<![\w-])" + re.escape(nm) + r"(?![\w-])", blob, re.I):
                keys.append(k)
    # de-dupe, preserve order
    out, seen = [], set()
    for k in keys:
        if k in places and k not in seen:
            seen.add(k)
            out.append(k)
    return out


def apply_inet(payload, bundle, now=None):
    """Overlay Wire internet stories on an /api/netmap/inet payload.

    If the Wire was read successfully, the map is no longer 'all down': places
    default to Normal (Matt: green unless there is evidence) and current Wire
    outages mark the matching country or region. 'No data' stays only when the
    Wire could not be read and IODA is also down.
    """
    now = now or _now()
    out = dict(payload or {})
    places = {k: dict(v) for k, v in (out.get("places") or {}).items()}
    out["places"] = places
    if bundle is None:
        out.setdefault("wire_ok", False)
        return out
    stories = list(bundle.get("internet") or [])
    out["wire_ok"] = True
    out["wire"] = stories
    if out.get("all_down"):
        out["all_down"] = False
        out["via"] = (out.get("via") + "+wire") if out.get("via") not in (None, "none") else "wire"
        for v in places.values():
            if v.get("level", -1) < 0:
                v.update(level=0, status="Normal", signals=v.get("signals") or [])
    for s in stories:
        entry = dict(
            t=s["title"], src=s.get("src") or "The Wire", url=s.get("href") or s.get("url"),
            at=s.get("t"), shutdown=bool(s.get("shutdown")), cur=bool(s.get("cur")), id=s.get("id"),
        )
        for k in match_keys(s, places):
            p = places[k]
            w = list(p.get("wire") or [])
            if not any(x.get("id") == entry["id"] for x in w):
                w.append(entry)
            p["wire"] = w[:5]
            if s.get("cur"):
                lvl = 3 if s.get("shutdown") or (s.get("hours") or 0) >= 6 else 2
                if lvl > p.get("level", -1):
                    p.update(level=lvl, status="Outage" if lvl >= 3 else "Degraded", since=s.get("t"))
    lv = [p.get("level", -1) for p in places.values()]
    out["counts"] = dict(
        places=len(lv),
        live=sum(1 for x in lv if x >= 0),
        outage=lv.count(3),
        degraded=lv.count(2),
        normal=lv.count(0),
        no_data=lv.count(-1),
    )
    return out


def countries(stories, centroids=None, alias=None, small=None, now=None):
    """IODA-shaped country records plus Wire story links, for /api/netmap/data."""
    now = now or _now()
    centroids = centroids or {}
    alias = alias or {}
    small = small or {}
    by = {}
    for s in stories or []:
        if s.get("kind") and s["kind"] != "internet":
            continue
        name = (s.get("place") or s.get("title") or "").split(",")[0].strip() or s.get("cc") or "Unknown"
        cc = (s.get("cc") or name[:2] or "").upper() if s.get("cc") else ""
        key = s.get("cc") or name
        o = by.setdefault(key, dict(
            cc=cc or key, name=name, cur=False, stories=[], last=None, hours=None,
            lat=s.get("lat"), lon=s.get("lon"),
        ))
        o["cur"] = o["cur"] or bool(s.get("cur"))
        if s.get("lat") is not None:
            o["lat"], o["lon"] = s.get("lat"), s.get("lon")
        o["stories"].append(s)
        st = _ts(s.get("t"))
        if st and (o["last"] is None or st > _ts(o["last"]) or _ts(o["last"]) is None):
            o["last"] = s.get("t")
            o["hours"] = s.get("hours")
            if name:
                o["name"] = name
    out = []
    for o in by.values():
        geo = alias.get(o["name"], o["name"])
        c = centroids.get(geo) or small.get(o["cc"])
        lon = o["lon"] if o["lon"] is not None else (c[0] if c else None)
        lat = o["lat"] if o["lat"] is not None else (c[1] if c else None)
        top = o["stories"][0]
        out.append(dict(
            cc=o["cc"], name=o["name"], geo=geo, lon=lon, lat=lat,
            cur=o["cur"], major=bool(o["cur"] and (o["hours"] or 0) >= 6),
            signals=["wire"], last=o["last"],
            ioda=f"https://ioda.inetintel.cc.gatech.edu/country/{o['cc']}" if len(o["cc"]) == 2 else None,
            src=top.get("src") or "The Wire",
            href=top.get("href") or "",
            stories=[{"id": s["id"], "title": s["title"], "t": s["t"], "end": s.get("end"),
                      "cur": s["cur"], "src": s.get("src"), "href": s.get("href"),
                      "hours": s.get("hours")} for s in o["stories"][:5]],
        ))
    out.sort(key=lambda x: (not x["cur"], x["name"] or ""))
    return out


def daily_from(stories, days=30, now=None):
    now = now or _now()
    n0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    daily = [0] * days
    for s in stories or []:
        st = _ts(s.get("t"))
        if not st:
            continue
        k = (n0 - st.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)).days
        if 0 <= k < days:
            daily[days - 1 - k] += 1
    return daily
