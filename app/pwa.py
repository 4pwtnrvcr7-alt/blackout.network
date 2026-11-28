"""PWA / home-screen add-on: web app manifest, app icons and the mobile install guide (static/pwa/).
GET /manifest.webmanifest (aliases /manifest.json, /site.webmanifest), /apple-touch-icon.png (+ -precomposed), /icons/<file>.png,
/install-guide.js, /install-guide.css. Plain files only: fixed names, no directory listing, no path traversal, no data collected."""
import os, re, base64
BASE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(BASE, "static", "pwa")
FIXED = {"/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json"),
         "/manifest.json": ("manifest.webmanifest", "application/manifest+json"),
         "/site.webmanifest": ("manifest.webmanifest", "application/manifest+json"),
         "/apple-touch-icon.png": ("apple-touch-icon.png", "image/png"),
         "/apple-touch-icon-precomposed.png": ("apple-touch-icon.png", "image/png"),
         "/install-guide.js": ("install-guide.js", "application/javascript"),
         "/install-guide.css": ("install-guide.css", "text/css"),
         "/bn-menu-city.js": ("bn-menu-city.js", "application/javascript"),   # menu background loop, loaded by menu5.py on first menu open
         "/bn-menu-city-m.mp4": ("bn-menu-city-m.mp4", "video/mp4"),
         "/bn-menu-city-d.mp4": ("bn-menu-city-d.mp4", "video/mp4")}
_LOOP_CACHE = {}
def _read(name):
    if name in ("bn-menu-city-m.mp4", "bn-menu-city-d.mp4"):
        if name in _LOOP_CACHE:
            return _LOOP_CACHE[name]
        parts, i, base = [], 0, os.path.join(D, name + ".b64")
        while True:
            path = base if i == 0 else f"{base}.{i:02d}"
            if not os.path.isfile(path):
                break
            parts.append(path)
            i += 1
        if parts:
            buf = []
            for path in parts:
                with open(path, "r", encoding="ascii") as fh:
                    buf.append(fh.read())
            data = base64.b64decode("".join("".join(buf).split()))
        else:
            with open(os.path.join(D, name), "rb") as fh:
                data = fh.read()
        _LOOP_CACHE[name] = data
        return data
    with open(os.path.join(D, name), "rb") as fh: return fh.read()
def handle_get(path, qs):
    if path in FIXED:
        name, ct = FIXED[path]; b = _read(name)
        if name == "install-guide.js":   # Matt, Nov 17 2026: no pop-ups. Auto install sheet + alerts soft-ask only when BN_POPUPS=1
            b = b.replace(b'"__BN_POPUPS__"', b"1" if os.environ.get("BN_POPUPS", "0").strip() == "1" else b"0")
        if name == "manifest.webmanifest":   # Nov 24 2026: /live deactivated (deactivated.py) -> the installed app opens on The Wire
            try:
                import deactivated
                if deactivated.is_off("/live"): b = b.replace(b'"start_url": "/live"', b'"start_url": "/wire"')
            except Exception: pass
        return 200, b, ct
    if path.startswith("/icons/"):
        name = path[len("/icons/"):]
        if re.fullmatch(r"icon-[a-z0-9\-]+\.png", name) and os.path.isfile(os.path.join(D, name)): return 200, _read(name), "image/png"
    return 404, {"error": "not found"}

def _mp4_names():
    return {"/bn-menu-city-m.mp4": "bn-menu-city-m.mp4", "/bn-menu-city-d.mp4": "bn-menu-city-d.mp4"}

def handle_stream(path, qs, h):
    """Byte-range for the menu Earth loops (iOS/Safari). Other PWA files go through handle_get."""
    mp4 = _mp4_names()
    if path not in mp4:
        r = handle_get(path, qs)
        return h.send(*r)
    name = mp4[path]
    try:
        data = _read(name)
    except Exception:
        return h.send(404, {"error": "not found"})
    n = len(data)
    start, end = 0, n - 1
    rng = h.headers.get("Range") or h.headers.get("range") or ""
    partial = False
    if rng.startswith("bytes="):
        spec = rng[6:].split(",")[0].strip()
        a, _, b = spec.partition("-")
        try:
            if a and b:
                start, end = int(a), int(b)
            elif a:
                start = int(a)
            elif b:
                start = max(0, n - int(b))
        except ValueError:
            start, end = 0, n - 1
        else:
            start = max(0, min(start, n - 1))
            end = max(start, min(end, n - 1))
            partial = True
    chunk = data[start:end + 1]
    h.send_response(206 if partial else 200)
    h.send_header("Content-Type", "video/mp4")
    h.send_header("Accept-Ranges", "bytes")
    h.send_header("Content-Length", str(len(chunk)))
    if partial:
        h.send_header("Content-Range", f"bytes {start}-{end}/{n}")
    h.send_header("Cache-Control", "public, max-age=31536000, immutable")
    h.send_header("X-Content-Type-Options", "nosniff")
    h.end_headers()
    h.wfile.write(chunk)
    return True
