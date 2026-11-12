"""Small site-wide extras (t338/t347), served to every page by server.version_assets():
  /linkguard.js           hides links the nightly link checker flagged dead (tools/linkcheck.py -> linkcheck_dead.json)
  /api/linkcheck/dead     the flagged URLs (data-level 'dead' flags: the link stays in the data, the page just stops showing it)
  /bn-icons.js            emoji -> inline SVG icons on every page (Matt: no emojis on the site)
  /bn-eggs.js             a few discreet, accessible easter eggs (see the comment at the top of extras_static/eggs.js)"""
import os, json, time
BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "extras_static")
DEAD_F = os.path.join(BASE, "linkcheck_dead.json")
_cache = {"t": 0, "m": None, "body": None}

def dead():
    try: m = os.path.getmtime(DEAD_F)
    except OSError: return {"generated": None, "count": 0, "urls": []}
    if _cache["m"] != m:
        try:
            d = json.load(open(DEAD_F))
            _cache.update(m=m, body={"generated": d.get("generated"), "count": len(d.get("dead", {})),
                                     "urls": sorted(u for u, f in d.get("dead", {}).items() if f.get("dead"))})
        except Exception: _cache.update(m=m, body={"generated": None, "count": 0, "urls": []})
    return _cache["body"]

def handle_get(path, qs):
    if path == "/api/linkcheck/dead": return 200, dead()
    files = {"/linkguard.js": "linkguard.js", "/bn-eggs.js": "eggs.js", "/bn-icons.js": "icons.js"}
    if path in files:
        with open(os.path.join(STATIC, files[path]), "rb") as fh: return 200, fh.read(), "application/javascript"
    return 404, {"error": "not found"}

def page_404(path):
    """Friendly HTML 404 for people (API clients still get JSON). About 1 in 20 visits shows one quiet extra line (easter egg 4)."""
    import html, random
    rare = random.random() < 0.05
    extra = '<p class="nf-rare">Even the best scanners miss one now and then. You found the blank spot on the map.</p>' if rare else ""
    try:   # the one shared header + menu (sitenav), same as every other page (Nov 12); a failure here must not break the 404
        import sitenav as SN, sitenav_ui as UI
        top, head = SN.header_html(""), UI.THEME_SCRIPT + '<script src="/sitenav.js" defer></script>'
    except Exception:
        top, head = "", ""
    return ("<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content=\"width=device-width,initial-scale=1\">"
            "<title>Page not found | BLACKOUT.NETWORK</title><meta name=robots content=noindex><link rel=stylesheet href=/sitenav.css>" + head +
            "<style>body{margin:0;background:var(--bn-bg,#0B0D10);color:var(--bn-text,#E6E9EE);font:15px/1.6 var(--bn-font-body,Inter,system-ui,sans-serif)}"
            "main{padding:48px 0}h1{font:800 28px/1.2 var(--bn-font-ui,Montserrat,system-ui,sans-serif);margin:0 0 8px}a{color:var(--bn-link,#4aa3ff)}"
            ".nf-rare{color:var(--bn-muted,#8B95A3);font-size:13px;margin-top:28px}</style></head><body>" + top +
            f"<main id=main><h1>Page not found</h1><p>Nothing lives at <code>{html.escape(path[:120])}</code>.</p>"
            "<p><a href=\"/\">Go to The Wire</a> \u00b7 <a href=\"/sources\">Sources</a> \u00b7 <a href=\"/scoring\">How we score</a></p>"
            f"{extra}</main></body></html>").encode()
