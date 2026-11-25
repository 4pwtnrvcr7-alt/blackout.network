"""Licensed photo for a Wire story's share card, picked by entity and place.

Selection (never on the crawler request path):
  1. a rights-cleared event image from story_reports.json (USGS ShakeMap, federal, Commons)
  2. the box's pick for the story ("lead": the named person's portrait, or a photo of the story's own country)
  3. the first named person's Commons portrait, looked up in the background (Commons API, license read from the file page)
Only public domain, CC0, CC BY and the UK Open Government Licence are used. Share-alike, non-commercial and no-derivative
licenses are refused. The chosen image is downloaded once, shrunk, and kept on disk (BN_PERSIST_DIR or /var/data if the
host has a disk, else logs/story_photos), with the chosen credit in a small JSON next to it.

pick(cid, ...)     no network: the credited candidate (or None), from data already on the box
cached(src)        no network: the stored image file, or None
prefetch(cid, ...) network, bounded: pick + download + store (background warm and the write-up publish gate only)
"""
from __future__ import annotations
import hashlib
import re, io, json, os, re, threading, time, urllib.parse, urllib.request
from pathlib import Path

UA = "BLACKOUT.NETWORK-cards/1.0 (https://blackout.network; hello@blackout.network)"
OK = re.compile(r"^(public domain|cc0|cc by(?! ?-?(sa|nc|nd))|cc-by(?!-(sa|nc|nd))|ogl|open government|u\.?s\.? (government|federal)|attribution$)", re.I)
BAD = re.compile(r"(\bsa\b|-sa|share ?alike|\bnc\b|-nc|non ?commercial|\bnd\b|-nd|no ?deriv)", re.I)
MAX_BYTES = 6_000_000
_LOCK = threading.Lock()
_MEM = {}


def license_ok(lic):
    lic = (lic or "").strip()
    return bool(lic) and bool(OK.search(lic)) and not BAD.search(lic.replace("Public domain", ""))


def _dir():
    for d in (os.environ.get("BN_PERSIST_DIR"), "/var/data"):
        if d and os.path.isdir(d) and os.access(d, os.W_OK):
            p = Path(d) / "story_photos"
            break
    else:
        p = Path(__file__).resolve().parent / "logs" / "story_photos"
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception:
        import tempfile
        p = Path(tempfile.gettempdir()) / "bn-story-photos"
        p.mkdir(parents=True, exist_ok=True)
    return p


def _name(src):
    return hashlib.sha1(src.encode()).hexdigest()[:20]


def cached(src):
    """Path of the stored image for this source URL, or None. No network."""
    if not src:
        return None
    p = _dir() / (_name(src) + ".jpg")
    try:
        return p if p.is_file() and p.stat().st_size > 2000 else None
    except Exception:
        return None


def _cand(d, kind=""):
    if not isinstance(d, dict) or not d.get("src") or not license_ok(d.get("license")):
        return None
    cr = (d.get("credit") or "").strip()
    if len(cr) > 160 or re.search(r"\.(jpe?g|png|webp|tiff?):", cr, re.I):   # a collage of several files: not one clear photo of this story
        return None
    return dict(src=d["src"], credit=cr, license=d.get("license") or "", caption=(d.get("caption") or "").strip(),
                link=d.get("link") or "", kind=d.get("kind") or kind, alt=d.get("alt") or "", w=d.get("w"), h=d.get("h"))


def _choice_file(cid):
    return _dir() / f"choice_{cid}.json"


def stored_choice(cid):
    """The candidate chosen for this story by an earlier lookup (persisted), or None."""
    try:
        return json.loads(_choice_file(cid).read_text())
    except Exception:
        return None


def pick(cid, title="", loc="", text=""):
    """Best licensed candidate from data already on the box (no network); falls back to a stored Commons lookup."""
    try:
        import story_report as SR
        for im in ((SR.reports() or {}).get("images") or {}).get(cid) or []:
            c = _cand(im)
            if c:
                c["label"] = ""
                return c
    except Exception:
        pass
    try:
        import people as PP
        v = PP.lead_for(cid, title, loc, text)
        c = _cand(v) if v else None
        if c:
            c["label"] = c["caption"] if "file photo" in c["caption"].lower() else (c["caption"] + " File photo; not taken at this event.").strip()
            return c
    except Exception:
        pass
    s = stored_choice(cid)
    if s and s.get("src") and license_ok(s.get("license")):
        return s
    return None


def _fetch(src, timeout=7):
    sp = urllib.parse.urlsplit(src)
    if sp.scheme != "https" or not sp.hostname or not sp.hostname.endswith(("wikimedia.org", "wikipedia.org", "usgs.gov", "nasa.gov", "noaa.gov", "fema.gov", "defense.gov", "dvidshub.net", "whitehouse.gov", "treasury.gov", "gov.uk", "state.gov", "si.edu", "loc.gov", "flickr.com", "staticflickr.com")):
        return None
    req = urllib.request.Request(src, headers={"User-Agent": UA, "Accept": "image/jpeg,image/png,image/webp,image/*;q=0.8"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        ct = (r.headers.get("Content-Type") or "").split(";")[0].lower()
        b = r.read(MAX_BYTES + 1)
    if len(b) > MAX_BYTES or not ct.startswith("image/") or "svg" in ct:
        return None
    return b


def store(src):
    """Download (bounded), shrink to <=1600 px and keep the JPEG. Returns the path or None."""
    p = cached(src)
    if p:
        return p
    try:
        b = _fetch(src)
        if not b:
            return None
        from PIL import Image
        im = Image.open(io.BytesIO(b)).convert("RGB")
        im.thumbnail((1600, 1600))
        out = _dir() / (_name(src) + ".jpg")
        im.save(str(out) + ".tmp", "JPEG", quality=88)
        os.replace(str(out) + ".tmp", out)
        return out
    except Exception:
        return None


def _commons_portrait(name, timeout=7):
    """Newest-looking licensed Commons portrait whose file name or description carries the person's full name."""
    q = urllib.parse.urlencode({"action": "query", "format": "json", "generator": "search", "gsrsearch": f'"{name}" portrait', "gsrnamespace": 6, "gsrlimit": 12,
                                "prop": "imageinfo", "iiprop": "url|extmetadata|size", "iiurlwidth": 1280})
    req = urllib.request.Request("https://commons.wikimedia.org/w/api.php?" + q, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        pages = (json.loads(r.read().decode()).get("query") or {}).get("pages") or {}
    toks = [t.lower() for t in re.findall(r"[A-Za-z]+", name) if len(t) > 1]
    best = None
    for p in pages.values():
        ii = (p.get("imageinfo") or [{}])[0]
        m = ii.get("extmetadata") or {}
        g = lambda k: re.sub(r"<[^>]+>", "", (m.get(k) or {}).get("value") or "").strip()
        lic = g("LicenseShortName")
        title = (p.get("title") or "").lower()
        desc = g("ImageDescription").lower()
        if not license_ok(lic) or not ii.get("thumburl") or (ii.get("width") or 0) < 600 or (ii.get("height") or 0) < (ii.get("width") or 0) * 0.9:
            continue
        if not all(t in title or t in desc for t in toks) or any(x in title for x in ("logo", "signature", "caricature", "cartoon")):
            continue
        yr = (g("DateTimeOriginal") or g("DateTime"))[:4]
        score = ("official" in title or "portrait" in title) * 2 + (int(yr) if yr.isdigit() else 0) / 1e4
        if best is None or score > best[0]:
            best = (score, dict(src=ii["thumburl"], credit=f"{g('Artist') or 'Unknown author'} / Wikimedia Commons", license=lic, link=ii.get("descriptionurl") or "",
                                kind="person", alt=name, w=ii.get("thumbwidth"), h=ii.get("thumbheight"),
                                caption=f"{name}" + (f", {yr}" if yr.isdigit() else "") + ". File photo; not taken at this event."))
    if best:
        best[1]["label"] = best[1]["caption"]
        return best[1]
    return None


def _named_people(cid, title, text):
    try:
        import people as PP
        out = []
        for p in PP.people_for(cid, " ".join([title, text])):
            nm = p.get("name") or ""
            m = re.search(re.escape(nm), title or "") if nm else None
            if m:
                out.append((m.start(), nm))
        return [n for _, n in sorted(out)]
    except Exception:
        return []


def prefetch(cid, title="", loc="", text=""):
    """Network, bounded (7 s per request): pick, look up a Commons portrait if the box has none, store the image. Returns the candidate or None."""
    with _LOCK:
        c = pick(cid, title, loc, text)
        if not c:
            for nm in _named_people(cid, title, text)[:1]:
                try:
                    c = _commons_portrait(nm)
                except Exception:
                    c = None
                if c:
                    try:
                        _choice_file(cid).write_text(json.dumps(c))
                    except Exception:
                        pass
        if c and store(c["src"]):
            return c
        return None
