"""Per-page Open Graph / Twitter share images (1200x630) in the current SpaceX design.

Every public page's og:image and twitter:image points at /og/<page>.png (stories at
/og/wire/<id>.png). Images are rendered with Pillow from that page's own hero still,
darkened, with the page title, a small plain-text "blackout.network" wordmark and
the optional "Global threat monitoring" tagline. No yellow, no old dashboard tile,
no image credits, no emoji. Rank is a small grey label, or red when the rank is 7+.

Cached on disk per page/story, keyed to the content. Social caches are busted with
a ?v= query. Replaces the single static card at /icons/icon-og-v2-1200x630.png.
"""
from __future__ import annotations

import hashlib, html, io, os, re, tempfile, threading
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

SITE = "https://blackout.network"
BRAND = "BLACKOUT.NETWORK"
WORDMARK = "blackout.network"
TAGLINE = "Global threat monitoring"
HANDLE = "@BlkoutNtw"
VERSION = "19"  # bump to force social CDNs to refetch (Nov 25: v17 = strict exact-name photos; audit downgrades; typography hash)
W, H = 1200, 630

BASE = Path(__file__).resolve().parent
FONTS = BASE / "static" / "fonts"
NEWS_FONTS = BASE / "static" / "newsletter" / "fonts"
MONT_VAR = FONTS / "Montserrat-VariableFont_wght.ttf"
INTER_BOLD = NEWS_FONTS / "Inter-Bold.ttf"
INTER_MED = NEWS_FONTS / "Inter-Medium.ttf"

# Dark theme tokens (greys brightening to white; red only for rank 7+)
BG = (5, 6, 10)
WHITE = (255, 255, 255)
TITLE = (255, 255, 255)
MUTED = (160, 166, 176)
WORD = (220, 223, 230)
TAG = (140, 146, 156)
RANK_GREY = (168, 174, 184)
RANK_RED = (200, 16, 46)  # rank 7+ only
YELLOW_MAX = 28  # reject leftover yellow from the old card

# Page card copy + background. bg is ("media", "hero-d.jpg") from theme_static/media,
# or ("wire", "iss070e062746.webp") from wire_v2_static/img. Stills are the same
# licensed / original heroes already on the page (NASA, SDO, our own captures).
# Pages without a unique hero use the site hero still, never a fabricated event photo.
PAGES = {
    "home": dict(path="/", title="Global threat monitoring | BLACKOUT.NETWORK",
                 card="Global threat monitoring",
                 desc="Global threat monitoring: independent, sourced early-warning signals on US and world threats, ranked 0 to 10 and updated around the clock. Not official alerts.",
                 bg=("media", "hero-d.jpg"), tagline=True),
    "live": dict(path="/live", title="BLACKOUT.NETWORK · Global threat monitoring",
                 card="Live dashboard",
                 desc="Independent, sourced early-warning signals on US and global threats: threat alerts and breaking news, updated around the clock. Not official alerts.",
                 bg=("media", "lvvid-d.jpg"), tagline=True),
    "wire": dict(path="/wire", title="The Wire: live threat feed | BLACKOUT.NETWORK",
                 card="The Wire",
                 desc="BLACKOUT.NETWORK's free early-warning feed: outbreaks, quakes, cyber attacks, unrest and conflict, each ranked 0–10 and linked to its sources. Research only, not official alerts.",
                 bg=("wire", "iss070e062746.webp"), tagline=True),
    "map": dict(path="/map", title="Heat map | BLACKOUT.NETWORK",
                card="Heat map",
                desc="Full-screen live heat map of ranked alerts from the last 7 days: conflicts, weather and quakes, outbreaks, outages and unrest.",
                bg=("media", "hmvid-d.jpg"), tagline=True),
    "crime": dict(path="/crime", title="Crime map and statistics near you: ZIP, city, county, country | BLACKOUT.NETWORK",
                  card="Crime",
                  desc="Look up crime for any US ZIP code, city, county or state, or any country: official FBI rates per 100,000 with trends, near-real-time incident heat maps for 16 US cities, a US county map and a world homicide map.",
                  bg=("media", "crvid-d.jpg"), tagline=True),
    "streams": dict(path="/streams", title="Live TV & Radio | BLACKOUT.NETWORK",
                    card="Live TV & Radio",
                    desc="Watch news channels streaming live right now on BLACKOUT.NETWORK, each one watched and transcribed so you can catch breaking events as they air.",
                    bg=("media", "tvvid-d.jpg"), tagline=True),
    "broadcasts": dict(path="/broadcasts", title="Live Broadcasts: wire, TV and radio | BLACKOUT.NETWORK",
                       card="Live Broadcasts",
                       desc="Live wire, local TV and radio transcripts on BLACKOUT.NETWORK, searched for threat keywords and color-coded by category as they come in, around the clock.",
                       bg=("media", "bcvid-d.jpg"), tagline=True),
    "radio": dict(path="/radio", title="Radio: number stations and live HF | BLACKOUT.NETWORK",
                  card="Live Radio",
                  desc="Listen to number stations, military HF and live radio on BLACKOUT.NETWORK, playable right in the browser, with a rolling transcript and a location filter.",
                  bg=("media", "rdvid-d.jpg"), tagline=True),
    "solar": dict(path="/solar", title="Solar & Seismic: space weather and quakes | BLACKOUT.NETWORK",
                  card="Solar & Seismic",
                  desc="Space weather and earthquakes on BLACKOUT.NETWORK: solar flares, geomagnetic storms, the Kp index and live global quakes, plus a solar–quake correlation lab.",
                  bg=("media", "cover-d.jpg"), tagline=True),  # SDO solar flare, 2016, public domain; same still as the site coverage band
    "weather": dict(path="/weather", title="Weather: alerts and forecast | BLACKOUT.NETWORK",
                    card="Weather",
                    desc="Current conditions, official severe-weather alerts and the forecast for any place you choose, on BLACKOUT.NETWORK. Free, with no account or sign-up needed.",
                    bg=("media", "noise-d.jpg"), tagline=True),  # NASA ISS imagery of Hurricane Dorian, 2019, public domain; also the site ranking-band still
    "network": dict(path="/grid", title="The Grid: power grid, internet and cloud status | BLACKOUT.NETWORK",
                    card="The Grid",
                    desc="Live status of the power grid and the networks that run on it on BLACKOUT.NETWORK: grid operators, outages by state, internet, cloud, apps and ISPs.",
                    bg=("media", "planet-d.jpg"), tagline=True),  # NASA ISS Earth limb, 2024, public domain
    "sources": dict(path="/sources", title="Sources | BLACKOUT.NETWORK",
                    card="Sources",
                    desc="Every source BLACKOUT.NETWORK uses, with item counts, profiles and a transparent 0–10 confidence rating. Search the directory or suggest a new source.",
                    bg=("wire", "iss067e302248.webp"), tagline=True),
    "credits": dict(path="/credits", title="Image credits | BLACKOUT.NETWORK",
                    card="Image credits",
                    desc="Sources and licences for the images and video used on BLACKOUT.NETWORK.",
                    bg=("media", "planet-d.jpg"), tagline=True),
    "newsletter": dict(path="/newsletter", title="Newsletter | BLACKOUT.NETWORK",
                       card="Newsletter",
                       desc="Sign up for BLACKOUT.NETWORK's free email brief: the highest-severity sourced threats, once or twice a day. Double opt-in, one-click unsubscribe.",
                       bg=("media", "email-d.jpg"), tagline=True),
    "scoring": dict(path="/scoring", title="How we score | BLACKOUT.NETWORK",
                    card="How we score",
                    desc="How BLACKOUT.NETWORK scores threats: the 0–100 severity score and the 0–10 rank, explained factor by factor with real worked examples. Research only.",
                    bg=("wire", "gen_signal_lines.webp"), tagline=True),
    "privacy": dict(path="/privacy", title="Privacy Policy | BLACKOUT.NETWORK",
                    card="Privacy Policy",
                    desc="BLACKOUT.NETWORK's Privacy Policy: what the site collects, how the newsletter and YouTube data are used and stored, retention, deletion and how to reach us.",
                    bg=("media", "hero-d.jpg"), tagline=True),
    "tos": dict(path="/tos", title="Terms of Service | BLACKOUT.NETWORK",
                card="Terms of Service",
                desc="BLACKOUT.NETWORK's Terms of Service: acceptable use, research-only data with no warranty, limitation of liability, Florida governing law and contact details.",
                bg=("media", "hero-d.jpg"), tagline=True),
    "cookies": dict(path="/cookies", title="Cookie Policy | BLACKOUT.NETWORK",
                    card="Cookie Policy",
                    desc="BLACKOUT.NETWORK's Cookie Policy: every cookie and browser storage item the site uses, what each does, how long it lasts, and how to turn analytics off.",
                    bg=("media", "hero-d.jpg"), tagline=True),
    "privacy-choices": dict(path="/privacy-choices", title="Your Privacy Choices | BLACKOUT.NETWORK",
                            card="Your Privacy Choices",
                            desc="Your Privacy Choices at BLACKOUT.NETWORK: we don't sell or share personal information. Turn Google Analytics off in this browser, and how we honor Global Privacy Control.",
                            bg=("media", "hero-d.jpg"), tagline=True),
    "social": dict(path="/social", title="Videos & posts | BLACKOUT.NETWORK",
                   card="Videos & posts",
                   desc="BLACKOUT.NETWORK videos and posts: world threat updates and explainers from YouTube @blkoutntw and X @BLKOUTNTW, each with a full sourced story page.",
                   bg=("media", "hero-d.jpg"), tagline=True),
    "stats": dict(path="/stats", title="Public stats: site traffic, YouTube and X | BLACKOUT.NETWORK",
                  card="Public stats",
                  desc="BLACKOUT.NETWORK's open stats: daily visitors and page views, the most-read pages and stories, where readers come from, plus YouTube @blkoutntw and X @BlkoutNtw growth.",
                  bg=("media", "trvid-d.jpg"), tagline=True),
    "cern": dict(path="/cern", title="CERN and the Large Hadron Collider: how it works, who pays, what it found | BLACKOUT.NETWORK",
                 card="CERN & the LHC",
                 desc="How CERN's 27 km Large Hadron Collider works and was built, who funds it country by country, what it discovered, the conspiracy theories next to the physics, and CERN's live control-room displays.",
                 bg=("media", "hero-d.jpg"), tagline=True),
    "welcome": dict(path="/welcome", title="Start here | BLACKOUT.NETWORK",
                    card="Start here",
                    desc="A brief overview of BLACKOUT.NETWORK: a free early-warning threat monitor, what we are trying to do, and the tools on this site. Not official alerts.",
                    bg=("media", "hero-d.jpg"), tagline=True),
    "mesh": dict(path="/mesh", title="Off-grid network map: live public mesh radios | BLACKOUT.NETWORK",
                 card="Off-grid network",
                 desc="A live map of public off-grid mesh radios worldwide, opening on a U.S. view, with a drop-off watch that flags regions where radios go quiet.",
                 bg=("media", "planet-d.jpg"), tagline=True),
    "noise": dict(path="/noise", title="Background Noise: low-rank alerts | BLACKOUT.NETWORK",
                  card="Background Noise",
                  desc="Every lower-priority alert BLACKOUT.NETWORK's scanner logs, ranked 0 to 6 and newest first, so you can see what is simmering before it becomes news.",
                  bg=("media", "nzvid-d.jpg"), tagline=True),
    "trends": dict(path="/trends", title="Trends: alert volume over time | BLACKOUT.NETWORK",
                   card="Trends",
                   desc="See how BLACKOUT.NETWORK's alert volume, severity mix and source health have moved over hours, days and weeks, with charts you can read on any screen.",
                   bg=("media", "trvid-d.jpg"), tagline=True),
    "grid": dict(path="/grid", title="The Grid: power grid, internet and cloud status | BLACKOUT.NETWORK",   # Nov 24 2026: /grid is The Grid's canonical URL
                 card="The Grid",
                 desc="Live status of the power grid and the networks that run on it on BLACKOUT.NETWORK: grid operators, outages by state, internet, cloud, apps and ISPs.",
                 bg=("media", "planet-d.jpg"), tagline=True),
    "ai": dict(path="/ai", title="AI Threats: AI-driven attacks and fraud | BLACKOUT.NETWORK",
               card="AI Threats",
               desc="BLACKOUT.NETWORK tracks AI threats: AI-assisted hacking, rogue bots and agents, AI-enabled cyber attacks, deepfake fraud and model misuse, ranked 0–10.",
               bg=("media", "hero-d.jpg"), tagline=True),
    "midterms": dict(path="/midterms", title="Midterms 2026: races, polls and results | BLACKOUT.NETWORK",
                     card="Midterms 2026",
                     desc="The 2026 U.S. midterms on BLACKOUT.NETWORK: every Senate, House and governor race, with cited ratings, polls, market odds and official live results.",
                     bg=("media", "hero-d.jpg"), tagline=True),
    "spacex": dict(path="/spacex", title="SpaceX: launches, Starship and Starlink | BLACKOUT.NETWORK",
                   card="SpaceX",
                   desc="SpaceX on BLACKOUT.NETWORK: next-launch countdown, the full launch schedule, Starship and Starlink updates, recent news and related prediction markets.",
                   bg=("media", "cover-d.jpg"), tagline=True),
    "figures": dict(path="/figures", title="Key Figures: people in the news | BLACKOUT.NETWORK",
                    card="Key Figures",
                    desc="A neutral reference to the people named in the stories BLACKOUT.NETWORK follows: their current role, why they are in the news and the latest headlines.",
                    bg=("media", "hero-d.jpg"), tagline=True),
    "politics": dict(path="/politics", title="Politics: developments and markets | BLACKOUT.NETWORK",
                     card="Politics",
                     desc="Political developments flagged by BLACKOUT.NETWORK's scanner, alongside public prediction-market prices, so you can see what might shift and how fast.",
                     bg=("media", "hero-d.jpg"), tagline=True),
    "finance": dict(path="/finance", title="Finance: global markets | BLACKOUT.NETWORK",
                    card="Finance",
                    desc="Global markets on BLACKOUT.NETWORK: indices, ETFs, stocks, bonds, options and volatility, forex and crypto, in one dark, phone-friendly dashboard tab.",
                    bg=("media", "hero-d.jpg"), tagline=True),
    "jets": dict(path="/jets", title="Private jets: business jets airborne now | BLACKOUT.NETWORK",
                 card="Private jets",
                 desc="Private and business jets airborne right now anywhere in the world, tracked on BLACKOUT.NETWORK from public transponder data and refreshed every few minutes.",
                 bg=("media", "hero-d.jpg"), tagline=True),
    "intel": dict(path="/intel", title="Intel Streams: research, leaks, patents | BLACKOUT.NETWORK",
                  card="Intel Streams",
                  desc="BLACKOUT.NETWORK's Intel Streams: new research papers, leak releases, patents, mergers and market shocks, each linked to its source, with an RSS feed.",
                  bg=("media", "hero-d.jpg"), tagline=True),
    "government": dict(path="/government", title="Government | BLACKOUT.NETWORK",
                       card="Government",
                       desc="Government organisations tracked on BLACKOUT.NETWORK.",
                       bg=("media", "hero-d.jpg"), tagline=True),
    "preppers": dict(path="/preppers", title="Preppers: suppliers, guidance and kits | BLACKOUT.NETWORK",
                     card="Preppers",
                     desc="Rated prepper suppliers, free official preparedness guidance, a supply planner and ready-made kit lists for every threat type, on BLACKOUT.NETWORK.",
                     bg=("media", "hero-d.jpg"), tagline=True),
    "games": dict(path="/games", title="Games: 8-bit arcade games | BLACKOUT.NETWORK",
                  card="Games",
                  desc="Original 8-bit style arcade, puzzle and board games you can play right in your browser on BLACKOUT.NETWORK, on desktop or phone. Free, no download.",
                  bg=("media", "hero-d.jpg"), tagline=True),
    "gunlaws": dict(path="/gunlaws", title="Gun Laws: court cases, bills and forecasts | BLACKOUT.NETWORK",
                    card="Gun Laws",
                    desc="Second Amendment cases in U.S. courts, gun bills in Congress and state ballot measures on BLACKOUT.NETWORK, with parties, odds and plain-English forecasts.",
                    bg=("media", "hero-d.jpg"), tagline=True),
    "medical": dict(path="/medical", title="Medical | BLACKOUT.NETWORK",
                    card="Medical",
                    desc="Medical and health signals on BLACKOUT.NETWORK.",
                    bg=("wire", "gen_health_abstract.webp"), tagline=True),
    "resources": dict(path="/resources", title="Resources | BLACKOUT.NETWORK",
                      card="Resources",
                      desc="Preparedness resources on BLACKOUT.NETWORK.",
                      bg=("media", "hero-d.jpg"), tagline=True),
    "bushcraft": dict(path="/bushcraft", title="Bushcraft | BLACKOUT.NETWORK",
                      card="Bushcraft",
                      desc="Bushcraft guides and plant knowledge on BLACKOUT.NETWORK.",
                      bg=("media", "hero-d.jpg"), tagline=True),
    "ranked": dict(path="/ranked", title="Ranked by Users | BLACKOUT.NETWORK",
                   card="Ranked by Users",
                   desc="Vote on how serious each alert is and compare the crowd's 0–10 threat level with the scanner's own ranking, live on BLACKOUT.NETWORK. No sign-up needed.",
                   bg=("media", "hero-d.jpg"), tagline=True),
    "thread": dict(path="/thread", title="The Thread: developing stories | BLACKOUT.NETWORK",
                   card="The Thread",
                   desc="BLACKOUT.NETWORK's Thread links related alerts into developing stories, showing every update, its sources and how the threat level changed over time.",
                   bg=("wire", "iss070e062746.webp"), tagline=True),
}

# Tab path keys that 302 to /live#<key> for humans; social crawlers get a 200 share page.
TAB_SHARE = ("solar", "weather", "streams", "broadcasts", "radio", "noise", "trends",
             "grid", "ai", "midterms", "spacex", "figures", "politics", "finance",
             "jets", "intel", "government", "preppers", "games", "gunlaws",
             "medical", "resources", "bushcraft", "ranked", "thread", "wire")

# Paths that already have a real HTML page (do not intercept as a share shim).
REAL_PATHS = {"wire", "network", "grid", "map", "crime", "sources", "credits", "newsletter",
              "scoring", "privacy", "tos", "cookies", "privacy-choices", "social",
              "stats", "cern", "welcome", "mesh", "live", "home"}

CRAWLER_RE = re.compile(
    r"(Twitterbot|facebookexternalhit|Facebot|FacebookBot|LinkedInBot|Slackbot|Slack-ImgProxy|"
    r"Discordbot|WhatsApp|TelegramBot|Pinterest|Applebot|Googlebot|bingbot|DuckDuckBot|"
    r"Baiduspider|YandexBot|ia_archiver|SkypeUriPreview|redditbot|vkShare|W3C_Validator|"
    r"Embedly|Quora Link Preview|BitlyBot|Iframely|Viber|Line/|QQBot)",
    re.I,
)

_LOCK = threading.Lock()
_MEM = {}  # key -> png bytes
_MEM_MAX = 48
_FONT_CACHE = {}


def cache_dir():
    p = Path(os.environ.get("BN_OG_CACHE") or os.path.join(tempfile.gettempdir(), "bn-og-cache"))
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception:
        p = Path(tempfile.gettempdir())
    return p


def is_crawler(ua):
    return bool(ua and CRAWLER_RE.search(ua))


def _font(path, size, weight=None, axes=None):
    key = (str(path), size, weight, tuple(axes) if axes else None)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    font = ImageFont.truetype(str(path), size=size)
    try:
        if axes:
            font.set_variation_by_axes(list(axes))
        elif weight is not None and hasattr(font, "set_variation_by_axes"):
            # Montserrat is a single wght axis; Inter variable would be opsz,wght.
            font.set_variation_by_axes([weight])
    except Exception:
        pass
    _FONT_CACHE[key] = font
    return font


def _resolve_font(path):
    """Prefer a real TTF; otherwise decode a sibling .b64 (text-only deploy path)."""
    path = Path(path)
    if path.is_file():
        return path
    b64 = Path(str(path) + ".b64")
    if b64.is_file():
        dest = cache_dir() / path.name
        if not dest.is_file() or dest.stat().st_size == 0:
            import base64
            dest.write_bytes(base64.b64decode(b64.read_bytes()))
        return dest
    return path

def mont(size, weight=800):
    p = _resolve_font(MONT_VAR)
    if p.is_file():
        return _font(p, size, weight=weight)
    # last-resort system font; Render ships the vendored .b64
    for cand in ("/usr/share/fonts/truetype/sand-box/google/Montserrat/Montserrat-VariableFont_wght.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.isfile(cand):
            return _font(cand, size, weight=weight)
    return ImageFont.load_default()


def inter(size, bold=False):
    path = INTER_BOLD if bold else INTER_MED
    if path.is_file():
        return _font(path, size)
    if INTER_BOLD.is_file():
        return _font(INTER_BOLD, size)
    return mont(size, 600 if not bold else 800)


def _cover(im, w=W, h=H):
    im = im.convert("RGB")
    iw, ih = im.size
    if iw < 1 or ih < 1:
        return Image.new("RGB", (w, h), BG)
    scale = max(w / iw, h / ih)
    nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
    im = im.resize((nw, nh), Image.Resampling.LANCZOS)
    left, top = (nw - w) // 2, (nh - h) // 2
    return im.crop((left, top, left + w, top + h))


def _media_bytes(name):
    try:
        import theme
        b = theme._media_bytes(name)
        if b:
            return b
    except Exception:
        pass
    # direct decode if theme's name filter or import fails
    media = BASE / "theme_static" / "media"
    p = media / (name + ".b64")
    try:
        if p.is_file():
            import base64
            return base64.b64decode(p.read_bytes())
    except Exception:
        return None
    return None


def _wire_bytes(name):
    folder = BASE / "wire_v2_static" / "img"
    fp = folder / name
    try:
        if fp.is_file():
            return fp.read_bytes()
        b64 = folder / (name + ".b64")
        if b64.is_file():
            import base64
            return base64.b64decode(b64.read_bytes())
    except Exception:
        return None
    return None


def _open_bg(kind, name):
    data = _media_bytes(name) if kind == "media" else _wire_bytes(name) if kind == "wire" else None
    if not data:
        return None
    try:
        return Image.open(io.BytesIO(data))
    except Exception:
        return None


def _darken(im):
    """Full-bleed still, darkened, with a heavier grade toward the lower third for type."""
    im = _cover(im)
    # slight blur so the photo sits behind the type, SpaceX-poster style
    try:
        im = ImageEnhance.Color(im).enhance(0.55)
        im = ImageEnhance.Brightness(im).enhance(0.72)
        im = Image.blend(im, im.filter(ImageFilter.GaussianBlur(1.2)), 0.25)
    except Exception:
        pass
    overlay = Image.new("RGB", (W, H), BG)
    im = Image.blend(im, overlay, 0.38)
    grade = Image.new("L", (W, H), 0)
    gd = ImageDraw.Draw(grade)
    for y in range(H):
        if y < H * 0.35:
            a = 40
        else:
            t = (y - H * 0.35) / (H * 0.65)
            a = int(40 + t * 200)
        gd.line([(0, y), (W, y)], fill=min(255, a))
    im = Image.composite(Image.new("RGB", (W, H), BG), im, grade)
    return im


def _plain_bg():
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    # quiet vertical grade, no map, no dots
    for y in range(H):
        c = 5 + int(10 * (y / H))
        d.line([(0, y), (W, y)], fill=(c, c + 1, c + 3))
    return im


def _strip_emoji(s):
    s = re.sub(r"[\U0001F000-\U0001FAFF\U00002700-\U000027BF\U00002600-\U000026FF\U0000FE00-\U0000FE0F\U0000200D]+", " ", s or "")
    return re.sub(r"\s+", " ", s).strip(" |:-")


def _wrap(draw, text, font, max_width, tracking, max_lines=3):
    words = (text or "").split()
    if not words:
        return [""]
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if _text_w(draw, trial, font, tracking) <= max_width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
            if len(lines) == max_lines:
                break
    if len(lines) < max_lines and cur:
        lines.append(cur)
    elif cur and len(lines) == max_lines:
        # overflow: ellipsis on the last accepted line
        last = lines[-1]
        while last and _text_w(draw, last.rstrip() + "…", font, tracking) > max_width:
            last = last[:-1]
        lines[-1] = (last.rstrip() + "…") if last else "…"
    return lines[:max_lines]


def _text_w(draw, text, font, tracking):
    if not text:
        return 0
    w = 0
    for i, ch in enumerate(text):
        w += draw.textlength(ch, font=font)
        if i < len(text) - 1:
            w += tracking
    return w


def _draw_tracked(draw, xy, text, font, fill, tracking=0):
    x, y = xy
    for i, ch in enumerate(text):
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + (tracking if i < len(text) - 1 else 0)
    return x


def render(title, bg_im=None, tagline=True, rank=None, wordmark=WORDMARK):
    """Return a 1200x630 RGB image. title is the large on-card line; rank is 0–10 or None."""
    title = _strip_emoji(title or TAGLINE)
    im = _darken(bg_im) if bg_im is not None else _plain_bg()
    d = ImageDraw.Draw(im)
    left, right = 72, W - 72
    max_w = right - left

    wm_font = inter(22, bold=True)
    _draw_tracked(d, (left, 56), wordmark, wm_font, WORD, tracking=3.2)

    if tagline:
        tg_font = inter(13, bold=False)
        _draw_tracked(d, (left, 92), TAGLINE.upper(), tg_font, TAG, tracking=3.8)

    # Title: letterspaced Montserrat, white, up to 3 lines in the lower half
    size = 64
    if len(title) > 70:
        size = 48
    elif len(title) > 42:
        size = 56
    tfont = mont(size, 750)
    tracking = 1.6 if size >= 56 else 1.1
    lines = _wrap(d, title, tfont, max_w, tracking, 3)
    line_h = int(size * 1.12)
    block_h = line_h * len(lines)
    y = H - 86 - block_h
    if rank is not None:
        y -= 28
    y = max(160, y)
    for line in lines:
        _draw_tracked(d, (left, y), line, tfont, TITLE, tracking=tracking)
        y += line_h

    if rank is not None:
        try:
            r = int(rank)
        except (TypeError, ValueError):
            r = None
        if r is not None and 0 <= r <= 10:
            color = RANK_RED if r >= 7 else RANK_GREY
            rf = inter(14, bold=True)
            label = f"RANK  {r}"
            _draw_tracked(d, (left, y + 14), label, rf, color, tracking=3.0)

    return im


def png_bytes(im):
    buf = io.BytesIO()
    im.convert("RGB").save(buf, format="PNG", compress_level=3)   # optimize=True cost ~1 s locally and 4-5 s on Render (X gives up), for only ~10% smaller files
    return buf.getvalue()


def _cache_key(kind, ident, title, rank, bg_id):
    raw = f"{VERSION}|{kind}|{ident}|{title}|{rank}|{bg_id}".encode("utf-8", "replace")
    return hashlib.sha1(raw).hexdigest()


def drop_mem():
    """Drop the in-process PNG memo so a rebuilt card is not hidden by a stale render."""
    with _LOCK:
        _MEM.clear()


def _cached(key, builder):
    with _LOCK:
        if key in _MEM:
            return _MEM[key]
    fp = cache_dir() / f"{key}.png"
    try:
        if fp.is_file() and fp.stat().st_size > 1000:
            data = fp.read_bytes()
            _store_mem(key, data)
            return data
    except Exception:
        pass
    data = builder()
    try:
        fp.write_bytes(data)
    except Exception:
        pass
    _store_mem(key, data)
    return data


def _store_mem(key, data):
    with _LOCK:
        _MEM[key] = data
        if len(_MEM) > _MEM_MAX:
            # drop oldest insertion
            for k in list(_MEM.keys())[: len(_MEM) - _MEM_MAX]:
                _MEM.pop(k, None)


def page_spec(key):
    return PAGES.get(key) or PAGES.get((key or "").lower())


def png_for(key):
    """PNG bytes for a named page. Never raises; always 1200x630."""
    spec = page_spec(key) or dict(card=(key or TAGLINE), bg=None, tagline=True)
    title = spec.get("card") or TAGLINE
    bg_id = ""
    bg_im = None
    if spec.get("bg"):
        kind, name = spec["bg"]
        bg_id = f"{kind}:{name}"
        bg_im = _open_bg(kind, name)
    keyhash = _cache_key("page", key or "home", title, "", bg_id)

    def build():
        return png_bytes(render(title, bg_im=bg_im, tagline=spec.get("tagline", True)))

    return _cached(keyhash, build)


def _story_spec(cid):
    """Look up a live story's headline, rank and hero still. None if it is not on the board."""
    cid = (cid or "").lower()
    if not re.fullmatch(r"[0-9a-f]{16}", cid):
        return None
    try:
        import theme, wire_v2
        st = theme._srv().api_state()
        items = list(wire_v2.items(st)) + list(st.get("watchlist") or [])
        it = next((x for x in items if str(x.get("cluster_id") or "").lower() == cid), None)
        if not it:
            return None
        title = wire_v2.headline(it.get("title") or "") or (it.get("title") or "Story")
        rank = int(it.get("rank") or 0)
        hero_src = ""
        try:
            import story_v3
            if story_v3.on():
                a = story_v3.assemble(story_v3.note_for(cid), it, wire_v2)
                title = a.get("headline") or title
                hero = a.get("hero") if isinstance(a.get("hero"), dict) else {}
                hero_src = (hero or {}).get("image") or ""
        except Exception:
            hero_src = ""
        if not hero_src:
            used = wire_v2.Used()
            k = used.take(wire_v2.img_keys(it)) or used.take(["night"])
            if k:
                hero_src = f"{wire_v2.ST}/img/{wire_v2.IMG[k][0]}"
        desc = ""
        try:
            desc = wire_v2.first_sentence(it.get("brief") or it.get("title") or "", 160)
        except Exception:
            desc = title
        return dict(title=title, rank=rank, hero=hero_src, desc=desc)
    except Exception:
        return None


def _bg_from_src(src):
    if not src:
        return None, ""
    s = src.split("?")[0]
    # only local, already-licensed stills: /wire2/static/img/* or /bnt/media/*
    m = re.search(r"/wire2/static/img/([a-z0-9_]+\.webp)$", s)
    if m:
        return _open_bg("wire", m.group(1)), "wire:" + m.group(1)
    m = re.search(r"/bnt/media/([a-z]+-[dm]\.(?:jpg|png))$", s)
    if m:
        return _open_bg("media", m.group(1)), "media:" + m.group(1)
    # bare filename from the wire catalogue
    if re.fullmatch(r"[a-z0-9_]+\.webp", s):
        return _open_bg("wire", s), "wire:" + s
    return None, ""


def _db_spec(cid):
    """Title/rank straight from blackout.db (a quick read, no board build) for stories that are not on the live board or while the board is rebuilding."""
    try:
        import story, wire_v2
        r, _al = story.load(cid)
        if r:
            return dict(title=wire_v2.headline(r.get("title") or "") or r.get("title") or "The Wire", rank=int(r.get("rank") or 0), hero="")
    except Exception:
        pass
    return None


def png_for_story_fast(cid):
    """/og/wire/<id>.png in under ~2 s: the finished photo or map card. On a cold miss, render the designed
    map card synchronously (fast, no network) instead of the 1200x630 earth fallback. The earth card is
    only used when the story itself cannot be loaded."""
    try:
        import share_card
        b = share_card.story_png_fast(cid, budget=1.0)
        if b:
            return b
        b = share_card.story_png_map_now(cid)
        if b:
            return b
    except Exception:
        pass
    spec = _db_spec(cid) or {}
    t = spec.get("title") or "The Wire"
    bg_im = _open_bg("wire", "iss070e062746.webp")
    return _cached(_cache_key("quick", cid, t, spec.get("rank"), "wire:iss070e062746.webp"), lambda: png_bytes(render(t, bg_im=bg_im, tagline=True, rank=spec.get("rank"))))


def png_for_story(cid, title=None, rank=None, hero=None):
    if title is None and rank is None and hero is None:
        try:   # Nov 25 2026: unique per-story card (rank, location map or licensed hero, summary); the old card below is the fallback
            import share_card
            b = share_card.story_png(cid)
            if b:
                return b
        except Exception:
            pass
    spec = _story_spec(cid) or _db_spec(cid) or {}
    title = title or spec.get("title") or "The Wire"
    if rank is None:
        rank = spec.get("rank")
    hero = hero or spec.get("hero")
    bg_im, bg_id = _bg_from_src(hero)
    if bg_im is None:
        # fall back to the Wire list hero, never a made-up event photograph
        bg_im = _open_bg("wire", "iss070e062746.webp")
        bg_id = bg_id or "wire:iss070e062746.webp"
    keyhash = _cache_key("story", cid, title, rank, bg_id)

    def build():
        return png_bytes(render(title, bg_im=bg_im, tagline=True, rank=rank))

    return _cached(keyhash, build)


ALIASES = {
    "index": "home", "": "home", "heatmap": "map", "heat-map": "map", "heat_map": "map",
    "tv": "streams", "tv-radio": "streams", "live-tv": "streams", "live-streams": "streams",
    "mesh-chat": "mesh", "mesh-guide": "mesh", "report-status": "home",
    "privacy-policy": "privacy", "terms": "tos", "terms-of-service": "tos",
    "cookie-policy": "cookies", "do-not-sell": "privacy-choices",
}

def image_url(key="home", story_id=None, title=None, rank=None):
    if story_id:
        path = f"{SITE}/og/wire/{story_id}.png"
        h = VERSION
        if title is not None or rank is not None:
            h = VERSION + "-" + hashlib.sha1(f"{title}|{rank}".encode("utf-8", "replace")).hexdigest()[:8]
        return f"{path}?v={h}"
    key = ALIASES.get((key or "home").lower(), (key or "home").lower())
    if key not in PAGES:
        key = "home"
    return f"{SITE}/og/{key}.png?v={VERSION}"


def attr(s):
    """Escape a string for an HTML attribute exactly once.

    Callers may pass plain text ('Live TV & Radio') or already-escaped text
    ('Live TV &amp; Radio'). Social crawlers must see a single &amp; so the
    decoded title and description read as '&', never a literal '&amp;'.
    """
    return html.escape(html.unescape(str(s if s is not None else "")), quote=True)


def tags(*, title, desc, url, image=None, key=None, story_id=None, rank=None, og_type="website"):
    """Open Graph + Twitter meta tags. image wins; otherwise built from key / story_id."""
    E = attr
    if story_id:
        try:   # build the story's share card now, so it is ready before the first crawler or share
            import share_card; share_card.warm(str(story_id))
        except Exception:
            pass
    img = image or image_url(key or "home", story_id=story_id, title=title, rank=rank)
    img_h = 675 if (story_id or "/og/share/" in (image or "")) else 630   # story and share cards are 1200x675
    t = title if title else BRAND
    d = desc or TAGLINE
    return (
        f'<meta property="og:type" content="{E(og_type)}">'
        f'<meta property="og:site_name" content="{BRAND}">'
        f'<meta property="og:title" content="{E(t)}">'
        f'<meta property="og:description" content="{E(d)}">'
        f'<meta property="og:url" content="{E(url)}">'
        f'<meta property="og:image" content="{E(img)}">'
        f'<meta property="og:image:width" content="1200">'
        f'<meta property="og:image:height" content="{img_h}">'
        f'<meta property="og:image:alt" content="{E(t)}">'
        f'<meta name="twitter:card" content="summary_large_image">'
        f'<meta name="twitter:image" content="{E(img)}">'
        f'<meta name="twitter:image:alt" content="{E(t)}">'
        f'<meta name="twitter:site" content="{HANDLE}">'
        f'<meta name="twitter:title" content="{E(t)}">'
        f'<meta name="twitter:description" content="{E(d)}">'
    )


def share_page(seg):
    """Minimal 200 HTML for social crawlers hitting a dashboard-tab path like /solar."""
    spec = page_spec(seg) or {}
    title = spec.get("title") or f"{_strip_emoji(seg).title()} | {BRAND}"
    desc = spec.get("desc") or "Global threat monitoring: independent, sourced early-warning signals. Not official alerts."
    path = spec.get("path") or f"/{seg}"
    url = SITE + path
    img_key = seg if seg in PAGES else "live"
    dest = "/live#" + seg
    E = attr
    meta = tags(title=title, desc=desc, url=url, key=img_key, og_type="website")
    # Nov 21 (Matt pt1687u): unlisted tab hubs stay reachable but are not indexed
    robots = '<meta name="robots" content="noindex,nofollow">' if seg in ("streams", "trends", "broadcasts", "radio", "intel", "ranked") else ""
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        f"<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>{E(title)}</title><meta name=\"description\" content=\"{E(desc)}\">"
        f"<link rel=\"canonical\" href=\"{E(url)}\">{robots}{meta}"
        f"<script>location.replace({dest!r})</script>"
        f"</head><body style=\"background:#05060a;color:#ECEEF5;font:15px/1.5 Inter,system-ui,sans-serif;padding:48px 24px\">"
        f"<p><a href=\"{E(dest)}\" style=\"color:#fff\">{E(spec.get('card') or title)}</a></p>"
        f"<p style=\"color:#9aa0aa\">{E(WORDMARK)} · {E(TAGLINE)}</p>"
        "</body></html>"
    ).encode("utf-8")


_SAFE = None


def _safe_png():
    """In-memory last-resort 1200x630 PNG so a crawler never gets HTML, a redirect, or an empty body."""
    global _SAFE
    if _SAFE and len(_SAFE) > 1000:
        return _SAFE
    try:
        _SAFE = png_bytes(render(TAGLINE, bg_im=None, tagline=True))
    except Exception:
        im = Image.new("RGB", (W, H), BG)
        buf = io.BytesIO(); im.save(buf, format="PNG", compress_level=3)
        _SAFE = buf.getvalue()
    return _SAFE


def _valid_png(b):
    return isinstance(b, (bytes, bytearray)) and len(b) > 1000 and b[:8] == b"\x89PNG\r\n\x1a\n"


def handle_get(path, qs=None):
    """Addon entry: /og/<page>.png and /og/wire/<id>.png. Always a 200 image/png for those paths (never a redirect, HTML, or 5xx)."""
    try:
        p = (path or "").split("?")[0].rstrip("/")
        m = re.fullmatch(r"/og/wire/([0-9a-f]{16})(?:\.png)?", p, re.I)
        if m:
            try:
                b = png_for_story_fast(m.group(1).lower())
            except Exception:
                b = None
            return 200, b if _valid_png(b) else _safe_png(), "image/png"
        m = re.fullmatch(r"/og/([a-z0-9-]{1,40})(?:\.png)?", p)
        if m:
            key = m.group(1).lower()
            if key in ("index",):
                key = "home"
            if key == "heatmap" or key == "heat-map":
                key = "map"
            if key == "tv" or key == "tv-radio" or key == "live-tv":
                key = "streams"
            try:
                b = png_for(key if key in PAGES or key == "home" else "home")
            except Exception:
                b = None
            return 200, b if _valid_png(b) else _safe_png(), "image/png"
        return 404, {"error": "not found"}
    except Exception:
        return 200, _safe_png(), "image/png"


def write_legacy_static():
    """Replace the old one-size card so leftover links at least show the new home design."""
    data = png_for("home")
    out = BASE / "static" / "pwa"
    for name in ("icon-og-v2-1200x630.png", "icon-og-1200x630.png"):
        (out / name).write_bytes(data)
    return data
