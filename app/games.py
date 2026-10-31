"""Games tab add-on: serves the self-hosted 8-bit games from games_static/ (no CDN, no external assets).
/api/games/app.js, /api/games/app.css: tab UI.  /api/games/bundle.js: engine.js + every g_*.js game, concatenated.
All game code and pixel art is original; it touches no other module, database or scanner data."""
import os, re, glob
BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "games_static")
TYPES = {".js": "application/javascript", ".css": "text/css", ".txt": "text/plain", ".png": "image/png", ".md": "text/plain"}
_B = {"sig": None, "body": b""}

def _bundle():
    files = [os.path.join(STATIC, "engine.js")] + sorted(glob.glob(os.path.join(STATIC, "g_*.js")))
    sig = tuple((f, os.path.getmtime(f)) for f in files)
    if sig != _B["sig"]:
        parts = []
        for f in files:
            with open(f, "rb") as fh: parts.append(b"/* ---- " + os.path.basename(f).encode() + b" ---- */\n" + fh.read() + b"\n;\n")
        _B["body"] = b"".join(parts); _B["sig"] = sig
    return _B["body"]

def handle_get(path, qs):
    if not path.startswith("/api/games/"): return 404, {"error": "not found"}
    name = path[len("/api/games/"):]
    if name == "bundle.js": return 200, _bundle(), "application/javascript"
    if name == "list":
        return 200, {"files": [os.path.basename(f) for f in sorted(glob.glob(os.path.join(STATIC, "g_*.js")))]}
    if not re.fullmatch(r"[A-Za-z0-9_\-]+\.[a-z]+", name): return 404, {"error": "not found"}
    ext = os.path.splitext(name)[1]
    f = os.path.join(STATIC, name)
    if ext not in TYPES or not os.path.isfile(f): return 404, {"error": "not found"}
    with open(f, "rb") as fh: return 200, fh.read(), TYPES[ext]
