"""BLACKOUT.NETWORK registry-driven sources (2026-11-27, pt1961u: "add 1000 sources ... way more volume, way faster").

One scanner source ("Registry feeds ...") backed by a JSON registry of feeds. The registry is pulled from the public repo
(branch `registry-data`, file sources_registry.json) every ~10 min and cached on disk, with a bundled copy next to this module
as the fallback, so new feeds need NO Mac paste. Feeds are fetched by a background thread (24 workers, 8 s timeout, <=2 requests
per host at a time, ETag/Last-Modified), parsed into scanner items, and handed to the scan in capped batches, so the scan itself
never waits on them. Public RSS/Atom/JSON/HTML previews only: no keys, no logins, no scraping behind bot checks, no X.

Feed types: rss (RSS/Atom/RDF, also Reddit/Lemmy/YouTube/Mastodon tag RSS), bsky (Bluesky public search), mastodon (public tag
timelines), telegram (t.me/s previews), statuspage (Atlassian /api/v2/incidents.json), kev (CISA KEV JSON).
Modes: all (forced category; obituaries, patents), threat (news: threat keywords + classifier), classify (official), crime.
Kill switches: env BN_SOURCES_REGISTRY=0, file `sources_registry_off`, `off: true` on a feed, or ids in sources_registry_disabled.json.
Does not touch scoring, ingest_items, push.py, jets.py or config.json. Scores stay low (news 6, official 10, social 5).
"""
import os, re, json, time, hashlib, threading, html, ipaddress, socket, traceback, functools
from urllib.parse import urlparse, quote, urljoin
from datetime import timedelta, datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import requests
import scanner as S

HERE = os.path.dirname(os.path.abspath(__file__))
REMOTE = os.environ.get("BN_REGISTRY_URL", "https://raw.githubusercontent.com/4pwtnrvcr7-alt/blackout.network/registry-data/sources_registry.json")
LOCAL = os.path.join(HERE, "sources_registry.json")
CACHE = os.path.join(HERE, "sources_registry_cache.json")
HEALTH = os.path.join(HERE, "sources_registry_health.json")
NAME = "Registry feeds (worldwide, site-hosted)"
UA = "Mozilla/5.0 (compatible; BlackoutNetworkBot/1.0; +https://blackout.network)"
WORKERS = int(os.environ.get("BN_REG_WORKERS", "12") or 12)
TIMEOUT = float(os.environ.get("BN_REG_TIMEOUT", "8") or 8)
REFRESH_REMOTE_S = 600
DRAIN_MAX = int(os.environ.get("BN_REG_DRAIN_MAX", "250") or 250)
PENDING_MAX_AGE_H = 24
PENDING_MAX = int(os.environ.get("BN_REG_PENDING_MAX", "2000") or 2000)
MAX_BYTES = 3_000_000
DEFAULT_IV = {"news": 300, "official": 300, "social": 180}

THREAT = (r"\b(killed|dead|deaths?|casualt|injur|wounded|evacuat|missile|airstrike|strikes?|attack|shelling|drone|troops|invasion|war\b|"
          r"explosion|blast|outbreak|epidemic|virus|infect|riot|clashes|unrest|curfew|sanction|emergency|martial law|coup|"
          r"default|collapse|crash|quake|earthquake|tsunami|flood|cyclone|hurricane|typhoon|wildfire|eruption|volcan|tornado|"
          r"ransomware|hack|breach|outage|blackout|cyber|terror|hostage|shooting|gunman|nuclear|radiation|chemical|spill|derail|"
          r"ebola|marburg|h5n1|bird flu|cholera|mpox|measles|plague|hijack|shot down|warship|navy|nato|ceasefire|mobiliz|"
          r"recall|contamina|explod|fire\b|storm|blizzard|heat ?wave|landslide|avalanche|lockdown|shelter|amber alert|evacuation|"
          r"bank failure|bank run|resign|impeach|assassinat|kidnap|stabbing|manhunt|plane|helicopter|train|bridge collapse|dam )")
NOISE = r"\b(podcast|quiz|recipe|review|opinion|horoscope|crossword|in pictures|watch:|live blog|sport|football|soccer|cricket|nba|nfl|oscar|celebrity|betting|odds|fashion|lifestyle)\b"
CRIMEX = r"\b(homicide|murder\w*|manslaughter|shooting|shot|stabb\w*|kidnap\w*|abduct\w*|robbery|carjack\w*|arson|armed|gunman|hostage|barricade|amber alert|missing (?:child|person)|fatal|killed|dead|manhunt|explosion|bomb threat|lockdown)\b"
SPORTX = r"\b(league|match|tournament|playoffs?|fixture)\b"

_lock = threading.Lock()
_state = {"started": False, "reg": None, "reg_t": 0.0, "remote_t": 0.0, "etag": "", "feeds": {}, "pending": {}, "titles": {}, "ok": 0, "fail": 0, "n": 0}
_hostsem = {}
_hostlk = threading.Lock()

def enabled():
    return os.environ.get("BN_SOURCES_REGISTRY", "1") != "0" and not os.path.exists(os.path.join(HERE, "sources_registry_off"))

def _disabled_ids():
    try: return set(json.load(open(os.path.join(HERE, "sources_registry_disabled.json"))))
    except Exception: return set()

def _safe_url(u):
    try:
        p = urlparse(u)
        if p.scheme not in ("http", "https") or not p.hostname: return False
        h = p.hostname.lower()
        if h in ("localhost",) or h.endswith((".local", ".internal", ".lan")): return False
        try:
            ip = ipaddress.ip_address(h)
            return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved)
        except ValueError:
            return not any(x in h for x in ("x.com", "twitter.com", "facebook.com", "instagram.com"))
    except Exception:
        return False

def _valid_feed(f):
    return isinstance(f, dict) and f.get("id") and f.get("url") and _safe_url(f["url"]) and (f.get("type") or "rss") in ("rss", "bsky", "mastodon", "telegram", "statuspage", "kev", "gdelt2", "ll2", "jetstream")

# ---------------------------------------------------------------- registry load (remote -> cache -> bundled)
def _read(path):
    try:
        d = json.load(open(path, encoding="utf-8"))
        return d if isinstance(d, dict) and isinstance(d.get("feeds"), list) else None
    except Exception:
        return None

def _load_registry():
    t = time.time()
    if _state["reg"] is not None and t - _state["remote_t"] < REFRESH_REMOTE_S:
        return _state["reg"]
    _state["remote_t"] = t
    reg = None
    try:
        h = {"User-Agent": UA}
        if _state["etag"] and _state["reg"] is not None: h["If-None-Match"] = _state["etag"]
        r = requests.get(REMOTE, headers=h, timeout=15)
        if r.status_code == 304 and _state["reg"] is not None:
            return _state["reg"]
        if r.status_code == 200 and len(r.content) < 20_000_000:
            d = r.json()
            if isinstance(d, dict) and isinstance(d.get("feeds"), list) and len(d["feeds"]) >= 1:
                reg = d; _state["etag"] = r.headers.get("ETag", "")
                try:
                    tmp = CACHE + ".tmp"; open(tmp, "w", encoding="utf-8").write(r.text); os.replace(tmp, CACHE)
                except Exception: pass
    except Exception as ex:
        print(f"registry: remote fetch failed ({type(ex).__name__}); using cache/bundled", flush=True)
    if reg is None: reg = _state["reg"] or _read(CACHE) or _read(LOCAL) or {"feeds": []}
    feeds = [f for f in reg["feeds"] if _valid_feed(f)]
    off = _disabled_ids()
    reg = {**reg, "feeds": [f for f in feeds if not f.get("off") and f["id"] not in off]}
    _state["reg"] = reg
    print(f"registry: {len(reg['feeds'])} feeds loaded (version {reg.get('version')}, generated {reg.get('generated')})", flush=True)
    return reg

# ---------------------------------------------------------------- http
def _sem(host):
    with _hostlk:
        return _hostsem.setdefault(host, threading.BoundedSemaphore(2))

def _http(f, url, accept="application/rss+xml, application/atom+xml, application/xml, text/xml, application/json, text/html;q=0.5, */*;q=0.3"):
    st = _state["feeds"].setdefault(f["id"], {})
    h = {"User-Agent": f.get("ua") or UA, "Accept": accept}
    key = "et:" + url
    if st.get(key) and st.get("body_ok"): h["If-None-Match"] = st[key]
    key2 = "lm:" + url
    if st.get(key2) and st.get("body_ok"): h["If-Modified-Since"] = st[key2]
    host = urlparse(url).hostname or ""
    with _sem(host):
        r = requests.get(url, headers=h, timeout=(5, TIMEOUT), stream=True, allow_redirects=True)
        if r.status_code == 304: r.close(); return None
        r.raise_for_status()
        body = b""
        for chunk in r.iter_content(65536):
            body += chunk
            if len(body) > MAX_BYTES: break
        r.close()
    st[key] = r.headers.get("ETag", ""); st[key2] = r.headers.get("Last-Modified", ""); st["body_ok"] = True
    return body

def _norm(t): return re.sub(r"[^a-z0-9 ]", "", (t or "").lower())[:90]

def _t(e):
    return S.parse_t(e.get("pubDate") or e.get("updated") or e.get("published") or e.get("date") or e.get("created") or e.get("sent"))

def _dedupe_title(title):
    k = _norm(title)
    if len(k) < 20: return False
    now = time.time()
    with _lock:
        tt = _state["titles"]
        if len(tt) > 20000:
            for kk in [x for x, v in tt.items() if now - v > 21600]: tt.pop(kk, None)
        if k in tt and now - tt[k] < 21600: return True
        tt[k] = now
    return False

def _domain(u):
    try:
        d = urlparse(u).netloc.lower(); return d[4:] if d.startswith("www.") else d
    except Exception: return ""


def _enqueue(items):
    """Newest items into the pending drain queue; cap so a firehose cannot grow memory without bound."""
    if not items: return
    now = time.time()
    with _lock:
        for it in items:
            _state["pending"][it["id"]] = (now, it)
        if len(_state["pending"]) > PENDING_MAX:
            extra = sorted(_state["pending"].items(), key=lambda kv: kv[1][0])
            for k,_ in extra[:len(_state["pending"]) - PENDING_MAX]:
                _state["pending"].pop(k, None)

# ---------------------------------------------------------------- adapters
def _a_rss(f, body):
    out = []; maxage = float(f.get("maxage_d", 2)); cap = int(f.get("cap", 8)); tier = f.get("tier", "news"); mode = f.get("mode") or ("threat" if tier == "news" else "classify")
    now = S.now(); seen = 0
    for e in S.rss_items(body):
        t = _t(e)
        if not t or t < now - timedelta(days=maxage) or t > now + timedelta(hours=6): continue
        title = S.strip(e.get("title")); desc = S.strip(e.get("description") or e.get("summary") or e.get("content") or e.get("encoded"))[:600]
        if not title or len(title) < 8: continue
        text = title + " " + desc
        if f.get("inc") and not re.search(f["inc"], text, re.I): continue
        if f.get("exc") and re.search(f["exc"], text, re.I): continue
        link = e.get("link") or e.get("guid") or f.get("home") or f["url"]
        if mode == "all":
            cat = f.get("cat") or S.classify(text, "other")
        elif mode == "crime":
            if not re.search(CRIMEX, text, re.I) or re.search(NOISE, title, re.I): continue
            cat = "crime"
        else:
            if re.search(NOISE, title, re.I) or (re.search(SPORTX, title, re.I) and not re.search(THREAT, title, re.I)): continue
            cat = S.classify(text, "other")
            if cat == "other" and not f.get("cat") and (tier == "news" or not re.search(THREAT, text, re.I)): continue
            if cat == "other": cat = f.get("cat") or "other"
            if mode == "threat" and not re.search(THREAT, title, re.I) and cat == "other": continue
        if cat == "other" and mode != "all": continue
        if _dedupe_title(title): continue
        if tier == "social":
            import sources_ext as X
            it = X.social_item(f["name"], e.get("guid") or e.get("id") or link, title[:280], link, t, [link] if _domain(link) else [], desc, base=int(f.get("base", 5)),
                               default_cat=cat if cat != "other" else "other", media_flag="youtube.com" in link or "youtu.be" in link)
            if it: out.append(it)
        else:
            base = int(f.get("base", 10 if tier == "official" else 6))
            out.append(S.item(f["name"], f.get("family") or _domain(link) or f["id"], e.get("guid") or e.get("id") or link or title, title, cat, link, t,
                              location=f.get("loc"), base=base, official=(tier == "official"),
                              extra={"tier": "official" if tier == "official" else "news", "publisher": _domain(link), "desc": desc[:300], "registry": f["id"]}))
        seen += 1
        if seen >= cap: break
    return out

def _a_statuspage(f, body):
    j = json.loads(body); out = []
    for inc in (j.get("incidents") or [])[:25]:
        imp = inc.get("impact") or "none"
        t = S.parse_t(inc.get("updated_at") or inc.get("started_at") or inc.get("created_at"))
        if not t or t < S.now() - timedelta(days=2): continue
        if imp in ("none", "minor") and inc.get("status") == "resolved": continue
        if imp == "none": continue
        title = f"{f['name']} outage: {inc.get('name')} ({imp} impact, {inc.get('status')})"
        out.append(S.item(f["name"], f.get("family") or f["id"], inc.get("id"), title, "cyber", inc.get("shortlink") or f.get("home") or f["url"], t,
                          location="Global (internet)", base={"critical": 25, "major": 15}.get(imp, 6), official=True,
                          extra={"impact": imp, "tier": "official", "kind": "service outage", "registry": f["id"]}))
    return out

def _a_kev(f, body):
    j = json.loads(body); out = []
    for v in j.get("vulnerabilities", []):
        t = S.parse_t(v.get("dateAdded"))
        if not t or t < S.now() - timedelta(days=4): continue
        title = f"CISA KEV adds {v.get('cveID')}: {v.get('vendorProject')} {v.get('product')} - {v.get('vulnerabilityName')}"
        out.append(S.item(f["name"], "CISA", v.get("cveID"), title, "cyber", "https://www.cisa.gov/known-exploited-vulnerabilities-catalog", t,
                          location="United States", base=22 + (8 if str(v.get("knownRansomwareCampaignUse")) == "Known" else 0), official=True,
                          extra={"tier": "official", "cve": v.get("cveID"), "registry": f["id"]}))
    return out

def _a_bsky(f, body=None):
    import sources_ext as X
    out = []
    for q in f.get("queries") or []:
        j = _http_json(f, f"https://api.bsky.app/xrpc/app.bsky.feed.searchPosts?q={quote(q)}&limit=25&sort=latest")
        for p in (j or {}).get("posts") or []:
            try:
                r = p.get("record") or {}; text = r.get("text") or ""
                emb = r.get("embed") or {}
                urls = []
                u0 = (emb.get("external") or {}).get("uri")
                if u0: urls.append(u0)
                for fc in r.get("facets") or []:
                    for ft in (fc or {}).get("features") or []:
                        if (ft or {}).get("uri"): urls.append(ft["uri"])
                media = "images" in json.dumps(emb) or "video" in json.dumps(emb)
                rkey = p["uri"].rsplit("/", 1)[-1]; h = (p.get("author") or {}).get("handle") or "unknown"
                it = X.social_item(f"Bluesky @{h}", p["uri"], text[:280], f"https://bsky.app/profile/{h}/post/{rkey}", S.parse_t(r.get("createdAt")),
                                   urls, text, extra={"query": q}, media_flag=media)
                if it and not _dedupe_title(text[:200]): out.append(it)
            except Exception:
                continue
    return out

def _http_json(f, url):
    b = _http(f, url, "application/json")
    return json.loads(b) if b else None

def _a_mastodon(f, body=None):
    import sources_ext as X
    out = []
    inst = f["url"].rstrip("/")
    for tag in f.get("tags") or []:
        j = _http_json(f, f"{inst}/api/v1/timelines/tag/{quote(tag)}?limit=30") or []
        for st in j:
            try:
                text = S.strip(st.get("content")); urls = [u for u in re.findall(r'href="([^"]+)"', st.get("content") or "") if "/tags/" not in u and "/@" not in u]
                if st.get("card") and st["card"].get("url"): urls.insert(0, st["card"]["url"])
                ct = S.parse_t(st.get("created_at"))
                if ct and ct < S.now() - timedelta(days=1): continue
                it = X.social_item(f"Mastodon @{(st.get('account') or {}).get('acct')}", st["id"], text[:280], st.get("url") or st.get("uri"), ct, urls, text,
                                   extra={"instance": inst}, media_flag=bool(st.get("media_attachments")))
                if it and not _dedupe_title(text[:200]): out.append(it)
            except Exception:
                continue
    return out

def _a_telegram(f, body=None):
    import sources_ext as X
    out = []
    for ch in f.get("channels") or []:
        b = _http(f, f"https://t.me/s/{quote(ch)}", "text/html")
        if not b: continue
        txt = b.decode("utf-8", "replace")
        for blk in txt.split('tgme_widget_message_wrap')[1:][-20:]:
            m = re.search(r'data-post="([^"]+)"', blk); tm = re.search(r'<time[^>]*datetime="([^"]+)"', blk)
            tx = re.search(r'tgme_widget_message_text[^>]*>(.*?)</div>', blk, re.S)
            if not (m and tm and tx): continue
            t = S.parse_t(tm.group(1)); body_t = S.strip(tx.group(1))
            if not t or t < S.now() - timedelta(days=1) or len(body_t) < 25: continue
            urls = re.findall(r'href="(https?://(?!t\.me)[^"]+)"', tx.group(1))
            it = X.social_item(f"Telegram {f.get('label') or ch}", m.group(1), body_t[:280], f"https://t.me/{m.group(1)}", t, urls, body_t,
                               extra={"channel": ch}, media_flag="tgme_widget_message_photo" in blk or "tgme_widget_message_video" in blk)
            if it and not _dedupe_title(body_t[:200]): out.append(it)
    return out


# CAMEO root-code labels for GDELT 2.0 event titles (English, generated; the export file has no headlines)
_CAMEO = {"13":"threatens","14":"protest","15":"military posture","16":"reduces relations","17":"coercion","18":"assault","19":"fight","20":"mass violence",
          "10":"demand","11":"disapproves","12":"rejects","18":"assault"}
_CAMEO_CAT = {"14":"political","17":"war/conflict","18":"war/conflict","19":"war/conflict","20":"war/conflict","13":"war/conflict","15":"war/conflict"}

def _a_gdelt2(f, body=None):
    """GDELT 2.0 15-minute event export (no API key, one zip ~30 KB). Titles are built from CAMEO codes + actors."""
    import zipfile, io
    raw = body if body and b"export.CSV.zip" in (body if isinstance(body, bytes) else b"") else _http(f, f["url"], "text/plain")
    if not raw: return []
    text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
    export = None
    for ln in text.splitlines():
        if "export.CSV.zip" in ln:
            export = ln.split()[-1].replace("http://", "https://"); break
    if not export or not _safe_url(export): return []
    zbody = _http(f, export, "application/zip")
    if not zbody or zbody[:2] != b"PK": return []
    z = zipfile.ZipFile(io.BytesIO(zbody)); rows = z.read(z.namelist()[0]).decode("utf-8", "replace").splitlines()
    cap = int(f.get("cap", 60)); out = []; scored = []
    for ln in rows:
        p = ln.split("\t")
        if len(p) < 61: continue
        root, url = p[28], p[60]
        try:
            ns, nm, gs = int(float(p[32] or 0)), int(float(p[31] or 0)), float(p[30] or 0)
        except Exception:
            continue
        space = bool(re.search(r"iss|astronaut|spacecraft|satellite|re-?entr|launch|spacex|nasa|debris|conjunction", url, re.I))
        if not (root in ("13","14","15","16","17","18","19","20") or ns >= 4 or gs <= -5 or space):
            continue
        scored.append((ns, -gs, p))
    scored.sort(reverse=True)
    now = S.now()
    for ns, _ngs, p in scored:
        actor1, actor2 = (p[6] or "").title(), (p[16] or "").title()
        geo = p[53] or p[36] or ""
        verb = _CAMEO.get(p[28], "event")
        title = " ".join(x for x in (actor1, verb, actor2) if x).strip() or "GDELT event"
        if geo: title = f"{title} — {geo}"
        title = (title + " (GDELT)").replace("  ", " ")
        if _dedupe_title(title) or _dedupe_title(p[60]): continue
        t = S.parse_t(re.sub(r"^(\d{4})(\d\d)(\d\d)(\d\d)(\d\d)(\d\d)$", r"\1-\2-\3T\4:\5:\6Z", p[59] or "")) or now
        cat = "space" if re.search(r"iss|astronaut|spacecraft|satellite|re-?entr|launch|spacex|nasa|debris", p[60]+title, re.I) else _CAMEO_CAT.get(p[28]) or S.classify(title, "other")
        if cat == "other": cat = "political"
        out.append(S.item("GDELT 2.0 events", "GDELT", p[0], title[:280], cat, p[60], t,
                          location=geo, base=int(f.get("base", 8)), official=False,
                          extra={"tier": "aggregate", "goldstein": p[30], "sources": p[32], "root": p[28], "registry": f["id"]}))
        if len(out) >= cap: break
    return out

def _a_ll2(f, body=None):
    """Launch Library 2 public API (thespacedevs), no key. Upcoming + recent launches only."""
    out = []; cap = int(f.get("cap", 20)); seen = 0
    for path in ("launch/upcoming/?limit=15&mode=list", "launch/previous/?limit=15&mode=list"):
        try:
            r = requests.get("https://ll.thespacedevs.com/2.2.0/" + path, headers={"User-Agent": UA, "Accept": "application/json"}, timeout=(5, 20))
            r.raise_for_status(); j = r.json()
        except Exception:
            continue
        for L in j.get("results") or []:
            t = S.parse_t(L.get("net") or L.get("window_start"))
            if not t: continue
            # upcoming within 7 days, or happened in the last 3 days
            if t > S.now() + timedelta(days=7) or t < S.now() - timedelta(days=3): continue
            st_obj = L.get("status")
            st = (st_obj.get("name") if isinstance(st_obj, dict) else (st_obj or "")).strip() if st_obj else ""
            name = L.get("name") or "Launch"
            pad = L.get("pad") or L.get("location") or ""
            if isinstance(pad, dict):
                loc = pad.get("location")
                pad = (loc.get("name") if isinstance(loc, dict) else None) or pad.get("name") or ""
            pad = pad if isinstance(pad, str) else ""
            title = f"Launch {st.lower() or 'update'}: {name}" + (f" — {pad}" if pad else "")
            if _dedupe_title(title): continue
            url = L.get("url") or L.get("news_url") or "https://thespacedevs.com/"
            out.append(S.item("Launch Library 2", "LaunchLibrary", str(L.get("id") or title), title[:280], "space", url, t,
                              location=pad, base=int(f.get("base", 12)), official=False,
                              extra={"tier": "aggregate", "status": st, "registry": f["id"]}))
            seen += 1
            if seen >= cap: return out
    return out

# ---------------------------------------------------------------- Bluesky Jetstream (public websocket, no account). Keyword-filtered only.
_JS_HOSTS = ("jetstream2.us-east.bsky.network", "jetstream1.us-east.bsky.network", "jetstream2.us-west.bsky.network")
_JS_PATH = "/subscribe?wantedCollections=app.bsky.feed.post"
_JS_RX = re.compile(THREAT + r"|\b(iss\b|astronaut|spacex|starship|falcon 9|soyuz|shenzhou|ariane|re-?entr|orbital debris|conjunction|eva\b|spacewalk|docking)\b", re.I)

def _js_recv(sock, buf):
    """Minimal RFC 6455 client reader. Returns (opcode, payload) or raises."""
    def need(n):
        nonlocal buf
        while len(buf) < n:
            c = sock.recv(65536)
            if not c: raise ConnectionError("closed")
            buf += c
        return True
    need(2)
    b1, b2 = buf[0], buf[1]; buf = buf[2:]
    opcode, masked, ln = b1 & 0x0F, b2 & 0x80, b2 & 0x7F
    if ln == 126:
        need(2); ln = int.from_bytes(buf[:2], "big"); buf = buf[2:]
    elif ln == 127:
        need(8); ln = int.from_bytes(buf[:8], "big"); buf = buf[8:]
    if masked:
        need(4); mask = buf[:4]; buf = buf[4:]
    need(ln); data, buf = buf[:ln], buf[ln:]
    if masked:
        data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    if ln > 1_000_000: raise ValueError("frame too big")
    return opcode, data, buf

def _js_connect(host):
    import ssl, os, base64, socket
    raw = socket.create_connection((host, 443), timeout=15)
    ss = ssl.create_default_context().wrap_socket(raw, server_hostname=host)
    key = base64.b64encode(os.urandom(16)).decode()
    req = (f"GET {_JS_PATH} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
           f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\nUser-Agent: {UA}\r\n\r\n")
    ss.sendall(req.encode()); ss.settimeout(30)
    buf = b""
    while b"\r\n\r\n" not in buf:
        c = ss.recv(4096)
        if not c: raise ConnectionError("upgrade closed")
        buf += c
    head, rest = buf.split(b"\r\n\r\n", 1)
    if b" 101 " not in head.split(b"\r\n", 1)[0]: raise ConnectionError(head.split(b"\r\n", 1)[0].decode("latin1")[:120])
    ss.settimeout(60)
    return ss, rest

def _jetstream_loop():
    import sources_ext as X
    if os.environ.get("BN_JETSTREAM", "1") == "0":
        print("registry: jetstream off (BN_JETSTREAM=0)", flush=True); return
    print("registry: jetstream starting", flush=True)
    hi = 0; backoff = 5
    while True:
        host = _JS_HOSTS[hi % len(_JS_HOSTS)]; hi += 1
        try:
            sock, buf = _js_connect(host)
            print(f"registry: jetstream connected {host}", flush=True)
            backoff = 5; n_min = 0; window = time.time(); kept = 0
            while True:
                op, data, buf = _js_recv(sock, buf)
                if op == 0x8: break
                if op == 0x1:
                    try: ev = json.loads(data)
                    except Exception: continue
                    rec = ((ev.get("commit") or {}).get("record")) or {}
                    if rec.get("$type") not in (None, "app.bsky.feed.post"): 
                        if rec.get("$type") and "feed.post" not in rec.get("$type",""): continue
                    text = rec.get("text") or ""
                    if len(text) < 20 or not _JS_RX.search(text): continue
                    nowm = time.time()
                    if nowm - window >= 60: n_min = 0; window = nowm
                    if n_min >= 40: continue          # cap 40 kept posts/min so the firehose cannot flood ingest
                    did = ev.get("did") or ""
                    rkey = ((ev.get("commit") or {}).get("rkey")) or ev.get("time_us") or str(int(nowm))
                    uri = f"at://{did}/app.bsky.feed.post/{rkey}"
                    handle = did[:20]
                    t = S.parse_t(rec.get("createdAt")) or S.now()
                    it = X.social_item(f"Bluesky firehose", uri, text[:280], f"https://bsky.app/profile/{did}/post/{rkey}", t, [], text,
                                       extra={"tier": "social", "via": "jetstream"})
                    if it and not _dedupe_title(text[:200]):
                        _enqueue([it]); n_min += 1; kept += 1
                        if kept % 100 == 1:
                            print(f"registry: jetstream kept {kept} on {host}", flush=True)
            try: sock.close()
            except Exception: pass
        except Exception as ex:
            print(f"registry: jetstream {host} {type(ex).__name__}: {ex}"[:200], flush=True)
            time.sleep(backoff); backoff = min(300, backoff * 2)


def _fetch_feed(f):
    ty = f.get("type") or "rss"
    if ty in ("bsky", "mastodon", "telegram", "ll2", "gdelt2"):
        return {"bsky": _a_bsky, "mastodon": _a_mastodon, "telegram": _a_telegram, "ll2": _a_ll2, "gdelt2": _a_gdelt2}[ty](f)
    if ty == "jetstream":
        return []          # the jetstream thread runs on its own; the feed row is a marker
    body = _http(f, f["url"])
    if body is None: return None
    if ty == "statuspage": return _a_statuspage(f, body)
    if ty == "kev": return _a_kev(f, body)
    return _a_rss(f, body)

# ---------------------------------------------------------------- background worker
def _do(f):
    st = _state["feeds"].setdefault(f["id"], {})
    now = time.time()
    try:
        items = _fetch_feed(f)
        st.update(ok=True, fails=0, err=None, last_ok=now, next=now + float(f.get("iv") or DEFAULT_IV.get(f.get("tier", "news"), 300)))
        if items is None: st["n"] = st.get("n", 0); return 0, True
        st["n"] = len(items); st["last_items"] = now if items else st.get("last_items")
        _enqueue(items)
        return len(items), True
    except Exception as ex:
        fails = st.get("fails", 0) + 1
        st.update(ok=False, fails=fails, err=f"{type(ex).__name__}: {str(ex)[:120]}", n=0, next=now + (900 if fails < 3 else 3600 if fails < 6 else 21600))
        return 0, False

def _cycle():
    reg = _load_registry(); feeds = reg["feeds"]; now = time.time()
    due = [f for f in feeds if _state["feeds"].get(f["id"], {}).get("next", 0) <= now]
    due.sort(key=lambda f: _state["feeds"].get(f["id"], {}).get("next", 0))
    due = due[:600]
    if not due: return
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        res = list(ex.map(_do, due))
    new = sum(r[0] for r in res)
    ok = sum(1 for f in feeds if _state["feeds"].get(f["id"], {}).get("ok")); bad = sum(1 for f in feeds if _state["feeds"].get(f["id"], {}).get("ok") is False)
    _state.update(ok=ok, fail=bad, n=len(feeds))
    print(f"registry cycle: {len(due)} feeds in {time.time() - t0:.0f}s, {new} items parsed, ok={ok} fail={bad} of {len(feeds)}", flush=True)
    try:
        h = {f["id"]: {k: v for k, v in _state["feeds"].get(f["id"], {}).items() if k in ("ok", "n", "err", "fails", "last_ok", "last_items")} for f in feeds}
        tmp = HEALTH + ".tmp"; json.dump({"t": time.time(), "ok": ok, "fail": bad, "feeds": h}, open(tmp, "w")); os.replace(tmp, HEALTH)
    except Exception: pass

def _loop():
    print("registry: feed thread started", flush=True)
    for _ in range(45):                      # let the scanner finish importing before the first cycle
        if hasattr(S, "scan"): break
        time.sleep(1)
    while True:
        try:
            if enabled(): _cycle()
        except Exception:
            traceback.print_exc()
        time.sleep(15)

def start():
    with _lock:
        if _state["started"]: return
        _state["started"] = True
    threading.Thread(target=_loop, name="registry-feeds", daemon=True).start()
    threading.Thread(target=_jetstream_loop, name="registry-jetstream", daemon=True).start()

def f_registry():
    """Scanner source: hands over parsed registry items in capped batches (newest first); never waits on the network."""
    if not enabled(): return []
    start()
    now = time.time(); keep = []
    with _lock:
        pend = _state["pending"]
        for k in [k for k, (t, _) in pend.items() if now - t > PENDING_MAX_AGE_H * 3600]: pend.pop(k, None)
        rows = sorted(pend.items(), key=lambda kv: kv[1][1].get("event_time") or "", reverse=True)[:DRAIN_MAX]
        out = [v[1] for _, v in rows]
        for k, _ in rows: pend.pop(k, None)
    return out

# ---------------------------------------------------------------- overrides for known-bad sources (Nov 27 Mac scan output)
DROP_PREFIXES = ("Reddit public RSS", "Bluesky public search API")

def _guard(fn, min_interval=0, backoff=1800):
    """Keep the function's __name__ (SLOW_FNS matches on it). Skips calls inside min_interval and after a failure."""
    st = {"last": 0.0, "block": 0.0}
    @functools.wraps(fn)
    def w(*a, **k):
        n = time.time()
        if n < st["block"] or (min_interval and n - st["last"] < min_interval): return []
        st["last"] = n
        try:
            return fn(*a, **k)
        except Exception:
            st["block"] = n + backoff; raise
    return w

def apply(ext_sources, ext_failed):
    if not enabled(): return
    try:
        ext_sources[:] = [r for r in ext_sources if not str(r[0]).startswith(DROP_PREFIXES)]
        for i, r in enumerate(list(ext_sources)):
            nm = getattr(r[2], "__name__", "")
            if nm == "f_gdelt": ext_sources[i] = (r[0], r[1], _guard(r[2], 900, 1800))
            elif nm == "f_ioda": ext_sources[i] = (r[0], r[1], _guard(r[2], 0, 1800))
            elif str(r[0]).startswith(("Safecast", "CelesTrak", "UN OCHA")): ext_sources[i] = (r[0], r[1], _guard(r[2], 600, 1800))
        ext_sources.append((NAME, REMOTE, f_registry))
        ext_failed.append(("Reddit public RSS (multireddit, 404 from long URL)", "https://www.reddit.com/r/worldnews+news/new/.rss", "replaced by per-sub registry feeds"))
        ext_failed.append(("Bluesky public search API (old adapter, NoneType crash)", "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts", "replaced by registry bsky adapter"))
        start()                              # fetch thread runs independently of the scan, so the first slow scan cannot delay it
    except Exception as ex:
        ext_failed.append(("[registry] sources_registry module", "sources_registry.py", f"apply failed: {type(ex).__name__}: {ex}"[:300]))
