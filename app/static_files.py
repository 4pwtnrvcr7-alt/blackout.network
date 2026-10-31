"""Static add-on routes: /guides/<file> (guide content fragments), /maps/<file> (downloadable PDFs) and /img/<file> (small UI images).
Serves only plain files from static/guides and static/maps; no directory listing, no path traversal."""
import os, re
BASE = os.path.dirname(os.path.abspath(__file__))
DIRS = {"/guides": os.path.join(BASE, "static", "guides"), "/maps": os.path.join(BASE, "static", "maps"), "/img": os.path.join(BASE, "static", "img")}
TYPES = {".html": "text/html", ".pdf": "application/pdf", ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".js": "application/javascript", ".css": "text/css", ".ico": "image/x-icon"}
def handle_get(path, qs):
    if path == "/theme.css":
        with open(os.path.join(BASE, "static", "theme.css"), "rb") as fh: return 200, fh.read(), "text/css"
    if path == "/favicon.ico":
        with open(os.path.join(BASE, "static", "img", "favicon.ico"), "rb") as fh: return 200, fh.read(), "image/x-icon"
    for pre, d in DIRS.items():
        if path.startswith(pre + "/"):
            name = path[len(pre) + 1:]
            if not re.fullmatch(r"[A-Za-z0-9_\-]+(\.[A-Za-z0-9]+)", name): return 404, {"error": "not found"}
            f = os.path.join(d, name); ext = os.path.splitext(name)[1].lower()
            if ext not in TYPES or not os.path.isfile(f): return 404, {"error": "not found"}
            with open(f, "rb") as fh: return 200, fh.read(), TYPES[ext]
    return 404, {"error": "not found"}
