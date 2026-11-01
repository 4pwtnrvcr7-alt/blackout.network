"""Route table for add-on dashboard modules (hot-reloaded by server.py when this file or a module changes).
Each module exposes handle_get(path, qs) -> (code, body) and optionally handle_post(path, data) -> (code, body).
Add-ons are separate files: they never modify scanner.py, scoring, push.py or jets.py."""
ROUTES = {
    "/api/arcs": "arcs",
    "/api/arcs_window": "arcs",
    "/api/broadcasts": "broadcasts",
    "/api/broadcast_keywords": "broadcasts",
    "/api/resources": "resources",
    "/api/maps": "maps",
    "/api/timeline": "timeline",
    "/snapshots": "timeline",
    "/api/stream": "livepush",
    "/api/live_status": "livepush",
    "/api/streams": "streams",
    "/api/radio": "radio",
    "/api/geo": "visitor_geo",
    "/api/live_archive": "live_archive",
    "/api/tips": "tips",
    "/api/netstatus": "netstatus",
    "/api/netstatus/alerts": "netstatus",
    "/api/vote": "votes",
    "/api/votes": "votes",
    "/api/user_ranked": "votes",
    "/api/solar_seismic": "solar_seismic",
    "/api/solar_quake": "solar_quake",   # Solar–Earthquake Correlation Lab (t242), precomputed by tools/solar_quake_build.py
    "/api/heatmap": "heatmap",
    "/api/weather": "weather",
    "/api/trends": "trends",
    "/api/wire_history": "wire_history",   # Wire tab scrollable history + ARCHIVE items (t246)
    "/api/noise": "bnoise",
    "/api/politics": "politics",
    "/api/games": "games",
    "/api/translate": "translate",
    "/guides": "static_files",
    "/maps": "static_files",
    "/img": "static_files",
    "/favicon.ico": "static_files",
    "/theme.css": "static_files",
    "/sitenav.js": "sitenav",       # shared tab bar + per-page/tab SEO (t301/t302)
    "/sitenav.css": "sitenav",
    "/fonts": "sitenav",            # self-hosted Montserrat + Inter woff2 (OFL), t323
    "/scoring": "scoring",
    "/about/scoring": "scoring",
    "/privacy": "legal",            # Privacy Policy (t270), static page, served during warm-up
    "/privacy-policy": "legal",
    "/tos": "legal",                # Terms of Service (t270)
    "/terms": "legal",
    "/terms-of-service": "legal",
    "/api/video_subs": "video_subs",
    "/vsubs": "video_subs",
    "/api/search": "search",
    "/newsletter": "newsletter",
    "/api/newsletter": "newsletter",
    "/sources": "sources",
    "/api/sources": "sources",
    "/wire": "story",               # /wire/<cluster_id>: one page per scanner story, every source (story.py, t303); newsletter items link here
    "/social": "social",            # Videos & posts hub + /social/thumb/<file> hosted thumbnails (social.py, t303)
    "/api/social": "social",
    "/story": "social",             # /story/<slug>: one page per launch video (article + nocookie embed), hidden until publish_at (t311)
    "/api/spacex": "spacex",
    "/api/elon": "elon",
    "/api/finance": "finance",
    "/api/intel": "intel_streams",
    "/api/ai": "aithreats",          # tab #ai (t231; in the nav since t233)
    "/api/grid": "gridwatch",        # tab #grid (t231; in the nav since t233)
    "/api/gridstatus": "gridstatus", # #grid status map, local outages, weather-triggered checks (t234)
    "/api/government": "government",   # Government tab #government (t247): index + org chart, government.db from government_collect.py
    "/api/midterms": "midterms",   # Midterms 2026 tab #midterms: races, ratings, polls vs markets, official live results (midterms.py)
    "/midterms": "midterms", "/election": "midterms", "/elections": "midterms",
    "/api/preppers": "preppers",
    "/api/report": "reports",
    "/api/reports": "reports",
    "/report-status": "reports",
    "/manifest.webmanifest": "pwa",
    "/manifest.json": "pwa",
    "/apple-touch-icon.png": "pwa",
    "/apple-touch-icon-precomposed.png": "pwa",
    "/icons": "pwa",
    "/install-guide.js": "pwa",
    "/install-guide.css": "pwa",
}
