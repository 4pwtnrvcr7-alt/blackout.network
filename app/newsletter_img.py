"""Email-safe images for the v2 newsletter (BN_NL_V2=1), all served from blackout.network as plain JPEG/PNG.

Routes (newsletter.handle_get sends /newsletter/img/* here before anything else; no worker is started for them)
  /newsletter/img/lead/<id>.jpg     1200x675 JPEG crop of a same-origin story image (/api/media/<id>, people.py allowlist only:
                                    an id that is not in the signed story_reports.json returns 404). Portraits crop high so
                                    faces stay in frame.
  /newsletter/img/person/<slug>.jpg 160x160 JPEG headshot from the committed static/img/people/<slug>.webp (else the profile's
                                    allowlisted portrait). Outlook and older clients do not show WebP, so email never links it.
  /newsletter/img/card/<cid>.png    "Story at a glance" graphic drawn only from this story's own data (rank, category, place,
                                    independent and official sources, reports, time tracked). Read-only: the newsletter source
                                    DB (file:...?mode=ro) or the committed desk story. Labelled as a BLACKOUT.NETWORK graphic.
Every image is cached on disk (logs/nl_img, 10 min for cards, 14 days for photos). Without Pillow the photo routes pass the
original same-origin bytes through and the card route returns the hosted brand tile, so an email never shows a broken image.
"""
import hashlib, io, json, os, re, sqlite3, threading, time
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(BASE, "logs", "nl_img")
FONTS = os.path.join(BASE, "static", "newsletter", "fonts")
BRAND_TILE = os.path.join(BASE, "static", "social", "brand_tile_v2_dark_168.png")
CID = re.compile(r"^[0-9a-f]{16}$")
MID = re.compile(r"^([0-9a-f]{20})\.(jpg|png|webp|gif)$")
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,80}$")
UTC = timezone.utc
RANK_NAME = {0: "Noise", 1: "Background", 2: "Minor", 3: "Minor regional", 4: "Regional", 5: "Significant", 6: "Serious", 7: "Major",
             8: "Severe", 9: "Critical", 10: "Catastrophic"}
BAND = ((7, (255, 59, 59)), (4, (255, 194, 26)), (0, (63, 166, 106)))   # site three-band scale: red 7-10, amber 4-6, green 0-3
_lock = threading.Lock()

def band_rgb(rank):
    r = int(rank or 0)
    for k, col in BAND:
        if r >= k: return col
    return BAND[-1][1]

def _pil():
    try:
        from PIL import Image, ImageDraw, ImageFont  # noqa: F401
        return True
    except Exception:
        return False

def _cache_get(key, ttl):
    p = os.path.join(CACHE, key)
    try:
        if time.time() - os.path.getmtime(p) < ttl:
            with open(p, "rb") as fh: return fh.read()
    except OSError: pass
    return None

def _cache_put(key, b):
    try:
        os.makedirs(CACHE, exist_ok=True)
        p = os.path.join(CACHE, key)
        with open(p + ".tmp", "wb") as fh: fh.write(b)
        os.replace(p + ".tmp", p)
    except OSError: pass

def _font(bold, size):
    from PIL import ImageFont
    f = os.path.join(FONTS, "Inter-Bold.ttf" if bold else "Inter-Medium.ttf")
    try: return ImageFont.truetype(f, size)
    except Exception: return ImageFont.load_default()

def _jpeg(im, q=84):
    out = io.BytesIO()
    im.convert("RGB").save(out, "JPEG", quality=q, optimize=True, progressive=True)
    return out.getvalue()   # Pillow writes no EXIF/XMP unless asked: no camera or author metadata leaves the server

def crop_to(im, w, h, top_bias=0.33):
    """Cover-crop to w x h. Portrait sources keep the upper part (faces); landscape ones crop evenly."""
    from PIL import Image
    sw, sh = im.size
    scale = max(w / sw, h / sh)
    nw, nh = max(w, round(sw * scale)), max(h, round(sh * scale))
    im = im.resize((nw, nh), Image.LANCZOS)
    x = (nw - w) // 2
    y = int((nh - h) * (top_bias if sh > sw * 0.9 else 0.5))
    return im.crop((x, y, x + w, y + h))

def frame(im, w, h):
    """Landscape photos fill the frame. Portraits (most file photos of people) are shown whole on a soft, darkened copy of
    themselves instead of being zoomed into the face."""
    from PIL import Image, ImageFilter, ImageEnhance
    sw, sh = im.size
    if sw / max(1, sh) >= 1.25: return crop_to(im, w, h)
    bg = crop_to(im, w // 4, h // 4, 0.5).filter(ImageFilter.GaussianBlur(6)).resize((w, h), Image.LANCZOS)
    bg = ImageEnhance.Brightness(bg).enhance(0.38)
    fh = h; fw = max(1, round(sw * fh / sh))
    if fw > w * 0.8: fw = round(w * 0.8); fh = round(sh * fw / sw)
    fg = im.resize((fw, fh), Image.LANCZOS)
    bg.paste(fg, ((w - fw) // 2, (h - fh) // 2))
    return bg

# ------------------------------------------------------------------ photos
_LBL = {"mt": None, "v": {}}
def archive_label(name):
    """Small on-image archive label for a file photo ("FILE PHOTO · MYKOLA AZAROV, 2012"), looked up server-side from the signed
    story_reports.json people block by media id, so no caller can make this route draw arbitrary text. None for event photos."""
    try:
        import people as PP
        b = PP.block()
    except Exception:
        return None
    mt = id(b)
    if _LBL["mt"] != mt:
        v = {}
        def cap_label(d):
            cap = str((d or {}).get("caption") or "")
            m = re.match(r"^File photo of (.{2,60}?) \((\d{4})\)", cap)
            if m: return f"FILE PHOTO \u00b7 {m.group(1).upper()}, {m.group(2)}"
            m = re.match(r"^(.{2,60}?), (\d{4})\. File photo", cap)
            if m: return f"FILE PHOTO \u00b7 {m.group(1).upper()}, {m.group(2)}"
            return "FILE PHOTO" if "file photo" in cap.lower() else None
        for d in list((b.get("places") or {}).values()) + list((b.get("lead") or {}).values()):
            if isinstance(d, dict) and str(d.get("src") or "").startswith("https://"):
                lab = cap_label(d)
                if lab: v[PP.mid(d["src"])] = lab
        for p in (b.get("profiles") or {}).values():
            po = (p or {}).get("portrait") or {}
            if str(po.get("src") or "").startswith("https://"):
                yr = str(po.get("date") or "")[:4]
                v.setdefault(PP.mid(po["src"]), f"FILE PHOTO \u00b7 {str(p.get('name') or '').upper()}" + (f", {yr}" if yr.isdigit() else ""))
        _LBL.update(mt=mt, v=v)
    return _LBL["v"].get(name)

def _stamp(im, label):
    """Bottom-left archive label (pre-publish A13: place/person and year on the picture itself), readable at phone width."""
    if not label: return im
    from PIL import ImageDraw
    im = im.convert("RGBA"); W, H = im.size
    ov = __import__("PIL.Image", fromlist=["Image"]).new("RGBA", im.size, (0, 0, 0, 0)); dr = ImageDraw.Draw(ov)
    f = _font(False, 40); label = label[:60]   # 40px on a 1136px picture shows at ~12.6px on a 390px phone
    tw = dr.textlength(label, font=f); pad = 16
    if tw > W - 80: f = _font(False, 32); tw = dr.textlength(label, font=f)
    x0, y1 = 20, H - 20; y0 = y1 - 40 - 2 * pad + 8
    dr.rounded_rectangle((x0, y0, x0 + tw + 2 * pad, y1), radius=10, fill=(0, 0, 0, 165))
    dr.text((x0 + pad, y0 + pad - 4), label, font=f, fill=(245, 245, 247, 235))
    im.alpha_composite(ov)
    return im.convert("RGB")

def lead_jpg(name):
    if not MID.match(name or ""): return None
    key = "lead3_" + name.rsplit(".", 1)[0] + ".jpg"
    hit = _cache_get(key, 14 * 86400)
    if hit: return hit, "image/jpeg"
    try:
        import people as PP
        r = PP.media_bytes(name)
    except Exception:
        r = None
    if not r: return None
    if not _pil(): return r
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(r[0])); im.load()
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA"); bg = Image.new("RGB", im.size, (22, 24, 28)); bg.paste(im, mask=im.split()[-1]); im = bg
        b = _jpeg(_stamp(frame(im, 1136, 640), archive_label(name)), 80)
        _cache_put(key, b)
        return b, "image/jpeg"
    except Exception:
        return r

def person_jpg(slug):
    if not SLUG.match(slug or ""): return None
    key = f"person_{slug}.jpg"
    hit = _cache_get(key, 14 * 86400)
    if hit: return hit, "image/jpeg"
    raw = None
    f = os.path.join(BASE, "static", "img", "people", slug + ".webp")
    if os.path.isfile(f):
        with open(f, "rb") as fh: raw = fh.read()
    else:
        try:
            import people as PP
            p = (PP.profiles() or {}).get(slug) or {}
            po = p.get("portrait") or {}
            u = po.get("avatar_src") or po.get("src")
            loc = PP.media_url(u) if u else ""
            if loc.startswith("/api/media/"):
                r = PP.media_bytes(loc[len("/api/media/"):]); raw = r[0] if r else None
        except Exception:
            raw = None
    if not raw or not _pil(): return None
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(raw)); im.load()
        if im.mode != "RGB": im = im.convert("RGB")
        b = _jpeg(crop_to(im, 160, 160, 0.2), 86)
        _cache_put(key, b)
        return b, "image/jpeg"
    except Exception:
        return None

# ------------------------------------------------------------------ story-at-a-glance card
def _dt(s):
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=UTC)
    except Exception: return None

def _span(a, b):
    d1, d2 = _dt(a), _dt(b)
    if not (d1 and d2) or d2 < d1: return ""
    h = (d2 - d1).total_seconds() / 3600
    return "under 1 hour" if h < 1 else (f"{h:.0f} hour{'s' if round(h) != 1 else ''}" if h < 48 else f"{h / 24:.0f} days")

def card_data(cid):
    """Facts for the card, only from this story's own records. None when the story is unknown."""
    if not CID.match(cid or ""): return None
    try:
        import desk_stories as DS
        s = DS.get(cid)
    except Exception:
        s = None
    if s:
        reps = s.get("reports") or []
        return {"rank": int(s.get("rank") or 0), "category": s.get("category") or "other", "place": s.get("location") or "", "title": s.get("title") or "",
                "sources": len(set(r.get("family") for r in reps if r.get("family"))) or len(s.get("families") or []),
                "official": len(set(r.get("family") for r in reps if r.get("official"))), "reports": len(reps),
                "span": _span(s.get("first_seen"), s.get("updated"))}
    d = _db_card(cid)
    if d: return d
    try:   # a story only in the analyst notes (the brief's own note is what the story page shows)
        import story_report as SR
        n = ((SR.reports() or {}).get("notes") or {}).get(cid) or {}
    except Exception:
        n = {}
    if not n.get("headline"): return None
    srcs = [(u.get("url") if isinstance(u, dict) else u) for u in (n.get("sources") or [])]
    srcs = [u for u in srcs if isinstance(u, str) and u.startswith("http")]
    hosts = {re.sub(r"^www\.", "", u.split("/")[2]) for u in srcs if u.count("/") >= 2}
    return {"rank": None, "category": "", "place": "", "note": True, "confidence": (n.get("confidence") or "").strip().capitalize(),
            "trajectory": {"UPTREND": "Rising", "DOWNTREND": "Easing"}.get(str(n.get("trajectory") or "").upper(), "Steady"),
            "sources": len(hosts), "cited": len(srcs)}

def _db_card(cid):
    try:
        import newsletter as N
        k = N.src()
        try:
            r = k.execute("SELECT rank, category, location, title, eff_families, n_families, n_items, first_seen, updated FROM clusters WHERE cluster_id=?", (cid,)).fetchone()
            if not r: return None
            try:
                off = k.execute("SELECT COUNT(DISTINCT family) FROM alerts WHERE cluster_id=? AND official=1", (cid,)).fetchone()[0]
                nrep = k.execute("SELECT COUNT(*) FROM alerts WHERE cluster_id=?", (cid,)).fetchone()[0]
            except sqlite3.Error:
                off, nrep = 0, 0
        finally:
            k.close()
        loc = (r["location"] or "").strip()
        if re.search(r"not (?:specified|reported|recorded)|unknown location", loc, re.I): loc = ""
        return {"rank": int(r["rank"] or 0), "category": r["category"] or "other", "place": "", "title": r["title"] or "",   # scanner places can be off; the email kicker shows a checked one
                "sources": int(r["eff_families"] or r["n_families"] or 0), "official": int(off or 0),
                "reports": int(nrep or r["n_items"] or 0), "span": _span(r["first_seen"], r["updated"])}
    except Exception:
        return None

CAT_LABEL = {"war/conflict": "War and conflict", "political": "Politics", "natural disaster": "Natural disaster", "disease": "Health",
             "cyber": "Cyber", "space weather": "Space weather", "financial": "Economy", "infrastructure": "Infrastructure",
             "terrorism": "Terrorism", "other": "Report"}

def _fit(draw, text, font, maxw):
    if draw.textlength(text, font=font) <= maxw: return text
    t = text
    while t and draw.textlength(t + "\u2026", font=font) > maxw: t = t[:-1]
    return t.rstrip(" ,;:-") + "\u2026"

def card_png(d):
    """1200x675 PNG. Dark plate, rank ring in the story's band colour, four facts, BLACKOUT.NETWORK label."""
    from PIL import Image, ImageDraw
    W, H, S = 1200, 675, 1
    im = Image.new("RGB", (W, H), (14, 16, 20))
    dr = ImageDraw.Draw(im)
    for y in range(H):   # quiet vertical gradient, no texture
        t = y / H; c = (int(18 - 6 * t), int(21 - 6 * t), int(27 - 7 * t))
        dr.line([(0, y), (W, y)], fill=c)
    if d.get("note"): return _note_png(d)
    col = band_rgb(d["rank"]); rank = max(0, min(10, int(d["rank"] or 0)))
    # rank ring
    cx, cy, R, wd = 250, 300, 140, 24
    dr.ellipse([cx - R, cy - R, cx + R, cy + R], outline=(44, 48, 56), width=wd)
    if rank:
        dr.arc([cx - R, cy - R, cx + R, cy + R], start=-90, end=-90 + 360 * rank / 10, fill=col, width=wd)
    f_big, f_lab, f_nm = _font(True, 128), _font(False, 30), _font(True, 34)
    num = str(rank); tw = dr.textlength(num, font=f_big)
    dr.text((cx - tw / 2, cy - 100), num, font=f_big, fill=(245, 245, 247))
    sub = "of 10"; tw = dr.textlength(sub, font=f_lab)
    dr.text((cx - tw / 2, cy + 44), sub, font=f_lab, fill=(190, 194, 202))
    nm = RANK_NAME.get(rank, ""); tw = dr.textlength(nm, font=f_nm)
    dr.text((cx - tw / 2, cy + R + 28), nm, font=f_nm, fill=col)
    # kicker
    x0 = 480
    f_k, f_n, f_l = _font(True, 28), _font(True, 64), _font(False, 28)
    kick = (CAT_LABEL.get((d.get("category") or "other").lower(), (d.get("category") or "Report").capitalize())).upper()
    try:   # the same category group the email files this story under (so the picture and its section never disagree)
        import newsletter_v2 as NV2
        g = NV2.group_of({"category": d.get("category"), "title": d.get("title") or "", "display_title": d.get("title") or ""})
        if g != "world": kick = NV2.GROUPS[g][0].upper()
    except Exception:
        pass
    dr.rounded_rectangle([x0, 92, x0 + 10, 132], radius=5, fill=col)
    dr.text((x0 + 26, 94), _fit(dr, kick, f_k, W - x0 - 90), font=f_k, fill=(245, 245, 247))
    if d.get("place"):
        dr.text((x0 + 26, 136), _fit(dr, d["place"], f_l, W - x0 - 90), font=f_l, fill=(170, 175, 184))
    stats = [(str(d.get("sources") or 0), "independent sources"), (str(d.get("official") or 0), "official sources"),
             (str(d.get("reports") or 0), "reports logged"), (d.get("span") or "n/a", "tracked so far")]
    for i, (n, lab) in enumerate(stats):
        x = x0 + (i % 2) * 340; y = 230 + (i // 2) * 160
        dr.text((x, y), _fit(dr, n, f_n, 320), font=f_n, fill=(245, 245, 247))
        dr.text((x, y + 80), lab, font=f_l, fill=(160, 165, 174))
    # footer label
    f_f = _font(True, 24); f_f2 = _font(False, 24)
    dr.line([(64, 590), (W - 64, 590)], fill=(40, 44, 52), width=2)
    dr.text((64, 610), "BLACKOUT.NETWORK", font=f_f, fill=(255, 194, 26))
    lab = "Story at a glance · graphic built from our own reports"
    dr.text((W - 64 - dr.textlength(lab, font=f_f2), 610), lab, font=f_f2, fill=(150, 155, 164))
    out = io.BytesIO(); im.save(out, "PNG", optimize=True)
    return out.getvalue()

def _base_plate():
    from PIL import Image, ImageDraw
    W, H = 1200, 675
    im = Image.new("RGB", (W, H), (14, 16, 20)); dr = ImageDraw.Draw(im)
    for y in range(H):
        t = y / H; dr.line([(0, y), (W, y)], fill=(int(18 - 6 * t), int(21 - 6 * t), int(27 - 7 * t)))
    return im, dr, W, H

def _footer(dr, W):
    f_f, f_f2 = _font(True, 24), _font(False, 24)
    dr.line([(64, 590), (W - 64, 590)], fill=(40, 44, 52), width=2)
    dr.text((64, 610), "BLACKOUT.NETWORK", font=f_f, fill=(255, 194, 26))
    lab = "Story at a glance · graphic built from our own reports"
    dr.text((W - 64 - dr.textlength(lab, font=f_f2), 610), lab, font=f_f2, fill=(150, 155, 164))

def _note_png(d):
    """Card for a story known only from our analyst brief: confidence, trend and how many outlets the brief cites. No rank is shown
    because none was given."""
    im, dr, W, H = _base_plate()
    f_k, f_big, f_n, f_l = _font(True, 28), _font(True, 96), _font(True, 64), _font(False, 28)
    dr.rounded_rectangle([64, 92, 74, 132], radius=5, fill=(255, 194, 26))
    dr.text((90, 94), "OUR ANALYST BRIEF", font=f_k, fill=(245, 245, 247))
    dr.text((64, 190), d.get("confidence") or "n/a", font=f_big, fill=(245, 245, 247))
    dr.text((64, 310), "confidence in the reporting", font=f_l, fill=(160, 165, 174))
    stats = [(d.get("trajectory") or "Steady", "trend over the next 72 hours"), (str(d.get("sources") or 0), "outlets cited in the brief")]
    for i, (n, lab) in enumerate(stats):
        x = 64 + i * 540; y = 400
        dr.text((x, y), _fit(dr, n, f_n, 500), font=f_n, fill=(245, 245, 247))
        dr.text((x, y + 80), lab, font=f_l, fill=(160, 165, 174))
    _footer(dr, W)
    out = io.BytesIO(); im.save(out, "PNG", optimize=True)
    return out.getvalue()

def card(cid):
    d = card_data(cid)
    if not d: return None
    key = f"card_{cid}_{hashlib.sha1(json.dumps(d, sort_keys=True).encode()).hexdigest()[:10]}.png"
    hit = _cache_get(key, 600)
    if hit: return hit, "image/png"
    if not _pil():
        try:
            with open(BRAND_TILE, "rb") as fh: return fh.read(), "image/png"
        except OSError: return None
    with _lock:
        b = card_png(d)
    _cache_put(key, b)
    return b, "image/png"

def handle_get(path):
    p = path.rstrip("/")
    m = re.match(r"^/newsletter/img/(lead|person|card)/([A-Za-z0-9_.-]{1,90})$", p)
    if not m: return 404, {"error": "not found"}
    kind, name = m.groups()
    try:
        if kind == "lead": r = lead_jpg(name)
        elif kind == "person": r = person_jpg(name[:-4]) if name.endswith(".jpg") else None
        else: r = card(name[:-4]) if name.endswith(".png") else None
    except Exception:
        r = None
    return (200, r[0], r[1]) if r else (404, {"error": "not found"})
