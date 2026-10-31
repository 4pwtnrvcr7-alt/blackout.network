#!/usr/bin/env python3
"""Feed externally gathered items (e.g. X search results from the hourly chat check) through the normal
Blackout normalization / 12h dedup / clustering / scoring pipeline.

stdin: JSON list of {"title": str, "url": str, "source": str, "time": ISO-8601, "text": str}
  - "source" e.g. "X @handle" or "X search: <query>"; any non-social link inside text/url is treated as the cited primary source.
  - Social posts never confirm each other unless they cite distinct primary sources (same rule as Reddit/Bluesky/Telegram).
stdout: JSON summary incl. any clusters now high-severity (score>=60, non-watchlist).
Usage: echo '[{"title":"...","url":"https://x.com/...","source":"X @foo","time":"2026-10-29T04:00:00Z","text":"... https://reuters.com/..."}]' | python3 ingest_external.py
"""
import sys, json, re
import scanner as S
import sources_ext as X

def main():
    raw = json.load(sys.stdin)
    if isinstance(raw, dict): raw = [raw]
    items, skipped = [], 0
    for r in raw:
        title = (r.get("title") or r.get("text") or "").strip()
        url = (r.get("url") or "").strip()
        if not title or not url.startswith("http"): skipped += 1; continue
        text = r.get("text") or ""
        urls = re.findall(r"https?://[^\s\"'<>)]+", text) + [url]
        it = X.social_item(r.get("source") or "external", url, title[:280], url, S.parse_t(r.get("time")) or S.now(), urls, text,
                           extra={"ingest": "external"}, media_flag=bool(r.get("media")))
        if it: items.append(it)
        else: skipped += 1   # not threat-relevant, or new-category item with no reliable link/eyewitness media
    with S.SCAN_LOCK:
        c = S.db()
        new = S.ingest_items(c, items)
        c.commit()
        ids = [i["id"] for i in items]
        rows = []
        if ids:
            q = ",".join("?" * len(ids))
            rows = [dict(x) for x in c.execute(f"""SELECT DISTINCT cl.cluster_id, cl.score, cl.confidence, cl.title, cl.watchlist, cl.rising, cl.brief
                     FROM clusters cl JOIN alerts a ON a.cluster_id=cl.cluster_id WHERE a.id IN ({q})""", ids)]
        c.close()
    import push
    pushres = push.push_new()
    print(json.dumps({"push": pushres, "received": len(raw), "accepted": len(items), "new": len(new), "skipped": skipped,
                      "clusters": rows, "high": [r for r in rows if r["score"] >= S.HIGH and not r["watchlist"]]}, indent=1))

if __name__ == "__main__":
    main()
