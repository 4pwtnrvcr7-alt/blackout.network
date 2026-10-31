#!/usr/bin/env python3
"""Dump current Blackout data as compact JSON for regenerating the
'Blackout Network Threat Dashboard' Page.  Usage: python3 export_page_data.py [--scan] [-o page_data.json]"""
import json, sys, sqlite3
from datetime import timedelta
from zoneinfo import ZoneInfo
import scanner

ET = ZoneInfo("America/New_York")
def et(s, fmt="%b %d, %I:%M %p %Z"):
    d = scanner.parse_t(s)
    return d.astimezone(ET).strftime(fmt).replace(" 0", " ") if d else ""

def main():
    args = sys.argv[1:]
    out = args[args.index("-o") + 1] if "-o" in args else f"{scanner.BASE}/page_data.json"
    scan = scanner.scan("page-export") if "--scan" in args else None
    c = scanner.db()
    q = lambda sql, a=(): [dict(r) for r in c.execute(sql, a)]
    now = scanner.now(); cut = scanner.iso(now - timedelta(days=7))
    def clean(r):
        return {"score": r["score"], "category": r["category"], "title": r["title"], "location": r["location"],
                "lat": r["lat"], "lon": r["lon"], "time_et": et(r["event_time"]), "event_time": r["event_time"],
                "confidence": r["confidence"], "families": json.loads(r["families"] or "[]"), "n_items": r["n_items"],
                "links": json.loads(r["links"] or "[]")[:5], "brief": r["brief"]}
    high = [clean(r) for r in q("SELECT * FROM clusters WHERE watchlist=0 AND score>=? ORDER BY score DESC, event_time DESC", (scanner.HIGH,))]
    watch = [clean(r) for r in q("SELECT * FROM clusters WHERE watchlist=1 AND COALESCE(event_time,first_seen)>=? ORDER BY score DESC, event_time DESC", (cut,))]
    days = [(now - timedelta(days=i)).astimezone(ET).strftime("%Y-%m-%d") for i in range(6, -1, -1)]
    cats = ["war/conflict", "disease", "natural disaster", "cyber", "space weather", "other"]
    rows = q("SELECT COALESCE(event_time, first_seen) t, category, score, watchlist FROM clusters WHERE COALESCE(event_time, first_seen)>=?", (cut,))
    vol = {cat: [0] * 7 for cat in cats}; mx = [0] * 7; tot = [0] * 7; n = [0] * 7; hi = [0] * 7
    for r in rows:
        d = et(r["t"], "%Y-%m-%d")
        if d not in days: continue
        i = days.index(d); vol.setdefault(r["category"], [0] * 7)[i] += 1
        if not r["watchlist"]:
            mx[i] = max(mx[i], r["score"]); tot[i] += r["score"]; n[i] += 1; hi[i] += r["score"] >= scanner.HIGH
    geo = [{"lat": round(r["lat"], 2), "lon": round(r["lon"], 2), "score": r["score"], "category": r["category"], "title": r["title"][:90]}
           for r in q("SELECT * FROM clusters WHERE lat IS NOT NULL AND COALESCE(event_time,first_seen)>=? ORDER BY score DESC", (cut,))]
    sources = q("SELECT name, url, ok, items, last_checked, error FROM source_health ORDER BY ok DESC, name")
    last = q("SELECT * FROM scans ORDER BY id DESC LIMIT 1")
    data = {"as_of_utc": scanner.iso(now), "as_of_et": "as of " + now.astimezone(ET).strftime("%I:%M %p %Z, %b %d").lstrip("0"),
            "scan": scan or (last[0] if last else None), "high_threshold": scanner.HIGH,
            "counts": {"clusters_7d": len(rows), "high": len(high), "watchlist": len(watch)},
            "high": high, "watchlist": watch, "days": days, "volume": vol,
            "trend": {"max": mx, "avg": [round(t / k, 1) if k else 0 for t, k in zip(tot, n)], "high": hi},
            "geo": geo, "sources": sources}
    ts = [d for r in high + watch for d in (scanner.parse_t(r["event_time"]),) if d and d <= now]
    data["data_range"] = ("Data range: " + min(ts).astimezone(ET).strftime("%b %-d, %Y %-I:%M %p %Z") + " – "
                          + max(ts).astimezone(ET).strftime("%b %-d, %Y %-I:%M %p %Z")) if ts else "Data range: no items"
    json.dump(data, open(out, "w"), indent=1, default=str)
    print(out)

if __name__ == "__main__":
    main()
