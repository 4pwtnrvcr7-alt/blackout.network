#!/usr/bin/env python3
"""Precompute the BLACKOUT.NETWORK story-report layer for /wire/<cluster_id> pages (app/story.py).

Box-side only. Never runs on Render, never calls an LLM, never writes blackout.db (it does not open it at all).
Output: one JSON file, data/story_reports.json, which the box pushes to Render with a signed one-file push (push.py here).

Inputs
  1. Analyst notes the newsletter desk already writes for every brief (analysis/newsletter_analysis_*.json, plus the
     current app newsletter_analysis.json). Each note is keyed by cluster_id and every claim in it is sourced. We keep the
     newest note per story. Prep tips (what_to_do / guide) are dropped: the site report is news only.
  2. The public /api/state + /api/state_items on blackout.network (source URLs per story), used only to find images
     with clear rights:
       - USGS ShakeMap intensity maps for earthquakes the USGS event page covers (public domain, U.S. Geological Survey)
       - Wikimedia Commons files a source page uses as its og:image (license read from the Commons API; free licenses only)
       - optional, OFF by default: og:image of U.S. federal pages (--federal-og) and of news outlets with credit (--outlet-og).
         Both are off because the pre-publish rules forbid wire-agency photos (AP, Getty, Reuters) and unnamed faces,
         which cannot be checked automatically.
Word rules: sentences with "verified", "first to", "before the news", anniversary / "today in history" framing are dropped.
Never invents text: every string in the output is copied from a note or from the image's own source metadata.

usage: build.py --out data/story_reports.json [--notes DIR_OR_FILE ...] [--site https://blackout.network] [--no-net]
"""
import argparse, glob, hashlib, html, io, json, os, re, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

UTC = timezone.utc; ET = ZoneInfo("America/New_York")
UA = "Mozilla/5.0 (compatible; BLACKOUT.NETWORK story-reports/1.0; +https://blackout.network)"
NOTE_FIELDS = ("headline", "what_happened", "why_it_matters", "analysis", "trajectory", "outlook", "confidence", "confidence_why")
BANNED = re.compile(r"\b(?:un)?verified\b|\bverif(?:y|ies|ying)\b|\bfirst to\b|\bwe were first\b|\bbefore the news\b|\banniversar(?:y|ies)\b|"
                    r"\btoday in history\b|\byears ago today\b|\bon this day\b|\bbreaking\b", re.I)
BRAND_FIX = re.compile(r"\bblackout[ .]network\b", re.I)
TRAJ = {"UPTREND": "Rising", "DOWNTREND": "Easing", "STEADY": "Steady", "Rising": "Rising", "Easing": "Easing", "Steady": "Steady"}
CONF = {"High", "Medium", "Low"}
FREE_LIC = re.compile(r"^(?:cc0|public domain|pd\b|pd-|cc[ -]by(?:[ -]sa)?(?:[ -]\d\.\d)?)", re.I)
FEDERAL = ("nasa.gov", "noaa.gov", "weather.gov", "usgs.gov", "defense.gov", "dvidshub.net", "nps.gov", "fema.gov", "cdc.gov", "army.mil",
           "navy.mil", "af.mil", "marines.mil", "uscg.mil", "spaceforce.mil")
BAD_IMG = re.compile(r"logo|seal|favicon|icon|default|placeholder|share[-_]?image|social[-_]?share|og[-_]?default|banner|sprite|avatar", re.I)

def log(*a): print(*a, file=sys.stderr, flush=True)

def sentences(s): return [x for x in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"“'(])", (s or "").strip()) if x.strip()]

def clean_text(s):
    """Drop sentences that break the word rules; normalise the brand name. Returns '' when nothing clean is left."""
    keep = [x for x in sentences(s) if not BANNED.search(x)]
    return BRAND_FIX.sub("BLACKOUT.NETWORK", " ".join(keep)).strip()

def parse_dt(s):
    try: return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(UTC)
    except Exception: return None

def edition_label(path, gen):
    m = re.search(r"_(\d{8})(?:_(am|pm))?\.json$", path or "")
    d = gen.astimezone(ET) if gen else None
    part = (m.group(2) if m and m.group(2) else ("am" if d and d.hour < 15 else "pm")) if d or m else ""
    day = datetime.strptime(m.group(1), "%Y%m%d") if m else d
    if not day: return "BLACKOUT.NETWORK brief"
    return f"{day.strftime('%b')} {day.day} {'morning' if part == 'am' else 'evening'} brief"

def note_files(paths):
    out = []
    for p in paths:
        if os.path.isdir(p): out += [f for f in glob.glob(os.path.join(p, "newsletter_analysis_*.json")) if re.search(r"_\d{8}(?:_(?:am|pm))?\.json$", f)]
        elif os.path.isfile(p): out.append(p)
    return sorted(set(out))

def load_notes(paths, max_age_days):
    best, now = {}, datetime.now(UTC)
    for f in note_files(paths):
        try: d = json.load(open(f))
        except Exception as ex: log(f"skip {f}: {ex}"); continue
        gen = parse_dt(d.get("generated_at"))
        if not gen or gen > now + timedelta(minutes=10) or now - gen > timedelta(days=max_age_days): continue
        for cid, it in (d.get("items") or {}).items():
            if not re.fullmatch(r"[0-9a-f]{16}", str(cid)) or not isinstance(it, dict): continue
            if cid in best and best[cid]["generated_at"] >= gen.isoformat(): continue
            n = {k: clean_text(it.get(k)) if k not in ("trajectory", "confidence") else (it.get(k) or "") for k in NOTE_FIELDS}
            n["trajectory"] = TRAJ.get(n["trajectory"], "")
            n["confidence"] = n["confidence"] if n["confidence"] in CONF else ""
            srcs = [u for u in (it.get("sources") or []) if isinstance(u, str) and re.match(r"^https?://[^\s<>\"]+$", u)]
            if not srcs or not n["what_happened"]: continue        # analysis must be grounded in cited sources
            n.update(sources=[{"url": u, "domain": urllib.parse.urlsplit(u).netloc.lower().removeprefix("www.")} for u in srcs[:8]],
                     generated_at=gen.isoformat(), edition=edition_label(f, gen), file=os.path.basename(f))
            best[cid] = n
    return best

# ---------------------------------------------------------------- network helpers (cached)
class Net:
    def __init__(self, cache_path, enabled=True):
        self.p, self.on = cache_path, enabled
        try: self.c = json.load(open(cache_path))
        except Exception: self.c = {}
    def save(self):
        if not self.p: return
        tmp = self.p + ".tmp"; json.dump(self.c, open(tmp, "w")); os.replace(tmp, self.p)
    def get(self, url, limit=1_500_000, ttl=86400, binary=False):
        k = ("B:" if binary else "T:") + url
        hit = self.c.get(k)
        if hit and time.time() - hit["t"] < ttl and not binary: return hit["code"], hit.get("final", url), hit.get("body", "")
        if not self.on: return 0, url, ""
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"}), timeout=15)
            raw = r.read(limit); code, final = r.status, r.geturl()
        except urllib.error.HTTPError as e: code, final, raw = e.code, url, b""
        except Exception: code, final, raw = 0, url, b""
        if binary: return code, final, raw
        body = raw.decode("utf-8", "replace")
        self.c[k] = {"t": time.time(), "code": code, "final": final, "body": body[:200_000] if code == 200 else ""}
        return code, final, body

def link_status(net, url):
    """'ok' | 'blocked' (bot wall, page probably fine) | 'dead' (404/410/redirect to a homepage)."""
    code, final, body = net.get(url, limit=200_000)
    if code in (404, 410): return "dead"
    if code == 200:
        if re.search(r"<title>\s*(?:One moment, please|Just a moment|Attention Required|Access denied)", body or "", re.I): return "blocked"
        if urllib.parse.urlsplit(final).path in ("", "/") and urllib.parse.urlsplit(url).path not in ("", "/"): return "dead"
        return "ok"
    return "blocked"

def img_size(net, url):
    code, _, raw = net.get(url, limit=8_000_000, binary=True)
    if code != 200 or not raw: return None
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(raw)); return im.size
    except Exception: return None

def usgs_shakemap(net, url):
    m = re.search(r"earthquake\.usgs\.gov/earthquakes/eventpage/([a-z0-9]+)", url)
    if not m: return None
    code, _, body = net.get(f"https://earthquake.usgs.gov/fdsnws/event/1/query?eventid={m.group(1)}&format=geojson", limit=3_000_000)
    if code != 200: return None
    try: ev = json.loads(body)
    except Exception: return None
    p = ev.get("properties") or {}
    sm = ((p.get("products") or {}).get("shakemap") or [None])[0]
    if not sm: return None
    img = ((sm.get("contents") or {}).get("download/intensity.jpg") or {}).get("url")
    if not img: return None
    wh = img_size(net, img)
    if not wh: return None
    t = datetime.fromtimestamp(p["time"] / 1000, UTC).astimezone(ET) if p.get("time") else None
    when = f", {t.strftime('%b')} {t.day}, {t.year}" if t else ""
    return {"src": img, "w": wh[0], "h": wh[1], "kind": "map",
            "alt": f"USGS ShakeMap of estimated shaking intensity for the {p.get('title') or 'earthquake'}",
            "caption": f"Estimated shaking intensity, {p.get('title') or 'earthquake'}{when}.",
            "credit": "U.S. Geological Survey ShakeMap", "license": "Public domain (U.S. government work)", "link": p.get("url") or url}

def og_meta(body):
    def meta(prop):
        m = re.search(r'<meta[^>]+(?:property|name)=["\']' + re.escape(prop) + r'["\'][^>]*content=["\']([^"\']+)', body, re.I) or \
            re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\']' + re.escape(prop) + r'["\']', body, re.I)
        return html.unescape(m.group(1)).strip() if m else ""
    return {"image": meta("og:image") or meta("twitter:image"), "alt": meta("og:image:alt") or meta("twitter:image:alt"),
            "title": meta("og:title"), "site": meta("og:site_name")}

def commons_image(net, page_url, og):
    m = re.search(r"upload\.wikimedia\.org/wikipedia/commons/(?:thumb/)?[0-9a-f]/[0-9a-f]{2}/([^/?#]+)", og.get("image") or "")
    if not m: return None
    fn = urllib.parse.unquote(m.group(1))
    api = ("https://commons.wikimedia.org/w/api.php?action=query&format=json&prop=imageinfo&iiprop=url|size|extmetadata&iiurlwidth=1200&titles="
           + urllib.parse.quote("File:" + fn))
    code, _, body = net.get(api, limit=500_000)
    if code != 200: return None
    try: page = next(iter(json.loads(body)["query"]["pages"].values())); ii = page["imageinfo"][0]
    except Exception: return None
    md = ii.get("extmetadata") or {}
    lic = re.sub(r"<[^>]+>", "", (md.get("LicenseShortName") or {}).get("value", "")).strip()
    artist = re.sub(r"<[^>]+>", "", (md.get("Artist") or {}).get("value", "")).strip()
    if not FREE_LIC.match(lic) or not artist: return None
    return {"src": ii.get("thumburl") or ii["url"], "w": ii.get("thumbwidth") or ii["width"], "h": ii.get("thumbheight") or ii["height"], "kind": "photo",
            "alt": og.get("alt") or re.sub(r"\.\w+$", "", fn).replace("_", " "), "caption": og.get("alt") or "",
            "credit": f"{artist} / Wikimedia Commons", "license": lic, "link": ii.get("descriptionurl") or page_url}

def og_image(net, page_url, allow_federal, allow_outlet, seen):
    dom = urllib.parse.urlsplit(page_url).netloc.lower().removeprefix("www.")
    is_fed = any(dom == d or dom.endswith("." + d) for d in FEDERAL)
    code, final, body = net.get(page_url)
    if code != 200 or not body: return None
    og = og_meta(body)
    c = commons_image(net, page_url, og)
    if c: return c
    if not og["image"] or not (allow_outlet or (allow_federal and is_fed)): return None
    src = urllib.parse.urljoin(final, og["image"])
    if not src.startswith("https://") or BAD_IMG.search(src): return None
    seen.setdefault((dom, src), set()).add(page_url)
    if len(seen[(dom, src)]) > 1: return None            # same image on several pages of one site = a site default, not story art
    wh = img_size(net, src)
    if not wh or wh[0] < 600 or not (1.2 <= wh[0] / max(1, wh[1]) <= 2.2): return None
    site = og["site"] or dom
    return {"src": src, "w": wh[0], "h": wh[1], "kind": "photo", "alt": og["alt"] or og["title"] or f"Image from {site}",
            "caption": og["alt"] or og["title"] or "", "credit": site,
            "license": "Public domain (U.S. government work)" if is_fed else f"Image: {site}. Shown with credit; links to the source.",
            "link": page_url}

def fetch_json(url):
    r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60)
    return json.loads(r.read())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--notes", nargs="*", default=["/workspace/launch/newsletter/analysis", "/workspace/blackout/newsletter_analysis.json"])
    ap.add_argument("--site", default="https://blackout.network")
    ap.add_argument("--cache", default="")
    ap.add_argument("--max-age-days", type=float, default=21)
    ap.add_argument("--max-images", type=int, default=3)
    ap.add_argument("--min-rank", type=int, default=3)
    ap.add_argument("--federal-og", action="store_true")
    ap.add_argument("--outlet-og", action="store_true")
    ap.add_argument("--no-net", action="store_true")
    a = ap.parse_args()
    net = Net(a.cache or (a.out + ".cache.json"), enabled=not a.no_net)
    notes = load_notes(a.notes, a.max_age_days)
    for cid, n in notes.items():          # pre-publish rule B1: drop source links that 404 or bounce to a homepage
        for s in n["sources"]: s["status"] = link_status(net, s["url"]) if not a.no_net else "unchecked"
        n["sources"] = [s for s in n["sources"] if s["status"] != "dead"]
    notes = {k: v for k, v in notes.items() if v["sources"]}
    images, st, items = {}, {}, {}
    if not a.no_net:
        try:
            st = fetch_json(a.site.rstrip("/") + "/api/state"); items = fetch_json(a.site.rstrip("/") + "/api/state_items").get("items") or {}
        except Exception as ex: log(f"state fetch failed: {ex}")
    seen = {}
    for c in (st.get("main") or []) + (st.get("watchlist") or []):
        cid = c.get("cluster_id") or ""
        if (c.get("rank") or 0) < a.min_rank and cid not in notes: continue
        urls = [l.get("url") for l in (c.get("links") or [])] + [i.get("url") for i in items.get(cid) or []] + [s["url"] for s in (notes.get(cid) or {}).get("sources", [])]
        urls = [u for u in dict.fromkeys(urls) if isinstance(u, str) and u.startswith("http")][:12]
        got = []
        for u in urls:
            im = usgs_shakemap(net, u)
            if im is None and (a.federal_og or a.outlet_og or "wikipedia.org" in u): im = og_image(net, u, a.federal_og, a.outlet_og, seen)
            if im and im["src"] not in {g["src"] for g in got}: got.append(im)
            if len(got) >= a.max_images: break
        if got: images[cid] = got
    net.save()
    out = {"v": 1, "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(), "notes": notes, "images": images,
           "image_policy": {"usgs_shakemap": True, "commons": True, "federal_og": a.federal_og, "outlet_og": a.outlet_og}}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    tmp = a.out + ".tmp"
    with open(tmp, "w") as f: json.dump(out, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    os.replace(tmp, a.out)
    log(f"story_reports: {len(notes)} notes, {sum(map(len, images.values()))} images for {len(images)} stories -> {a.out}")

if __name__ == "__main__":
    main()
