#!/usr/bin/env python3
"""Blackout Network snapshot worker (runs under /workspace/.shotenv python; started by timeline.py).
Captures a screenshot of each eligible alert's source page (rank >= 4 or confirmed by 2+ source families), then burns a
black metadata bar BELOW the capture (never over it) and embeds the same metadata as EXIF + XMP.
Reads blackout.db READ-ONLY; writes only timeline.db and snapshots/. Rate-capped, 3 GB disk cap. Never touches scoring."""
import json, os, re, sqlite3, sys, time, textwrap, traceback, io
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont
BASE = os.path.dirname(os.path.abspath(__file__)); SNAP = os.path.join(BASE, "snapshots"); TDB = os.path.join(BASE, "timeline.db")
DISK_CAP = 3 * 1024 ** 3; MIN_GAP_S = 12; MAX_PER_HOUR = 180; ET = ZoneInfo("America/New_York")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"; FONTB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"; FONTM = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
def tdb():
    c = sqlite3.connect(TDB, timeout=30); c.execute("PRAGMA journal_mode=WAL")
    c.execute("""CREATE TABLE IF NOT EXISTS snapshots(cluster_id TEXT PRIMARY KEY, status TEXT, file TEXT, url TEXT, captured_at TEXT,
                 attempts INTEGER DEFAULT 0, error TEXT, bytes INTEGER DEFAULT 0, title TEXT, rank INTEGER, score INTEGER)"""); return c
def src():
    return sqlite3.connect(f"file:{BASE}/blackout.db?mode=ro", uri=True, timeout=30)
def disk_used(): return sum(os.path.getsize(os.path.join(SNAP, f)) for f in os.listdir(SNAP) if f.endswith(".jpg"))
def pick_url(links):
    good = [l for l in links if l.get("url", "").startswith("http")]
    pref = [l for l in good if "news.google.com" not in l["url"] and "api.weather.gov" not in l["url"]]
    return (pref or good or [{}])[0]
def wrap(draw, text, font, width):
    out = []
    for para in text.split("\n"):
        line = ""
        for tok in re.split(r"(\s+|(?<=[/&?=_-]))", para):
            if not tok: continue
            if draw.textlength(line + tok, font=font) <= width: line += tok; continue
            if line.strip(): out.append(line.rstrip())
            tok = tok.lstrip()
            while tok and draw.textlength(tok, font=font) > width:   # very long token (URL): hard-break
                k = len(tok)
                while k > 1 and draw.textlength(tok[:k], font=font) > width: k -= 1
                out.append(tok[:k]); tok = tok[k:]
            line = tok
        out.append(line.rstrip())
    return [l for l in out if l] or [""]
def burn(png_bytes, meta):
    shot = Image.open(io.BytesIO(png_bytes)).convert("RGB"); W = shot.width; pad = 18
    f_t, f_b, f_m, f_h = ImageFont.truetype(FONTB, 26), ImageFont.truetype(FONT, 19), ImageFont.truetype(FONTM, 17), ImageFont.truetype(FONTB, 15)
    d0 = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    rows = [("BLACKOUT.NETWORK SNAPSHOT", f_h, "#ff4d4f")]
    rows += [(l, f_t, "#ffffff") for l in wrap(d0, meta["title"], f_t, W - 2 * pad)]
    rows += [(l, f_b, "#e6e9ee") for l in wrap(d0, f"Rank {meta['rank']}/10 · Score {meta['score']}/100 · Category: {meta['category']} · Confidence: {meta['confidence']} · {meta['feed']}", f_b, W - 2 * pad)]
    rows += [(l, f_b, "#c9d0d9") for l in wrap(d0, f"Sources ({len(meta['sources'])}): " + ", ".join(meta["sources"]), f_b, W - 2 * pad)]
    rows += [(l, f_m, "#7fc1ff") for l in wrap(d0, "Source URL: " + meta["url"], f_m, W - 2 * pad)]
    if meta.get("final_url") and meta["final_url"] != meta["url"]: rows += [(l, f_m, "#9fb3c8") for l in wrap(d0, "Page shown: " + meta["final_url"], f_m, W - 2 * pad)]
    rows += [(l, f_b, "#e6e9ee") for l in wrap(d0, f"Captured: {meta['captured_et']}  ({meta['captured_utc']})  ·  Event time: {meta['event_et']}  ·  Item {meta['cluster_id']}", f_b, W - 2 * pad)]
    lh = lambda f: int(f.size * 1.38)
    H = pad * 2 + sum(lh(f) for _, f, _ in rows)
    out = Image.new("RGB", (W, shot.height + H), "#000000"); out.paste(shot, (0, 0))
    d = ImageDraw.Draw(out); d.line([(0, shot.height), (W, shot.height)], fill="#ff4d4f", width=3); y = shot.height + pad
    for text, f, col in rows: d.text((pad, y), text, font=f, fill=col); y += lh(f)
    return out
def xmp(meta):
    e = lambda s: str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    return f"""<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?><x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
<rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:xmp="http://ns.adobe.com/xap/1.0/" xmlns:photoshop="http://ns.adobe.com/photoshop/1.0/" xmlns:bn="https://blackout.network/ns/1.0/"
 dc:source="{e(meta['url'])}" xmp:CreateDate="{e(meta['captured_utc_iso'])}" xmp:CreatorTool="blackout.network snapshot worker" photoshop:Headline="{e(meta['title'])}"
 bn:rank="{meta['rank']}" bn:score="{meta['score']}" bn:category="{e(meta['category'])}" bn:sources="{e(', '.join(meta['sources']))}" bn:clusterId="{e(meta['cluster_id'])}" bn:capturedET="{e(meta['captured_et'])}">
<dc:title><rdf:Alt><rdf:li xml:lang="x-default">{e(meta['title'])}</rdf:li></rdf:Alt></dc:title>
<dc:description><rdf:Alt><rdf:li xml:lang="x-default">{e(meta['summary'])}</rdf:li></rdf:Alt></dc:description>
<dc:creator><rdf:Seq><rdf:li>blackout.network snapshot</rdf:li></rdf:Seq></dc:creator></rdf:Description></rdf:RDF></x:xmpmeta><?xpacket end="w"?>""".encode()
def save(img, path, meta):
    ex = Image.Exif()
    ex[0x010E] = meta["summary"][:1900]          # ImageDescription
    ex[0x013B] = "blackout.network snapshot"      # Artist
    ex[0x0131] = "blackout.network snapshot worker"  # Software
    ex[0x0132] = meta["captured_dt"].strftime("%Y:%m:%d %H:%M:%S")  # DateTime (UTC)
    ex[0x8298] = "Screenshot of " + meta["url"][:900]  # Copyright field used for the source link
    img.save(path, "JPEG", quality=82, optimize=True, progressive=True, exif=ex.tobytes(), xmp=xmp(meta))
def fmt_et(iso):
    try: return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(ET).strftime("%b %-d, %Y %-I:%M %p ET")
    except Exception: return "n/a"
def main():
    from playwright.sync_api import sync_playwright
    open(os.path.join(BASE, "logs", "snapshot_worker.pid"), "w").write(str(os.getpid()))
    hist = []
    with sync_playwright() as p:
        br = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox", "--disable-dev-shm-usage", "--mute-audio"])
        while True:
            try:
                if disk_used() > DISK_CAP: time.sleep(600); continue
                now = time.time(); hist = [t for t in hist if now - t < 3600]
                if len(hist) >= MAX_PER_HOUR: time.sleep(60); continue
                c = tdb(); done = {r[0] for r in c.execute("SELECT cluster_id FROM snapshots WHERE status='ok' OR attempts>=2")}
                s = src(); s.row_factory = sqlite3.Row
                rows = s.execute("""SELECT cluster_id,title,category,score,rank,confidence,families,links,event_time,first_seen,watchlist,eff_families,n_families
                                    FROM clusters WHERE (rank>=4 OR eff_families>=2 OR n_families>=2) ORDER BY first_seen DESC LIMIT 2000""").fetchall(); s.close()
                todo = [r for r in rows if r["cluster_id"] not in done]
                if not todo: c.close(); time.sleep(30); continue
                r = todo[0]; links = json.loads(r["links"] or "[]"); L = pick_url(links); url = L.get("url")
                att = (c.execute("SELECT attempts FROM snapshots WHERE cluster_id=?", (r["cluster_id"],)).fetchone() or [0])[0]
                if not url:
                    c.execute("INSERT OR REPLACE INTO snapshots(cluster_id,status,attempts,error,title,rank,score) VALUES(?,?,?,?,?,?,?)", (r["cluster_id"], "nolink", 2, "no http link", r["title"], r["rank"], r["score"])); c.commit(); c.close(); continue
                ctx = br.new_context(viewport={"width": 1280, "height": 900}, device_scale_factor=1, java_script_enabled=True, user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36 BlackoutNetworkSnapshot")
                pg = ctx.new_page(); err = None; png = None; final = url
                try:
                    pg.goto(url, timeout=25000, wait_until="domcontentloaded"); pg.wait_for_timeout(3500); png = pg.screenshot(type="png")
                    final = pg.url
                except Exception as ex:
                    err = f"{type(ex).__name__}: {str(ex)[:160]}"
                    try: png = pg.screenshot(type="png"); final = pg.url
                    except Exception: png = None
                finally:
                    ctx.close()
                if png:
                    dt = datetime.now(timezone.utc)
                    fams = json.loads(r["families"] or "[]")
                    meta = dict(cluster_id=r["cluster_id"], title=r["title"] or "", rank=r["rank"], score=r["score"], category=r["category"], confidence=r["confidence"],
                                feed="Watchlist" if r["watchlist"] else "The Wire", sources=fams or [L.get("source", "")], url=url, final_url=final,
                                captured_dt=dt, captured_utc=dt.strftime("%Y-%m-%d %H:%M:%S UTC"), captured_utc_iso=dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                captured_et=dt.astimezone(ET).strftime("%b %-d, %Y %-I:%M:%S %p ET"), event_et=fmt_et(r["event_time"] or r["first_seen"]))
                    meta["summary"] = (f"{meta['title']} | Rank {meta['rank']}/10, score {meta['score']}/100, {meta['category']} | Sources: {', '.join(meta['sources'])} | "
                                       f"Source URL: {url} | Page shown: {final} | Captured {meta['captured_et']} ({meta['captured_utc']}) | blackout.network snapshot")
                    fn = f"{r['cluster_id']}_{dt.strftime('%Y%m%dT%H%M%SZ')}.jpg"
                    save(burn(png, meta), os.path.join(SNAP, fn), meta)
                    c.execute("INSERT OR REPLACE INTO snapshots VALUES(?,?,?,?,?,?,?,?,?,?,?)", (r["cluster_id"], "ok", fn, url, meta["captured_utc_iso"], att + 1, err, os.path.getsize(os.path.join(SNAP, fn)), r["title"], r["rank"], r["score"]))
                else:
                    c.execute("INSERT OR REPLACE INTO snapshots(cluster_id,status,url,attempts,error,title,rank,score) VALUES(?,?,?,?,?,?,?,?)", (r["cluster_id"], "failed", url, att + 1, err, r["title"], r["rank"], r["score"]))
                c.commit(); c.close(); hist.append(time.time()); time.sleep(MIN_GAP_S)
            except Exception:
                traceback.print_exc(); time.sleep(30)
if __name__ == "__main__":
    import fcntl
    _lk = open(os.path.join(BASE, "logs", "snapshot_worker.lock"), "w")
    try: fcntl.flock(_lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError: sys.exit(0)   # another instance is already running
    os.nice(10); main()
