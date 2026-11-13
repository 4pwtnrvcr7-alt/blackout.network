"""People in the news: story-page people drawers, /people/<slug> profiles and same-origin images (t1351u, Nov 13 2026).

Data: the "people" block of data/story_reports.json, built on the box by tools/story_reports/people_engine.py (Wikidata for
structured facts, English Wikipedia for short section excerpts, Wikimedia Commons for freely licensed photos; every fact keeps
its source link). Nothing here calls an LLM; nothing here invents text.

Routes
  /people                     index of profiles, most mentioned on our board first
  /people/<slug>              full profile: photos, early life, family, education, career, ideology and goals, key actions,
                              controversies, supporters and critics, timeline, every BLACKOUT.NETWORK story linked to them
  /api/people/img/<slug>.webp committed 400x400 headshot (static/img/people), else the portrait through the media cache
  /api/people/people.js       drawer motion for the story-page strip (same easing and timing as the homepage drawers)
  /api/media/<id>.<ext>       same-origin copy of a story or profile image. Only URLs listed in the signed story_reports.json
                              push are fetched (allowlist by id), https only, public hosts only, images only, <= 4 MB,
                              cached on disk 14 days, at most 40 upstream fetches a minute.
Kill switches (Render env): BN_PEOPLE=0 hides the strip and the /people pages (story pages fall back to the old name chips);
BN_MEDIA_PROXY=0 serves story images from their original URLs again (the pre-Nov 13 behaviour).
Read-only: blackout.db only as file:blackout.db?mode=ro (archive story lookup); never touches scanner.py, scoring, push.py,
jets.py, config.json or aviation_watch.py.
"""
import hashlib, html, ipaddress, json, os, re, socket, sqlite3, threading, time, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "blackout.db")
IMG_DIR = os.path.join(BASE, "static", "img", "people")
CACHE_DIR = os.path.join(BASE, "logs", "media_cache")
SITE = "https://blackout.network"
UA = "BLACKOUT.NETWORK-media/1.0 (https://blackout.network; hello@blackout.network)"
ET = ZoneInfo("America/New_York"); UTC = timezone.utc
E = lambda s: html.escape(str(s if s is not None else ""), quote=True)
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,80}$")
MID = re.compile(r"^([0-9a-f]{20})\.(jpg|png|webp|gif)$")
MAX_BYTES, TTL, NEG_TTL, MAX_FILES, RATE = 4_000_000, 14 * 86400, 600, 5000, 40
CT = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}

def on(): return os.environ.get("BN_PEOPLE", "1") != "0"
def proxy_on(): return os.environ.get("BN_MEDIA_PROXY", "1") != "0"

# ------------------------------------------------------------------ data
_D = {"mt": None, "v": {}, "allow": {}, "rx": []}
def _reports():
    try:
        import story_report as SR
        return SR.reports() or {}, SR.reports_mtime()
    except Exception:
        return {}, 0

def block():
    R, mt = _reports()
    if _D["mt"] != mt:
        v = R.get("people") if isinstance(R.get("people"), dict) else {}
        allow = {}
        def add(u):
            if isinstance(u, str) and u.startswith("https://"): allow[mid(u)] = u
        for lst in (R.get("images") or {}).values():
            for i in lst or []: add((i or {}).get("src"))
        for lst in (R.get("shares") or {}).values():
            for i in lst or []: add((i or {}).get("src"))
        for i in (v.get("lead") or {}).values(): add((i or {}).get("src"))
        for i in (v.get("places") or {}).values(): add((i or {}).get("src"))
        rx = []
        for slug, p in (v.get("profiles") or {}).items():
            po = p.get("portrait") or {}
            add(po.get("src")); add(po.get("avatar_src"))
            for g in p.get("gallery") or []: add(g.get("src"))
            try: rx.append((slug, re.compile(p.get("rx") or (r"\b" + re.escape(p.get("name") or "~~") + r"\b"))))
            except re.error: pass
        _D.update(mt=mt, v=v, allow=allow, rx=rx)
    return _D["v"]

def profiles(): return block().get("profiles") or {}

def mid(u):
    ext = (urllib.parse.urlsplit(u).path.rsplit(".", 1)[-1] or "").lower()
    ext = {"jpeg": "jpg"}.get(ext, ext)
    if ext not in ("jpg", "png", "webp", "gif"): ext = "jpg"
    return hashlib.sha1(u.encode()).hexdigest()[:20] + "." + ext

def media_url(u):
    """Same-origin URL for an allowlisted image, else the original URL (proxy off or not in the signed data)."""
    if not proxy_on() or not isinstance(u, str) or not u.startswith("https://"): return u
    block(); m = mid(u)
    return f"/api/media/{m}" if m in _D["allow"] else u

def _fb(src):
    """Original-URL fallback for a proxied <img>: if the same-origin copy fails, the browser loads the Commons file once."""
    loc = media_url(src)
    if not src or loc == src: return ""
    return f' data-o="{E(src)}" onerror="if(this.dataset.o){{this.onerror=null;this.src=this.dataset.o}}"'

def _short(t, n):
    t = re.sub(r"\s+", " ", str(t or "")).strip()
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0].rstrip(",;:([") + "…"

def avatar(p):
    s = p.get("slug") or ""
    if os.path.isfile(os.path.join(IMG_DIR, s + ".webp")): return f"/api/people/img/{s}.webp"
    po = p.get("portrait") or {}
    u = po.get("avatar_src") or po.get("src")
    return media_url(u) if u else ""

# ------------------------------------------------------------------ media cache (same-origin copies)
_lock = threading.Lock(); _rate = []; _neg = {}
def _public_host(h):
    if os.environ.get("BN_MEDIA_TEST_ALLOW_PRIVATE") == "1": return True   # local sandbox tests only (the box resolves through a 198.18/15 egress proxy)
    try:
        for fam, _, _, _, sa in socket.getaddrinfo(h, 443, proto=socket.IPPROTO_TCP):
            ip = ipaddress.ip_address(sa[0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified: return False
        return True
    except Exception:
        return False

def _prune():
    try:
        fs = sorted((os.path.getmtime(os.path.join(CACHE_DIR, f)), f) for f in os.listdir(CACHE_DIR) if not f.endswith(".ct"))
        for _, f in fs[:max(0, len(fs) - MAX_FILES)]:
            for x in (f, f + ".ct"):
                try: os.remove(os.path.join(CACHE_DIR, x))
                except OSError: pass
    except Exception: pass

def media_bytes(name):
    """(bytes, content-type) for /api/media/<id>.<ext>, or None."""
    if not MID.match(name or ""): return None
    block(); u = _D["allow"].get(name)
    cp = os.path.join(CACHE_DIR, name)
    def cached(stale_ok):
        try:
            if os.path.exists(cp) and (stale_ok or time.time() - os.path.getmtime(cp) < TTL):
                with open(cp, "rb") as fh: b = fh.read()
                ct = open(cp + ".ct").read().strip() if os.path.exists(cp + ".ct") else "image/jpeg"
                return b, ct
        except Exception: pass
        return None
    hit = cached(False)
    if hit: return hit
    if not u: return cached(True)
    if time.time() - _neg.get(name, 0) < NEG_TTL: return cached(True)
    with _lock:
        t = time.time(); _rate[:] = [x for x in _rate if t - x < 60]
        if len(_rate) >= RATE: return cached(True)
        _rate.append(t)
    sp = urllib.parse.urlsplit(u)
    if sp.scheme != "https" or not sp.hostname or not _public_host(sp.hostname):
        _neg[name] = time.time(); return cached(True)
    try:
        req = urllib.request.Request(u, headers={"User-Agent": UA, "Accept": "image/avif,image/webp,image/jpeg,image/png,image/*;q=0.8"})
        with urllib.request.urlopen(req, timeout=12) as r:
            ct = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower(); b = r.read(MAX_BYTES + 1)
            final = r.geturl()
        if len(b) > MAX_BYTES or ct not in CT or not final.startswith("https://"): _neg[name] = time.time(); return cached(True)
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(cp + ".tmp", "wb") as fh: fh.write(b)
        os.replace(cp + ".tmp", cp)
        with open(cp + ".ct", "w") as fh: fh.write(ct)
        if len(_rate) == 1: _prune()
        return b, ct
    except Exception:
        _neg[name] = time.time(); return cached(True)

# ------------------------------------------------------------------ helpers
def _first_line(t, n=150):
    t = re.sub(r"\s+", " ", (t or "").split("\n")[0]).strip()
    try:
        import story_report as SR; t = SR.txt(t)
    except Exception: pass
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0].rstrip(" ,;:-") + "…"

def _et(iso):
    try: d = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except Exception: return ""
    if d.tzinfo is None: d = d.replace(tzinfo=UTC)
    return d.astimezone(ET).strftime("%b %-d, %Y")

def _sent(t, n=2):
    s = re.split(r"(?<=[.!?])\s+(?=[A-Z\"“(])", (t or "").strip())
    return " ".join(s[:n])

def wiki_link(p, sec=None):
    t = p.get("wiki_title") or p.get("name") or ""
    u = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(t.replace(" ", "_"))
    return u + ("#" + urllib.parse.quote(sec.replace(" ", "_")) if sec else "")

def people_for(cid, text=""):
    """Profiles for a story: the box's match list first, then a request-time match on the story text (archive pages)."""
    if not on(): return []
    b = block(); P = b.get("profiles") or {}
    slugs = list((b.get("story_people") or {}).get(cid) or [])
    if not slugs and text:
        hits = [(s, len(rx.findall(text))) for s, rx in _D["rx"]]
        slugs = [s for s, n in sorted(hits, key=lambda x: -x[1]) if n][:6]
    return [P[s] for s in slugs if s in P][:6]

_CR = {"mt": None, "rx": None}
def lead_for(cid, title="", loc="", text=""):
    """Credited lead photo for a story page with no image of its own: the box's pick, else (request time, for archive pages) the
    first named public figure's Commons portrait, else a Commons photo of the country or region in the headline or location.
    Captions say "file photo" so nobody reads them as pictures of the event."""
    if not on() or os.environ.get("BN_STORY_LEAD_FALLBACK", "1") == "0": return None
    b = block()
    hit = (b.get("lead") or {}).get(cid)
    if isinstance(hit, dict) and hit.get("src") and hit.get("kind") != "person": return hit
    def pos(p):
        m = re.search(p.get("rx") or "~~", title or "")
        return m.start() if m else 10 ** 6
    for p in sorted(people_for(cid, " ".join([title, text])), key=pos):
        po = p.get("portrait") or {}
        if po.get("src") and pos(p) < 10 ** 6:
            yr = (po.get("date") or "")[:4]
            return {"src": po["src"], "w": po.get("w") or 800, "h": po.get("h") or 1000, "kind": "person", "person": p["slug"], "alt": p.get("name"),
                    "caption": f'{p.get("name")}' + (f", {yr}" if yr.isdigit() else "") + ". File photo; not taken at this event.",
                    "credit": f'{po.get("author") or "Unknown author"} / Wikimedia Commons', "license": po.get("license") or "", "link": po.get("source") or ""}
    if isinstance(hit, dict) and hit.get("src"): return hit
    places, alias = b.get("places") or {}, b.get("country_alias") or {}
    if places and alias:
        if _CR["mt"] != _D["mt"]:
            ks = sorted(alias, key=len, reverse=True)
            _CR.update(mt=_D["mt"], rx=re.compile(r"\b(" + "|".join(re.escape(k) for k in ks) + r")\b", re.I) if ks else None)
        rx = _CR["rx"]
        for t in (title, loc):
            m = rx.search(t or "") if rx else None
            if m:
                v = places.get(alias.get(m.group(1).lower(), ""))
                if v and v.get("src"): return v
    return None

def facts(p):
    out = []
    if p.get("role"): out.append(("Role", p["role"]))
    if p.get("born"): out.append(("Born", p["born"] + (f", {p['born_in']}" if p.get("born_in") else "")))
    if p.get("died"): out.append(("Died", p["died"]))
    if p.get("party"): out.append(("Party", p["party"]))
    if p.get("ideology"): out.append(("Ideology", ", ".join(p["ideology"][:3])))
    elif p.get("occupations"): out.append(("Work", ", ".join(p["occupations"][:3])))
    return out

def credit(po, short=False):
    if not po: return ""
    lic = po.get("license") or ""
    lu = po.get("license_url") or ""
    lic_h = f'<a href="{E(lu)}" target="_blank" rel="noopener">{E(lic)}</a>' if lu.startswith("http") else E(lic)
    return (f'Photo: {E(po.get("author") or "Unknown author")} / Wikimedia Commons, {lic_h}. '
            f'<a href="{E(po.get("source") or "")}" target="_blank" rel="noopener">{"Source" if short else "File page"}</a>')

# ------------------------------------------------------------------ story-page strip (drawers)
def strip_html(cid, text=""):
    def pos(p):
        try: m = re.search(p.get("rx") or "~~", text or "")
        except re.error: m = None
        return m.start() if m else 10 ** 6
    ps = sorted(people_for(cid, text), key=pos)   # headline order: the person named first leads
    if not ps: return ""
    cards = []
    for i, p in enumerate(ps):
        did = f"pp_{cid[:8]}_{i}"; av = avatar(p)
        img = (f'<img class="pp-av" src="{E(av)}" alt="" width="56" height="56" loading="lazy" decoding="async">' if av
               else f'<span class="pp-av pp-ini" aria-hidden="true">{E("".join(w[0] for w in (p.get("name") or "?").split()[:2]))}</span>')
        fl = "".join(f'<div><dt>{E(k)}</dt><dd>{E(v)}</dd></div>' for k, v in facts(p))
        cards.append(
            f'<div class="pp-card"><button type="button" class="pp-h" aria-expanded="false" aria-controls="{did}">{img}'
            f'<span class="pp-t"><span class="pp-n">{E(p.get("name"))}</span><span class="pp-r">{E(p.get("role") or p.get("description") or "")}</span></span>'
            f'<span class="pp-chev" aria-hidden="true"></span></button>'
            f'<div class="pp-x" id="{did}" role="region" aria-label="About {E(p.get("name"))}" hidden><div class="pp-xi">'
            + (f'<dl class="pp-dl">{fl}</dl>' if fl else "")
            + (f'<p class="pp-bio">{E(_sent(p.get("summary"), 2))} <a class="pp-src" href="{E(wiki_link(p))}" target="_blank" rel="noopener">Wikipedia</a></p>' if p.get("summary") else "")
            + f'<a class="pp-btn" href="/people/{E(p["slug"])}">Full profile: {E(p.get("name"))}<span aria-hidden="true"> →</span></a>'
            + (f'<p class="pp-cr">{credit(p.get("portrait"), True)}</p>' if p.get("portrait") and av else "")
            + '</div></div></div>')
    return (f'<style>{STRIP_CSS}</style><section class="pp-strip" aria-labelledby="pp_h_{cid[:8]}"><h2 class="pp-k" id="pp_h_{cid[:8]}">'
            f'<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="9" cy="8" r="3.2"/><path d="M3.5 19c.8-3.2 3-5 5.5-5s4.7 1.8 5.5 5"/><circle cx="17" cy="9" r="2.4"/><path d="M15.5 14.2c2.3-.4 4.3 1 5 3.8"/></svg>'
            f'People in this story</h2><div class="pp-list">{"".join(cards)}</div>'
            '<p class="pp-note">Neutral reference profiles built from Wikipedia and Wikidata. Tap a name for a short bio.</p></section>'
            '<script src="/api/people/people.js" defer></script>')

STRIP_CSS = """
.pp-strip{--pp-y:var(--sr-y,var(--a-y,#FFC21A));--pp-ink:var(--sr-ink,var(--a-ink,#e6e9ee));--pp-ink2:var(--sr-ink2,var(--a-ink2,#D2D2D7));--pp-mu:var(--sr-mu,var(--a-mu,#8a94a3));
 --pp-sf:var(--sr-sf,var(--a-sf,#16181C));--pp-ln:var(--sr-ln,var(--a-ln,#2A2D33));--pp-drw:cubic-bezier(.65,0,.35,1);margin:18px 0 22px}
html[data-theme="light"] .pp-strip{--pp-y:#C97B00}
.pp-k{display:flex;align-items:center;gap:8px;font:700 13px/1.2 Inter,system-ui,sans-serif!important;letter-spacing:.09em!important;text-transform:uppercase;color:var(--pp-y)!important;-webkit-text-fill-color:var(--pp-y);margin:0 0 10px!important}
.pp-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px;align-items:start}
.pp-card{background:var(--pp-sf);border-radius:16px;box-shadow:0 0 0 1px var(--pp-ln);overflow:hidden}
.pp-h{all:unset;box-sizing:border-box;display:flex;align-items:center;gap:12px;width:100%;min-height:72px;padding:10px 14px;cursor:pointer;color:var(--pp-ink)}
.pp-h:focus-visible{outline:2px solid var(--pp-y);outline-offset:-3px;border-radius:16px}
.pp-av{flex:none;width:56px;height:56px;border-radius:50%;object-fit:cover;object-position:50% 22%;background:#2a2d33;box-shadow:0 0 0 2px var(--pp-ln)}
.pp-ini{display:flex;align-items:center;justify-content:center;font:700 18px/1 Inter,system-ui,sans-serif;color:var(--pp-ink2)}
.pp-t{display:flex;flex-direction:column;gap:3px;min-width:0;flex:1}
.pp-n{font:650 16px/1.25 Inter,system-ui,sans-serif;color:var(--pp-ink)}
.pp-r{font-size:13.5px;line-height:1.35;color:var(--pp-mu);overflow:hidden;text-overflow:ellipsis;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.pp-chev{flex:none;width:28px;height:28px;border-radius:50%;position:relative;transition:background .2s}
.pp-chev::before{content:"";position:absolute;left:10px;top:8px;width:7px;height:7px;border-right:2px solid var(--pp-mu);border-bottom:2px solid var(--pp-mu);transform:rotate(45deg);transition:transform .38s var(--pp-drw)}
.pp-card.pp-open .pp-chev::before{transform:translate(0,4px) rotate(-135deg)}
@media (hover:hover){.pp-h:hover .pp-chev{background:var(--pp-ln)}}
.pp-x{box-sizing:border-box;border-top:1px solid var(--pp-ln)}
.pp-x.pp-dz{overflow:hidden;will-change:height;transition:height .38s var(--pp-drw),opacity .3s var(--pp-drw),border-color .38s var(--pp-drw)}
.pp-x.pp-dz>*{transition:transform .38s var(--pp-drw)}
.pp-x.pp-dz0{opacity:0;border-top-color:transparent}.pp-x.pp-dz0>*{transform:translateY(-10px)}
.pp-xi{padding:12px 16px 16px;font-size:14.5px;line-height:1.55;color:var(--pp-ink2)}
.pp-dl{display:grid;grid-template-columns:auto 1fr;gap:6px 14px;margin:0 0 10px}.pp-dl div{display:contents}
.pp-dl dt{font:600 12px/1.6 Inter,system-ui,sans-serif;letter-spacing:.05em;text-transform:uppercase;color:var(--pp-mu)}.pp-dl dd{margin:0;color:var(--pp-ink)}
.pp-bio{margin:0 0 12px}.pp-src{font-size:13px;color:var(--pp-mu)!important}
.pp-btn{display:inline-flex;align-items:center;gap:6px;min-height:40px;padding:0 16px;border-radius:999px;background:var(--pp-y);color:#111!important;-webkit-text-fill-color:#111;font:650 14px/1 Inter,system-ui,sans-serif;text-decoration:none!important}
.pp-cr{margin:10px 0 0;font-size:12px;line-height:1.45;color:var(--pp-mu)}.pp-cr a{color:var(--pp-mu)!important}
.pp-note{margin:8px 2px 0;font-size:12.5px;color:var(--pp-mu)}
@media(max-width:600px){.pp-list{grid-template-columns:1fr}}
"""

JS = r"""(function(){
 // Story-page people drawers (t1351u). Same motion as the homepage drawers: height slides with ease-in-out over 380 ms while the
 // content fades and settles; a second tap reverses from the current height; instant under prefers-reduced-motion.
 var MS=380,RM=window.matchMedia?window.matchMedia("(prefers-reduced-motion: reduce)"):null;
 function done(p,g,open){if(p._g!==g)return;clearTimeout(p._t);p.classList.remove("pp-dz","pp-dz0");p.style.height="";if(!open)p.hidden=true}
 function drawer(p,open){var g=(p._g||0)+1;p._g=g;clearTimeout(p._t);
  if(RM&&RM.matches){p.classList.remove("pp-dz","pp-dz0");p.style.height="";p.hidden=!open;return}
  var wasHidden=p.hidden,cur=wasHidden?0:p.getBoundingClientRect().height;
  p.hidden=false;p.classList.remove("pp-dz","pp-dz0");p.style.height="";
  var to=open?p.getBoundingClientRect().height:0;
  if(Math.abs(to-cur)<1){done(p,g,open);return}
  if(wasHidden)p.classList.add("pp-dz0");p.style.height=cur+"px";void p.offsetHeight;
  p.classList.add("pp-dz");void p.offsetHeight;p.classList.toggle("pp-dz0",!open);p.style.height=to+"px";
  var end=function(e){if(e&&(e.target!==p||e.propertyName!=="height"))return;p.removeEventListener("transitionend",end);done(p,g,open)};
  p.addEventListener("transitionend",end);p._t=setTimeout(end,MS+120)}
 function toggle(c,open){var b=c.querySelector(".pp-h"),p=c.querySelector(".pp-x");if(!b||!p)return;
  b.setAttribute("aria-expanded",open?"true":"false");c.classList.toggle("pp-open",open);drawer(p,open)}
 function init(){document.querySelectorAll(".pp-strip").forEach(function(s){if(s._pp)return;s._pp=1;
  s.addEventListener("click",function(e){var b=e.target.closest(".pp-h");if(!b||!s.contains(b))return;var c=b.closest(".pp-card"),open=!c.classList.contains("pp-open");
   s.querySelectorAll(".pp-card.pp-open").forEach(function(o){if(o!==c)toggle(o,false)});toggle(c,open)})});
  document.querySelectorAll(".pf-acc").forEach(function(a){if(a._pp)return;a._pp=1;var b=a.querySelector(".pf-acc-h");if(!b)return;
   b.addEventListener("click",function(){var open=!a.classList.contains("pp-open");b.setAttribute("aria-expanded",open?"true":"false");a.classList.toggle("pp-open",open);drawer(a.querySelector(".pp-x"),open)})})}
 if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init);else init();
})();"""

# ------------------------------------------------------------------ archive stories from the live DB (read-only)
_AC = {}
def archive_stories(p, limit=60):
    key = p.get("slug"); hit = _AC.get(key)
    if hit and time.time() - hit[0] < 600: return hit[1]
    out = []
    try:
        rx = re.compile(p.get("rx") or (r"\b" + re.escape(p.get("name") or "~~") + r"\b"))
        words = [w for w in re.findall(r"[A-Za-zÀ-ɏ]{4,}", p.get("name") or "")][-1:]
        if words:
            c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=5)
            try:
                rows = c.execute("SELECT cluster_id, title, COALESCE(updated, first_seen), rank FROM clusters WHERE title LIKE ? "
                                 "ORDER BY COALESCE(updated, first_seen) DESC LIMIT 400", (f"%{words[0]}%",)).fetchall()
            finally: c.close()
            for cid, title, t, rank in rows:
                if rx.search(title or ""): out.append({"cid": cid, "title": title or "", "t": t or "", "rank": rank or 0})
                if len(out) >= limit: break
    except Exception:
        out = []
    _AC[key] = (time.time(), out)
    return out

def stories(p):
    seen, out = set(), []
    for s in sorted((p.get("stories") or []) + archive_stories(p), key=lambda x: str(x.get("t") or ""), reverse=True):
        cid = s.get("cid") or ""
        if not re.fullmatch(r"[0-9a-f]{16}", cid) or cid in seen: continue
        t = _first_line(s.get("title"))
        if not t: continue
        seen.add(cid); out.append(dict(s, title=t))
    return out[:200]

# ------------------------------------------------------------------ pages
def _page(title, desc, body, path, image=None, ld=None, noindex=False):
    try:
        import site_page as S
        return S.page(title, desc, body, path, "figures", noindex=noindex, image=image, jsonld=ld)
    except Exception:
        return (f"<!doctype html><html lang=en><head><meta charset=utf-8><title>{E(title)}</title></head><body>{body}</body></html>").encode()

def src_line(p, sec=None, wd=False):
    if wd: return f'<p class="pf-s">Source: <a href="{E(p.get("wikidata_url"))}" target="_blank" rel="noopener">Wikidata {E(p.get("qid"))}</a> (CC0)</p>'
    return f'<p class="pf-s">Source: <a href="{E(wiki_link(p, sec))}" target="_blank" rel="noopener">Wikipedia, “{E(sec)}”</a> (CC BY-SA 4.0)</p>' if sec else ""

def _quote(x, p): return f'<p>{E(x["text"])}</p>' + src_line(p, x.get("section"))

def _span(a, b): return (a or "?") + (f" to {b}" if b else (" to present" if a else ""))

def profile_page(slug):
    p = profiles().get(slug)
    if not p: return 404, _page("Profile not found", "No BLACKOUT.NETWORK profile with that name.", '<h1 class="t">Profile not found</h1><p><a href="/people">All people in the news</a></p>', f"/people/{slug}", noindex=True)
    nm = p.get("name") or slug; av = avatar(p); po = p.get("portrait") or {}
    nav, secs = [], []
    def sec(key, title, body, acc=False):
        if not body: return
        nav.append((key, title))
        if acc:
            secs.append(f'<section class="pf-sec pf-acc" id="{key}"><h2 class="pf-h"><button type="button" class="pf-acc-h" aria-expanded="false" aria-controls="{key}_x">{E(title)}<span class="pp-chev" aria-hidden="true"></span></button></h2>'
                        f'<div class="pp-x" id="{key}_x" hidden><div class="pp-xi">{body}</div></div></section>')
        else:
            secs.append(f'<section class="pf-sec" id="{key}"><h2 class="pf-h">{E(title)}</h2>{body}</section>')
    S = p.get("sections") or {}
    # overview facts
    f = facts(p)
    if p.get("citizenship"): f.append(("Citizenship", ", ".join(p["citizenship"])))
    if p.get("occupations"): f.append(("Occupations", ", ".join(p["occupations"][:5])))
    mil = p.get("military") or {}
    if mil.get("branch"): f.append(("Military", ", ".join(mil["branch"]) + (f" ({', '.join(mil.get('rank') or [])})" if mil.get("rank") else "")))
    if p.get("religion"): f.append(("Religion", ", ".join(p["religion"])))
    # photos
    gal = p.get("gallery") or []
    if gal:
        figs = "".join(f'<figure class="pf-fig"><a href="{E(g.get("source"))}" target="_blank" rel="noopener"><img src="{E(media_url(g.get("src")))}"{_fb(g.get("src"))} alt="{E(_short(g.get("desc") or nm, 140))}" width="{E(g.get("w") or 960)}" height="{E(g.get("h") or 640)}" loading="lazy" decoding="async" referrerpolicy="no-referrer"></a>'
                       f'<figcaption>{E(_short(g.get("desc") or "", 140))} <span class="pf-cr">{credit(g)}</span></figcaption></figure>' for g in gal)
        sec("photos", "Photos", f'<div class="pf-gal">{figs}</div><p class="pf-s">Freely licensed photos from Wikimedia Commons used in the Wikipedia article about {E(nm)}. Each caption names the photographer and license.</p>')
    # early life + birth
    el = []
    if p.get("born"): el.append(f'<p class="pf-lede"><b>Born</b> {E(p["born"])}' + (f' in {E(p["born_in"])}' if p.get("born_in") else "") + '.</p>' + src_line(p, wd=True))
    if S.get("early"): el.append(_quote(S["early"], p))
    sec("early", "Early life", "".join(el))
    fam = p.get("family") or {}; fl = []
    if fam.get("spouses"): fl.append("<li><b>Spouse" + ("s" if len(fam["spouses"]) > 1 else "") + ":</b> " + "; ".join(E(s["name"]) + (f' ({E(_span(s.get("from"), s.get("to")))})' if s.get("from") else "") for s in fam["spouses"]) + "</li>")
    if fam.get("parents"): fl.append("<li><b>Parents:</b> " + ", ".join(E(x) for x in fam["parents"]) + "</li>")
    if fam.get("children"): fl.append(f"<li><b>Children:</b> {int(fam['children'])}</li>")
    if fam.get("relatives"): fl.append("<li><b>Notable relatives:</b> " + ", ".join(E(x) for x in fam["relatives"]) + "</li>")
    fb = (f'<ul class="pf-ul">{"".join(fl)}</ul>' + src_line(p, wd=True) if fl else "") + (_quote(S["family"], p) if S.get("family") else "")
    sec("family", "Family", fb + ('<p class="pf-s">Public information only.</p>' if fb else ""))
    ed = p.get("education") or []
    eb = (('<ul class="pf-ul">' + "".join(f'<li>{E(e["name"])}' + (f' <span class="pf-m">({E(e["to"])})</span>' if e.get("to") else "") + "</li>" for e in ed) + "</ul>" + src_line(p, wd=True)) if ed else "") + (_quote(S["education"], p) if S.get("education") else "")
    sec("education", "Education", eb)
    pos = p.get("positions") or []; emp = p.get("employers") or []
    cb = ""
    if pos: cb += '<h3 class="pf-h3">Offices and positions</h3><ul class="pf-ul">' + "".join(f'<li><b>{E(x["title"])}</b> <span class="pf-m">{E(_span(x.get("from"), x.get("to")))}</span></li>' for x in pos) + "</ul>"
    if emp: cb += '<h3 class="pf-h3">Employers</h3><ul class="pf-ul">' + "".join(f'<li>{E(x["name"])} <span class="pf-m">{E(_span(x.get("from"), x.get("to")) if x.get("from") else "")}</span></li>' for x in emp) + "</ul>"
    if pos or emp: cb += src_line(p, wd=True)
    if S.get("career"): cb += _quote(S["career"], p)
    sec("career", "Career and jobs", cb)
    ib = ""
    if p.get("parties"): ib += '<p><b>Party:</b> ' + "; ".join(E(x["name"]) + (f' ({E(_span(x.get("from"), x.get("to")))})' if x.get("from") else "") for x in p["parties"]) + "</p>"
    if p.get("ideology"): ib += '<p><b>Ideology (Wikidata, person or party):</b> ' + ", ".join(E(x) for x in p["ideology"]) + "</p>"
    if ib: ib += src_line(p, wd=True)
    if S.get("ideology"): ib += _quote(S["ideology"], p)
    if p.get("goals"): ib += '<h3 class="pf-h3">Stated goals and positions</h3>' + "".join(_quote(x, p) for x in p["goals"])
    sec("ideology", "Political ideology and goals", ib)
    if p.get("actions"): sec("actions", "Key actions", "".join(f'<h3 class="pf-h3">{E(x["section"])}</h3>' + _quote(x, p) for x in p["actions"]), acc=True)
    if p.get("controversies"):
        sec("controversies", "Scandals and controversies", '<p class="pf-s">As reported in the Wikipedia article and its cited sources. Allegations are not findings unless a court or official body says so.</p>'
            + "".join(f'<h3 class="pf-h3">{E(x["section"])}</h3>' + _quote(x, p) for x in p["controversies"]), acc=True)
    V = p.get("views") or {}
    if V.get("supporters") and V.get("critics"):
        vb = ('<div class="pf-two"><div><h3 class="pf-h3">What supporters say</h3>' + "".join(_quote(x, p) for x in V["supporters"]) + '</div>'
              '<div><h3 class="pf-h3">What critics say</h3>' + "".join(_quote(x, p) for x in V["critics"]) + '</div></div>')
        if S.get("image"): vb = _quote(S["image"], p) + vb
        sec("views", "Supporters and critics", vb)
    elif S.get("image"):
        sec("views", "Public image", _quote(S["image"], p))
    tl = p.get("timeline") or []
    if tl:
        sec("timeline", "How they rose: timeline", '<ol class="pf-tl">' + "".join(f'<li><time>{E(x["label"])}</time><p>{E(x["text"])}</p></li>' for x in tl) + "</ol>" + src_line(p, wd=True))
    st = stories(p)
    if st:
        now = datetime.now(UTC); li = []
        for s in st:
            try: d = datetime.fromisoformat(str(s.get("t")).replace("Z", "+00:00")); d = d if d.tzinfo else d.replace(tzinfo=UTC)
            except Exception: d = None
            arch = d is not None and now - d > timedelta(days=7)
            li.append(f'<li><a href="/wire/{E(s["cid"])}">{E(s["title"])}</a><span class="pf-m">{E(_et(s.get("t")))}' + (f' · rank {int(s["rank"])}/10' if s.get("rank") else "") + ('</span><span class="pf-tag">Archive</span>' if arch else "</span>") + "</li>")
        sec("stories", f"BLACKOUT.NETWORK stories ({len(st)})", f'<ol class="pf-st">{"".join(li)}</ol><p class="pf-s">Newest first. Stories older than a week are marked Archive.</p>')
    srcs = p.get("sources") or []
    sec("sources", "Sources", '<ul class="pf-ul">' + "".join(f'<li><a href="{E(x["url"])}" target="_blank" rel="noopener">{E(x["label"])}</a></li>' for x in srcs) + "</ul>"
        '<p class="pf-s">Facts in lists come from Wikidata (CC0). Quoted passages are short excerpts of the English Wikipedia article (CC BY-SA 4.0), each linked to its section, where the original citations are. BLACKOUT.NETWORK does not rank, score or rate people.</p>')
    hero_img = (f'<img class="pf-av" src="{E(av)}" alt="{E(nm)}" width="220" height="220" fetchpriority="high">' if av else "")
    hero = (f'<header class="pf-hero">{hero_img}<div class="pf-hb"><p class="crumb"><a href="/people">People in the news</a> › Profile</p><h1 class="t pf-name">{E(nm)}</h1>'
            f'<p class="pf-role">{E(p.get("role") or p.get("description") or "")}</p>'
            + (f'<dl class="pp-dl pf-dl">{"".join(f"<div><dt>{E(k)}</dt><dd>{E(v)}</dd></div>" for k, v in f)}</dl>' if f else "")
            + (f'<p class="pf-sum">{E(p.get("summary"))}</p>' + src_line(p, "") if p.get("summary") else "")
            + (f'<p class="pf-s">Summary: <a href="{E(wiki_link(p))}" target="_blank" rel="noopener">Wikipedia</a> (CC BY-SA 4.0)</p>' if p.get("summary") else "")
            + (f'<p class="pf-cr">{credit(po)}</p>' if po and av else "") + '</div></header>')
    jump = '<nav class="pf-nav" aria-label="On this page">' + "".join(f'<a href="#{k}">{E(t.split(" (")[0])}</a>' for k, t in nav) + "</nav>"
    body = f'<style>{STRIP_CSS}{PAGE_CSS}</style><article class="pf pp-strip">{hero}{jump}{"".join(secs)}</article><script src="/api/people/people.js" defer></script>'
    desc = (f"{nm}: {p.get('role') or p.get('description') or ''}. Neutral, sourced profile: early life, career, ideology, controversies, timeline and every BLACKOUT.NETWORK story about them.")[:300]
    ld = {"@context": "https://schema.org", "@type": "ProfilePage", "url": f"{SITE}/people/{slug}",
          "mainEntity": {"@type": "Person", "name": nm, "description": p.get("role") or p.get("description") or "", "sameAs": [wiki_link(p), p.get("wikidata_url")] + ([p["website"]] if p.get("website") else []),
                         **({"birthDate": p["born_iso"]} if p.get("born_iso") else {}), **({"image": SITE + av} if av.startswith("/") else {})}}
    return 200, _page(f"{nm}: profile", desc, body, f"/people/{slug}", image=(SITE + av) if av.startswith("/") else None, ld=ld)

def index_page():
    P = profiles(); top = [s for s in (block().get("top") or []) if s in P]
    rest = sorted((s for s in P if s not in top), key=lambda s: P[s].get("name") or s)
    cards = []
    for s in top + rest:
        p = P[s]; av = avatar(p); n = p.get("mentions_now") or 0
        cards.append(f'<a class="pf-card" href="/people/{E(s)}">' + (f'<img class="pp-av" src="{E(av)}" alt="" width="56" height="56" loading="lazy" decoding="async">' if av else "")
                     + f'<span class="pp-t"><span class="pp-n">{E(p.get("name"))}</span><span class="pp-r">{E(p.get("role") or p.get("description") or "")}</span>'
                     + (f'<span class="pf-m">In {n} current stor{"y" if n == 1 else "ies"}</span>' if n else "") + '</span></a>')
    body = (f'<style>{STRIP_CSS}{PAGE_CSS}</style><div class="pf pp-strip"><p class="crumb"><a href="/#wire">The Wire</a> › People</p><h1 class="t">People in the news</h1>'
            '<p class="dek">Public figures named in the stories BLACKOUT.NETWORK is tracking, most mentioned first. Each profile is neutral and sourced to Wikipedia and Wikidata.</p>'
            f'<div class="pf-grid">{"".join(cards) or "<p>No profiles yet.</p>"}</div></div>')
    return 200, _page("People in the news", "Neutral, sourced profiles of the public figures in BLACKOUT.NETWORK stories.", body, "/people")

PAGE_CSS = """
.pf{max-width:1040px;margin:0 auto}
.pf-hero{display:grid;grid-template-columns:220px minmax(0,1fr);gap:28px;align-items:start;margin:8px 0 18px}
.pf-av{width:220px;height:220px;border-radius:28px;object-fit:cover;object-position:50% 22%;background:#2a2d33;box-shadow:0 10px 40px rgba(0,0,0,.35)}
.pf-name{margin:4px 0 4px!important}.pf-role{font:600 17px/1.4 Inter,system-ui,sans-serif;color:var(--pp-y);margin:0 0 12px}
.pf-dl{margin:0 0 12px}.pf-sum{font-size:17px;line-height:1.6;color:var(--pp-ink);margin:0 0 6px}
.pf-s{font-size:12.5px;line-height:1.45;color:var(--pp-mu);margin:4px 0 12px}.pf-s a,.pf-cr a{color:var(--pp-mu)!important}
.pf-cr{font-size:12px;color:var(--pp-mu);margin:6px 0 0}
.pf-nav{position:sticky;top:64px;z-index:5;display:flex;gap:8px;overflow-x:auto;padding:10px 2px;margin:0 0 10px;background:var(--a-bg,var(--bg,#0b0c0e));scrollbar-width:none}
.pf-nav::-webkit-scrollbar{display:none}
.pf-nav a{flex:none;padding:8px 14px;border-radius:999px;box-shadow:0 0 0 1px var(--pp-ln);font:600 13px/1 Inter,system-ui,sans-serif;color:var(--pp-ink2)!important;text-decoration:none!important;white-space:nowrap}
.pf-nav a:hover{box-shadow:0 0 0 1px var(--pp-y);color:var(--pp-ink)!important}
.pf-sec{background:var(--pp-sf);border-radius:18px;box-shadow:0 0 0 1px var(--pp-ln);padding:18px 22px;margin:0 0 14px;scroll-margin-top:120px}
.pf-h{font:700 13px/1.2 Inter,system-ui,sans-serif!important;letter-spacing:.09em!important;text-transform:uppercase;color:var(--pp-y)!important;-webkit-text-fill-color:var(--pp-y);margin:0 0 12px!important}
.pf-sec p{font-size:16px;line-height:1.62;color:var(--pp-ink2);margin:0 0 6px}.pf-lede{color:var(--pp-ink)!important}
.pf-h3{font:650 15.5px/1.35 Inter,system-ui,sans-serif;color:var(--pp-ink);margin:16px 0 6px}
.pf-ul{margin:0 0 8px;padding-left:20px}.pf-ul li{font-size:15.5px;line-height:1.55;margin:0 0 5px;color:var(--pp-ink2)}.pf-m{color:var(--pp-mu);font-size:13.5px;margin-left:6px}
.pf-two{display:grid;grid-template-columns:1fr 1fr;gap:22px}
.pf-gal{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px}
.pf-fig{margin:0;background:rgba(127,127,127,.06);border-radius:14px;overflow:hidden}.pf-fig img{display:block;width:100%;height:200px;object-fit:cover}
.pf-fig figcaption{padding:8px 10px 10px;font-size:13px;line-height:1.4;color:var(--pp-ink2)}.pf-fig .pf-cr{display:block;margin-top:4px}
.pf-tl{list-style:none;margin:0;padding:0 0 0 18px;border-left:2px solid var(--pp-ln)}
.pf-tl li{position:relative;margin:0 0 14px;padding-left:10px}.pf-tl li::before{content:"";position:absolute;left:-25px;top:6px;width:10px;height:10px;border-radius:50%;background:var(--pp-y)}
.pf-tl time{font:650 13px/1.3 Inter,system-ui,sans-serif;color:var(--pp-y)}.pf-tl p{margin:2px 0 0!important}
.pf-st{margin:0;padding-left:22px}.pf-st li{margin:0 0 9px;font-size:15.5px;line-height:1.45}.pf-st .pf-m{display:inline-block}
.pf-tag{display:inline-block;margin-left:8px;padding:2px 8px;border-radius:999px;box-shadow:0 0 0 1px var(--pp-ln);font:600 11px/1.4 Inter,system-ui,sans-serif;letter-spacing:.06em;text-transform:uppercase;color:var(--pp-mu)}
.pf-acc .pf-h{margin:0!important}.pf-acc-h{all:unset;box-sizing:border-box;display:flex;align-items:center;justify-content:space-between;width:100%;min-height:36px;cursor:pointer}
.pf-acc .pp-x{border-top:0}.pf-acc .pp-xi{padding:6px 0 0}
.pf-acc.pp-open .pp-chev::before{transform:translate(0,4px) rotate(-135deg)}
.pf-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px;margin-top:14px}
.pf-card{display:flex;align-items:center;gap:12px;padding:12px 14px;background:var(--pp-sf);border-radius:16px;box-shadow:0 0 0 1px var(--pp-ln);text-decoration:none!important;color:var(--pp-ink)!important}
.pf-card:hover{box-shadow:0 0 0 1px var(--pp-y)}
@media(max-width:700px){.pf-hero{grid-template-columns:1fr;gap:16px}.pf-av{width:148px;height:148px;border-radius:24px}.pf-two{grid-template-columns:1fr}.pf-sec{padding:16px}.pf-nav{top:56px}.pf-gal{grid-template-columns:1fr 1fr}.pf-fig img{height:150px}}
"""

# ------------------------------------------------------------------ routing
def handle_get(path, qs=None):
    p = path.rstrip("/") or "/"
    if p.startswith("/api/media/"):
        r = media_bytes(p[len("/api/media/"):])
        return (200, r[0], r[1]) if r else (404, {"error": "not found"})
    if not on(): return 404, {"error": "not found"}
    if p == "/api/people/people.js": return 200, JS.encode(), "application/javascript"
    if p.startswith("/api/people/img/") and p.endswith(".webp"):
        s = p[len("/api/people/img/"):-5]
        if SLUG.match(s):
            f = os.path.join(IMG_DIR, s + ".webp")
            if os.path.isfile(f):
                with open(f, "rb") as fh: return 200, fh.read(), "image/webp"
        return 404, {"error": "not found"}
    if p == "/people": return (lambda r: (r[0], r[1], "text/html"))(index_page())
    m = re.match(r"^/people/([a-z0-9][a-z0-9-]{0,80})$", p)
    if m: return (lambda r: (r[0], r[1], "text/html"))(profile_page(m.group(1)))
    return 404, {"error": "not found"}
