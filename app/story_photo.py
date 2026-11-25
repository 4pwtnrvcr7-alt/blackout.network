"""Licensed photo for a Wire story's share card, picked by entity and place.

Selection (never on the crawler request path):
  1. a rights-cleared event image from story_reports.json (USGS ShakeMap, federal, Commons)
  2. the box's pick for the story ("lead": the named person's portrait, or a photo of the story's own country)
  3. the first named person's Commons portrait, looked up in the background (Commons API, license read from the file page)
Only public domain, CC0, CC BY and the UK Open Government Licence are used. Share-alike, non-commercial and no-derivative
licenses are refused. The chosen image is downloaded once, shrunk, and kept in cards.db (Render-owned, handed to the next instance the same way as story_writer.db) and also on disk when a disk exists.

pick(cid, ...)     no network: the credited candidate (or None), from data already on the box
cached(src)        no network: the stored image file, or None
prefetch(cid, ...) network, bounded: pick + download + store (background warm and the write-up publish gate only)
"""
from __future__ import annotations
import hashlib, queue
import re, io, json, os, re, sqlite3, threading, time, urllib.parse, urllib.request
from pathlib import Path

UA = "BLACKOUTNETWORK-cards/1.2 (https://blackout.network/; hello@blackout.network)"
OK = re.compile(r"^(public domain|cc0|cc by(?! ?-?(sa|nc|nd))|cc-by(?!-(sa|nc|nd))|ogl|open government|u\.?s\.? (government|federal)|attribution$)", re.I)
BAD = re.compile(r"(\bsa\b|-sa|share ?alike|\bnc\b|-nc|non ?commercial|\bnd\b|-nd|no ?deriv)", re.I)
MAX_BYTES = 6_000_000
_LOCK = threading.Lock()
_MEM = {}
_DB_REL = "cards.db"
_PHOTO_SCHEMA = """
CREATE TABLE IF NOT EXISTS story_photos(
  cid TEXT PRIMARY KEY, src TEXT, credit TEXT, license TEXT, caption TEXT, kind TEXT, label TEXT, link TEXT,
  jpg BLOB, none INTEGER DEFAULT 0, stored_at TEXT);
CREATE TABLE IF NOT EXISTS story_cards(
  cid TEXT PRIMARY KEY, png BLOB, v TEXT, src TEXT, built_at TEXT);
"""
_WQ = queue.Queue()
_WSTARTED = False
_WLOCK = threading.Lock()
_WTHREAD = None
_WPID = None
_REOPEN = object()


def _db_path():
    return (os.environ.get("BN_CARDS_DB") or "").strip() or str(Path(__file__).resolve().parent / _DB_REL)


def _connect_writer(path):
    k = sqlite3.connect(path, timeout=30, check_same_thread=False)
    k.execute("PRAGMA journal_mode=WAL")
    k.execute("PRAGMA busy_timeout=8000")
    k.executescript(_PHOTO_SCHEMA)
    return k


def _card_writes():
    """The only thread that writes cards.db (WAL + busy_timeout). Reconnects if the path
    changes or after a deploy handoff replaces the file. The target name must not contain
    "loop" — render_app.py's thread guard silently refuses those targets (the #228 `_floop`
    and the `_write_loop` bug: photos were served from memory and vanished on the next instance).
    """
    path = _db_path()
    k = _connect_writer(path)
    while True:
        job = _WQ.get()
        if job is None:
            try:
                k.close()
            except Exception:
                pass
            break
        fn, ev, err = job
        if fn is _REOPEN:
            try:
                k.close()
            except Exception:
                pass
            path = _db_path()
            k = _connect_writer(path)
            ev.set()
            continue
        cur = _db_path()
        if cur != path:
            try:
                k.close()
            except Exception:
                pass
            path = cur
            k = _connect_writer(path)
        try:
            fn(k)
            k.commit()
            try:
                k.execute("PRAGMA wal_checkpoint(PASSIVE)")
            except Exception:
                pass
        except Exception as e:
            err.append(e)
            try:
                k.rollback()
            except Exception:
                pass
        ev.set()


def _ensure_writer():
    """Start (or restart) the cards.db writer in this process. PID-checked and only
    marked started if the thread is actually alive (the thread guard can swallow start()).
    """
    global _WSTARTED, _WTHREAD, _WPID
    pid = os.getpid()
    if _WTHREAD is not None and _WTHREAD.is_alive() and _WPID == pid:
        return True
    with _WLOCK:
        if _WTHREAD is not None and _WTHREAD.is_alive() and _WPID == pid:
            return True
        t = threading.Thread(target=_card_writes, name="cards-db", daemon=True)
        t.start()
        _WTHREAD = t
        _WPID = pid
        _WSTARTED = t.is_alive()
        if not _WSTARTED:
            print("story_photo: cards writer failed to start (thread guard?)", flush=True)
        return _WSTARTED


def _write(fn, timeout=15):
    """Run fn(conn) on the single writer thread and wait for it to commit. Returns False if the write did not finish."""
    if not _ensure_writer():
        return False
    ev, err = threading.Event(), []
    _WQ.put((fn, ev, err))
    if not ev.wait(timeout):
        return False
    return not err


def reopen():
    """Reopen the writer on the file currently at _db_path() after a deploy handoff replaces cards.db."""
    if _WTHREAD is None or not _WTHREAD.is_alive():
        return
    ev, err = threading.Event(), []
    _WQ.put((_REOPEN, ev, err))
    ev.wait(5)


def _read(fn):
    """Read-only, short timeout, never writes."""
    k = sqlite3.connect(f"file:{_db_path()}?mode=ro", uri=True, timeout=2)
    try:
        k.execute("PRAGMA busy_timeout=1000")
        return fn(k)
    finally:
        k.close()


def db_choice(cid):
    """Persisted photo choice (and none=1 when a lookup already found no licensed photo). No network."""
    if not cid:
        return None
    try:
        r = _read(lambda k: k.execute("SELECT src, credit, license, caption, kind, label, link, none FROM story_photos WHERE cid=?", (cid,)).fetchone())
        if not r:
            return None
        # columns: 0 src, 1 credit, 2 license, 3 caption, 4 kind, 5 label, 6 link, 7 none
        if r[7]:
            return {"none": True}
        if r[0] and license_ok(r[2]):
            return dict(src=r[0], credit=r[1] or "", license=r[2] or "", caption=r[3] or "", kind=r[4] or "", label=r[5] or "", link=r[6] or "")
    except Exception:
        pass
    return None


def db_put(cid, cand, jpg=None, none=False):
    """Store the choice (or a negative lookup) and optional JPEG bytes so a deploy does not have to refetch."""
    if not cid:
        return
    c = cand or {}
    blob = sqlite3.Binary(jpg) if jpg else None
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    def fn(k):
        k.execute(
            "INSERT OR REPLACE INTO story_photos(cid, src, credit, license, caption, kind, label, link, jpg, none, stored_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (cid, c.get("src") or "", " ".join((c.get("credit") or "").split()), c.get("license") or "",
             " ".join((c.get("caption") or c.get("label") or "").split()),
             c.get("kind") or "", " ".join((c.get("label") or "").split()), c.get("link") or "", blob, 1 if none else 0, ts))
    try:
        _write(fn)
    except Exception:
        pass


def _db_jpg(src):
    if not src:
        return None
    try:
        r = _read(lambda k: k.execute("SELECT jpg FROM story_photos WHERE src=? AND jpg IS NOT NULL LIMIT 1", (src,)).fetchone())
        return bytes(r[0]) if r and r[0] else None
    except Exception:
        return None


def get_card(cid):
    """Built share-card PNG for this story, or None. No network."""
    m = card_meta(cid)
    return m["png"] if m else None


def card_meta(cid):
    """png, v, src for a stored card, or None. No network."""
    if not cid:
        return None
    try:
        r = _read(lambda k: k.execute("SELECT png, v, src FROM story_cards WHERE cid=?", (cid,)).fetchone())
        if not r or not r[0]:
            return None
        b = bytes(r[0])
        if not (b.startswith(b"\x89PNG") and len(b) > 2000):
            return None
        return {"png": b, "v": (r[1] or ""), "src": (r[2] or "")}
    except Exception:
        return None


def card_stale(meta):
    """True when the stored PNG was built under a previous og.VERSION and should be rebuilt (reusing any stored photo)."""
    if not meta:
        return False
    try:
        import og
        return str(meta.get("v") or "") != str(og.VERSION)
    except Exception:
        return False


def card_has_photo(cid):
    """True when the stored PNG was built from a licensed photo (story_cards.src is a URL). No network."""
    if not cid:
        return False
    try:
        r = _read(lambda k: k.execute("SELECT src FROM story_cards WHERE cid=?", (cid,)).fetchone())
        return bool(r and (r[0] or "").startswith("https://"))
    except Exception:
        return False


def put_card(cid, png, src=""):
    """Store a built card. A stored photo card always beats a map: never replace a photo PNG with a map PNG
    (live Zelensky photo was lost when a fetch=True rebuild without a photo overwrote it)."""
    if not cid or not png or not png.startswith(b"\x89PNG"):
        return
    blob = sqlite3.Binary(png)
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    src = src or ""
    def fn(k):
        old = k.execute("SELECT src FROM story_cards WHERE cid=?", (cid,)).fetchone()
        old_src = (old[0] if old else "") or ""
        if old_src.startswith("https://") and not src.startswith("https://"):
            return
        # Also refuse a map when this story already has a licensed JPEG in story_photos.
        if not src.startswith("https://"):
            ph = k.execute("SELECT src, none, jpg FROM story_photos WHERE cid=?", (cid,)).fetchone()
            if ph and not ph[1] and (ph[0] or "").startswith("https://") and ph[2]:
                return
        ver = "11"
        try:
            import og
            ver = str(og.VERSION)
        except Exception:
            pass
        k.execute("INSERT OR REPLACE INTO story_cards(cid, png, v, src, built_at) VALUES(?,?,?,?,?)",
                  (cid, blob, ver, src, ts))
    try:
        _write(fn)
    except Exception:
        pass


def has_photo(cid):
    """True when a licensed photo and its JPEG bytes are on hand (DB or disk). No network."""
    c = db_choice(cid)
    if not c or c.get("none") or not c.get("src") or not license_ok(c.get("license") or ""):
        return False
    if cached(c["src"]):
        return True
    return bool(_db_jpg(c["src"]))


def resolved(cid):
    """True only when a licensed photo is actually stored. A previous miss or a map-only card is not final
    (live Bessent/Riyadh were skipped after a failed or never-run lookup)."""
    return has_photo(cid)


def card_cids(limit=40):
    """Story ids that already have a built card in cards.db (newest first). No network."""
    try:
        rows = _read(lambda k: k.execute("SELECT cid FROM story_cards ORDER BY built_at DESC LIMIT ?", (int(limit),)).fetchall())
        return [r[0] for r in (rows or []) if r and r[0]]
    except Exception:
        return []


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
    """Path of the stored image for this source URL, or None. No network. Restores JPEG bytes from the persistent DB onto disk."""
    if not src:
        return None
    p = _dir() / (_name(src) + ".jpg")
    try:
        if p.is_file() and p.stat().st_size > 2000:
            return p
    except Exception:
        pass
    b = _db_jpg(src)
    if b and len(b) > 2000:
        try:
            tmp = str(p) + ".tmp"
            with open(tmp, "wb") as f:
                f.write(b)
            os.replace(tmp, p)
            return p
        except Exception:
            return None
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
    s = db_choice(cid)
    if s and s.get("src") and license_ok(s.get("license")):
        return s
    return None


def _http(url, accept, timeout=12, retries=1):
    """GET with the Wikimedia-required UA; one retry on timeout or HTTP 403/429/5xx."""
    last = None
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Api-User-Agent": UA, "Accept": accept, "Accept-Language": "en"})
    for _ in range(1 + retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read(MAX_BYTES + 1), r.headers
        except Exception as e:
            last = e
            time.sleep(0.4)
    if last:
        raise last
    return None, {}


def _fetch(src, timeout=10):
    sp = urllib.parse.urlsplit(src)
    if sp.scheme != "https" or not sp.hostname or not sp.hostname.endswith(("wikimedia.org", "wikipedia.org", "usgs.gov", "nasa.gov", "noaa.gov", "fema.gov", "defense.gov", "dvidshub.net", "whitehouse.gov", "treasury.gov", "gov.uk", "state.gov", "si.edu", "loc.gov", "flickr.com", "staticflickr.com")):
        return None
    b, hdrs = _http(src, "image/jpeg,image/png,image/webp,image/*;q=0.8", timeout=timeout)
    ct = ((hdrs.get("Content-Type") if hdrs else "") or "").split(";")[0].lower()
    if not b or len(b) > MAX_BYTES or not ct.startswith("image/") or "svg" in ct:
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
    raw, _hdrs = _http("https://commons.wikimedia.org/w/api.php?" + q, "application/json", timeout=timeout)
    pages = (json.loads((raw or b"{}").decode()).get("query") or {}).get("pages") or {}
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


# Full names for people who often appear as a bare surname in a headline. Commons is still license-gated.
_ALIASES = {
    "burnham": "Andy Burnham",
    "bessent": "Scott Bessent",
    "zelensky": "Volodymyr Zelensky",
    "zelenskyy": "Volodymyr Zelensky",
    "zelenskiy": "Volodymyr Zelensky",
    "hegseth": "Pete Hegseth",
}

_STOP = set("the a an of in on at to for and or with by from as near after into its new says said "
            "unleashes fresh warns against using struck inquiry launches recorded magnitude landmark "
            "second time five days secretary war yet approved wanted back ceo director official "
            "update updates live report reports more than us united states iran tehran sanctions "
            "tankers strait hormuz nuclear bomb test veterans records aerial attack".split())

def _named_people(cid, title, text):
    """Names of people this story is about: profiles first (last name in the title is enough), then First Last in the headline."""
    out, seen = [], set()
    blob = " ".join(x for x in (title, text) if x)
    try:
        import people as PP
        for p in PP.people_for(cid, blob):
            nm = p.get("name") or ""
            if not nm:
                continue
            last = nm.split()[-1]
            rx = p.get("rx")
            hit = False
            try:
                hit = bool(rx and re.search(rx, title or ""))
            except Exception:
                hit = False
            if not hit:
                hit = bool(re.search(r"\b" + re.escape(nm) + r"\b", title or "", re.I) or
                           (len(last) > 3 and re.search(r"\b" + re.escape(last) + r"\b", title or "", re.I)))
            if hit and nm.lower() not in seen:
                seen.add(nm.lower()); out.append(nm)
    except Exception:
        pass
    words = re.findall(r"[A-Za-z][A-Za-z'-]+", title or "")
    i = 0
    while i < len(words) - 1:
        a, b = words[i], words[i + 1]
        if (a[0].isupper() and b[0].isupper() and a.lower() not in _STOP and b.lower() not in _STOP
                and a.isalpha() and b.isalpha() and len(a) > 1 and len(b) > 2):
            nm = a + " " + b
            if nm.lower() not in seen:
                seen.add(nm.lower()); out.append(nm)
            i += 2
            continue
        i += 1
    # Last-name-only headlines ("Burnham launches…", "Zelensky says…") need the full name for Commons;
    # a bare-surname search returns the wrong person (sculptor A. E. Zelensky).
    blob_l = (title or "")
    for word in words:
        if not word or not word[0].isupper():
            continue
        full = _ALIASES.get(word.lower())
        if full and full.lower() not in seen and re.search(r"\b" + re.escape(word) + r"\b", blob_l):
            seen.add(full.lower()); out.append(full)
    return out


# Curly and straight quotes. Possessives like "Riyadh's" / "Riyadh’s" do not match (next char is lowercase).
_QCHARS = "\"“”„«»'‘’‛′″"
_PLACE_EXPAND = {
    "pif tower": "Public Investment Fund Tower",
}


def landmark_in(title):
    """Quoted or aliased landmark in a headline (for queue priority). No network."""
    return bool(_landmark_terms(title))


def _landmark_terms(title):
    """Search terms for a named landmark in the headline. Unquoted: a quoted Commons search for
    'PIF Tower' only returned CC BY-SA files and missed the CC BY 4.0 'Public Investment Fund Tower' photo."""
    title = title or ""
    terms = []
    m = re.search(r"[\"“”„«»'‘’‛′″]([A-Z0-9][^\"“”„«»'‘’‛′″]{1,60})[\"“”„«»'‘’‛′″]", title)
    if m:
        land = m.group(1).strip()
        if land:
            terms.append(land)
            exp = _PLACE_EXPAND.get(land.lower())
            if exp and exp.lower() != land.lower():
                terms.append(exp)
    else:
        low = title.lower()
        for short, exp in _PLACE_EXPAND.items():
            if short in low or exp.lower() in low:
                terms.append(exp)
                if short.title() not in terms:
                    terms.append(short.title())
    # unique, keep order
    out, seen = [], set()
    for x in terms:
        k = x.lower()
        if k not in seen:
            seen.add(k); out.append(x)
    return out


def _commons_place(loc, title, timeout=7):
    """Licensed photo of a named landmark (quoted in the headline) or the story's location. Never a logo or map."""
    loc = " ".join((loc or "").split())
    terms = _landmark_terms(title)
    landmark = terms[0] if terms else ""
    q = (landmark + (" " + loc if loc and not landmark else "")).strip() if landmark else loc
    if not q or len(q) < 3:
        return None
    pages = {}
    # Unquoted terms: quoted "PIF Tower" missed the licensed Public Investment Fund Tower file (CC BY 4.0).
    for term in (terms or [q]):
        qs = urllib.parse.urlencode({"action": "query", "format": "json", "generator": "search", "gsrsearch": term, "gsrnamespace": 6, "gsrlimit": 12,
                                     "prop": "imageinfo", "iiprop": "url|extmetadata|size", "iiurlwidth": 1280})
        try:
            raw, _hdrs = _http("https://commons.wikimedia.org/w/api.php?" + qs, "application/json", timeout=timeout)
            more = (json.loads((raw or b"{}").decode()).get("query") or {}).get("pages") or {}
            pages.update(more)
        except Exception:
            continue
        # Stop early if a licensed landmark file is already in the set.
        if any("investment fund tower" in ((p.get("title") or "").lower()) or (landmark and landmark.lower() in (p.get("title") or "").lower()) for p in more.values()):
            # still keep going only if no licensed candidate yet — checked below after filters
            pass
    toks = [t.lower() for t in re.findall(r"[A-Za-z0-9]+", landmark or q) if len(t) > 2]
    best = None
    for p in pages.values():
        ii = (p.get("imageinfo") or [{}])[0]
        md = ii.get("extmetadata") or {}
        g = lambda k: re.sub(r"<[^>]+>", "", (md.get(k) or {}).get("value") or "").strip()
        lic = g("LicenseShortName")
        title_f = (p.get("title") or "").lower()
        desc = g("ImageDescription").lower()
        w, h = int(ii.get("width") or 0), int(ii.get("height") or 0)
        if not license_ok(lic) or not ii.get("thumburl") or w < 800 or h < 400:
            continue
        if any(x in title_f for x in ("logo", "icon", "flag", "map", "coat of arms", "signature", "cartoon", "collage")):
            continue
        if toks and not any(t in title_f or t in desc for t in toks):
            continue
        named = bool(landmark and landmark.lower() in title_f or all(t in title_f or t in desc for t in toks))
        # portrait landmark shots are useful (subject-right layout); require landscape only when we have no named landmark
        if not landmark and h > w * 1.25:
            continue
        score = (3 if landmark and landmark.lower() in title_f else 0) + (2 if named else 0) + min(w, 2000) / 2000
        if best is None or score > best[0]:
            where = landmark or loc
            yr = (g("DateTimeOriginal") or g("DateTime"))[:4]
            best = (score, dict(src=ii["thumburl"], credit=f"{g('Artist') or 'Unknown author'} / Wikimedia Commons", license=lic,
                                link=ii.get("descriptionurl") or "", kind="place", alt=where, w=ii.get("thumbwidth"), h=ii.get("thumbheight"),
                                caption=f"{where}" + (f", {yr}" if yr.isdigit() else "") + ". File photo; not taken at this event."))
    if best:
        best[1]["label"] = best[1]["caption"]
        return best[1]
    return None


def prefetch(cid, title="", loc="", text=""):
    """Network, bounded: pick, look up a Commons portrait or place photo if the box has none, store the image (disk + persistent DB).
    If a stored or box pick cannot be downloaded, fall through to Commons instead of locking in a dead choice."""
    with _LOCK:
        err = ""
        c = pick(cid, title, loc, text)
        path = store(c["src"]) if c and c.get("src") else None
        if c and not path:
            err = "stored pick was not downloadable"
            c = None
        if not c:
            for nm in _named_people(cid, title, text)[:2]:
                try:
                    c = _commons_portrait(nm)
                except Exception as e:
                    err = type(e).__name__
                    c = None
                if c:
                    path = store(c["src"])
                    if path:
                        break
                    err = "commons portrait not downloadable"
                    c = None
        if not c:
            try:
                c = _commons_place(loc, title)
            except Exception as e:
                err = type(e).__name__
                c = None
            if c:
                path = store(c["src"])
                if not path:
                    err = "commons place not downloadable"
                    c = None
        if c and path:
            try:
                _choice_file(cid).write_text(json.dumps(c))
            except Exception:
                pass
            jpg = None
            try:
                jpg = Path(path).read_bytes()
            except Exception:
                jpg = None
            db_put(cid, c, jpg=jpg, none=False)
            print(f"story_photo: prefetch {cid} photo=1 license={c.get('license') or ''} kind={c.get('kind') or ''}", flush=True)
            return c
        # Do not persist a negative lookup after an error or a failed download: the next warm may succeed.
        if not err:
            db_put(cid, None, none=True)
        print(f"story_photo: prefetch {cid} photo=0 err={err or 'no licensed photo'}", flush=True)
        return None
