#!/usr/bin/env python3
"""YouTube channel watch: pull the public RSS feed of each channel in youtube_channels.json
(https://www.youtube.com/feeds/videos.xml?channel_id=...), keep videos published in the last 24 h whose title/description
match a threat category (scanner.classify + scanner.THREAT_RX, trivia filtered), and feed them into the normal pipeline via
ingest_external.py (normalization, 12 h dedupe, clustering, scoring). Already-sent video ids are kept in
youtube_watch_state.json (7 days), so re-running is safe. No keys, no logins, read-only.
Usage: python3 youtube_watch.py [--dry-run] [--hours 24] [--json]"""
import os, sys, json, re, time, subprocess, argparse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
import requests

BASE = os.path.dirname(os.path.abspath(__file__))
CHANNELS = os.path.join(BASE, "youtube_channels.json")
STATE = os.path.join(BASE, "youtube_watch_state.json")
LOG = os.path.join(BASE, "logs", "youtube_watch.log")
NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015", "m": "http://search.yahoo.com/mrss/"}
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) blackout.network research monitor", "Accept-Language": "en"}

def log(msg):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as f: f.write(f"[{datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%SZ}] {msg}\n")

def load_state():
    try: s = json.load(open(STATE))
    except Exception: s = {}
    s.setdefault("seen", {}); s.setdefault("channels", {})
    cut = time.time() - 7 * 86400
    s["seen"] = {k: v for k, v in s["seen"].items() if v >= cut}
    return s

def save_state(s):
    tmp = STATE + ".tmp"; json.dump(s, open(tmp, "w"), indent=1); os.replace(tmp, STATE)

def fetch(cid, tries=2):
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
    last = None
    for i in range(tries):
        try:
            r = requests.get(url, headers=UA, timeout=15)
            if r.status_code == 200 and "<feed" in r.text[:500]: return r.text, None
            last = f"HTTP {r.status_code}"
        except Exception as ex: last = type(ex).__name__
        time.sleep(1.5)
    return None, last

def parse(xml):
    root = ET.fromstring(xml); out = []
    for e in root.findall("a:entry", NS):
        vid = (e.findtext("yt:videoId", "", NS) or "").strip()
        title = (e.findtext("a:title", "", NS) or "").strip()
        pub = e.findtext("a:published", "", NS)
        desc = e.findtext("m:group/m:description", "", NS) or ""
        if vid and title: out.append({"id": vid, "title": title, "published": pub, "desc": desc})
    return out

def relevant(S, title, desc):
    """-> category or None. Title must carry the threat signal; the description only helps pick the category."""
    if re.search(S.TRIVIA_RX, title, re.I) and not re.search(S.BOOST_RX, title, re.I): return None
    if not re.search(S.THREAT_RX, title, re.I): return None
    cat = S.classify(title, "other")
    if cat == "other": cat = S.classify(title + " " + desc[:300], "other")
    return None if cat == "other" else cat

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--hours", type=float, default=24)
    ap.add_argument("--json", action="store_true", help="print the full summary as JSON")
    a = ap.parse_args(argv)
    sys.path.insert(0, BASE); import scanner as S
    chans = json.load(open(CHANNELS))["channels"]
    st = load_state(); since = datetime.now(timezone.utc) - timedelta(hours=a.hours)
    batch, report = [], []
    for ch in chans:
        xml, err = fetch(ch["channel_id"])
        rec = {"name": ch["name"], "ok": bool(xml), "error": err, "recent": 0, "relevant": 0, "new": 0}
        if xml:
            try: vids = parse(xml)
            except Exception as ex: vids = []; rec.update(ok=False, error="parse: " + type(ex).__name__)
            for v in vids:
                t = S.parse_t(v["published"])
                if not t or t < since: continue
                rec["recent"] += 1
                cat = relevant(S, v["title"], v["desc"])
                if not cat: continue
                rec["relevant"] += 1
                if v["id"] in st["seen"]: continue
                rec["new"] += 1
                batch.append({"title": v["title"], "url": f"https://www.youtube.com/watch?v={v['id']}", "source": f"YouTube: {ch['name']}",
                              "time": v["published"], "text": (v["title"] + " " + re.sub(r"\s+", " ", v["desc"]))[:600], "media": True, "_id": v["id"], "_cat": cat})
        st["channels"][ch["channel_id"]] = {"name": ch["name"], "ok": rec["ok"], "error": err, "checked": S.iso(S.now())}
        report.append(rec)
    res = None
    if batch and not a.dry_run:
        payload = [{k: v for k, v in b.items() if not k.startswith("_")} for b in batch]
        p = subprocess.run([sys.executable, os.path.join(BASE, "ingest_external.py")], input=json.dumps(payload), capture_output=True, text=True, cwd=BASE, timeout=300)
        if p.returncode != 0:
            log(f"ingest failed rc={p.returncode}: {p.stderr[-400:]}"); print(json.dumps({"ok": False, "error": "ingest_external failed", "stderr": p.stderr[-400:]})); return 1
        try: res = json.loads(p.stdout)
        except Exception: res = {"raw": p.stdout[-400:]}
        for b in batch: st["seen"][b["_id"]] = time.time()
    if not a.dry_run: save_state(st)
    ok = sum(r["ok"] for r in report)
    summ = {"ok": True, "dry_run": a.dry_run, "channels": len(chans), "feeds_ok": ok, "feeds_failed": [r["name"] + f" ({r['error']})" for r in report if not r["ok"]],
            "recent_videos": sum(r["recent"] for r in report), "relevant": sum(r["relevant"] for r in report), "sent": len(batch),
            "ingest": {k: res.get(k) for k in ("received", "accepted", "new", "skipped")} if isinstance(res, dict) else None,
            "high": (res or {}).get("high") if isinstance(res, dict) else None,
            "items": [{"source": b["source"], "title": b["title"], "url": b["url"], "category": b["_cat"]} for b in batch]}
    log(f"channels={len(chans)} ok={ok} recent={summ['recent_videos']} relevant={summ['relevant']} sent={len(batch)} dry={a.dry_run} ingest={summ['ingest']}")
    if a.json: print(json.dumps(summ, indent=1))
    else:
        print(f"YouTube watch: {ok}/{len(chans)} feeds OK, {summ['recent_videos']} videos in the last {a.hours:g} h, {summ['relevant']} threat-relevant, {len(batch)} new sent"
              + (f"; ingest accepted {summ['ingest']['accepted']}, new {summ['ingest']['new']}" if summ["ingest"] else "") + (" (dry run)" if a.dry_run else ""))
        for f in summ["feeds_failed"]: print("  feed failed:", f)
        for it in summ["items"][:40]: print(f"  [{it['category']}] {it['source']}: {it['title'][:110]}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
