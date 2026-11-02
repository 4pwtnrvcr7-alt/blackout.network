#!/usr/bin/env python3
"""blackout.network dashboard + scheduler (stdlib HTTP server)."""
import json, os, re, time, threading, secrets, hmac, sqlite3, traceback
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone, timedelta
import scanner
import push
import jets
import display_links

BASE = scanner.BASE
CONFIG = f"{BASE}/config.json"
NOTIFY = f"{BASE}/notify_settings.json"
PASSFILE = f"{BASE}/ADMIN_PASSCODE.txt"
PORT = int(os.environ.get("BLACKOUT_PORT", "8787"))
ALLOWED = [5, 10, 15, 20, 30, 45, 60, 90, 120, 180, 240, 300, 360]   # scan interval choices, 5 min to 6 h (t225)
REFRESH_COOLDOWN = 120   # manual scans: at most one per 2 minutes (t225)
wake = threading.Event()
jet_wake = threading.Event()
jet_state = {"running": False, "last": None}
state = {"last_scan": None, "last_result": None, "next_scan": None, "last_manual": 0, "scanning": False}
fails = {}   # ip -> [timestamps] of bad passcodes

def load_json(p, default):
    try:
        with open(p) as f: return {**default, **json.load(f)}
    except Exception: return dict(default)
def save_json(p, d, mode=0o644):
    tmp = p + ".tmp"
    with open(tmp, "w") as f: json.dump(d, f, indent=1)
    os.chmod(tmp, mode); os.replace(tmp, p)
def cfg(): return load_json(CONFIG, {"interval_minutes": 60, "push_min_rank": 7, "push_min_sources": 2})
NOTIFY_DEFAULT = {"phone": "", "channels": {"sms": False, "email": True, "app": True}, "updated": None}
def notify(): 
    d = load_json(NOTIFY, NOTIFY_DEFAULT); d["channels"] = {**NOTIFY_DEFAULT["channels"], **(d.get("channels") or {})}; return d
def passcode():
    if not os.path.exists(PASSFILE):
        fd = os.open(PASSFILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f: f.write(secrets.token_urlsafe(12) + "\n")
    os.chmod(PASSFILE, 0o600)
    return open(PASSFILE).read().strip()
def mask(phone): return f"***-***-{phone[-4:]}" if phone and len(phone) == 10 else ""
def norm_phone(s):
    d = re.sub(r"[\s().\-]", "", s or "")
    if d.startswith("+1"): d = d[2:]
    elif d.startswith("1") and len(d) == 11: d = d[1:]
    if not re.fullmatch(r"[2-9]\d{2}[2-9]\d{6}", d): return None
    return d
def public_settings():
    n = notify()
    return {"phone_masked": mask(n.get("phone")), "phone_saved": bool(n.get("phone")), "channels": n["channels"], "updated": n.get("updated"),
            "delivery_status": {"app": "active: delivered as a message in the Grok Bot chat by the hourly check",
                                "email": "not yet deliverable: no email sending mechanism configured",
                                "sms": "not yet deliverable: no SMS gateway configured"}}

def run_scan(trigger):
    state["scanning"] = True
    try:
        r = scanner.scan(trigger)
        if r.get("status") != "busy":
            state["last_scan"] = time.time(); state["last_result"] = r
            try: r["push"] = push.push_new()          # push hook runs after every completed scan
            except Exception as ex: r["push"] = {"status": "error", "error": str(ex)[:200]}
        return r
    finally:
        state["scanning"] = False

def scheduler():
    # first scan at startup if stale
    c = scanner.db(); last = c.execute("SELECT finished FROM scans ORDER BY id DESC LIMIT 1").fetchone(); c.close()
    if last:
        state["last_scan"] = scanner.parse_t(last[0]).timestamp()
    while True:
        iv = cfg()["interval_minutes"] * 60
        due = (state["last_scan"] or 0) + iv
        state["next_scan"] = due
        if time.time() >= due:
            try: run_scan("scheduled")
            except Exception: traceback.print_exc()
            continue
        wake.wait(timeout=min(60, max(1, due - time.time())))   # re-check config at least every 60s
        wake.clear()

def jet_loop():
    """Jet sampler: every min(jet_sample_minutes [default 5], interval_minutes). Writes only jets.db; never touches threat scoring."""
    while True:
        c = cfg(); st = jets.settings(c)
        jet_state["running"] = True
        try: jet_state["last"] = jets.run_pass(c)
        except Exception: traceback.print_exc()
        finally: jet_state["running"] = False
        jet_wake.wait(timeout=st["sample_minutes"] * 60); jet_wake.clear()

def q(sql, args=()):
    c = scanner.db()
    try: return [dict(r) for r in c.execute(sql, args)]
    finally: c.close()

def clusters_out(rows):
    for r in rows:
        r["families"] = json.loads(r["families"] or "[]"); r["links"] = json.loads(r["links"] or "[]")
    return rows

def api_state():
    cut = scanner.iso(scanner.now() - timedelta(days=7))
    main = clusters_out(q("SELECT * FROM clusters WHERE watchlist=0 AND COALESCE(event_time, first_seen)>=? ORDER BY score DESC, event_time DESC LIMIT 150", (cut,)))
    watch = clusters_out(q("SELECT * FROM clusters WHERE watchlist=1 AND COALESCE(event_time, first_seen)>=? ORDER BY score DESC, event_time DESC LIMIT 150", (cut,)))
    nwatch = q("SELECT COUNT(*) n FROM clusters WHERE watchlist=1")[0]["n"]
    vol = q("""SELECT substr(COALESCE(event_time, first_seen),1,10) d, category, COUNT(*) n FROM clusters
               WHERE COALESCE(event_time, first_seen)>=? GROUP BY d, category ORDER BY d""", (cut,))
    trend = q("""SELECT substr(COALESCE(event_time, first_seen),1,10) d, MAX(score) mx, ROUND(AVG(score),1) avg,
               SUM(score>=?) high FROM clusters WHERE COALESCE(event_time, first_seen)>=? AND watchlist=0 GROUP BY d ORDER BY d""", (scanner.HIGH, cut))
    geo = q("SELECT lat, lon, score, title, category, watchlist FROM clusters WHERE lat IS NOT NULL AND COALESCE(event_time, first_seen)>=?", (cut,))
    health = q("SELECT * FROM source_health ORDER BY ok DESC, name")
    scans = q("SELECT * FROM scans ORDER BY id DESC LIMIT 10")
    pub = ""
    try: pub = open(f"{BASE}/PUBLIC_URL.txt").read().strip()
    except Exception: pass
    return {"generated": scanner.iso(scanner.now()), "high_threshold": scanner.HIGH, "main": main, "watchlist": watch, "watchlist_count": nwatch,
            "volume": vol, "trend": trend, "geo": geo, "sources": health, "scans": scans,
            "interval_minutes": cfg()["interval_minutes"], "allowed_intervals": ALLOWED,
            "next_scan": scanner.iso(datetime.fromtimestamp(state["next_scan"], timezone.utc)) if state["next_scan"] else None,
            "scanning": state["scanning"], "settings": public_settings(), "public_url": pub}

# ---- add-on modules (Story Arcs, ...): separate files listed in addons.py, hot-reloaded on change ----
import importlib
_addon_mods = {}
_addon_lock = threading.Lock()
def _addon_mod(name):
    mt = os.path.getmtime(f"{BASE}/{name}.py")
    with _addon_lock:
        m = _addon_mods.get(name)
        if m is None or m[0] != mt:
            mod = importlib.reload(m[1]) if m else importlib.import_module(name)
            _addon_mods[name] = (mt, mod)
        return _addon_mods[name][1]
def addon_for(path):
    try: routes = _addon_mod("addons").ROUTES
    except Exception: traceback.print_exc(); return None
    for pre, name in routes.items():
        if path == pre or path.startswith(pre + "/"): return _addon_mod(name)
    return None

# "Report a problem" widget (reports.py): added to every HTML page that doesn't already load it (dashboard.html loads it itself).
_RW = b'<link rel="stylesheet" href="/api/report/app.css"><script src="/api/report/app.js" defer></script>'
# PWA / home-screen support + site title (pwa.py, static/pwa/): every full HTML page served through send() gets the manifest, icons,
# iOS/Android web-app meta tags and the install guide in its <head>, and the public title "BLACKOUT.NETWORK · Signal over noise.™" (Compliance format, TM never R) (tagline Nov 1; never shown without the brand).
SITE_TITLE = "BLACKOUT.NETWORK · Signal over noise.™".encode("utf-8")
# Light/dark theme (t323): set data-theme on <html> before first paint (saved choice, else the OS setting) + preload the self-hosted fonts.
THEME_HEAD = (b'<script>(function(){var d=document.documentElement,t;try{t=localStorage.getItem("bn_theme")}catch(e){}'
              b'if(t!=="light"&&t!=="dark")t=window.matchMedia&&matchMedia("(prefers-color-scheme: light)").matches?"light":"dark";'
              b'd.setAttribute("data-theme",t);d.style.colorScheme=t;var m=document.querySelector(\'meta[name="theme-color"]\');if(m)m.content=t=="light"?"#f6f7f9":"#0b0d10"})()</script>'
              b'<link rel="icon" type="image/svg+xml" href="/img/favicon.svg">'
              b'<link rel="preload" href="/fonts/montserrat-latin-wght-normal.woff2" as="font" type="font/woff2" crossorigin>'
              b'<link rel="preload" href="/fonts/inter-latin-wght-normal.woff2" as="font" type="font/woff2" crossorigin>')
_BRANDED = b"BLACKOUT.NETWORK"
PWA_HEAD = (b'<link rel="manifest" href="/manifest.webmanifest"><link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">'
            b'<link rel="icon" type="image/png" sizes="32x32" href="/icons/icon-32.png"><link rel="icon" type="image/png" sizes="16x16" href="/icons/icon-16.png">'
            b'<meta name="theme-color" content="#0b0d10"><meta name="apple-mobile-web-app-capable" content="yes"><meta name="mobile-web-app-capable" content="yes">'
            b'<meta name="apple-mobile-web-app-title" content="BLACKOUT"><meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">'
            b'<link rel="icon" type="image/png" sizes="96x96" href="/icons/icon-96-v2.png"><link rel="icon" type="image/png" sizes="192x192" href="/icons/icon-192-v2.png">'   # BN favicons, new names so Google's favicon cache (YouTube channel links) refetches
            b'<link rel="icon" href="/favicon.ico" sizes="48x48"><link rel="mask-icon" href="/img/safari-pinned-tab.svg" color="#0B0D10">'   # BN master tile icon set (t333)
            b'<meta name="msapplication-TileColor" content="#0B0D10"><meta name="msapplication-TileImage" content="/icons/icon-mstile-150.png">'
            b'<link rel="stylesheet" href="/install-guide.css"><script src="/install-guide.js" defer></script>')
ALERTS_HEAD = b'<link rel="stylesheet" href="/alerts.css"><script src="/alerts.js" defer></script>'   # Alerts bell + panel (webpush.py, t341)
PROGRESS_HEAD = b'<link rel="stylesheet" href="/bn-progress.css"><script src="/bn-progress.js" defer></script>'   # t480 shared search progress bar
GROWTH_HEAD = b'<link rel="stylesheet" href="/api/growth/app.css"><script src="/api/growth/app.js" defer></script>'   # growth.py: share/follow/visual Wire cards (Nov 1)
_OLD_TAGLINES = [b"The world's threats, scored and sourced, before cable news catches up.", b"The world&#x27;s threats, scored and sourced, before cable news catches up.",
                 b"The world&#39;s threats, scored and sourced, before cable news catches up."]
_DASH_FALLBACK = (b'<header class="bn-top" id="bn_topbar"><div class="bn-tbar"><a class="bn-logo" href="/">BLACKOUT.<b>NETWORK</b></a></div>'
                  b'<div class="bn-pop" id="bn_settings" hidden><div class="ctl"><span id="status">loading\xe2\x80\xa6</span><button class="pri" id="refresh">Manual refresh</button>'
                  b'<label>Scans every <select id="interval"></select></label><span id="msg"></span></div></div></header>')
def dashboard_page():
    """dashboard.html with the shared top bar + sidebar (sitenav.py, t320/t321) in place of <!--BN_TOP-->."""
    b = open(f"{BASE}/dashboard.html", "rb").read()
    try:
        import sitenav
        top = sitenav.dashboard_top().encode("utf-8")
    except Exception:
        traceback.print_exc(); top = _DASH_FALLBACK
    b = b.replace(b"<!--BN_TOP-->", top, 1)
    try:   # JSON-LD NewsMediaOrganization (sameAs X + YouTube) + WebSite/SearchAction on the home page (growth.py)
        ld = _addon_mod("growth").home_ld_tag(); i = b.find(b"</head>")
        if i > 0 and b"application/ld+json" not in b[:i]: b = b[:i] + ld + b[i:]
    except Exception: traceback.print_exc()
    return b

# GA4 (seo/batch-1; Compliance 2026-11-01_privacy-ga4.md + 2026-11-01_global-legal-gap.md): Google Analytics 4 (G-KND6CPBB1X), opt-out model.
# gtag.js is never loaded for: visitors in the EEA/UK/CH (CF-IPCountry, read here and not stored; no consent banner); visitors whose country is
# unknown when the browser time zone starts with "Europe/"; GPC or DNT; or a /privacy-choices opt-out (localStorage bn_analytics=denied).
# Consent Mode v2 defaults keep all ad signals denied. Google signals and ad personalization off, 13-month cookie expiry, tokens/emails stripped
# from page_location. Every full HTML page also gets "Cookie Policy" and "Your Privacy Choices" footer links. Inserted once; fragments untouched.
GA4_ID = b"G-KND6CPBB1X"
EU_REGION = set("AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE IS LI NO GB CH".split())
GA_JS = r"""(function(){
window.dataLayer=window.dataLayer||[];window.gtag=window.gtag||function(){dataLayer.push(arguments);};var gtag=window.gtag;
var BN_GA_ID='G-KND6CPBB1X',PV=window.BN_POLICY_V||'',BV=1,MAXAGE=183*864e5;
function ls(k,v){try{if(v===undefined)return localStorage.getItem(k);if(v===null)localStorage.removeItem(k);else localStorage.setItem(k,v);}catch(e){return null;}}
function tz(){try{return Intl.DateTimeFormat().resolvedOptions().timeZone||'';}catch(e){return '';}}
/* seo/batch-1 consent (owner direction, Nov 1; Compliance banner spec A): EEA/UK/CH by CF-IPCountry; header missing -> browser
   timezone (Europe/* = consent region); timezone unknown too -> consent region. There GA loads only after "Accept analytics". */
var R=window.BN_GA_REGION,Z=tz();
var CR=R==='eu'||(R!=='ok'&&(Z===''||Z.indexOf('Europe/')===0));
var gpc=navigator.globalPrivacyControl===true, dnt=navigator.doNotTrack==='1'||window.doNotTrack==='1'||navigator.msDoNotTrack==='1';
function consent(){try{var c=JSON.parse(ls('bn_consent')||'null');if(!c||(c.choice!=='granted'&&c.choice!=='denied'))return null;
if(c.policy_version!==PV||c.banner_version!==BV||!(Date.now()-Date.parse(c.timestamp)<MAXAGE))return null;return c;}catch(e){return null;}}
function logConsent(choice){var c={choice:choice,timestamp:new Date().toISOString(),policy_version:PV,banner_version:BV,region:CR?'consent':'other'};ls('bn_consent',JSON.stringify(c));return c;}
function why(){if(gpc)return 'gpc';if(dnt)return 'dnt';if(ls('bn_analytics')==='denied')return 'optout';
if(CR){var c=consent();if(!c)return 'consent_pending';if(c.choice!=='granted')return 'consent_denied';}return '';}
var skip=why();window.BN_GA_SKIP=skip;window.BN_CONSENT_REGION=CR;
gtag('consent','default',{ad_storage:'denied',ad_user_data:'denied',ad_personalization:'denied',analytics_storage:(CR||skip)?'denied':'granted',functionality_storage:'granted',security_storage:'granted'});
/* compliance 2026-11-02: one shared sanitizer (window.bnPII / bnSanitize) for bnTrack, bn-ga-events.js and page_location. Drops: emails,
   phone numbers, any run of 9+ digits, street addresses (house number + street word), PO Box, US ZIP+4. Tested on decoded text. */
/* G1/G2 (Compliance 2026-11-02): phone part replaced with the spec pattern (catches (407) 555-1234, +44 20 7946 0958, +1-407-555-1234,
   407.555.1234); address suffixes extended per spec plus trail/route/pike/crossing/run/path/row/sr/cr; Apt/Suite/Ste/Unit forms. */
/* G-fixes-2: + SSN shapes (123-45-6789, 123 45 6789) and precise lat,lon pairs (3+ decimals; 1-2 decimals kept). */
var PII=/@|%40|\b\d{3}[\s.\-]\d{2}[\s.\-]\d{4}\b|-?\d{1,2}\.\d{3,}\s*,?\s*-?\d{1,3}\.\d{3,}|(?:\+?\d{1,3}[\s.\-]?)?\(?\d{2,4}\)?[\s.\-]?\d{3,4}[\s.\-]?\d{3,4}|\d{9,}|\bp\.?\s*o\.?\s*box\b|\b\d{5}-\d{4}\b|\b(?:apt|suite|ste|unit)\s*#?\s*\d+|\b\d{1,6}[a-z]?\s+(?:[a-z0-9.'\-]+\s+){0,4}(?:st|street|ave|avenue|rd|road|blvd|boulevard|ln|lane|dr|drive|ct|court|way|pl|place|hwy|highway|pkwy|parkway|ter|terrace|cir|circle|trl|trail|loop|sq|square|plz|plaza|apt|suite|ste|unit|run|path|row|crossing|xing|pike|route|rte)\b|\b\d{1,6}\s+(?:highway|hwy|route|rte|sr|cr|state\s+road|county\s+road)\s*-?\d+\b|\b(?:sr|cr)[\s\-]?\d{1,4}\b/i;
function dec(v){try{return decodeURIComponent(String(v).replace(/\+/g,' '));}catch(e){return String(v);}}
window.bnPII=function(v){return typeof v==='string'&&(PII.test(v)||PII.test(dec(v)));};
/* site-generated ids (item_id, transaction_id, story_id): exempt from the digit rules (phone / 9+ digits) only when strictly id-shaped and
   containing at least one letter (pure-digit values stay filtered, so a phone number can't pass as an id). Free-text fields never exempt. */
var IDK={item_id:1,transaction_id:1,story_id:1};
window.bnIdOK=function(k,v){return !!IDK[k]&&typeof v==='string'&&/[a-z]/i.test(v)&&(/^[0-9a-f]{8,40}$/i.test(v)||/^[A-Za-z0-9_-]{6,64}$/.test(v));};
window.bnSanitize=function(v,k){return (window.bnPII(v)&&!window.bnIdOK(k,v))?undefined:v;};
/* page_location: place (/crime GET form), term, address, name, phone and tokens always removed. Site-search params q (/?q= SearchAction
   deep link), s, search, query are KEPT when the decoded value passes bnPII (GA site-search report) and dropped when not; any other
   param whose name/value looks like PII removed; newsletter token routes lose the whole query; the #fragment (#search=<q>) is never sent. */
/* G3: /report-status/<ref> (status.js pushState) and ?id= lose the reference ID; id/rid/ref removed everywhere. G4: same cleaner is used for
   page_referrer, which also loses key/code/session/auth/sid/state/password/sig params. */
var BN_STRIP=['token','email','e','zip','q_email','internal','place','term','address','name','phone','id','rid','ref','key','api_key','code','session','session_id','sessionid','sid','auth','auth_token','access_token','state','password','pass','sig','signature','otp'];
function bnCleanUrl(u){try{var url=new URL(u,location.href);
if(/^\/report-status(\/|$)/.test(url.pathname)){url.pathname='/report-status/';url.search='';}
var del=[];url.searchParams.forEach(function(v,k){if(BN_STRIP.indexOf(k.toLowerCase())>=0||window.bnPII(v)||window.bnPII(k)||/token|session|auth|secret|passw|email|^(id|rid|ref|key|api_key|code|sid|state|sig|signature|otp|pass)$/i.test(k))del.push(k);   /* case-insensitive (G-fixes-2) */});del.forEach(function(k){url.searchParams.delete(k);});
if(/^\/newsletter\/(confirm|unsubscribe|manage|breaking_off|stop_tracking|follow|unfollow)/.test(url.pathname))url.search='';url.hash='';return url.toString();}catch(e){return location.origin+location.pathname;}}
/* content_group (seo/batch-1): one of Home, Wire, Midterms, Solar, Weather, Preppers, Bushcraft, Network, Gov, Alerts, Stats, Legal */
var TABG={threat:'Wire',wire:'Wire',noise:'Wire',thread:'Wire',bcast:'Wire',broadcasts:'Wire',streams:'Wire',radio:'Wire',ai:'Wire',heatmap:'Wire',trends:'Wire',
finance:'Wire',jets:'Wire',spacex:'Wire',intel:'Wire',ranked:'Wire',figures:'Wire',sources:'Wire',net:'Network',network:'Network',grid:'Network',
solar_seismic:'Solar',solar:'Solar',weather:'Weather',midterms:'Midterms',politics:'Gov',gunlaws:'Gov',gov:'Gov',government:'Gov',
preppers:'Preppers',res:'Preppers',resources:'Preppers',med:'Preppers',medical:'Preppers',maps:'Preppers',bush:'Bushcraft',bushcraft:'Bushcraft'};
function tabKey(){var h=(location.hash||'').slice(1).split(/[\/=?&]/)[0].toLowerCase();return TABG[h]?h:'';}
function bnGroup(k){var p=location.pathname.toLowerCase();
if(/^\/(wire|story)(\/|$)/.test(p))return 'Wire';if(/^\/(midterms|elections?)\/?$/.test(p))return 'Midterms';
if(/^\/(privacy|cookies|cookie-policy|privacy-choices|do-not-sell|tos|terms)\/?$/.test(p))return 'Legal';
if(/^\/(stats|report-status)\/?$/.test(p))return 'Stats';if(/^\/(alerts|crime)(\/|$)/.test(p))return 'Alerts';
if(p==='/'||p===''){k=k||tabKey();return k?TABG[k]:'Home';}
var s=p.split('/')[1];return TABG[s]||'Home';}
window.bnContentGroup=bnGroup;
/* G-fixes-2: /crime titles echo the geocoder label ('Crime in <place>'), which for international or free-text lookups can be user-typed text,
   so /crime always reports a generic page_title. */
function bnTitle(){return /^\/crime(\/|$)/.test(location.pathname)?'Crime lookup | BLACKOUT.NETWORK':document.title;}
function bnLoadGA(){if(window.bnGALoaded||window.BN_GA_SKIP)return;window.bnGALoaded=true;var s=document.createElement('script');s.async=true;
s.src='https://www.googletagmanager.com/gtag/js?id='+BN_GA_ID;document.head.appendChild(s);gtag('js',new Date());
var gc={page_title:bnTitle(),allow_google_signals:false,allow_ad_personalization_signals:false,cookie_expires:34128000,page_location:bnCleanUrl(location.href),content_group:bnGroup()};
if(document.referrer)gc.page_referrer=bnCleanUrl(document.referrer);   /* G4: every referrer cleaned (same-site token pages included) */
/* analytics 2026-11-01: staff/bot traffic -> traffic_type=internal (GA4 Admin > Data filters > Internal Traffic). Staff cookie bn_internal=1 is set by
   any page opened with ?internal=1 (cleared by ?internal=0); our box tools send a User-Agent containing BlackoutNetwork-Internal. */
if(!/[?&]internal=0(&|$)/.test(location.search)&&(/(^|;\s*)bn_internal=1(;|$)/.test(document.cookie)||/[?&]internal=1(&|$)/.test(location.search)||/BlackoutNetwork-Internal/i.test(navigator.userAgent||'')))gc.traffic_type='internal';
gtag('config',BN_GA_ID,gc);gtag('set',{page_title:bnTitle()});}
/* Events (seo/batch-1, spec in ga4-events.md): sent only when GA is loaded and allowed. Nothing is queued while GA is skipped
   (EEA/UK/CH, Europe/ timezone, GPC, DNT, opt-out), and nothing that looks like an email or phone number is ever sent. */
window.bnTrack=function(name,p){if(!window.bnGALoaded||window.BN_GA_SKIP)return false;var o={};p=p||{};
for(var k in p){if(!Object.prototype.hasOwnProperty.call(p,k))continue;var v=p[k];if(v==null||v==='')continue;
if(typeof v==='string'){if(window.bnPII(v)&&!window.bnIdOK(k,v))continue;v=v.slice(0,100);}else if(typeof v!=='number'&&typeof v!=='boolean')continue;o[k]=v;}
o.content_group=o.content_group||bnGroup();o.page_title=bnTitle();gtag('event',name,o);return true;};
var T=window.bnTrack;
function killGA(){window['ga-disable-'+BN_GA_ID]=true;gtag('consent','update',{analytics_storage:'denied'});
document.cookie.split(';').forEach(function(c){var n=c.split('=')[0].trim();if(n==='_ga'||n.indexOf('_ga_')===0){document.cookie=n+'=; Max-Age=0; path=/; domain=.blackout.network';document.cookie=n+'=; Max-Age=0; path=/';document.cookie=n+'=; Max-Age=0; path=/; domain='+location.hostname;}});}
window.bnSetAnalytics=function(choice){
if(choice==='denied'){if(CR)logConsent('denied');else ls('bn_analytics','denied');window.BN_GA_SKIP=why()||'optout';killGA();}
else{ls('bn_analytics',null);if(CR)logConsent('granted');window.BN_GA_SKIP=why();if(!window.BN_GA_SKIP){window['ga-disable-'+BN_GA_ID]=false;gtag('consent','update',{analytics_storage:'granted'});bnLoadGA();}}
if(window.bnConsentUI)window.bnConsentUI.sync();};
window.bnConsent=function(){return {region:CR?'consent':'other',skip:window.BN_GA_SKIP,record:consent(),gpc:gpc,dnt:dnt};};
bnLoadGA();
/* hooks are always installed; bnTrack drops everything until GA has loaded with consent, so nothing is queued */
function cat(){var s=document.getElementById('bn_story');if(s)return s.getAttribute('data-cat')||'';var b=document.querySelector('.tabs button.on[data-tab]');return tabKey()||(b&&b.getAttribute('data-tab'))||bnGroup().toLowerCase();}
function platform(){var ua=navigator.userAgent||'';var ios=/iPhone|iPad|iPod/.test(ua)||(/Macintosh/.test(ua)&&navigator.maxTouchPoints>1);
var sa=false;try{sa=matchMedia('(display-mode: standalone)').matches||navigator.standalone===true;}catch(e){}
return (ios?'ios':/Android/i.test(ua)?'android':'desktop')+(sa?'_app':'_web');}
var lastTab='';
/* G4: #search=<q> and /report-status/<ref> never reach GA: page_location is re-set clean on every hash/history change (before and after
   pushState/replaceState). Recommend also turning off Enhanced Measurement > Page views > "Page changes based on browser history events". */
/* !!! DEPLOY REQUIREMENT (G-fixes-2): this commit sends its own clean SPA page_view. GA4 Admin > Data streams > Enhanced measurement >
   Page views > "Page changes based on browser history events" MUST be switched OFF in the same deploy, or SPA page views double-count and
   GA's own history page_view could still carry an uncleaned URL. Live Admin change: awaiting Matt's yes via CoS. !!!
   bnReLoc: re-sets the clean page_location and sends one page_view per NEW cleaned URL (deduplicated back-to-back; never on initial load,
   which config covers). Respects consent (bnGALoaded && !BN_GA_SKIP) and BN_GA_OFF (whole script absent). */
var bnLastPV=bnCleanUrl(location.href);
function bnReLoc(){var c=bnCleanUrl(location.href);gtag('set',{page_location:c,page_title:bnTitle()});
if(c===bnLastPV)return;bnLastPV=c;if(!window.bnGALoaded||window.BN_GA_SKIP)return;gtag('event','page_view',{page_location:c,page_title:bnTitle(),content_group:bnGroup()});}
['pushState','replaceState'].forEach(function(m){try{var o=history[m];if(!o||o.bnWrapped)return;history[m]=function(st,t,u){if(u!=null){try{gtag('set',{page_location:bnCleanUrl(String(u))});}catch(x){}}var r=o.apply(this,arguments);bnReLoc();return r;};history[m].bnWrapped=1;}catch(e){}});
window.addEventListener('hashchange',function(){bnReLoc();gtag('set',{content_group:bnGroup()});},true);
window.addEventListener('popstate',function(){bnReLoc();gtag('set',{content_group:bnGroup()});},true);
document.addEventListener('click',function(e){var t=e.target;if(!t||!t.closest)return;
var b=t.closest('.tabs button[data-tab]');if(b){var k=b.getAttribute('data-tab');if(k&&k!==lastTab){lastTab=k;var g=bnGroup(TABG[k]?k:'');gtag('set',{content_group:g});T('tab_view',{content_category:k,content_group:g});}return;}
if(t.closest('.tab-ref,#refresh,[data-bn-refresh]')){T('refresh_click',{});return;}
var a=t.closest('a[href]');
if(a&&(a.hasAttribute('data-affiliate')||/(^|\s)sponsored(\s|$)/.test(a.getAttribute('rel')||''))){var h='';try{h=new URL(a.href).hostname.replace(/^www\./,'');}catch(x){}T('affiliate_click',{partner:a.getAttribute('data-affiliate')||h});return;}
var sh=t.closest('.bng-share .bng-copy,.bng-share .bng-native,.bng-share a[href*="/intent/"]');
if(sh){T('share',{method:sh.classList.contains('bng-copy')?'copy_link':sh.classList.contains('bng-native')?'native':'x',content_category:cat()});return;}
if(t.closest('.bn-theme-bar,.bn-theme-row,[data-bn-theme]')){setTimeout(function(){T('settings_change',{setting:'theme',value:document.documentElement.getAttribute('data-theme')||'toggle'});},0);}
},true);
document.addEventListener('change',function(e){var el=e.target;if(!el||!el.closest)return;
if(el.classList&&el.classList.contains('bntr-sel')){T('translate_language',{language_code:el.value});return;}
if(!el.closest('#bn_settings'))return;var ty=(el.type||'').toLowerCase();if(/^(text|email|tel|password|search|hidden|url)$/.test(ty)||el.tagName==='TEXTAREA')return;
T('settings_change',{setting:el.id||el.name||'setting',value:ty==='checkbox'?(el.checked?'on':'off'):String(el.value)});},true);
document.addEventListener('toggle',function(e){var d=e.target;if(!d||d.tagName!=='DETAILS'||!d.open||!d.hasAttribute('data-bn-expand'))return;if(d.hasAttribute('data-bn-bulk')){d.removeAttribute('data-bn-bulk');return;}T('expand',{content_category:d.getAttribute('data-cat')||cat(),item:(d.getAttribute('data-item')||'').slice(0,100)});},true);
var played=[];document.addEventListener('play',function(e){var m=e.target;if(!m||!/^(AUDIO|VIDEO)$/.test(m.tagName)||played.indexOf(m)>=0)return;played.push(m);
var c=m.closest&&m.closest('[data-station],.rd-card,.bnp,.card,section');var n=(m.getAttribute('data-station')||(c&&(c.getAttribute('data-station')||((c.querySelector('b,h3,h2')||{}).textContent)))||m.getAttribute('aria-label')||'').trim();
T('broadcast_play',{station:n||'unknown'});},true);
try{if(window.PushManager&&PushManager.prototype.subscribe&&!PushManager.prototype.subscribe.bnWrapped){var ps=PushManager.prototype.subscribe;
PushManager.prototype.subscribe=function(){return ps.apply(this,arguments).then(function(s){T('push_subscribe',{platform:platform()});T('push_optin',{platform:platform()});return s;});};PushManager.prototype.subscribe.bnWrapped=1;}}catch(e){}
try{var f0=window.fetch;if(f0&&!f0.bnWrapped){window.fetch=function(input,init){var u=typeof input==='string'?input:(input&&input.url)||'';var r=f0.apply(this,arguments);
if(/\/api\/newsletter\/subscribe(\?|$)/.test(u)&&init&&String(init.method||'').toUpperCase()==='POST'){var src='form';try{src=String(JSON.parse(init.body).source||'form');}catch(x){}
r.then(function(res){if(res&&res.ok){var loc=location.pathname==='/'?'home'+(tabKey()?'_'+tabKey():''):location.pathname.replace(/^\/+|\/+$/g,'').replace(/\/[0-9a-f]{16}$/,'').replace(/\//g,'_');
var p={signup_source:src,form_location:loc||'home'};T('newsletter_signup',p);T('generate_lead',p);}},function(){});}
return r;};window.fetch.bnWrapped=1;}}catch(e){}
function onReady(){var p=location.pathname,st=document.getElementById('bn_story');
var ok=document.querySelector('.nl-result.ok h2');if(/^\/newsletter\/confirm\/?$/.test(p)&&ok&&/Subscription confirmed/.test(ok.textContent))T('newsletter_confirm',{});
if(st&&/^\/wire\/[0-9a-f]{16}\/?$/.test(p)){var rk=parseInt(st.getAttribute('data-rank'),10),c=st.getAttribute('data-cat')||'';T('story_view',{content_category:c,story_rank:isNaN(rk)?0:rk});
if(/[?&]utm_(source=push|medium=alert)/.test(location.search))T('alert_view',{alert_severity:st.getAttribute('data-tier')||'',content_category:c});}
if(window.bnShare&&!window.bnShare.bnWrapped){var s0=window.bnShare;window.bnShare=function(){T('share',{method:navigator.share?'native':'copy_link',content_category:cat()});return s0.apply(this,arguments);};window.bnShare.bnWrapped=1;}}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',onReady);else onReady();
/* ---- cookie consent banner (consent region; reopened anywhere by footer "Cookie settings" or [data-bn-cookie-settings]) ---- */
var CSS='#bn_cb{position:fixed;left:0;right:0;bottom:0;z-index:4950;box-sizing:border-box;padding:12px 14px calc(12px + env(safe-area-inset-bottom));background:#0b0d10;color:#e6e9ee;border-top:2px solid #c8102e;font:13px/1.45 Inter,system-ui,-apple-system,"Segoe UI",sans-serif;box-shadow:0 -6px 24px rgba(0,0,0,.35)}'
+'#bn_cb .bn-cb-in{max-width:980px;margin:0 auto;display:flex;flex-direction:column;gap:10px}'
+'#bn_cb p{margin:0}#bn_cb b.bn-cb-h{font:700 14px/1.3 Montserrat,Inter,system-ui,sans-serif;color:#fff;display:block;margin-bottom:2px}'
+'#bn_cb .bn-cb-row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}'
+'#bn_cb .bn-cb-btn{flex:1 1 0;min-width:0;min-height:44px;padding:0 14px;border-radius:8px;border:2px solid #c8102e;background:#c8102e;color:#fff;font:700 14px/1 Montserrat,Inter,system-ui,sans-serif;cursor:pointer}'
+'#bn_cb .bn-cb-btn:focus-visible{outline:3px solid #fff;outline-offset:2px}#bn_cb .bn-cb-btn[disabled]{opacity:.45;cursor:not-allowed}'
+'#bn_cb a{color:#ff8a9a}#bn_cb .bn-cb-lk{flex:0 0 100%;text-align:center;font-size:12.5px}#bn_cb .bn-cb-st{font-size:12px;color:#aab3bf}'
+'#bn_cb .bn-cb-x{position:absolute;top:4px;right:6px;width:36px;height:36px;border:0;background:none;color:#aab3bf;font-size:20px;cursor:pointer}'
+'@media(min-width:760px){#bn_cb{padding:12px 20px}#bn_cb .bn-cb-in{flex-direction:row;align-items:center;gap:18px}#bn_cb .bn-cb-tx{flex:1}#bn_cb .bn-cb-row{flex:0 0 auto;flex-wrap:nowrap}#bn_cb .bn-cb-btn{flex:0 0 150px}#bn_cb .bn-cb-lk{flex:0 0 auto}}'
+'html.bn-cb-on body{padding-bottom:var(--bn-cb-h,140px)}html.bn-cb-on #toasts,html.bn-cb-on .bnr-fab,html.bn-cb-on .bnig-toast{bottom:calc(var(--bn-cb-h,140px) + 12px)!important}'
+'html.bn-cb-on .bng-bar,html.bn-cb-on .bng-prompt{display:none!important}'
+'[data-theme=light] #bn_cb{background:#fff;color:#1b2129;box-shadow:0 -6px 24px rgba(0,0,0,.12)}[data-theme=light] #bn_cb b.bn-cb-h{color:#0b0d10}[data-theme=light] #bn_cb a{color:#c8102e}[data-theme=light] #bn_cb .bn-cb-st{color:#5b6573}';
function esc(t){return String(t).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function fmtD(iso){try{return new Date(iso).toLocaleDateString(undefined,{year:'numeric',month:'short',day:'numeric'});}catch(e){return iso;}}
var UI={el:null,ro:null,
status:function(){var c=consent();if(gpc||dnt)return 'Your browser sends a '+(gpc?'Global Privacy Control':'Do Not Track')+' signal, so analytics stays off.';
 if(CR){return c?('Current choice: '+(c.choice==='granted'?'analytics accepted':'analytics rejected')+' on '+fmtD(c.timestamp)+'.'):'';}
 return ls('bn_analytics')==='denied'?'Current choice: analytics off in this browser.':'Current choice: analytics on (you can turn it off).';},
open:function(reopen){if(!document.body)return;if(!document.getElementById('bn_cb_css')){var st=document.createElement('style');st.id='bn_cb_css';st.textContent=CSS;document.head.appendChild(st);}
 var d=this.el;if(!d){d=document.createElement('div');d.id='bn_cb';d.setAttribute('role','region');d.setAttribute('aria-label','Cookie consent');this.el=d;}
 var off=gpc||dnt;
 d.innerHTML='<div class="bn-cb-in"><div class="bn-cb-tx"><p><b class="bn-cb-h">Can we count your visit?</b> We\'d like to use Google Analytics to see which pages are useful. It sets cookies on your device and sends usage data to Google. It\'s off unless you say yes, and the site works the same either way.</p>'
  +'<p class="bn-cb-st" aria-live="polite">'+esc(this.status())+'</p></div>'
  +'<div class="bn-cb-row"><button type="button" class="bn-cb-btn" data-cb="granted"'+(off?' disabled':'')+'>Accept analytics</button><button type="button" class="bn-cb-btn" data-cb="denied"'+(off?' disabled':'')+'>Reject</button>'
  +'<span class="bn-cb-lk"><a href="/cookies">Cookie Policy</a></span></div></div>'+(reopen||off?'<button type="button" class="bn-cb-x" aria-label="Close cookie settings">×</button>':'');
 if(!d.parentNode)document.body.appendChild(d);document.documentElement.classList.add('bn-cb-on');this.size();
 var me=this;if(window.ResizeObserver&&!this.ro){this.ro=new ResizeObserver(function(){me.size();});this.ro.observe(d);}
 if(reopen){var b=d.querySelector('.bn-cb-btn:not([disabled])')||d.querySelector('.bn-cb-x');if(b)try{b.focus({preventScroll:true});}catch(e){}}},
size:function(){if(this.el)document.documentElement.style.setProperty('--bn-cb-h',this.el.offsetHeight+'px');},
close:function(){if(this.el&&this.el.parentNode)this.el.parentNode.removeChild(this.el);document.documentElement.classList.remove('bn-cb-on');},
sync:function(){if(this.el&&this.el.parentNode){var s=this.el.querySelector('.bn-cb-st');if(s)s.textContent=this.status();}}};
window.bnConsentUI=UI;window.bnCookieSettings=function(){UI.open(true);};
document.addEventListener('click',function(e){var t=e.target;if(!t||!t.closest)return;
 var k=t.closest('[data-bn-cookie-settings],a[href="/cookies#settings"]');if(k){e.preventDefault();UI.open(true);return;}
 var b=t.closest('#bn_cb .bn-cb-btn');if(b&&!b.disabled){var ch=b.getAttribute('data-cb');if(!CR&&ch==='granted')ls('bn_analytics',null);window.bnSetAnalytics(ch);UI.close();return;}
 if(t.closest('#bn_cb .bn-cb-x'))UI.close();});
function boot(){if(CR&&!gpc&&!dnt&&!consent())UI.open(false);}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();"""
LEGAL_LINKS = (b'<span class="bn-legal-links"> \xc2\xb7 <a href="/cookies">Cookie Policy</a> \xc2\xb7 <a href="/cookies#settings" data-bn-cookie-settings>Cookie settings</a>'
               b' \xc2\xb7 <a href="/privacy-choices">Your Privacy Choices</a></span>')
# Consent policy version: stored with every banner choice (localStorage bn_consent). Bump it when /privacy or /cookies change in a
# material way and every visitor in the consent region is asked again. Choices also expire after 6 months (GA_JS MAXAGE).
CONSENT_POLICY_VERSION = "2026-11-01"
def ga_region(country):
    c = (country or "").strip().upper()
    if c in EU_REGION: return "eu"
    return "ok" if len(c) == 2 and c.isalpha() and c not in ("XX", "T1") else "unknown"
# seo/batch-1 kill switches (Render env vars; a restart applies them, no code deploy): BN_GA_OFF=1 stops the GA4 loader, the consent banner and all
# GA4 events on every page (no gtag request at all); BN_LEGAL_FOOTER_OFF=1 stops the injected Cookie Policy / Your Privacy Choices footer links.
def _flag(name): return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")

def ga_head(b, country=None, ga=True):
    try:
        lo = b[:6000].lower(); h = lo.find(b"<head>")
        if h < 0 or b"<html" not in lo: return b
        if ga and not _flag("BN_GA_OFF") and b"BN_GA_REGION" not in b[:60000]:
            tag = ("<script>window.BN_GA_REGION=" + json.dumps(ga_region(country)) + ";window.BN_POLICY_V=" + json.dumps(CONSENT_POLICY_VERSION) + ";" + GA_JS + "</script><script src=\"/bn-ga-events.js\" defer></script>").encode("utf-8")
            m = re.search(rb"<meta charset=[^>]*>", b[:60000], re.I); i = m.end() if m and m.start() < b.lower().find(b"</head>") else h + 6   # after <meta charset>, else right after <head>
            b = b[:i] + tag + b[i:]
        lo = b.lower(); j = lo.rfind(b"</footer>"); fs = lo.rfind(b"<footer", 0, j) if j >= 0 else -1
        if not _flag("BN_LEGAL_FOOTER_OFF") and b'href="/privacy-choices"' not in (b[fs:j] if j >= 0 else b'') and b"bn-legal-ft" not in b:   # footer links on every full page (last </footer>, else a small footer before </body>)
            if j >= 0: b = b[:j] + LEGAL_LINKS + b[j:]
            else:
                k = b.lower().rfind(b"</body>")
                if k >= 0: b = (b[:k] + b'<footer class="bn-legal-ft" style="text-align:center;font:12px/1.6 Inter,system-ui,sans-serif;color:#8b95a3;padding:14px 12px 24px">'
                                b'<a href="/privacy" style="color:inherit">Privacy</a> \xc2\xb7 <a href="/tos" style="color:inherit">Terms</a>' + LEGAL_LINKS + b'</footer>' + b[k:])
    except Exception: pass
    return b

def pwa_head(b):
    try:
        h = b[:4000].lower().find(b"<head>")
        if h >= 0 and b"<html" in b[:4000].lower() and b"bn_theme" not in b[:30000]:   # light/dark theme before first paint (t323)
            b = b[:h + 6] + THEME_HEAD + b[h + 6:]
        al = b[:120000].lower(); j = al.find(b"</head>")   # Alerts bell + Web Push (webpush.py, t341)
        if j >= 0 and b"<html" in al[:4000] and b"/alerts.js" not in al[:j]: b = b[:j] + ALERTS_HEAD + b[j:]
        al = b[:120000].lower(); j = al.find(b"</head>")
        if j >= 0 and b"<html" in al[:4000] and b"/api/growth/app.js" not in al[:j]: b = b[:j] + GROWTH_HEAD + b[j:]
        al = b[:120000].lower(); j = al.find(b"</head>")
        if j >= 0 and b"<html" in al[:4000] and b"/bn-progress.js" not in al[:j]: b = b[:j] + PROGRESS_HEAD + b[j:]
        lo = b[:20000].lower(); i = lo.find(b"</head>")
        if i < 0 or b"<html" not in lo: return b          # fragments (cards, iframes, JSON) are left alone
        if b"/manifest.webmanifest" not in lo[:i]: b = b[:i] + PWA_HEAD + b[i:]
        # per-page titles such as "How we score | BLACKOUT.NETWORK" (sitenav.py, t302) are kept; any other title becomes the site title
        b = re.sub(rb"<title>([^<]*)</title>", lambda m: m.group(0) if _BRANDED in m.group(1) else b"<title>" + SITE_TITLE + b"</title>", b, count=1)
        b = re.sub(rb'(<meta (?:property="og:title"|name="twitter:title") content=")([^"]*)(")', lambda m: m.group(0) if _BRANDED in m.group(2) else m.group(1) + SITE_TITLE + m.group(3), b)
        b = re.sub(rb'(<meta name="viewport" content="width=device-width,\s*initial-scale=1)(")', rb"\g<1>,viewport-fit=cover\g<2>", b, count=1)
        for t in _OLD_TAGLINES: b = b.replace(t, SITE_TITLE)
        return b
    except Exception: return b

# t338/t343: Render's free tier drops some of a page's ~40 parallel requests (502/503). (1) every same-origin JS/CSS URL in a page gets
# ?v=<build> so Cloudflare and browsers can cache it for a year (Cache-Control immutable below) and the origin rarely sees asset requests;
# (2) BN_RETRY_HEAD retries a failed script/stylesheet (twice, with backoff) and same-origin GET fetches that come back 502/503/504.
_ASSET_RE = re.compile(rb'((?:src|href)=["\']?)(/?(?:api/[a-z_]+/[\w.-]+|sitenav|theme|install-guide|alerts|linkguard|bn-eggs|bn-icons)\.(?:js|css)|/?api/[a-z_]+/[\w.-]+\.(?:js|css))(["\'\s>])')
_ASSET_V = {"t": 0, "v": b"0"}
def asset_version():
    now = time.time()
    if now - _ASSET_V["t"] > 20:
        h = 0
        try:
            for d in [BASE, f"{BASE}/static"] + [e.path for e in os.scandir(BASE) if e.is_dir() and e.name.endswith("_static")]:
                for e in os.scandir(d):
                    if e.name.endswith((".js", ".css", ".html")): h = (h * 31 + int(e.stat().st_mtime) + len(e.name)) % 0xFFFFFFFFFF
        except Exception: pass
        _ASSET_V.update(t=now, v=format(h, "x").encode())
    return _ASSET_V["v"]
def version_assets(b):
    try:
        v = asset_version(); lo = b[:6000].lower(); h = lo.find(b"<head>")
        if h >= 0 and b"<html" in lo and b"bnRetry" not in b[:40000]: b = b[:h + 6] + BN_RETRY_HEAD + b[h + 6:]
        j = b.rfind(b"</body>")   # dead-link guard + easter eggs (bn_extras.py) on every full page
        if j > 0 and b"<html" in lo and b"/linkguard.js" not in b: b = b[:j] + b'<script src="/bn-icons.js"></script><script src="/linkguard.js" defer></script><script src="/bn-eggs.js" defer></script>' + b[j:]   # bn-icons runs before first paint (no emoji flash)
        return _ASSET_RE.sub(lambda m: m.group(1) + m.group(2) + b"?v=" + v + m.group(3), b)
    except Exception: return b
BN_RETRY_HEAD = (b'<script>/*bnRetry*/(function(){if(window.__bnRetry)return;window.__bnRetry=1;var o=location.origin;'
  b'addEventListener("error",function(e){var t=e.target;if(!t||t===window||!t.tagName)return;var tag=t.tagName,u=tag=="SCRIPT"?t.src:tag=="LINK"&&t.rel=="stylesheet"?t.href:"";'
  b'if(!u||u.indexOf(o)!==0)return;var n=+(t.getAttribute("data-bn-retry")||0);if(n>=2)return;setTimeout(function(){var c=document.createElement(tag);'
  b'if(tag=="SCRIPT"){c.src=u+(u.indexOf("?")<0?"?":"&")+"r="+(n+1);c.async=false}else{c.rel="stylesheet";c.href=u+(u.indexOf("?")<0?"?":"&")+"r="+(n+1)}'
  b'c.setAttribute("data-bn-retry",n+1);(t.parentNode||document.head).insertBefore(c,t.nextSibling)},700*(n+1)*(n+1))},true);'
  b'var F=window.fetch;if(!F)return;window.fetch=function(i,init){var m=((init&&init.method)||(i&&i.method)||"GET").toUpperCase(),u=typeof i=="string"?i:(i&&i.url)||"";'
  b'var same=u.indexOf("://")<0||u.indexOf(o)===0;if(m!="GET"||!same||(init&&init.bnNoRetry)||/\\/api\\/stream/.test(u))return F.apply(this,arguments);var a=arguments,s=this,k=0;'
  b'return new Promise(function(res,rej){(function go(){F.apply(s,a).then(function(r){if((r.status==502||r.status==503||r.status==504)&&k<3){k++;setTimeout(go,500*k*k)}else res(r)},'
  b'function(err){if(k<2&&!(init&&init.signal&&init.signal.aborted)){k++;setTimeout(go,600*k)}else rej(err)})})()})}})()</script>')

# Visitor beacon (analytics 2026-11-01): our own counter counts a unique visitor only when a page's script reports it (POST /api/hit,
# usage_stats.beacon), so page-only checkers (curl, link checkers, scanners, link previews) never count as visitors. No cookies, no
# identifiers in the request: the server hashes IP + User-Agent with the daily key. Skipped for DNT/GPC, the staff cookie, and webdriver.
# Only on the public web node (BN_WEB_ONLY=1, set by render_app.py); BN_HIT_BEACON=0 turns it off, BN_HIT_BEACON=1 forces it on.
HIT_JS = (b"<script>(function(){try{var n=navigator;if(n.webdriver||n.globalPrivacyControl===true||n.doNotTrack==='1'||window.doNotTrack==='1'"
          b"||/(^|;\\s*)bn_internal=1(;|$)/.test(document.cookie)||/[?&]internal=[01](&|$)/.test(location.search))return;var sent=0;"
          b"function go(){if(sent||document.visibilityState==='hidden'||document.visibilityState==='prerender')return;sent=1;"
          b"var d=JSON.stringify({p:location.pathname});try{if(n.sendBeacon&&n.sendBeacon('/api/hit',new Blob([d],{type:'text/plain'})))return;}catch(e){}"
          b"try{fetch('/api/hit',{method:'POST',body:d,keepalive:true,credentials:'same-origin',headers:{'Content-Type':'text/plain'}});}catch(e){}}"
          b"if(document.readyState==='complete')setTimeout(go,800);else addEventListener('load',function(){setTimeout(go,800);});"
          b"document.addEventListener('visibilitychange',function(){setTimeout(go,800);});}catch(e){}})();</script>")
def hit_beacon(b):
    try:
        f = os.environ.get("BN_HIT_BEACON", "").strip()
        if f == "0" or (f != "1" and os.environ.get("BN_WEB_ONLY") != "1"): return b
        lo = b[:6000].lower()
        if b"<html" not in lo or b"/api/hit" in b: return b
        i = b.lower().rfind(b"</body>")
        return b[:i] + HIT_JS + b[i:] if i >= 0 else b
    except Exception: return b

def report_widget(b):
    try:
        i = b.rfind(b"</body>")
        if i < 0 or b"/api/report/app.js" in b or b"data-bn-noreport" in b or b"http-equiv=refresh" in b[:600]: return b
        return b[:i] + _RW + b[i:]
    except Exception: return b

class H(BaseHTTPRequestHandler):
    server_version = "Blackout/1.0"
    def log_message(self, fmt, *a): pass
    def ip(self): return self.headers.get("CF-Connecting-IP") or self.client_address[0]
    def send(self, code, body, ctype="application/json"):
        b = body if isinstance(body, bytes) else (json.dumps(body, default=str) if ctype == "application/json" else body).encode()
        if ctype == "application/json" and b"://" in b:   # t347: show people the human page, not the raw API/RSS endpoint (display only)
            try: b = display_links.rewrite_json(b.decode("utf-8")).encode("utf-8")
            except Exception: pass
        if ctype == "text/html": b = version_assets(report_widget(pwa_head(b)))
        if ctype.startswith("text/html"): b = ga_head(b, self.headers.get("CF-IPCountry"))   # GA4 also on pages returned as "text/html; charset=utf-8" (e.g. /stats)
        if ctype.startswith("text/html"): b = hit_beacon(b)   # own visitor counter (public node only)
        self.send_response(code); self.send_header("Content-Type", ctype if ctype.startswith("image/") else ctype + "; charset=utf-8")
        versioned = "v=" in (self.path.split("?", 1)[1] if "?" in self.path else "") and code == 200 and ctype in ("application/javascript", "text/css")
        self.send_header("Cache-Control", "public, max-age=2592000, immutable" if ctype.startswith("font/") else "public, max-age=31536000, immutable" if versioned else "no-store"); self.send_header("X-Content-Type-Options", "nosniff")
        # hotfix/confirm-origin: was no-referrer, which makes Safari send "Origin: null" on same-site form POSTs (403 on /newsletter/confirm).
        # same-origin keeps the real Origin for our own POSTs and still sends no Referer (no token leak) to any other site.
        self.send_header("Referrer-Policy", "same-origin"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    # Security headers (Security Officer baseline 2026-11-01). Added to EVERY response (send(), redirects, add-on raw replies)
    # at end_headers(); headers already set by the handler (send() sets nosniff + Referrer-Policy) are never duplicated.
    # HSTS: 6 months, no includeSubDomains (M365/Resend CNAMEs like autodiscover/sip/email are not verified HTTPS sites), no preload.
    # CSP is Report-Only for now; frame-ancestors is ignored in Report-Only mode, so X-Frame-Options does the real anti-framing.
    CSP_REPORT_ONLY = "; ".join([
        "default-src 'self'",
        "script-src 'self' 'unsafe-inline' https://unpkg.com https://cdn.jsdelivr.net https://translate.google.com https://translate.googleapis.com https://www.gstatic.com https://www.googletagmanager.com",
        "style-src 'self' 'unsafe-inline' https://unpkg.com https://cdn.jsdelivr.net https://fonts.googleapis.com https://translate.googleapis.com https://www.gstatic.com",
        "font-src 'self' data: https://fonts.gstatic.com",
        "img-src 'self' data: blob: https:",
        "media-src 'self' blob: https:",
        "connect-src 'self' https://api.rainviewer.com https://tilecache.rainviewer.com https://tiles.openfreemap.org https://tiles.versatiles.org https://services.swpc.noaa.gov https://unpkg.com https://cdn.jsdelivr.net https://translate.googleapis.com https://translate-pa.googleapis.com https://www.google-analytics.com https://*.google-analytics.com https://www.googletagmanager.com",
        "frame-src 'self' https://www.youtube-nocookie.com https://www.youtube.com https://rumble.com https://t.me https://translate.google.com",
        "worker-src 'self' blob:",
        "manifest-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'self'",
    ])
    SECURITY_HEADERS = (("Strict-Transport-Security", "max-age=15552000"), ("X-Frame-Options", "SAMEORIGIN"),
                        ("X-Content-Type-Options", "nosniff"), ("Referrer-Policy", "strict-origin-when-cross-origin"),
                        ("Content-Security-Policy-Report-Only", CSP_REPORT_ONLY))
    def end_headers(self):
        try:
            sent = b"".join(getattr(self, "_headers_buffer", []) or []).lower()
            for k, v in self.SECURITY_HEADERS:
                if (k.lower() + ":").encode() not in sent: self.send_header(k, v)
        except Exception: pass
        return super().end_headers()
    def body(self):
        n = min(int(self.headers.get("Content-Length") or 0), 2_000_000 if self.path.startswith("/api/reports/") else 16000 if self.path.startswith("/api/report") else 10000)
        self._raw = self.rfile.read(n)   # kept for add-ons that accept form posts (newsletter: no-JS forms, RFC 8058 one-click unsubscribe)
        try: return json.loads(self._raw or b"{}")
        except Exception: return {}
    def authed(self, d):
        ip = self.ip(); t = time.time()
        fails[ip] = [x for x in fails.get(ip, []) if t - x < 600]
        if len(fails[ip]) >= 5: return "locked"
        given = str(d.get("passcode") or self.headers.get("X-Admin-Passcode") or "")
        if given and hmac.compare_digest(given.encode(), passcode().encode()): return "ok"
        fails[ip].append(t); return "bad"

    TAB_PATHS = set("wire noise thread broadcasts streams radio network grid ai solar heatmap midterms spacex figures preppers tips weather trends "
                    "politics gunlaws finance jets medical resources bushcraft intel ranked games government maps".split())
    def not_found_page(self, path):
        """t347: a dashboard tab name typed as a path (/maps) -> 302 to /#maps; any other unknown non-API path -> the HTML 404 page.
        API / internal paths keep their JSON 404. Returns True if a response was sent."""
        if path.startswith(("/api/", "/internal/")): return False
        seg = path.strip("/").lower()
        if seg == "elon": seg = "figures"   # t353: the old Elon Musk tab is now Key Figures
        if seg == "ready":   # seo/ready-hub: /ready is a real page (ready.py); variants like /ready/ or /READY 301 to /ready (keep ?utm_*)
            q = urlparse(self.path).query
            self.send_response(301); self.send_header("Location", "/ready" + ("?" + q if q else "")); self.send_header("Content-Length", "0")
            self.send_header("Cache-Control", "public, max-age=3600"); self.end_headers(); return True
        if seg in self.TAB_PATHS:
            q = urlparse(self.path).query   # seo/batch-1: keep ?utm_* (and any other query) through the tab redirect
            self.send_response(302); self.send_header("Location", "/" + ("?" + q if q else "") + "#" + seg); self.send_header("Content-Length", "0")
            self.send_header("Cache-Control", "no-store"); self.end_headers(); return True
        try:
            import bn_extras; self.send(404, bn_extras.page_404(path), "text/html"); return True
        except Exception: return False

    def do_GET(self):
        u = urlparse(self.path); qs = parse_qs(u.query)
        try:
            if u.path in ("/", "/index.html"):
                return self.send(200, dashboard_page(), "text/html")
            if u.path == "/api/state": return self.send(200, api_state())
            if u.path == "/api/health":
                return self.send(200, {"ok": True, "scanning": state["scanning"], "last_scan": state["last_scan"], "interval_minutes": cfg()["interval_minutes"]})
            if u.path == "/api/settings": return self.send(200, public_settings())
            if u.path == "/api/config": return self.send(200, {"interval_minutes": cfg()["interval_minutes"], "allowed": ALLOWED})
            if u.path == "/api/jets": return self.send(200, {**jets.api_state(cfg()), "sampler": jet_state})
            if u.path in ("/api/jet_spikes/new", "/api/jet_spikes"):
                since = (qs.get("since") or [None])[0]
                sd = scanner.parse_t(since) if since else scanner.now() - timedelta(hours=1 if u.path.endswith("new") else 24 * 30)
                if not sd: return self.send(400, {"error": "since must be ISO-8601, e.g. 2026-10-29T04:00:00Z"})
                items = jets.new_spikes(sd)
                return self.send(200, {"since": scanner.iso(sd), "now": scanner.iso(scanner.now()), "count": len(items), "items": items,
                                       "note": "Informational only. Jet spikes never change threat ranks/scores."})
            if u.path == "/api/new_high":
                since = (qs.get("since") or [None])[0]
                mn = int((qs.get("min") or [scanner.HIGH])[0])
                mode = (qs.get("mode") or ["alert"])[0]
                sd = scanner.parse_t(since) if since else scanner.now() - timedelta(hours=1)
                if not sd: return self.send(400, {"error": "since must be ISO-8601, e.g. 2026-10-29T04:00:00Z"})
                if mode == "alert":   # push hook: rank >= push_min_rank AND confirmed by >= push_min_sources independent source families
                    cf = cfg(); pr = int(cf.get("push_min_rank", 7)); ps = int(cf.get("push_min_sources", 2))
                    rows = clusters_out(q("""SELECT * FROM clusters WHERE watchlist=0 AND high_at>=? AND rank>=? AND eff_families>=?
                                             ORDER BY rank DESC, score DESC""", (scanner.iso(sd), pr, ps)))
                else:                 # mode=all: every main-feed item with score>=min or rank>=7
                    rows = clusters_out(q("SELECT * FROM clusters WHERE watchlist=0 AND high_at>=? AND (score>=? OR rank>=7) ORDER BY rank DESC, score DESC",
                                          (scanner.iso(sd), mn)))
                return self.send(200, {"since": scanner.iso(sd), "min_score": mn, "mode": mode,
                                       "push_rule": {"push_min_rank": int(cfg().get("push_min_rank", 7)), "push_min_sources": int(cfg().get("push_min_sources", 2))} if mode == "alert" else None, "count": len(rows), "now": scanner.iso(scanner.now()),
                                       "items": [{k: r[k] for k in ("cluster_id", "score", "confidence", "category", "title", "location", "lat", "lon",
                                                                     "event_time", "high_at", "families", "links", "brief", "rank", "rising", "eff_families")} for r in rows]})
            m = addon_for(u.path)
            if m and hasattr(m, "handle_stream"): return m.handle_stream(u.path, qs, self)   # long-lived add-on responses (SSE /api/stream)
            if m:
                r = m.handle_get(u.path, qs)
                if not (r and r[0] == 404 and self.not_found_page(u.path)): return self.send(*r)
                return
            if self.not_found_page(u.path): return
            return self.send(404, {"error": "not found"})
        except (BrokenPipeError, ConnectionResetError): return
        except Exception as ex:
            traceback.print_exc(); return self.send(500, {"error": str(ex)})

    def do_POST(self):
        u = urlparse(self.path); d = self.body()
        try:
            if u.path == "/api/refresh":
                left = REFRESH_COOLDOWN - (time.time() - state["last_manual"])
                if left > 0: return self.send(429, {"status": "rate_limited", "retry_after_s": int(left) + 1})
                if state["scanning"]: return self.send(409, {"status": "busy"})
                state["last_manual"] = time.time()
                r = run_scan("manual")
                wake.set()
                return self.send(200, r)
            if u.path == "/api/interval":
                a = self.authed(d)
                if a != "ok": return self.send(429 if a == "locked" else 403, {"error": "too many attempts, wait 10 min" if a == "locked" else "admin passcode required"})
                try: m = int(d.get("minutes"))
                except Exception: m = None
                if m not in ALLOWED: return self.send(400, {"error": f"minutes must be one of {ALLOWED}"})
                c = cfg(); c["interval_minutes"] = m; save_json(CONFIG, c); wake.set()
                return self.send(200, {"status": "ok", "interval_minutes": m})
            if u.path == "/api/jets/settings":
                a = self.authed(d)
                if a != "ok": return self.send(429 if a == "locked" else 403, {"error": "too many attempts, wait 10 min" if a == "locked" else "admin passcode required"})
                c = cfg()
                if "k" in d:
                    try: k = round(float(d["k"]), 2)
                    except Exception: k = None
                    if k is None or not (jets.K_MIN <= k <= jets.K_MAX): return self.send(400, {"error": f"k must be between {jets.K_MIN} and {jets.K_MAX}"})
                    c["jet_spike_k"] = k
                if "enabled" in d: c["jet_spike_alerts_enabled"] = bool(d["enabled"])
                save_json(CONFIG, c)
                return self.send(200, {"status": "ok", "jet_spike_k": c.get("jet_spike_k", 2.0), "jet_spike_alerts_enabled": c.get("jet_spike_alerts_enabled", True)})
            if u.path == "/api/settings":
                a = self.authed(d)
                if a != "ok": return self.send(429 if a == "locked" else 403, {"error": "too many attempts, wait 10 min" if a == "locked" else "admin passcode required"})
                n = notify()
                if "phone" in d and str(d["phone"]).strip() != "":
                    p = norm_phone(str(d["phone"]))
                    if not p: return self.send(400, {"error": "Phone must be a valid US 10-digit number, e.g. (555) 555-0100"})
                    n["phone"] = p
                if d.get("clear_phone"): n["phone"] = ""
                ch = d.get("channels") or {}
                for k in ("sms", "email", "app"):
                    if k in ch: n["channels"][k] = bool(ch[k])
                if n["channels"]["sms"] and not n["phone"]:
                    return self.send(400, {"error": "Save a valid phone number before enabling SMS"})
                n["updated"] = scanner.iso(scanner.now())
                save_json(NOTIFY, n, 0o600)
                return self.send(200, {"status": "saved", **public_settings()})
            m = addon_for(u.path)
            if m and hasattr(m, "handle_post"):
                import inspect
                sig = inspect.signature(m.handle_post).parameters
                if "headers" in sig:   # newsletter: same-origin check, query-string token, raw form body
                    return self.send(*m.handle_post(u.path, d if isinstance(d, dict) else {}, ip=self.ip(), qs=parse_qs(u.query),
                                                    headers={k.lower(): v for k, v in self.headers.items()}, raw=getattr(self, "_raw", b"")))
                if "ip" in sig: return self.send(*m.handle_post(u.path, d, ip=self.ip()))   # in-memory rate limiting only
                return self.send(*m.handle_post(u.path, d))
            return self.send(404, {"error": "not found"})
        except Exception as ex:
            traceback.print_exc(); return self.send(500, {"error": str(ex)})

if __name__ == "__main__":
    passcode()
    if not os.path.exists(CONFIG): save_json(CONFIG, {"interval_minutes": 60})
    if not os.path.exists(NOTIFY): save_json(NOTIFY, NOTIFY_DEFAULT, 0o600)
    threading.Thread(target=scheduler, daemon=True).start()
    threading.Thread(target=jet_loop, daemon=True).start()
    try: import newsletter; newsletter.ensure_worker(force=True)   # newsletter scheduler: separate light process (newsletter_worker.py)
    except Exception: traceback.print_exc()
    print(f"Blackout dashboard on http://127.0.0.1:{PORT}", flush=True)
    ThreadingHTTPServer.daemon_threads = True
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
