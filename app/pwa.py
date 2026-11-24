"""PWA / home-screen add-on: web app manifest, app icons and the mobile install guide (static/pwa/).
GET /manifest.webmanifest (aliases /manifest.json, /site.webmanifest), /apple-touch-icon.png (+ -precomposed), /icons/<file>.png,
/install-guide.js, /install-guide.css. Plain files only: fixed names, no directory listing, no path traversal, no data collected."""
import os, re
BASE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(BASE, "static", "pwa")
FIXED = {"/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json"),
         "/manifest.json": ("manifest.webmanifest", "application/manifest+json"),
         "/site.webmanifest": ("manifest.webmanifest", "application/manifest+json"),
         "/apple-touch-icon.png": ("apple-touch-icon.png", "image/png"),
         "/apple-touch-icon-precomposed.png": ("apple-touch-icon.png", "image/png"),
         "/install-guide.js": ("install-guide.js", "application/javascript"),
         "/install-guide.css": ("install-guide.css", "text/css")}
def _read(name):
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
