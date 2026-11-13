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
NOTE_FIELDS = ("headline", "what_happened", "why_it_matters", "analysis", "trajectory", "outlook", "confidence", "confidence_why",
               "what_to_do", "if_true", "if_false", "pattern", "risk", "risk_why")   # v2 (t1324u): prep tip kept for "What you should do"; if_true/if_false/pattern optional
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
            n = {k: clean_text(it.get(k)) if k not in ("trajectory", "confidence", "risk") else (it.get(k) or "") for k in NOTE_FIELDS}
            n["trajectory"] = TRAJ.get(n["trajectory"], "")
            n["confidence"] = n["confidence"] if n["confidence"] in CONF else ""
            n["risk"] = (it.get("risk") or "") if it.get("risk") in ("Low", "Medium", "High") else ""
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

# ---------------------------------------------------------------- v2 (t1324u): homepage coverage, note aliases, outlet share cards
AGENCY_IMG = re.compile(r"getty|gettyimages|apimages|assets\.apnews|/ap-?photo|reuters\.com/resizer|reutersmedia|afp\.com|afpforum|shutterstock|alamy|epa-?images|"
                        r"(?:^|[/_-])(?:afp|reuters|getty|epa|ap)[_-]|_(?:afp|reuters|getty|epa)\b|media_attachments|"
                        r"fallback|og[-_]?image|opengraph|metatag|og\.png|share[-_]?v?\d|home[-_]share|/themes/|/assets/frontend|thumbnail\.png|"
                        r"ytimg\.com|youtube|twimg\.com|fbcdn|redd\.it|cdninstagram|telegram|bsky", re.I)
SOCIAL = ("x.com", "twitter.com", "youtube.com", "youtu.be", "reddit.com", "bsky.app", "t.me", "facebook.com", "instagram.com", "tiktok.com",
          "mastodon.social", "news.google.com", "threads.net")
_STOPW = set("""the and for with from that this have has had will would could after amid about against their there where which while what when were been than
then they them said says say report reports reported news live breaking update latest video people new more warns warning alert official officials just today
week month year also another other over into under least""".split())
def _tok(t): return {w for w in re.findall(r"[a-z\u00c0-\u024f]{4,}", (t or "").lower()) if w not in _STOPW}

def homepage_stories(net, site):
    """{cluster_id: {"rank": int, "title": str}} for every /wire/<id> the live homepage links (server list + BNA cards)."""
    code, _, body = net.get(site.rstrip("/") + "/", limit=3_000_000, ttl=0)
    out = {}
    if code != 200: return out
    for m in re.finditer(r'\{"rank":(\d+),"url":"/wire/([0-9a-f]{16})","title":"((?:[^"\\]|\\.)*)"', body):
        try: out.setdefault(m.group(2), {"rank": int(m.group(1)), "title": json.loads('"' + m.group(3) + '"')})
        except Exception: pass
    for m in re.finditer(r'\{"cluster_id":"([0-9a-f]{16})","title":"((?:[^"\\]|\\.)*)"[^{}]*?"rank":(\d+)', body):
        try: out.setdefault(m.group(1), {"rank": int(m.group(3)), "title": json.loads('"' + m.group(2) + '"')})
        except Exception: pass
    for cid in re.findall(r"/wire/([0-9a-f]{16})", body): out.setdefault(cid, {"rank": 0, "title": ""})
    return out

def wire_links(net, site, cid):
    """Source links listed on our own /wire/<id> page (Timeline and sources), cached 6 h."""
    code, _, body = net.get(f"{site.rstrip('/')}/wire/{cid}", limit=600_000, ttl=6 * 3600)
    if code != 200: return []
    i = body.find('<ul class="tl">')
    seg = body[i:] if i >= 0 else body
    return [html.unescape(u) for u in re.findall(r'<a href="(https?://[^"]+)" target="_blank"', seg)][:40]

_WHEN = re.compile(r'<div class="when">(?:<span[^>]*>[^<]*</span>)?([A-Z][a-z]{2} \d{1,2}, \d{4}, \d{1,2}:\d{2} [AP]M) (E[SD]T)</div>')
def wire_latest(net, site, cid):
    """Time (UTC ISO) of the newest report on our /wire/<id> timeline, cached 30 min. '' when unknown."""
    code, _, body = net.get(f"{site.rstrip('/')}/wire/{cid}", limit=600_000, ttl=1800)
    best = None
    for t, z in _WHEN.findall(body or "") if code == 200 else []:
        try:
            d = datetime.strptime(t, "%b %d, %Y, %I:%M %p").replace(tzinfo=ET).astimezone(UTC)
            best = d if best is None or d > best else best
        except Exception: pass
    return best.isoformat() if best else ""

def load_desk_briefs(path, max_age_days):
    """Desk briefs (desk/briefs.json, written by analysts or the scheduled brief job, see desk/BRIEF_HOWTO.md):
    {cluster_id: {headline, what_happened, why_it_matters, analysis, rank_why, risk, risk_why, if_true, if_false, what_to_do,
    confidence, confidence_why, sources[], written_at}}. Same word rules and source rules as newsletter notes."""
    try: d = json.load(open(path)) if path and os.path.exists(path) else {}
    except Exception as ex: log(f"desk briefs unreadable: {ex}"); return {}
    out, now = {}, datetime.now(UTC)
    for cid, it in (d.get("briefs") if isinstance(d.get("briefs"), dict) else d).items():
        if not re.fullmatch(r"[0-9a-f]{16}", str(cid)) or not isinstance(it, dict): continue
        gen = parse_dt(it.get("written_at"))
        if not gen or gen > now + timedelta(minutes=10) or now - gen > timedelta(days=max_age_days): continue
        n = {k: clean_text(it.get(k)) if k not in ("trajectory", "confidence", "risk") else (it.get(k) or "") for k in NOTE_FIELDS + ("rank_why",)}
        n["trajectory"] = TRAJ.get(n["trajectory"], ""); n["confidence"] = n["confidence"] if n["confidence"] in CONF else ""
        n["risk"] = it.get("risk") if it.get("risk") in ("Low", "Medium", "High") else ""
        srcs = [u for u in (it.get("sources") or []) if isinstance(u, str) and re.match(r"^https?://[^\s<>\"]+$", u)]
        if not srcs or not n["what_happened"]: continue
        n.update(sources=[{"url": u, "domain": urllib.parse.urlsplit(u).netloc.lower().removeprefix("www.")} for u in srcs[:8]],
                 generated_at=gen.isoformat(), edition="BLACKOUT.NETWORK desk brief", file=os.path.basename(path), desk=True)
        out[cid] = n
    return out

def newsletter_hold(path):
    """Cluster ids the desk keeps out of the newsletter (desk/briefs.json entries with "newsletter": "hold", e.g. a scanner
    false positive that is briefed as over-ranked). The sender drops these cards (app/newsletter.py _hold_unbriefed)."""
    try: d = json.load(open(path)) if path and os.path.exists(path) else {}
    except Exception: return []
    b = d.get("briefs") if isinstance(d.get("briefs"), dict) else d
    return sorted(k for k, v in b.items() if re.fullmatch(r"[0-9a-f]{16}", str(k)) and isinstance(v, dict) and v.get("newsletter") == "hold")

def note_alias(notes, home):
    """Carry a desk note to the homepage's newer cluster id for the same story. Strict (a wrong note is worse than none):
    4+ shared distinctive words and Jaccard >= 0.3 between the note headline and the homepage title, one match only."""
    out = {}
    for cid, h in home.items():
        if cid in notes or not h.get("title"): continue
        ht = _tok(h["title"]); best = []
        for nid, n in notes.items():
            nt = _tok(n.get("headline"))
            inter = len(ht & nt); j = inter / max(1, len(ht | nt))
            fresh = (datetime.now(UTC) - (parse_dt(n.get("generated_at")) or datetime.min.replace(tzinfo=UTC))) <= timedelta(hours=48)
            if inter >= 4 and j >= 0.3 and fresh: best.append((j, nid))
        if len(best) == 1 or (len(best) > 1 and sorted(best)[-1][0] - sorted(best)[-2][0] > 0.15): out[cid] = sorted(best)[-1][1]
    return out

def outlet_share(net, page_url, seen):
    """og:image of a news article as a link-preview card. Skips social/aggregator pages, wire-agency and social CDNs, site defaults,
    logos, small images and old file photos. ok=False marks it unreviewed; with --outlet-share-auto (share_policy.auto) the page still shows it
    as a credited link preview (outlet name + link), per the desk decision of Nov 12; --shares-ok lists reviewed images."""
    dom = urllib.parse.urlsplit(page_url).netloc.lower().removeprefix("www.")
    if any(dom == d or dom.endswith("." + d) for d in SOCIAL + FEDERAL): return None
    code, final, body = net.get(page_url)
    if code != 200 or not body: return None
    og = og_meta(body)
    if not og["image"]: return None
    src = urllib.parse.urljoin(final, og["image"])
    if not src.startswith("https://") or BAD_IMG.search(src) or AGENCY_IMG.search(src): return None
    fn = urllib.parse.urlsplit(src).path.rsplit("/", 1)[-1][:40]
    near = " ".join(body[max(0, i - 400):i + 600] for i in [m.start() for m in re.finditer(re.escape(fn), body)][:6]) if len(fn) > 6 else ""
    if re.search(r"getty|associated press|\bAP Photo|\(AP\)|reuters|\bAFP\b|shutterstock|\bEPA\b", (og["alt"] or "") + " " + near, re.I): return None   # wire-agency photo
    m = re.search(r"/(20\d\d)/(\d\d)/", src)
    if m and (datetime.now(UTC).year * 12 + datetime.now(UTC).month) - (int(m.group(1)) * 12 + int(m.group(2))) > 1: return None   # A3: older file photo
    seen.setdefault((dom, src), set()).add(page_url)
    if len(seen[(dom, src)]) > 1: return None
    wh = img_size(net, src)
    if not wh or wh[0] < 600 or not (1.2 <= wh[0] / max(1, wh[1]) <= 2.2): return None
    return {"src": src, "w": wh[0], "h": wh[1], "kind": "share", "site": og["site"] or dom, "title": og["title"][:200], "alt": og["alt"] or og["title"][:200],
            "link": page_url, "ok": False}

def fetch_json(url):
    r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60)
    return json.loads(r.read())

NL_SELECTION = "/workspace/launch/story_reports/desk/newsletter_selection.json"
NL_GATE = "/workspace/launch/newsletter/qa/brief_gate.py"

def refresh_nl_selection():
    """Matt's rule (Nov 12): every story the next newsletter links to needs a live brief. Re-render the next issue's selection
    (newsletter/qa/brief_gate.py --stage select, render only, never sends) so the queue below can include it. Off with BN_NL_SELECT=0."""
    if os.environ.get("BN_NL_SELECT", "1") == "0" or not os.path.exists(NL_GATE): return
    import subprocess
    try:
        p = subprocess.run([sys.executable, NL_GATE, "--stage", "select"], capture_output=True, text=True, timeout=240,
                           env=dict(os.environ, NEWSLETTER_NO_WORKER="1"))
        log(((p.stdout or "").strip().splitlines() or [f"newsletter selection exit={p.returncode}"])[-1][:300])
    except Exception as ex: log(f"newsletter selection skipped: {type(ex).__name__}: {ex}")

def nl_selection(path):
    """[(cluster_id, item)] the next newsletter issue links to, from desk/newsletter_selection.json when it is fresh (< 14 h)."""
    if not path: return []
    try: d = json.load(open(path))
    except Exception: return []
    g, at = parse_dt(d.get("generated_at")), parse_dt(d.get("at"))
    if not g or datetime.now(UTC) - g > timedelta(hours=14): return []
    if at and datetime.now(UTC) - at > timedelta(hours=2): return []
    return [(x["cluster_id"], x) for x in d.get("items") or [] if isinstance(x, dict) and re.fullmatch(r"[0-9a-f]{16}", str(x.get("cluster_id")))]

def write_queue(a, net, notes, alias, home):
    """desk/needs_brief.json: every story the next newsletter links to (any rank) with no brief, then rank >= queue-rank homepage
    stories with no brief, or a brief over 24 h old with newer reports."""
    now, q = datetime.now(UTC), []
    seen = set()
    for cid, x in nl_selection(getattr(a, "nl_selection", "")):   # newsletter stories first, regardless of rank
        if notes.get(cid) or notes.get(alias.get(cid, "")): continue
        seen.add(cid)
        q.append({"cluster_id": cid, "rank": (home.get(cid) or {}).get("rank") or x.get("rank") or 0, "title": x.get("title") or (home.get(cid) or {}).get("title", ""),
                  "url": f"{a.site.rstrip('/')}/wire/{cid}", "latest_report": wire_latest(net, a.site, cid),
                  "reason": "newsletter story (next issue), no brief", "newsletter": True})
    for cid, h in sorted(home.items(), key=lambda x: -(x[1].get("rank") or 0)):
        if (h.get("rank") or 0) < a.queue_rank or cid in seen: continue
        n = notes.get(cid) or notes.get(alias.get(cid, ""))
        latest = wire_latest(net, a.site, cid)
        e = {"cluster_id": cid, "rank": h.get("rank"), "title": h.get("title", ""), "url": f"{a.site.rstrip('/')}/wire/{cid}", "latest_report": latest}
        if not n: q.append(dict(e, reason="no brief")); continue
        g = parse_dt(n.get("generated_at"))
        e["brief_written_at"] = n.get("generated_at"); e["brief_kind"] = "desk" if n.get("desk") else "newsletter"
        if g and now - g > timedelta(hours=24) and latest and parse_dt(latest) and parse_dt(latest) > g: q.append(dict(e, reason="brief over 24 h old, new reports since"))
    tmp = a.queue + ".tmp"
    with open(tmp, "w") as f: json.dump({"generated_at": now.replace(microsecond=0).isoformat(), "count": len(q), "items": q}, f, ensure_ascii=False, indent=1)
    os.replace(tmp, a.queue)
    log(f"needs_brief: {len(q)} stories queued -> {a.queue}")

def write_review(path, shares, home):
    """Contact sheet for the desk: every outlet share card, full size, with its story title. Approve by listing the image URL in --shares-ok."""
    rows = []
    for cid, lst in shares.items():
        for x in lst:
            rows.append(f'<tr><td><img src="{html.escape(x["src"])}" style="max-width:420px"></td><td><b>{html.escape((home.get(cid) or {}).get("title", ""))}</b><br>'
                        f'/wire/{cid}<br>{html.escape(x["site"])}: {html.escape(x["title"])}<br><code>{html.escape(x["src"])}</code><br>approved: {x["ok"]}</td></tr>')
    open(path, "w").write("<meta charset=utf-8><h1>Share cards for review</h1><p>Check A1 subject, A2 place, A11 faces, A12 victims, A16 agency photos.</p><table border=1 cellpadding=6>" + "".join(rows) + "</table>")

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
    ap.add_argument("--outlet-share", action="store_true", help="v2: outlet og:image link-preview cards")
    ap.add_argument("--outlet-share-auto", action="store_true", help="v2: show every filtered share card automatically (desk decision, Nov 12)")
    ap.add_argument("--briefs", default="/workspace/launch/story_reports/desk/briefs.json", help="v2: desk briefs file")
    ap.add_argument("--queue", default="", help="v2: write needs_brief.json (rank >= --queue-rank homepage stories without a fresh brief)")
    ap.add_argument("--queue-rank", type=int, default=5)
    ap.add_argument("--nl-selection", default=NL_SELECTION, help="next-issue newsletter selection (newsletter/qa/brief_gate.py); '' = off")
    ap.add_argument("--shares-ok", default="", help="v2: JSON list of approved share image URLs (desk review)")
    ap.add_argument("--desk", default="/workspace/launch/story_reports/desk/overrides.json",
                    help="v2: desk overrides {cluster_id: {risk, risk_why, if_true, if_false, pattern, what_to_do}}; every value must come from a cited source")
    ap.add_argument("--review-html", default="", help="v2: write a contact sheet of share cards for review")
    a = ap.parse_args()
    net = Net(a.cache or (a.out + ".cache.json"), enabled=not a.no_net)
    notes = load_notes(a.notes, a.max_age_days)
    for cid, b in load_desk_briefs(a.briefs, a.max_age_days).items():   # desk brief wins unless a newsletter note is 12 h+ newer
        n = notes.get(cid)
        if not n or (parse_dt(n["generated_at"]) or datetime.min.replace(tzinfo=UTC)) - parse_dt(b["generated_at"]) < timedelta(hours=12): notes[cid] = b
    for cid, n in notes.items():          # pre-publish rule B1: drop source links that 404 or bounce to a homepage
        for s in n["sources"]: s["status"] = link_status(net, s["url"]) if not a.no_net else "unchecked"
        n["sources"] = [s for s in n["sources"] if s["status"] != "dead"]
    notes = {k: v for k, v in notes.items() if v["sources"]}
    try: desk = json.load(open(a.desk)) if a.desk and os.path.exists(a.desk) else {}
    except Exception as ex: desk = {}; log(f"desk overrides unreadable: {ex}")
    for cid, o in (desk or {}).items():        # v2: desk overrides only extend an existing sourced note (never create one)
        if cid in notes and isinstance(o, dict):
            for k in ("risk_why", "if_true", "if_false", "pattern", "what_to_do"):
                if isinstance(o.get(k), str) and clean_text(o[k]): notes[cid][k] = clean_text(o[k])
            if o.get("risk") in ("Low", "Medium", "High"): notes[cid]["risk"] = o["risk"]
    images, st, items = {}, {}, {}
    if not a.no_net:
        try:
            st = fetch_json(a.site.rstrip("/") + "/api/state"); items = fetch_json(a.site.rstrip("/") + "/api/state_items").get("items") or {}
        except Exception as ex: log(f"state fetch failed: {ex}")
    seen, sseen = {}, {}
    home = homepage_stories(net, a.site) if not a.no_net else {}
    alias = note_alias(notes, home)
    cand = {}
    for c in (st.get("main") or []) + (st.get("watchlist") or []):
        cid = c.get("cluster_id") or ""
        if (c.get("rank") or 0) < a.min_rank and cid not in notes and cid not in home: continue
        cand[cid] = [l.get("url") for l in (c.get("links") or [])] + [i.get("url") for i in items.get(cid) or []]
    for cid, h in home.items():          # v2: every homepage-linked story at rank >= min-rank, plus every top card
        if cid in cand or (h.get("rank") or 0) < a.min_rank and cid not in notes and cid not in alias: continue
        cand[cid] = wire_links(net, a.site, cid) if not a.no_net else []
    ok_list = set()
    if a.shares_ok:
        try: ok_list = set(json.load(open(a.shares_ok)))
        except Exception as ex: log(f"shares-ok unreadable: {ex}")
    shares = {}
    for cid, urls in cand.items():
        nn = notes.get(cid) or notes.get(alias.get(cid, "")) or {}
        urls = [u for u in dict.fromkeys(urls + [s["url"] for s in nn.get("sources", [])]) if isinstance(u, str) and u.startswith("http")][:14]
        got, sh = [], []
        for u in urls:
            im = usgs_shakemap(net, u)
            if im is None and (a.federal_og or a.outlet_og or "wikipedia.org" in u): im = og_image(net, u, a.federal_og, a.outlet_og, seen)
            if im and im["src"] not in {g["src"] for g in got}: got.append(im)
            elif im is None and a.outlet_share and len(sh) < 2:
                x = outlet_share(net, u, sseen)
                if x and x["src"] not in {g["src"] for g in sh}:
                    x["ok"] = x["src"] in ok_list; sh.append(x)
            if len(got) >= a.max_images: break
        if got: images[cid] = got
        if sh: shares[cid] = sh
    net.save()
    out = {"v": 2, "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(), "notes": notes, "images": images,
           "image_policy": {"usgs_shakemap": True, "commons": True, "federal_og": a.federal_og, "outlet_og": a.outlet_og, "outlet_share": a.outlet_share},
           "alias": alias, "shares": shares, "share_policy": {"auto": bool(a.outlet_share_auto)},
           "home": {k: v.get("rank", 0) for k, v in home.items()}, "newsletter_hold": newsletter_hold(a.briefs)}
    if a.review_html: write_review(a.review_html, shares, home)
    if a.queue and a.nl_selection: refresh_nl_selection()
    if a.queue and home: write_queue(a, net, notes, alias, home)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    tmp = a.out + ".tmp"
    with open(tmp, "w") as f: json.dump(out, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    os.replace(tmp, a.out)
    log(f"story_reports: {len(notes)} notes, {sum(map(len, images.values()))} images for {len(images)} stories -> {a.out}")
    if home:
        hn = sum(1 for k in home if k in notes or k in alias); hi = sum(1 for k in home if k in images); hs = sum(1 for k in home if k in shares)
        log(f"story_reports v2 coverage: {len(home)} homepage stories | every page gets an automatic brief | desk note {hn} ({len(alias)} via alias) | "
            f"rights-cleared image {hi} | share cards {hs} ({'shown automatically' if a.outlet_share_auto else str(sum(1 for v in shares.values() for x in v if x.get('ok'))) + ' approved'})")

if __name__ == "__main__":
    main()
