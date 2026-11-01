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

PAGE_UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36", "Accept-Language": "en"}
AGO_RX = re.compile(r"(\d+)\s*(second|sec|s|minute|min|m|hour|hr|h|day|d|week|wk|w|month|mo|year|yr|y)s?\b", re.I)
AGO_SEC = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800, "mo": 2592000, "y": 31536000}

def ago_to_iso(txt):
    """'9h ago' / '9 hours ago' / 'Streamed 2 days ago' -> ISO time (upper bound of the age, so never newer than reality)."""
    m = AGO_RX.search(txt or "")
    if not m: return None
    u = m.group(2).lower()
    key = "mo" if u.startswith("mo") else "m" if u.startswith("mi") or u == "m" else u[0]
    sec = (int(m.group(1)) + 1) * AGO_SEC[key] - 1 if key in ("s", "m", "h") else int(m.group(1)) * AGO_SEC[key]
    return (datetime.now(timezone.utc) - timedelta(seconds=sec)).strftime("%Y-%m-%dT%H:%M:%S+00:00")

def fetch_page(cid):
    """Fallback when the RSS feed server is down (it periodically answers 404/500 for every channel for hours):
    read the public channel /videos page and pull id, title and relative age from ytInitialData. -> (vids, err)"""
    try:
        r = requests.get(f"https://www.youtube.com/channel/{cid}/videos", headers=PAGE_UA, cookies={"CONSENT": "YES+1"}, timeout=20)
        if r.status_code != 200: return None, f"page HTTP {r.status_code}"
        m = re.search(r"var ytInitialData = (\{.*?\});</script>", r.text)
        if not m: return None, "page: no ytInitialData"
        data = json.loads(m.group(1))
    except Exception as ex: return None, "page " + type(ex).__name__
    out, seen = [], set()
    def walk(o):
        if isinstance(o, dict):
            lv = o.get("lockupViewModel")
            if isinstance(lv, dict) and lv.get("contentId") and lv["contentId"] not in seen:
                md = (lv.get("metadata") or {}).get("lockupMetadataViewModel") or {}
                title = ((md.get("title") or {}).get("content") or "").strip()
                parts = [p.get("text", {}).get("content", "") for row in ((md.get("metadata") or {}).get("contentMetadataViewModel") or {}).get("metadataRows", [])
                         for p in row.get("metadataParts", [])]
                pub = next((ago_to_iso(t) for t in parts if "ago" in t), None)
                if title and pub: seen.add(lv["contentId"]); out.append({"id": lv["contentId"], "title": title, "published": pub, "desc": ""})
            vr = o.get("videoRenderer")
            if isinstance(vr, dict) and vr.get("videoId") and vr["videoId"] not in seen:
                title = "".join(x.get("text", "") for x in (vr.get("title") or {}).get("runs", [])).strip()
                pub = ago_to_iso((vr.get("publishedTimeText") or {}).get("simpleText", ""))
                if title and pub: seen.add(vr["videoId"]); out.append({"id": vr["videoId"], "title": title, "published": pub, "desc": ""})
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for x in o: walk(x)
    walk(data)
    if out: return out, None
    # a real channel page with no public uploads listed (RSS for such channels is an empty feed) -> ok, 0 videos
    return ([], None) if "channelMetadataRenderer" in m.group(1) else (None, "page: no videos parsed")

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
        rec = {"name": ch["name"], "ok": bool(xml), "error": err, "recent": 0, "relevant": 0, "new": 0, "via": "rss"}
        vids = None
        if xml:
            try: vids = parse(xml)
            except Exception as ex: vids = None; rec.update(ok=False, error="parse: " + type(ex).__name__)
        if vids is None:  # RSS down or unparsable -> channel page fallback
            pv, perr = fetch_page(ch["channel_id"])
            if pv is not None: vids = pv; rec.update(ok=True, via="page", error=None, rss_error=rec["error"])
            else: rec["error"] = f"{rec['error']}; {perr}"
        err = rec["error"]
        if vids is not None:
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
    ok = sum(r["ok"] for r in report); via_page = sum(r["via"] == "page" for r in report)
    summ = {"ok": True, "dry_run": a.dry_run, "channels": len(chans), "feeds_ok": ok, "via_page_fallback": via_page, "feeds_failed": [r["name"] + f" ({r['error']})" for r in report if not r["ok"]],
            "recent_videos": sum(r["recent"] for r in report), "relevant": sum(r["relevant"] for r in report), "sent": len(batch),
            "ingest": {k: res.get(k) for k in ("received", "accepted", "new", "skipped")} if isinstance(res, dict) else None,
            "high": (res or {}).get("high") if isinstance(res, dict) else None,
            "items": [{"source": b["source"], "title": b["title"], "url": b["url"], "category": b["_cat"]} for b in batch]}
    log(f"channels={len(chans)} ok={ok} page_fallback={via_page} recent={summ['recent_videos']} relevant={summ['relevant']} sent={len(batch)} dry={a.dry_run} ingest={summ['ingest']}")
    if a.json: print(json.dumps(summ, indent=1))
    else:
        print(f"YouTube watch: {ok}/{len(chans)} feeds OK ({via_page} via channel-page fallback, RSS down), " if via_page else f"YouTube watch: {ok}/{len(chans)} feeds OK, ", end="")
        print(f"{summ['recent_videos']} videos in the last {a.hours:g} h, {summ['relevant']} threat-relevant, {len(batch)} new sent"
              + (f"; ingest accepted {summ['ingest']['accepted']}, new {summ['ingest']['new']}" if summ["ingest"] else "") + (" (dry run)" if a.dry_run else ""))
        for f in summ["feeds_failed"]: print("  feed failed:", f)
        for it in summ["items"][:40]: print(f"  [{it['category']}] {it['source']}: {it['title'][:110]}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
