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
    try:
        cols = {row[1] for row in k.execute("PRAGMA table_info(story_cards)").fetchall()}
        if "title_hash" not in cols:
            k.execute("ALTER TABLE story_cards ADD COLUMN title_hash TEXT")
    except Exception:
        pass
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
        r = _read(lambda k: k.execute("SELECT png, v, src, title_hash FROM story_cards WHERE cid=?", (cid,)).fetchone())
        if not r or not r[0]:
            return None
        b = bytes(r[0])
        if not (b.startswith(b"\x89PNG") and len(b) > 2000):
            return None
        return {"png": b, "v": (r[1] or ""), "src": (r[2] or ""), "title_hash": (r[3] or "") if len(r) > 3 else ""}
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
    """True when the stored PNG was built from a licensed photo of this story's main subject.
    A wrong-subject photo (Trump on the Huang story) does not count: the worker must look again."""
    if not cid:
        return False
    try:
        r = _read(lambda k: k.execute("SELECT src, png FROM story_cards WHERE cid=?", (cid,)).fetchone())
        if not (r and (r[0] or "").startswith("https://")):
            return False
        if photo_is_wrong_subject(cid, r[0], ""):
            return False
        # A place photo on a person-subject story, or a historical map/scan, is not a valid subject photo.
        ph = _read(lambda k: k.execute("SELECT kind, credit, caption, label FROM story_photos WHERE cid=?", (cid,)).fetchone())
        title, text = _story_text(cid)
        if ph:
            kind, credit, caption, label = (ph[0] or ""), (ph[1] or ""), (ph[2] or ""), (ph[3] or "")
            if is_non_photo(caption, " ".join((credit, label)), "", ""):
                return False
            if kind == "place" and not place_photo_ok(title, text):
                return False
        return True
    except Exception:
        return False


def put_card(cid, png, src="", title_hash=""):
    """Store a built card. A stored photo card always beats a map, with one exception:
    a wrong-subject photo (Trump or an Altoona map on the Huang story) may be replaced by a
    correct photo or a map. A typography rebuild may replace a photo PNG with a new photo PNG
    (same or different src) when the current cleaned title has changed."""
    if not cid or not png or not png.startswith(b"\x89PNG"):
        return
    blob = sqlite3.Binary(png)
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    src = src or ""
    title_hash = title_hash or ""
    def fn(k):
        old = k.execute("SELECT src FROM story_cards WHERE cid=?", (cid,)).fetchone()
        old_src = (old[0] if old else "") or ""
        # Photo-to-photo replacement is allowed (typography rebuild, or a correct-subject portrait
        # replacing a wrong-subject image). A correct photo still cannot be replaced by a map.
        if old_src.startswith("https://") and not src.startswith("https://"):
            if not photo_is_wrong_subject(cid, old_src, ""):
                return
        if not src.startswith("https://"):
            ph = k.execute("SELECT src, none, jpg, credit, caption, label FROM story_photos WHERE cid=?", (cid,)).fetchone()
            if ph and not ph[1] and (ph[0] or "").startswith("https://") and ph[2]:
                blob_meta = " ".join(x or "" for x in (ph[3], ph[4], ph[5]))
                if not photo_is_wrong_subject(cid, ph[0], blob_meta):
                    return
        ver = "11"
        try:
            import og
            ver = str(og.VERSION)
        except Exception:
            pass
        k.execute("INSERT OR REPLACE INTO story_cards(cid, png, v, src, built_at, title_hash) VALUES(?,?,?,?,?,?)",
                  (cid, blob, ver, src, ts, title_hash))
    try:
        _write(fn)
    except Exception:
        pass


def has_photo(cid):
    """True when a licensed photo of this story's main subject and its JPEG bytes are on hand. No network."""
    c = db_choice(cid)
    if not c or c.get("none") or not c.get("src") or not license_ok(c.get("license") or ""):
        return False
    if is_non_photo_candidate(c):
        return False
    title, text = _story_text(cid)
    if (c.get("kind") or "") == "place" and not place_photo_ok(title, text):
        return False
    if photo_is_wrong_subject(cid, c.get("src") or "", " ".join((c.get("credit") or "", c.get("caption") or "", c.get("label") or "", c.get("alt") or ""))):
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


def store_counts():
    """Row counts from the persistent cards.db (no network). photos = licensed JPEGs stored;
    cards = built PNGs; photo_cards = PNGs whose src is a licensed photo URL.
    Used by /healthz to prove the writer is actually committing, not just serving from memory."""
    try:
        def fn(k):
            photos = k.execute(
                "SELECT COUNT(*) FROM story_photos WHERE none=0 AND jpg IS NOT NULL AND length(jpg)>2000"
            ).fetchone()[0]
            cards = k.execute("SELECT COUNT(*) FROM story_cards").fetchone()[0]
            photo_cards = k.execute(
                "SELECT COUNT(*) FROM story_cards WHERE src LIKE 'https://%'"
            ).fetchone()[0]
            return int(photos or 0), int(cards or 0), int(photo_cards or 0)
        return _read(fn)
    except Exception:
        return (0, 0, 0)


def license_ok(lic):
    lic = (lic or "").strip()
    return bool(lic) and bool(OK.search(lic)) and not BAD.search(lic.replace("Public domain", ""))


# Historical maps, scans, documents, diagrams and collages are not a photo of the story's subject.
_NONPHOTO = re.compile(
    r"\b(maps?|atlas|cadastral|sanborn|plat map|street map|old map|historical map|antique map|"
    r"scans?|scanned|photocop(?:y|ies)|documents?|letters?|memos?|certificates?|"
    r"diagrams?|schematics?|flowcharts?|infographics?|org charts?|"
    r"collages?|montages?|composites?|blueprints?|manuscripts?)\b",
    re.I)
_BAD_MIME = re.compile(r"^(application/pdf|image/svg|image/x-djvu|image/vnd|application/postscript|application/vnd)", re.I)


def is_non_photo(title="", desc="", categories="", mime=""):
    """True for historical maps, scans, documents, diagrams, collages (title, category, or MIME)."""
    if mime and _BAD_MIME.search((mime or "").split(";")[0].strip().lower()):
        return True
    blob = " ".join(x for x in (title, desc, (categories or "").replace("|", " ").replace("/", " ")) if x)
    return bool(blob and _NONPHOTO.search(blob))


def is_non_photo_candidate(c):
    if not c:
        return True
    return is_non_photo(c.get("title") or c.get("alt") or "", " ".join((c.get("caption") or "", c.get("label") or "", c.get("credit") or "")),
                        c.get("categories") or "", c.get("mime") or "")


def place_photo_ok(title="", text=""):
    """Place photos are only for stories about that place, not person-subject stories (Huang must not get Altoona)."""
    title, text = title or "", text or ""
    if main_subject(title, text):
        return False
    if _named_people("", title, text):
        return False
    return True


def card_title_key(title):
    """Short hash of the cleaned card title, used to detect a stale typography PNG."""
    t = " ".join((title or "").split())
    return hashlib.sha1(t.encode("utf-8", "replace")).hexdigest()[:16] if t else ""


def card_title_stale(meta, current_key):
    """True when the stored card was rendered with a different title than the current cleaned headline."""
    if not meta or not current_key:
        return False
    return (meta.get("title_hash") or "") != current_key


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
    if is_non_photo(d.get("title") or d.get("alt") or "", " ".join((d.get("caption") or "", cr)),
                    d.get("categories") or "", d.get("mime") or ""):
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
    """Best licensed candidate from data already on the box (no network); falls back to a stored Commons lookup.
    A person photo is used only when it is this story's main subject; if that is ambiguous, return None (the card uses a map)."""
    def _ok(c):
        if not c or not c.get("src") or not license_ok(c.get("license") or ""):
            return None
        if is_non_photo_candidate(c):
            return None
        if (c.get("kind") or "") == "place":
            return c if place_photo_ok(title, text) else None
        if photo_is_wrong_subject(cid, c.get("src") or "", _photo_blob(c), title, text):
            return None
        # An ambiguous person story must not keep a leftover person photo.
        if (c.get("kind") or "person") == "person" and main_subject(title, text) is None and _named_people(cid, title, text):
            return None
        return c
    try:
        import story_report as SR
        for im in ((SR.reports() or {}).get("images") or {}).get(cid) or []:
            c = _ok(_cand(im))
            if c:
                c["label"] = ""
                return c
    except Exception:
        pass
    try:
        import people as PP
        v = PP.lead_for(cid, title, loc, text)
        c = _ok(_cand(v) if v else None)
        if c:
            c["label"] = c["caption"] if "file photo" in c["caption"].lower() else (c["caption"] + " File photo; not taken at this event.").strip()
            return c
    except Exception:
        pass
    s = _ok(stored_choice(cid))
    if s:
        return s
    s = _ok(db_choice(cid))
    if s:
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
    """Newest-looking licensed Commons portrait whose file name or description carries the person's full name.

    Do not require the word 'portrait' in the search query: '"Jensen Huang" portrait' returned
    no hits, while an unquoted 'Jensen Huang' search finds CC BY 4.0 portraits.
    """
    pages = {}
    for term in (name, f'"{name}"'):
        q = urllib.parse.urlencode({"action": "query", "format": "json", "generator": "search", "gsrsearch": term, "gsrnamespace": 6, "gsrlimit": 12,
                                    "prop": "imageinfo", "iiprop": "url|extmetadata|size|mime", "iiurlwidth": 1280})
        try:
            raw, _hdrs = _http("https://commons.wikimedia.org/w/api.php?" + q, "application/json", timeout=timeout)
            more = (json.loads((raw or b"{}").decode()).get("query") or {}).get("pages") or {}
            pages.update(more)
        except Exception:
            continue
    toks = [t.lower() for t in re.findall(r"[A-Za-z]+", name) if len(t) > 1]
    best = None
    for p in pages.values():
        ii = (p.get("imageinfo") or [{}])[0]
        m = ii.get("extmetadata") or {}
        g = lambda k: re.sub(r"<[^>]+>", "", (m.get(k) or {}).get("value") or "").strip()
        lic = g("LicenseShortName")
        title = (p.get("title") or "").lower()
        desc = g("ImageDescription").lower()
        cats = g("Categories")
        mime = (ii.get("mime") or "")
        w, h = int(ii.get("width") or 0), int(ii.get("height") or 0)
        if not license_ok(lic) or not ii.get("thumburl") or w < 600:
            continue
        # Prefer a portrait crop; allow mild landscape so a licensed headshot is not dropped.
        if h < w * 0.75:
            continue
        if is_non_photo(title, desc, cats, mime):
            continue
        if not all(t in title or t in desc for t in toks) or any(x in title for x in ("logo", "signature", "caricature", "cartoon")):
            continue
        yr = (g("DateTimeOriginal") or g("DateTime"))[:4]
        score = ("official" in title or "portrait" in title or "cropped" in title) * 2 + (h >= w * 0.9) + (int(yr) if yr.isdigit() else 0) / 1e4
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
    "huang": "Jensen Huang",
    "trump": "Donald Trump",
    "biden": "Joe Biden",
}

_STOP = set("the a an of in on at to for and or with by from as near after into its new says said "
            "unleashes fresh warns against using struck inquiry launches recorded magnitude landmark "
            "second time five days secretary war yet approved wanted back ceo director official "
            "update updates live report reports more than us united states iran tehran sanctions "
            "tankers strait hormuz nuclear bomb test veterans records aerial attack".split())

# Tests (and a caller that already has the title) can set SUBJECT_HINTS[cid] = (title, text).
SUBJECT_HINTS = {}

_OBJECT_VERBS = re.compile(
    r"\b(wanted|wants|want|asked|asks|nominated|nominates|tapped|named|appointed|appoints|"
    r"picked|picks|chose|chooses|urged|urges|invited|invites)\b", re.I)
_SPEAKER_VERBS = re.compile(
    r"\b(says|said|announces|announced|launches|launched|unleashes|unleashed|"
    r"warns|warned|declares|declared|tells|told|claims|claimed)\b", re.I)

# Last names of people who usually appear as political principals. Short/common surnames are omitted.
_POLITICIAN_LAST = {
    "trump", "biden", "harris", "obama", "clinton", "putin", "zelensky", "zelenskyy", "zelenskiy",
    "hegseth", "netanyahu", "starmer", "macron", "scholz", "sanders", "pelosi", "mcconnell",
    "orban", "erdogan", "modi", "lavrov", "blinken", "rubio", "vance", "newsom", "trudeau",
    "meloni", "sunak", "merkel", "hollande", "sarkozy", "khamenei", "raisi", "xi",
}


def _story_text(cid, title="", text=""):
    """Title and write-up body for subject scoring. SUBJECT_HINTS wins (tests); else the args, else the story row."""
    if cid and cid in SUBJECT_HINTS:
        return SUBJECT_HINTS[cid]
    if title or text:
        return title or "", text or ""
    if not cid:
        return "", ""
    try:
        import story
        r, _al = story.load(cid)
        if r:
            return r.get("title") or "", (r.get("brief") or "") + " " + (r.get("writeup") or r.get("body") or "")
    except Exception:
        pass
    return "", ""


def is_politician(name):
    """True when this name is a political principal (last-name list, or a people-profile office)."""
    if not name:
        return False
    last = name.split()[-1].lower()
    if last in _POLITICIAN_LAST:
        return True
    try:
        import people as PP
        for p in (PP.block().get("profiles") or {}).values():
            if (p.get("name") or "").lower() != name.lower():
                continue
            blob = " ".join(str(p.get(k) or "") for k in ("office", "role", "occupation", "title", "kind", "category")).lower()
            if re.search(r"\b(president|senator|congress|minister|secretary of|prime minister|chancellor|governor|politician)\b", blob):
                return True
    except Exception:
        pass
    return False


def main_subject(title, text=""):
    """The person the headline is about, or None if that is ambiguous (the card should then use a map).

    The topical subject is often the object ('X wanted Huang back as CEO of Nvidia' → Huang), not the first
    name in the headline. Candidates are scored by mentions in the write-up body, with a small tiebreak
    for non-politicians and a strong bump from the headline's speaker/object role.
    """
    title = title or ""
    text = text or ""
    cands = _named_people("", title, text)
    # Dedup last-name aliases against a fuller name already in the list.
    slim, seen_last = [], {}
    for n in cands:
        last = n.split()[-1].lower()
        if last in seen_last and len(n.split()) < len(seen_last[last].split()):
            continue
        if last in seen_last and len(n.split()) > len(seen_last[last].split()):
            slim = [x for x in slim if x.split()[-1].lower() != last]
        slim.append(n)
        seen_last[last] = n
    cands = slim
    if not cands:
        return None
    if len(cands) == 1:
        return cands[0]

    def _pos(name, blob):
        m = re.search(r"\b" + re.escape(name) + r"\b", blob, re.I)
        if m:
            return m.start()
        last = name.split()[-1]
        if len(last) > 3:
            m = re.search(r"\b" + re.escape(last) + r"\b", blob, re.I)
            if m:
                return m.start()
        return None

    role = {n: 0.0 for n in cands}
    obj = _OBJECT_VERBS.search(title)
    spk = _SPEAKER_VERBS.search(title)
    verb = obj or (spk if not obj else None)
    if verb:
        vpos = verb.start()
        for n in cands:
            p = _pos(n, title)
            if p is None:
                continue
            after = p >= vpos
            if obj:
                role[n] += 5.0 if after else 1.0
            else:
                role[n] += 5.0 if not after else 1.0

    blob = (title + " " + text).lower()
    mention = {}
    for n in cands:
        full = n.lower()
        last = n.split()[-1].lower()
        nfull = len(re.findall(r"\b" + re.escape(full) + r"\b", blob))
        nlast = len(re.findall(r"\b" + re.escape(last) + r"\b", blob)) if len(last) > 3 else 0
        mention[n] = nfull + 0.5 * max(0, nlast - nfull)

    scores = {}
    for n in cands:
        scores[n] = role[n] + mention[n]
        if not is_politician(n):
            scores[n] += 0.25  # tiebreak only

    ranked = sorted(cands, key=lambda n: (-scores[n], n))
    top, second = ranked[0], ranked[1]
    gap = scores[top] - scores[second]
    role_clear = role[top] >= 5.0 and role[top] > role[second] + 2.0
    if gap < 1.0 and not role_clear:
        return None
    return top


def _photo_blob(c):
    if not c:
        return ""
    return " ".join(str(c.get(k) or "") for k in ("alt", "caption", "label", "credit", "src", "person"))


def _name_in_blob(name, blob):
    if not name or not blob:
        return False
    b = blob.lower()
    last = name.split()[-1].lower()
    if len(last) > 2 and re.search(r"\b" + re.escape(last) + r"\b", b):
        return True
    # Commons file URLs often use underscores: Jensen_Huang
    if len(last) > 2 and last in b.replace("_", " "):
        return True
    return False


def photo_is_wrong_subject(cid, src, meta_blob="", title="", text=""):
    """True when this person photo is not the story's main subject (or the subject is too ambiguous to pick a person)."""
    title, text = _story_text(cid, title, text)
    people = _named_people(cid, title, text)
    if not people:
        return False  # no person in the headline: a place/event photo is fine
    subj = main_subject(title, text)
    blob = " ".join((src or "", meta_blob or ""))
    if not subj:
        # Ambiguous: any stored person photo is likely wrong.
        return True
    return not _name_in_blob(subj, blob)


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
                                     "prop": "imageinfo", "iiprop": "url|extmetadata|size|mime", "iiurlwidth": 1280})
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
        mime = (ii.get("mime") or "")
        cats = g("Categories")
        if is_non_photo(title_f, desc, cats, mime):
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
            names = []
            subj = main_subject(title, text)
            if subj:
                names = [subj]
            elif not _named_people(cid, title, text):
                names = []
            # Ambiguous (two+ people, no clear subject): do not guess a portrait; fall through to a place photo or a map.
            for nm in names:
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
        if not c and place_photo_ok(title, text):
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
