"""/static/ready/<NN-slug>.pdf|.webp: Everyday Readiness PDFs and their first-page thumbnails (static/ready/).
Raw response so PDFs go out as plain application/pdf (no charset), inline, cacheable for a day. No listing, no traversal."""
import os, re
BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "ready")
TYPES = {".pdf": "application/pdf", ".webp": "image/webp", ".png": "image/png"}
NAME = re.compile(r"\d\d-[a-z0-9-]+\.(pdf|webp|png)")

def handle_get(path, qs):
    name = path[len("/static/ready/"):] if path.startswith("/static/ready/") else ""
    f = os.path.join(BASE, name)
    if not NAME.fullmatch(name) or not os.path.isfile(f): return 404, {"error": "not found"}, None
    with open(f, "rb") as fh: return 200, fh.read(), name

def handle_stream(path, qs, h):
    r = handle_get(path, qs)
    if r[0] != 200: return h.send(404, {"error": "not found"})
    body, name = r[1], r[2]; ext = os.path.splitext(name)[1]
    h.send_response(200); h.send_header("Content-Type", TYPES[ext]); h.send_header("Content-Length", str(len(body)))
    h.send_header("Cache-Control", "public, max-age=86400"); h.send_header("X-Content-Type-Options", "nosniff")
    if ext == ".pdf": h.send_header("Content-Disposition", f'inline; filename="blackout-network-{name}"')
    h.end_headers()
    if h.command != "HEAD": h.wfile.write(body)
