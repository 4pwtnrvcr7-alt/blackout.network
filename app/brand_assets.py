#!/usr/bin/env python3
"""blackout.network asset branding (QR standard). Free, local only: segno (QR), Pillow (images), pypdf+reportlab (PDF), ffmpeg (video).
Every downloadable image/video/PDF gets a QR code linking to the page the asset relates to, the text "view more at" next to the QR,
and "blackout.network" directly under the image. See BRANDING.md.

CLI:  python3 brand_assets.py <file> --url <page-url> [--out <path>] [--inplace] [--force]
      python3 brand_assets.py <file> --decode        (print the QR URL found in a branded image/PDF/video end card)
Python: brand_pil(img, url) -> PIL.Image ; brand_file(path, url, out=None, inplace=False) -> output path
Imports only the stdlib at module level, so importing it is safe everywhere (box, Render)."""
import glob, os, shutil, subprocess, sys, tempfile

SITE = "https://blackout.network"
PAGE = {"wire": SITE + "/#wire", "maps": SITE + "/#maps", "home": SITE + "/"}   # real deep links (dashboard TABHASH); no per-story permalink exists
BG, PANEL, TX, MU, HI, AC = "#0b0d10", "#14181d", "#e6e9ee", "#8b95a3", "#ff4d4f", "#4aa3ff"   # static/theme.css
TAGLINE = "Signal over noise."
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"; FONTB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
MARK = "bn-brand-qr:"          # JPEG comment / PNG text / PDF metadata marker -> idempotent
# Logo V2-final mark (BN + severity meter, dark version, transparent), shown left of "blackout.network" on every band/end card.
_HERE = os.path.dirname(os.path.abspath(__file__))
LOGO_CANDIDATES = [os.path.join(_HERE, "static", "brand", "v2", "mark-dark@2x.png"),
                   "/workspace/launch/team/review/design/logo-variations/v2-final/png/mark-dark@2x.png"]
_logo_cache = {}

def logo_mark(h):
    """V2 mark as an RGBA PIL image h px tall (aspect ~2:1), or None if the asset is missing (branding still works without it)."""
    if h in _logo_cache: return _logo_cache[h]
    from PIL import Image
    im = None
    for p in LOGO_CANDIDATES:
        if os.path.isfile(p):
            src = Image.open(p).convert("RGBA"); im = src.resize((max(1, round(src.width * h / src.height)), h), Image.LANCZOS); break
    _logo_cache[h] = im; return im

def logo_path():
    return next((p for p in LOGO_CANDIDATES if os.path.isfile(p)), None)

def _libs():
    """segno lives in /workspace/.brandenv (pure python); make it importable from other venvs (e.g. the snapshot worker's)."""
    try: import segno  # noqa
    except ImportError:
        for p in glob.glob("/workspace/.brandenv/lib/python3*/site-packages"):
            if p not in sys.path: sys.path.append(p)

def qr_matrix(url):
    _libs(); import segno
    q = segno.make(url, error="q", micro=False, boost_error=False)
    return [list(r) for r in q.matrix]

def qr_pil(url, px, quiet=4):
    """Dark-on-light QR tile, ~px square, 4-module quiet zone, error correction Q."""
    from PIL import Image
    m = qr_matrix(url); n = len(m) + 2 * quiet; s = max(2, px // n)
    img = Image.new("L", (n, n), 255)
    for y, row in enumerate(m):
        for x, v in enumerate(row):
            if v: img.putpixel((x + quiet, y + quiet), 0)
    return img.resize((n * s, n * s), Image.NEAREST).convert("RGB")

def _short(url): return url.replace("https://", "").replace("http://", "").rstrip("/")

def _font(path, size):
    from PIL import ImageFont
    return ImageFont.truetype(path, size)

def band(W, url):
    """Footer band (W wide) in the site's dark theme: V2 mark + 'blackout.network' + tagline + 'view more at <url>' left, QR right."""
    from PIL import Image, ImageDraw
    qpx = max(140, min(260, int(W * 0.13)))
    f_lab = _font(FONT, max(15, qpx // 9)); f_big = _font(FONTB, max(24, min(56, int(W * 0.035)))); f_s = _font(FONT, max(15, min(26, int(W * 0.016))))
    pad = max(14, qpx // 8)
    tile = qr_pil(url, qpx); qpx = tile.width
    H = 3 + pad + qpx + pad                  # 3 px red rule on top; QR centred below it (the one "view more at" line is in the text block)
    b = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(b)
    d.rectangle([0, 0, W, 3], fill=HI)
    qx = W - pad - qpx
    b.paste(tile, (qx, 3 + pad))
    x = pad + 4; maxw = qx - x - pad
    big = f_big
    lh = max(28, min(104, int((H - 2 * pad) * 0.5)))
    lh = min(lh, int(maxw * 0.30 / 2))                 # narrow images: shrink the mark so the domain keeps its size
    lg = logo_mark(lh) if lh >= 24 else None
    if lg is not None:
        b.paste(lg, (x, (H + 3 - lg.height) // 2), lg); gap = max(18, lg.height // 3); x += lg.width + gap; maxw -= lg.width + gap
    while d.textlength("blackout.network", font=big) > maxw and big.size > 14: big = _font(FONTB, big.size - 2)
    small = f_s
    for t in (TAGLINE, "view more at " + _short(url)):
        while d.textlength(t, font=small) > maxw and small.size > 10: small = _font(FONT, small.size - 1)
    block = int(big.size * 1.35) + 12 + 2 * int(small.size * 1.5)
    y = max(pad // 2 + 3, (H + 3 - block) // 2)
    d.text((x, y), "blackout.network", font=big, fill=TX); y += int(big.size * 1.35)
    d.rectangle([x, y, x + min(maxw, int(big.size * 3)), y + 3], fill=HI); y += 12
    for t, col in ((TAGLINE, MU), ("view more at " + _short(url), AC)):
        if y + small.size < H - 4: d.text((x, y), t, font=small, fill=col); y += int(small.size * 1.5)
    return b

def brand_pil(img, url):
    from PIL import Image
    img = img.convert("RGB"); W = max(img.width, 480)
    bb = band(W, url); out = Image.new("RGB", (W, img.height + bb.height), BG)
    out.paste(img, ((W - img.width) // 2, 0)); out.paste(bb, (0, img.height)); return out

def is_branded(path):
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext in (".jpg", ".jpeg", ".png", ".webp"):
            from PIL import Image
            with Image.open(path) as im:
                c = im.info.get("comment", b""); c = c.decode("utf-8", "ignore") if isinstance(c, bytes) else str(c)
                return c.startswith(MARK) or str(im.info.get("bn-brand", "")).startswith(MARK)
        if ext == ".pdf":
            _libs(); from pypdf import PdfReader
            return str((PdfReader(path).metadata or {}).get("/BNBrand", "")).startswith(MARK)
        if ext in (".mp4", ".mov", ".m4v"):
            r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format_tags=comment", "-of", "default=nw=1:nk=1", path], capture_output=True, text=True)
            return r.stdout.strip().startswith(MARK)
    except Exception: return False
    return False

def save_image(img, dst, url, src_info=None):
    from PIL import PngImagePlugin
    ext = os.path.splitext(dst)[1].lower(); info = src_info or {}
    if ext in (".jpg", ".jpeg"):
        kw = dict(quality=82, optimize=True, progressive=True, comment=(MARK + url).encode())
        if info.get("exif"): kw["exif"] = info["exif"]
        if info.get("xmp"): kw["xmp"] = info["xmp"]
        img.save(dst, "JPEG", **kw)
    elif ext == ".png":
        pi = PngImagePlugin.PngInfo(); pi.add_text("bn-brand", MARK + url); img.save(dst, "PNG", optimize=True, pnginfo=pi)
    else: img.save(dst)

def brand_image_file(src, url, dst):
    from PIL import Image
    with Image.open(src) as im:
        info = {k: im.info.get(k) for k in ("exif", "xmp")}; im.load(); out = brand_pil(im, url)
    tmp = dst + ".tmp" + os.path.splitext(dst)[1]; save_image(out, tmp, url, info); os.replace(tmp, dst); return dst

def brand_pdf(src, url, dst, band_pt=None, keep_size=True):
    """Adds a footer band (vector QR) to the LAST page without covering anything: by default the page content is scaled down
    a little (~7%) so the paper size stays the same (e.g. tabloid prints 1:1); keep_size=False grows the page instead."""
    _libs()
    from pypdf import PdfReader, PdfWriter, Transformation
    from reportlab.pdfgen import canvas
    rd = PdfReader(src); wr = PdfWriter(clone_from=rd); pg = wr.pages[-1]
    x0, y0, x1, y1 = [float(v) for v in pg.mediabox]; W = x1 - x0
    bh = band_pt or max(72.0, min(110.0, W * 0.075)); qs = bh - 22; pad = 12
    fd, ov = tempfile.mkstemp(suffix=".pdf"); os.close(fd)
    c = canvas.Canvas(ov, pagesize=(W, bh))
    c.setFillColor(BG); c.rect(0, 0, W, bh, stroke=0, fill=1); c.setFillColor(HI); c.rect(0, bh - 2.5, W, 2.5, stroke=0, fill=1)
    m = qr_matrix(url); n = len(m) + 8; s = qs / n; qx = W - pad - qs; qy = 6
    c.setFillColor("#ffffff"); c.rect(qx, qy, qs, qs, stroke=0, fill=1); c.setFillColor("#000000")
    for yy, row in enumerate(m):
        for xx, v in enumerate(row):
            if v: c.rect(qx + (xx + 4) * s, qy + qs - (yy + 5) * s, s + 0.05, s + 0.05, stroke=0, fill=1)
    c.setFillColor(TX); c.setFont("Helvetica", 9); c.drawRightString(qx - 8, qy + qs - 12, "view more at")
    c.setFont("Helvetica-Bold", 11); c.setFillColor(AC); c.drawRightString(qx - 8, qy + qs - 26, _short(url))
    tx = pad + 4; lp = logo_path()
    if lp:   # V2 mark, ~2:1, vertically centred in the band
        lh = bh * 0.56; lw = lh * 1.9929; c.drawImage(lp, tx, (bh - lh) / 2 - 2, width=lw, height=lh, mask="auto"); tx += lw + lh * 0.38
    c.setFillColor(TX); c.setFont("Helvetica-Bold", min(30, bh * 0.34)); c.drawString(tx, bh * 0.48, "blackout.network")
    c.setFillColor(MU); c.setFont("Helvetica", 10); c.drawString(tx, bh * 0.22, TAGLINE + "  ·  scan the QR code to view more")
    c.showPage(); c.save()
    if keep_size:   # paper size unchanged (prints 1:1 on the same sheet): shrink the page content to make room, centred
        H = y1 - y0; k = (H - bh) / H; dx = (W - W * k) / 2
        pg.add_transformation(Transformation().translate(-x0, -y0).scale(k, k).translate(x0 + dx, y0 + bh)); by = y0
    else:           # grow the page downward instead
        by = y0 - bh; pg.mediabox.lower_left = (x0, by)
        for box in ("cropbox", "trimbox", "bleedbox", "artbox"):
            try: getattr(pg, box).lower_left = (x0, by)
            except Exception: pass
    pg.merge_transformed_page(PdfReader(ov).pages[0], Transformation().translate(x0, by), expand=False)
    meta = dict(rd.metadata or {}); meta["/BNBrand"] = MARK + url; wr.add_metadata(meta)
    tmp = dst + ".tmp.pdf"
    with open(tmp, "wb") as fh: wr.write(fh)
    os.replace(tmp, dst); os.remove(ov); return dst

def end_card(W, H, url):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(img); u = min(W, H)
    qpx = int(u * 0.42); tile = qr_pil(url, qpx); qpx = tile.width
    f_big = _font(FONTB, int(u * 0.075)); f_lab = _font(FONT, int(u * 0.04)); f_s = _font(FONT, int(u * 0.032))
    if W >= H:   # landscape: text left, QR right
        qx, qy = int(W * 0.60), (H - qpx) // 2 + int(u * 0.03); tx = int(W * 0.08)
        d.text((qx + qpx // 2, qy - int(u * 0.05)), "view more at", font=f_lab, fill=TX, anchor="mm")
        lg = logo_mark(int(u * 0.13))
        if lg is not None: img.paste(lg, (tx, H // 2 - int(u * 0.12) - lg.height - int(u * 0.05)), lg)
        d.text((tx, H // 2 - int(u * 0.10)), "blackout.network", font=f_big, fill=TX)
        d.rectangle([tx, H // 2 + int(u * 0.0), tx + int(u * 0.3), H // 2 + int(u * 0.0) + 5], fill=HI)
        d.text((tx, H // 2 + int(u * 0.04)), TAGLINE, font=f_s, fill=MU)
    else:        # portrait: stacked, vertically centred as a group (logo V2 on top)
        qx, qy = (W - qpx) // 2, int(H * 0.50)
        lg = logo_mark(int(u * 0.16))
        if lg is not None: img.paste(lg, ((W - lg.width) // 2, int(H * 0.33) - int(u * 0.06) - lg.height - int(u * 0.04)), lg)
        d.text((W // 2, int(H * 0.33)), "blackout.network", font=f_big, fill=TX, anchor="mm")
        d.rectangle([W // 2 - int(u * 0.15), int(H * 0.37), W // 2 + int(u * 0.15), int(H * 0.37) + 5], fill=HI)
        d.text((W // 2, int(H * 0.41)), TAGLINE, font=f_s, fill=MU, anchor="mm")
        d.text((W // 2, qy - int(u * 0.05)), "view more at", font=f_lab, fill=TX, anchor="mm")
    img.paste(tile, (qx, qy))
    d.text((qx + qpx // 2, qy + qpx + int(u * 0.04)), _short(url), font=f_s, fill=AC, anchor="mm")
    return img

def watermark(W, H):
    from PIL import Image, ImageDraw
    f = _font(FONTB, max(14, int(min(W, H) * 0.028)))
    tw = int(ImageDraw.Draw(Image.new("RGBA", (1, 1))).textlength("blackout.network", font=f)) + 24
    im = Image.new("RGBA", (tw, int(f.size * 1.8)), (11, 13, 16, 120)); ImageDraw.Draw(im).text((12, int(f.size * .35)), "blackout.network", font=f, fill=(230, 233, 238, 190))
    return im

def brand_video(src, url, dst, card_s=3.5, corner=False):
    """Appends a card_s-second end card (QR + 'view more at' + 'blackout.network'); optional small corner watermark (off by default: the ads already carry a corner bug). Audio kept, silence under the card."""
    pr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate", "-of", "csv=p=0", src], capture_output=True, text=True, check=True)
    W, H, fr = pr.stdout.strip().split("\n")[0].split(","); W, H = int(W), int(H)
    ha = bool(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", src], capture_output=True, text=True).stdout.strip())
    sr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=sample_rate,channels", "-of", "csv=p=0", src], capture_output=True, text=True).stdout.strip() if ha else ""
    rate, ch = (sr.split(",") + ["48000", "2"])[:2] if sr else ("48000", "2")
    td = tempfile.mkdtemp(prefix="bnbrand_"); card = os.path.join(td, "card.png"); wm = os.path.join(td, "wm.png")
    end_card(W, H, url).save(card); watermark(W, H).save(wm)
    lay = "stereo" if ch == "2" else "mono"
    fc = f"[0:v]setsar=1,format=yuv420p[v0];"
    if corner: fc += f"[2:v]format=rgba[wm];[v0][wm]overlay=W-w-{int(W*0.02)}:H-h-{int(H*0.03)}[v0w];"
    else: fc += "[v0]null[v0w];"
    fc += f"[1:v]scale={W}:{H},setsar=1,fps={fr},format=yuv420p[vc];"
    if ha: fc += f"anullsrc=r={rate}:cl={lay}:d={card_s}[sil];[0:a]aresample={rate}[a0];[v0w][a0][vc][sil]concat=n=2:v=1:a=1[v][a]"
    else: fc += "[v0w][vc]concat=n=2:v=1:a=0[v]"
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", src, "-loop", "1", "-framerate", fr, "-t", str(card_s), "-i", card, "-i", wm, "-filter_complex", fc, "-map", "[v]"]
    if ha: cmd += ["-map", "[a]", "-c:a", "aac", "-b:a", "160k"]
    tmp = dst + ".tmp.mp4"
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "22", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-metadata", "comment=" + MARK + url, tmp]
    subprocess.run(cmd, check=True); os.replace(tmp, dst); shutil.rmtree(td, ignore_errors=True); return dst

def default_out(path):
    b, e = os.path.splitext(path); return f"{b}_branded{e}"

def brand_file(path, url, out=None, inplace=False, backup_dir=None, force=False, keep_mtime=True, corner=False):
    """Brands one file. Default writes <name>_branded.<ext> alongside; inplace=True backs the original up first
    (to backup_dir, or <name>_pre_qr_backup.<ext> next to it) and replaces it under the same name."""
    if not force and is_branded(path): return None
    ext = os.path.splitext(path)[1].lower(); st = os.stat(path)
    if inplace:
        if backup_dir:
            os.makedirs(backup_dir, exist_ok=True); bk = os.path.join(backup_dir, os.path.basename(path))
        else:
            b, e = os.path.splitext(path); bk = f"{b}_pre_qr_backup{e}"
        if not os.path.exists(bk): shutil.copy2(path, bk)
        dst = path
    else: dst = out or default_out(path)
    if ext in (".jpg", ".jpeg", ".png", ".webp"): brand_image_file(path, url, dst)
    elif ext == ".pdf": brand_pdf(path, url, dst)
    elif ext in (".mp4", ".mov", ".m4v", ".webm"): brand_video(path, url, dst if not dst.endswith(".webm") else dst[:-5] + ".mp4", corner=corner)
    else: raise ValueError("unsupported file type: " + ext)
    if keep_mtime and inplace: os.utime(dst, (st.st_atime, st.st_mtime))   # keeps sync retention windows unchanged
    return dst

def decode(path):
    """Reads the QR back with OpenCV (free; /workspace/.brandenv). Images directly, PDFs via pdftoppm, videos via the last frame."""
    _libs(); import cv2
    td = tempfile.mkdtemp(prefix="bndec_"); ext = os.path.splitext(path)[1].lower(); img = path
    if ext == ".pdf":
        subprocess.run(["pdftoppm", "-r", "150", "-png", "-f", "1", path, os.path.join(td, "p")], check=True); img = sorted(glob.glob(os.path.join(td, "p*.png")))[-1]
    elif ext in (".mp4", ".mov", ".m4v"):
        img = os.path.join(td, "f.png"); subprocess.run(["ffmpeg", "-v", "error", "-y", "-sseof", "-1", "-i", path, "-frames:v", "1", img], check=True)
    a = cv2.imread(img); val, pts, _ = cv2.QRCodeDetector().detectAndDecode(a)
    shutil.rmtree(td, ignore_errors=True); return val or None

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Brand a blackout.network asset with a QR code footer / end card.")
    ap.add_argument("file"); ap.add_argument("--url", help="page the asset relates to, e.g. https://blackout.network/#wire")
    ap.add_argument("--out"); ap.add_argument("--inplace", action="store_true"); ap.add_argument("--backup-dir"); ap.add_argument("--force", action="store_true")
    ap.add_argument("--decode", action="store_true"); ap.add_argument("--corner", action="store_true", help="video: also burn a small corner watermark")
    a = ap.parse_args()
    if a.decode: print(decode(a.file)); sys.exit(0)
    if not a.url: ap.error("--url is required")
    r = brand_file(a.file, a.url, out=a.out, inplace=a.inplace, backup_dir=a.backup_dir, force=a.force, corner=a.corner)
    print(r or f"already branded: {a.file}")
