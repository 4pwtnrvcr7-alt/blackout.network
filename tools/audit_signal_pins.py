#!/usr/bin/env python3
"""Audit signal-map pin countries against Natural Earth admin-0.

Usage:
  python3 tools/audit_signal_pins.py [/path/to/blackout.db]

Reads clusters read-only (file:...?mode=ro). Reports % of plotted points whose
lat/lon sit inside the story's country (target 100%), lists corrections, and
counts location-unverified drops.
"""
import argparse, json, os, sys, sqlite3
from collections import defaultdict
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))
import signal_place  # noqa: E402


def load_rows(db):
    cut = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=8)
    c.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in c.execute(
            """SELECT cluster_id, title, category, location, lat, lon, event_time, first_seen, updated,
                      rank, links, watchlist, brief FROM clusters
               WHERE watchlist IN (0, 1) AND COALESCE(event_time, first_seen)>=?""", (cut,))]
    finally:
        c.close()


def naive_infer(story):
    hit = signal_place._nws(story)
    if hit: return hit
    hit = signal_place._from_text(story)
    if hit: return hit
    hit = signal_place._from_gazetteer(story)
    if hit: return hit
    return signal_place._region(story)


def check(hit, prefer=None):
    if not hit: return None
    cc = hit.get("cc") or prefer
    if not cc or (hit.get("precision") == "region" and not hit.get("cc")):
        return True
    return signal_place.in_country(hit["lat"], hit["lon"], cc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("db", nargs="?", default=os.path.join(ROOT, "app", "blackout.db"))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rows = load_rows(args.db)
    before_ok = before_bad = before_none = 0
    after_none = after_unverified = 0
    fixes = []
    country_buckets = defaultdict(list)
    plotted = []

    for r in rows:
        story = signal_place.story_text(r.get("title"), r.get("location"), r.get("brief"))
        named = signal_place.named_countries(story)
        prefer = named[0] if len(named) == 1 else None
        old = naive_infer(story)
        new = signal_place.infer(story, prefer_cc=prefer)

        if old is None: before_none += 1
        elif check(old, prefer): before_ok += 1
        else: before_bad += 1

        if new is None:
            if named: after_unverified += 1
            else: after_none += 1
        else:
            plotted.append((r, new))
            if new.get("precision") == "country" and new.get("cc"):
                country_buckets[new["cc"]].append((r, new))

        if old and new and (
            round(old["lat"], 3) != round(new["lat"], 3)
            or round(old["lon"], 3) != round(new["lon"], 3)
            or (old.get("place") or "") != (new.get("place") or "")
        ):
            fixes.append({
                "title": (r.get("title") or "")[:120],
                "old_place": old.get("place"), "old_cc": old.get("cc"),
                "old_lat": old.get("lat"), "old_lon": old.get("lon"),
                "new_place": new.get("place"), "new_cc": new.get("cc"),
                "new_lat": new.get("lat"), "new_lon": new.get("lon"),
            })
        elif old and not new and named:
            fixes.append({
                "title": (r.get("title") or "")[:120],
                "old_place": old.get("place"), "old_cc": old.get("cc"),
                "old_lat": old.get("lat"), "old_lon": old.get("lon"),
                "new_place": None, "new_cc": None, "note": "dropped (unverified)",
            })

    distributed = 0
    for cc, items in country_buckets.items():
        total = len(items)
        for n, (r, hit) in enumerate(items):
            placed = signal_place.place_in_country(
                cc, story_id=str(r.get("cluster_id") or n), index=n, total=total)
            if not placed: continue
            hit.update(lat=placed["lat"], lon=placed["lon"],
                       place=placed.get("place") or hit.get("place"),
                       approximate=True, precision="country", cc=cc)
            distributed += 1

    final_ok = final_bad = 0
    for r, hit in plotted:
        cc = hit.get("cc")
        if not cc or (hit.get("precision") == "region" and not cc):
            final_ok += 1; continue
        if signal_place.in_country(hit["lat"], hit["lon"], cc): final_ok += 1
        else: final_bad += 1

    plotted_n = final_ok + final_bad
    pct = (100.0 * final_ok / plotted_n) if plotted_n else 0.0
    before_plotted = before_ok + before_bad
    before_pct = (100.0 * before_ok / before_plotted) if before_plotted else 0.0
    report = {
        "db": args.db, "rows": len(rows),
        "before": {"plotted": before_plotted, "inside": before_ok, "outside": before_bad,
                   "none": before_none, "pct_inside": round(before_pct, 2)},
        "after": {"plotted": plotted_n, "inside": final_ok, "outside": final_bad,
                  "unmapped": after_none, "unverified": after_unverified,
                  "pct_inside": round(pct, 2), "distributed_country_pins": distributed},
        "fixes": fixes[:40], "fix_count": len(fixes),
    }
    print(json.dumps({k: report[k] for k in ("db", "rows", "before", "after", "fix_count")}, indent=2))
    print("\nExample fixes:")
    for f in fixes[:15]:
        print(f"  - {f.get('title')}")
        print(f"    old: {f.get('old_place')} ({f.get('old_cc')}) @ {f.get('old_lat')},{f.get('old_lon')}")
        print(f"    new: {f.get('new_place')} ({f.get('new_cc')}) @ {f.get('new_lat')},{f.get('new_lon')} {f.get('note','')}")
    if args.json:
        out = os.path.join(os.path.dirname(args.db) or ".", "audit_signal_pins.json")
        with open(out, "w", encoding="utf-8") as fh: json.dump(report, fh, indent=2)
        print("wrote", out)
    sys.exit(0 if final_bad == 0 else 2)

if __name__ == "__main__":
    main()
