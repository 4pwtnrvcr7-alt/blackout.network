"""PWA / home-screen add-on: web app manifest, app icons and the mobile install guide (static/pwa/).
GET /manifest.webmanifest (alias /manifest.json), /apple-touch-icon.png (+ -precomposed), /icons/<file>.png,
/install-guide.js, /install-guide.css. Plain files only: fixed names, no directory listing, no path traversal, no data collected."""
import os, re
BASE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(BASE, "static", "pwa")
FIXED = {"/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json"),
         "/manifest.json": ("manifest.webmanifest", "application/manifest+json"),
         "/apple-touch-icon.png": ("apple-touch-icon.png", "image/png"),
         "/apple-touch-icon-precomposed.png": ("apple-touch-icon.png", "image/png"),
         "/install-guide.js": ("install-guide.js", "application/javascript"),
         "/install-guide.css": ("install-guide.css", "text/css")}
def _read(name):
    with open(os.path.join(D, name), "rb") as fh: return fh.read()
def handle_get(path, qs):
    if path in FIXED:
        name, ct = FIXED[path]; return 200, _read(name), ct
    if path.startswith("/icons/"):
        name = path[len("/icons/"):]
        if re.fullmatch(r"icon-[a-z0-9\-]+\.png", name) and os.path.isfile(os.path.join(D, name)): return 200, _read(name), "image/png"
    return 404, {"error": "not found"}
