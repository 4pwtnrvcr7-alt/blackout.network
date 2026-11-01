"""t347: display-only link mapping. Some sources are shown to people with the machine endpoint the scanner fetches (API / RSS URLs
that 400/404/410 in a browser). server.H.send() rewrites those exact JSON string values to the human-readable page on the way out.
The scanner, sources_ext fetch lists and config are NOT touched: they keep fetching the real endpoints."""
import re
MAP = [  # (regex matching the whole URL value, human page)
    (r"https?://api\.bsky\.app/xrpc/app\.bsky\.feed\.searchPosts[^\"]*", "https://bsky.app/search"),
    (r"https?://api\.ioda\.inetintel\.cc\.gatech\.edu/v2/[^\"]*", "https://ioda.inetintel.cc.gatech.edu/"),
    (r"https?://api\.reliefweb\.int/v[12]/?[^\"]*", "https://reliefweb.int/updates"),
    (r"https?://home\.treasury\.gov/news/press-releases/feed/?", "https://home.treasury.gov/news/press-releases"),
    (r"https?://deprem\.afad\.gov\.tr/apiv2/[^\"]*", "https://deprem.afad.gov.tr/last-earthquakes"),
    (r"https?://(?:www\.)?promedmail\.org/feed/?", "https://promedmail.org/"),
    (r"https?://www\.gdacs\.org/gdacsapi/?", "https://www.gdacs.org/"),
    (r"https?://www\.who\.int/feeds/entity/csr/don/en/rss\.xml", "https://www.who.int/emergencies/disease-outbreak-news"),
    (r"https?://news\.google\.com/rss/search/?", "https://news.google.com/"),
    (r"https?://t\.me/s/", "https://telegram.org/"),
]
_RX = re.compile('"(' + "|".join("(?:%s)" % p for p, _ in MAP) + ')"')
_C = [(re.compile("^(?:%s)$" % p), h) for p, h in MAP]
def human(u):
    for rx, h in _C:
        if rx.match(u or ""): return h
    return u
def rewrite_json(s):
    """s: serialized JSON text. Only whole string values are replaced (URLs inside longer strings are left alone)."""
    if "://" not in s: return s
    return _RX.sub(lambda m: '"' + human(m.group(1)) + '"', s)
