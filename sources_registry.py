"""BLACKOUT.NETWORK registry-driven sources (2026-11-27, pt1961u: "add 1000 sources ... way more volume, way faster").

One scanner source ("Registry feeds ...") backed by a JSON registry of feeds. The registry is pulled from the public repo
(branch `registry-data`, file sources_registry.json) every ~10 min and cached on disk, with a bundled copy next to this module
as the fallback, so new feeds need NO Mac paste. Feeds are fetched by a background thread (24 workers, 8 s timeout, <=2 requests
per host at a time, ETag/Last-Modified), parsed into scanner items, and handed to the scan in capped batches, so the scan itself
never waits on them. Public RSS/Atom/JSON/HTML previews only: no keys, no logins, no scraping behind bot checks, no X.

Feed types: rss (RSS/Atom/RDF, YouTube/Mastodon tag RSS), bsky, mastodon, telegram, statuspage, kev, gdelt2, ll2, jetstream.
v5.2: v5.1, plus the feed cycle waits for SCAN_LOCK (1s poll, 180s timeout) instead of skip-and-sleep-15s, which
starved every cycle when scans ran back-to-back and left only a short gap. After the timeout the cycle still runs (it
only fills the in-memory pending queue; the scan drains it). First-scan wait is also bounded to 180s.
Modes: all (forced category; obituaries, patents), threat (news: threat keywords + classifier), classify (official), crime.
Kill switches: env BN_SOURCES_REGISTRY=0, file `sources_registry_off`, `off: true` on a feed, or ids in sources_registry_disabled.json.
Does not touch scoring, ingest_items, push.py, jets.py or config.json. GNews items use news_item-like base 15; other news stays 6 unless BOOST_RX.
"""
import os, re, json, time, hashlib, threading, html, ipaddress, socket, traceback, functools
from urllib.parse import urlparse, quote, urljoin
from datetime import timedelta, datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
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

def _http(f, url, accept="application/rss+xml, application/atom+xml, application/xml, text/xml, application/json, text/html;q=0.5, */*;q=0.3", conditional=True):
    st = _state["feeds"].setdefault(f["id"], {})
    h = {"User-Agent": f.get("ua") or UA, "Accept": accept}
    key = "et:" + url
    key2 = "lm:" + url
    if conditional:
        if st.get(key) and st.get("body_ok"): h["If-None-Match"] = st[key]
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
    for k in ("pubDate", "pubdate", "published", "updated", "date", "dc:date", "created", "issued", "modified", "sent", "isoDate"):
        v = e.get(k)
        if v:
            t = S.parse_t(v)
            if t: return t
    return None

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

def _publisher(e, link=""):
    return _domain(e.get("source@url") or e.get("source_url") or "") or _domain(link)

def _headline_from_url(url):
    """Turn a SOURCEURL path slug into a merge-friendly headline; None if it is not a usable slug."""
    try:
        from urllib.parse import unquote
        path = unquote(urlparse(url or "").path or "").rstrip("/")
        slug = path.split("/")[-1] if path else ""
        slug = re.sub(r"\.(html?|amp|cms|story|shtml|aspx?)$", "", slug, flags=re.I)
        slug = re.sub(r"[-_]+", " ", slug).strip()
        slug = re.sub(r"^\d{6,}\s*", "", slug)
        if len(slug) < 24 or slug.lower() in ("index", "article", "story", "news", "post", "index.html"):
            return None
        if slug.isupper() or slug.isdigit():
            return None
        return slug[0].upper() + slug[1:] if slug[0].islower() else slug
    except Exception:
        return None

def _scan_busy():
    lk = getattr(S, "SCAN_LOCK", None)
    if lk is None: return False
    locked = getattr(lk, "locked", None)
    if callable(locked):
        try: return bool(locked())
        except Exception: pass
    got = lk.acquire(blocking=False)
    if got:
        try: lk.release()
        except Exception: pass
        return False
    return True

SCAN_WAIT_S = float(os.environ.get("BN_REG_SCAN_WAIT_S", "180") or 180)

def _wait_scan(timeout=None, *, waiting="", still="", done="", timedout="", idle=""):
    """Block until SCAN_LOCK is free, or timeout. Returns True if the lock is free."""
    if timeout is None:
        timeout = SCAN_WAIT_S
    if not _scan_busy():
        if idle:
            print(idle, flush=True)
        return True
    if waiting:
        print(waiting, flush=True)
    t0 = last = time.time()
    while _scan_busy():
        if time.time() - t0 >= timeout:
            if timedout:
                print(timedout, flush=True)
            return False
        if time.time() - last >= 20:
            msg = still or "registry: still waiting for the scan to finish"
            print(f"{msg} ({time.time() - t0:.0f}s)", flush=True)
            last = time.time()
        time.sleep(1)
    if done:
        print(done, flush=True)
    return True

def _a_rss(f, body):
    out = []; cap = int(f.get("cap", 8)); tier = f.get("tier", "news"); mode = f.get("mode") or ("threat" if tier == "news" else "classify")
    is_gnews = "news.google.com" in (f.get("url") or "") or str(f.get("fam") or "").startswith("agg:gnews")
    maxage = float(f.get("maxage_d", 2))
    if is_gnews: maxage = max(maxage, 2)
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
            pub = _publisher(e, link)
            if is_gnews:
                base = max(15, int(f.get("base") or 0) or 15)
                fam = f.get("family") or pub or "GoogleNews"
            else:
                base = int(f.get("base", 10 if tier == "official" else 6))
                fam = f.get("family") or pub or _domain(link) or f["id"]
            if tier != "official" and re.search(getattr(S, "BOOST_RX", r"$^"), title, re.I):
                base = min(40, base + 20)
            out.append(S.item(f["name"], fam, e.get("guid") or e.get("id") or link or title, title, cat, link, t,
                              location=f.get("loc"), base=base, official=(tier == "official"),
                              extra={"tier": "official" if tier == "official" else "news", "publisher": pub or _domain(link), "desc": desc[:300], "registry": f["id"]}))
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
    st = _state["feeds"].setdefault(f["id"], {})
    raw = body if body and b"export.CSV.zip" in (body if isinstance(body, bytes) else b"") else _http(f, f["url"], "text/plain", conditional=False)
    if not raw: return []
    text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
    export = None
    for ln in text.splitlines():
        if "export.CSV.zip" in ln:
            export = ln.split()[-1].replace("http://", "https://"); break
    if not export or not _safe_url(export): return []
    # same 15-min file already parsed this process — do not re-emit (conditional GET on lastupdate was wrongly returning [])
    if st.get("gdelt_export") == export:
        return []
    zbody = _http(f, export, "application/zip", conditional=False)
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
        space = bool(re.search(r"\b(iss|astronauts?|spacecraft|satellites?|spacex|nasa|artemis|starship)\b|orbital debris|re-?entr(y|ies|ing)?", url, re.I))
        if not (root in ("13","14","15","16","17","18","19","20") or ns >= 4 or gs <= -5 or space):
            continue
        scored.append((ns, -gs, p))
    scored.sort(reverse=True)
    now = S.now()
    for ns, _ngs, p in scored:
        actor1, actor2 = (p[6] or "").title(), (p[16] or "").title()
        geo = p[53] or p[36] or ""
        verb = _CAMEO.get(p[28], "event")
        slug = _headline_from_url(p[60])
        if slug:
            title = slug
        else:
            title = " ".join(x for x in (actor1, verb, actor2) if x).strip() or "GDELT event"
            if geo: title = f"{title} — {geo}"
        if _dedupe_title(title) or _dedupe_title(p[60]): continue
        t = S.parse_t(re.sub(r"^(\d{4})(\d\d)(\d\d)(\d\d)(\d\d)(\d\d)$", r"\1-\2-\3T\4:\5:\6Z", p[59] or "")) or now
        cat = "space" if re.search(r"\b(iss|astronauts?|spacecraft|satellites?|spacex|nasa|artemis|starship)\b|orbital debris|re-?entr(y|ies|ing)?", (p[60] or "")+" "+title, re.I) else _CAMEO_CAT.get(p[28]) or S.classify(title + " " + (slug or ""), "other")
        if cat == "other": cat = "political"
        out.append(S.item("GDELT 2.0 events", "GDELT", p[0], title[:280], cat, p[60], t,
                          location=geo, base=int(f.get("base", 8)), official=False,
                          extra={"tier": "aggregate", "goldstein": p[30], "sources": p[32], "root": p[28], "registry": f["id"], "via": "gdelt2"}))
        if len(out) >= cap: break
    st["gdelt_export"] = export
    st["gdelt_n"] = len(out)
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
            # "{name} (status) — pad" merges with SpaceNews / NASA headlines better than "Launch launch successful: ..."
            status = st or "scheduled"
            title = name + (f" ({status})" if status.lower() not in name.lower() else "") + (f" — {pad}" if pad else "")
            if _dedupe_title(title): continue
            url = L.get("url") or L.get("news_url") or "https://thespacedevs.com/"
            out.append(S.item("Launch Library 2", "LaunchLibrary", str(L.get("id") or title), title[:280], "space", url, t,
                              location=pad, base=max(15, int(f.get("base") or 0) or 15), official=False,
                              extra={"tier": "aggregate", "status": st, "registry": f["id"], "via": "ll2"}))
            seen += 1
            if seen >= cap: return out
    return out

# ---------------------------------------------------------------- Bluesky Jetstream (public websocket, no account). Keyword-filtered only.
# Tight keep-filter (word-bounded "hack" so Hacksaw does not match; drop job listings, ham-radio chatter,
# and non-English unless a high-signal token is present). Client frames are masked; pings get pongs so the
# socket stays open across cycles instead of closing after the first kept post.
_JS_HOSTS = ("jetstream2.us-east.bsky.network", "jetstream1.us-east.bsky.network", "jetstream2.us-west.bsky.network", "jetstream1.us-west.bsky.network")
_JS_PATH = "/subscribe?wantedCollections=app.bsky.feed.post"
_JS_RX = re.compile(
    r"\b(killed|dead|deaths?|casualt|injur(?:y|ed|ies)|wounded|evacuat\w*|missile|airstrike|strikes?|attacks?|attacked|"
    r"shelling|drones?|troops|invasion|\bwar\b|explosion|blast|outbreak|epidemic|riot|clashes|unrest|curfew|"
    r"sanction|emergency|martial law|coup|earthquake|tsunami|flood|cyclone|hurricane|typhoon|wildfire|eruption|"
    r"ransomware|\bhacks?\b|\bhacked\b|\bhackers?\b|\bhacking\b|data breach|breached|cyber(?:attack|security)?|"
    r"terror|hostage|shooting|gunman|nuclear|radiation|chemical spill|derail|"
    r"ebola|marburg|h5n1|bird flu|cholera|mpox|measles|hijack|shot down|ceasefire|assassinat|"
    r"iss\b|astronaut|spacex|starship|falcon 9|soyuz|shenzhou|ariane|re-?entr|orbital debris|conjunction|"
    r"eva\b|spacewalk|docking)\b", re.I)
_JS_JOB = re.compile(r"\b(hiring|we['’]re hiring|now hiring|job openings?|apply (now|today|here)|open positions?|job listings?|job alerts?|looking for work|submit (your )?resume|we are hiring)\b", re.I)
_JS_HAM = re.compile(r"\b(baofeng|ham radio|amateurradio|hamradio|\bqrp\b|ft-?8\b|ft-?991|d-?star|\bcq dx\b|ham operators?|repeater net)\b", re.I)
_JS_SIGNAL = re.compile(r"\b(cve-\d{4}-\d+|ransomware|earthquake|magnitude\s+\d|astronaut|spacex|starship|\biss\b|data breach|nuclear|missile)\b", re.I)

def _js_english_or_signal(text):
    if _JS_SIGNAL.search(text or ""): return True
    if re.search(r"[\u0400-\u04FF\u0600-\u06FF\u3040-\u30FF\u3400-\u9FFF\uAC00-\uD7AF]", text or ""):
        if len(re.findall(r"[A-Za-z]", text)) < 48: return False
    try:
        from langdetect import detect
        return detect(text) == "en"
    except Exception:
        return len(re.findall(r"[A-Za-z]", text or "")) >= 20

_JS_WEAK = re.compile(r"\b(merch(?:andise)?|hacking fud|\bfud\b|weekend sale|considering buying|teenage girl hackers?)\b", re.I)
_JS_HACK_ONLY = re.compile(r"\b(hacks?|hacked|hackers?|hacking)\b", re.I)
_JS_HACK_CTX = re.compile(r"\b(ransomware|data|breach|hospital|government|ministr(?:y|ies)|airline|pipeline|power grid|stolen|customers?|database|servers?|cyber(?:attack|security)?|officials?|county|city|agency|cve-|phishing|malware|exploit|password|network)\b", re.I)

def _js_keep(text):
    if not text or len(text) < 20: return False
    if _JS_JOB.search(text) or _JS_HAM.search(text) or _JS_WEAK.search(text): return False
    if not _JS_RX.search(text): return False
    # bare "hack/hackers/hacking" without a serious context token is chatter or merch
    if _JS_HACK_ONLY.search(text):
        rest = _JS_HACK_ONLY.sub(" ", text)
        if not _JS_RX.search(rest) and not _JS_HACK_CTX.search(text):
            return False
    if not _js_english_or_signal(text): return False
    return True

def _js_send(sock, opcode, payload=b""):
    """RFC 6455 client frame (must be masked). opcode 0x9 ping, 0xA pong, 0x8 close."""
    import os
    mask = os.urandom(4)
    ln = len(payload)
    hdr = bytes([0x80 | (opcode & 0x0F)])
    if ln < 126:
        hdr += bytes([0x80 | ln])
    elif ln < 65536:
        hdr += bytes([0x80 | 126]) + ln.to_bytes(2, "big")
    else:
        hdr += bytes([0x80 | 127]) + ln.to_bytes(8, "big")
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    sock.sendall(hdr + mask + masked)

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
    if ln > 1_000_000: raise ValueError("frame too big")
    if masked:
        need(4); mask = buf[:4]; buf = buf[4:]
    need(ln); data, buf = buf[:ln], buf[ln:]
    if masked:
        data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    return opcode, data, buf

def _js_tcp_keepalive(sock):
    import sys
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        if sys.platform == "darwin":
            sock.setsockopt(socket.IPPROTO_TCP, getattr(socket, "TCP_KEEPALIVE", 0x10), 30)
        else:
            if hasattr(socket, "TCP_KEEPIDLE"):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30)
            if hasattr(socket, "TCP_KEEPINTVL"):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
            if hasattr(socket, "TCP_KEEPCNT"):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
    except Exception:
        pass

def _js_connect(host):
    import ssl, os, base64, socket as _socket
    raw = _socket.create_connection((host, 443), timeout=15)
    _js_tcp_keepalive(raw)
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
    ss.settimeout(45)
    return ss, rest

def _jetstream_loop():
    import sources_ext as X
    if os.environ.get("BN_JETSTREAM", "1") == "0":
        print("registry: jetstream off (BN_JETSTREAM=0)", flush=True); return
    print("registry: jetstream starting", flush=True)
    hi = 0; backoff = 5; fails_this_host = 0
    while True:
        host = _JS_HOSTS[hi % len(_JS_HOSTS)]
        kept = 0
        try:
            sock, buf = _js_connect(host)
            print(f"registry: jetstream connected {host}", flush=True)
            backoff = 5; n_min = 0; window = time.time(); kept = 0; last_ping = time.time(); last_hb = time.time()
            fails_this_host = 0
            while True:
                try:
                    op, data, buf = _js_recv(sock, buf)
                except socket.timeout:
                    # keep the socket alive across quiet stretches
                    if time.time() - last_ping >= 20:
                        try: _js_send(sock, 0x9, b"kb")
                        except Exception: raise ConnectionError("ping failed")
                        last_ping = time.time()
                    if time.time() - last_hb >= 30:
                        print(f"registry: jetstream alive kept {kept} on {host}", flush=True); last_hb = time.time()
                    continue
                if time.time() - last_hb >= 30:
                    print(f"registry: jetstream alive kept {kept} on {host}", flush=True); last_hb = time.time()
                if op == 0x9:                      # ping -> pong (missing this was closing the socket after ~1 kept post)
                    try: _js_send(sock, 0xA, data)
                    except Exception: raise ConnectionError("pong failed")
                    last_ping = time.time(); continue
                if op == 0xA: continue
                if op == 0x8: raise ConnectionError("peer close")
                if op != 0x1: continue
                try: ev = json.loads(data)
                except Exception: continue
                rec = ((ev.get("commit") or {}).get("record")) or {}
                if rec.get("$type") not in (None, "app.bsky.feed.post"):
                    if rec.get("$type") and "feed.post" not in rec.get("$type", ""): continue
                text = rec.get("text") or ""
                if not _js_keep(text): continue
                nowm = time.time()
                if nowm - window >= 60: n_min = 0; window = nowm
                if n_min >= 40: continue          # cap 40 kept posts/min so the firehose cannot flood ingest
                did = ev.get("did") or ""
                rkey = ((ev.get("commit") or {}).get("rkey")) or ev.get("time_us") or str(int(nowm))
                uri = f"at://{did}/app.bsky.feed.post/{rkey}"
                t = S.parse_t(rec.get("createdAt")) or S.now()
                it = X.social_item(f"Bluesky firehose", uri, text[:280], f"https://bsky.app/profile/{did}/post/{rkey}", t, [], text,
                                   extra={"tier": "social", "via": "jetstream"})
                if it and not _dedupe_title(text[:200]):
                    _enqueue([it]); n_min += 1; kept += 1
                    if kept == 1 or kept % 10 == 0:
                        print(f"registry: jetstream kept {kept} on {host}", flush=True)
            try: sock.close()
            except Exception: pass
        except Exception as ex:
            print(f"registry: jetstream {host} {type(ex).__name__}: {ex}"[:200], flush=True)
            if kept > 0:
                # had traffic on this host; reconnect here after a short pause, do not hop
                time.sleep(2); backoff = 5
            else:
                fails_this_host += 1
                if fails_this_host >= 2:
                    hi += 1; fails_this_host = 0
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
    ty = f.get("type") or "rss"
    # family hint so GNews / GDELT / LL2 show up as their own buckets in the cycle log
    if ty == "rss" and (str(f.get("fam") or "").startswith("agg:gnews") or "news.google.com" in (f.get("url") or "")):
        ty = "gnews"
    try:
        items = _fetch_feed(f)
        st.update(ok=True, fails=0, err=None, last_ok=now, next=now + float(f.get("iv") or DEFAULT_IV.get(f.get("tier", "news"), 300)))
        if items is None: st["n"] = st.get("n", 0); return 0, True, ty, "notmod"
        st["n"] = len(items); st["last_items"] = now if items else st.get("last_items")
        _enqueue(items)
        return len(items), True, ty, "ok"
    except Exception as ex:
        fails = st.get("fails", 0) + 1
        st.update(ok=False, fails=fails, err=f"{type(ex).__name__}: {str(ex)[:120]}", n=0, next=now + (900 if fails < 3 else 3600 if fails < 6 else 21600))
        return 0, False, ty, "fail"

def _cycle():
    # Rotation is intended: only feeds whose interval has elapsed are fetched, capped at 600, so later
    # cycles show 36-117 of ~1298. First fill takes a few cycles (next=0 for not-yet-fetched feeds).
    # Do not skip-and-return: the 15s loop sleep can miss a short gap between back-to-back scans and
    # starve every cycle. Wait for SCAN_LOCK (1s poll, 180s cap), then run. If the lock never drops
    # (overlapping scans), run anyway — fetch only fills the in-memory pending queue; the scan drains it.
    if _scan_busy():
        free = _wait_scan(
            waiting="registry cycle: scan in progress; waiting for it to finish",
            still="registry cycle: still waiting for the scan",
            done="registry cycle: scan finished; starting",
            timedout="registry cycle: scan still running after 180s; starting anyway (pending queue only, no DB writes)",
        )
        if free:
            time.sleep(0.5)
    reg = _load_registry(); feeds = reg["feeds"]; now = time.time()
    due = [f for f in feeds if _state["feeds"].get(f["id"], {}).get("next", 0) <= now]
    due.sort(key=lambda f: _state["feeds"].get(f["id"], {}).get("next", 0))
    due = due[:600]
    if not due: return
    t0 = time.time()
    print(f"registry cycle: starting {len(due)} due of {len(feeds)}", flush=True)
    res = []; last_prog = t0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(_do, f) for f in due]
        for i, fut in enumerate(as_completed(futs), 1):
            res.append(fut.result())
            if time.time() - last_prog >= 20 or i == len(due):
                print(f"registry cycle: progress {i}/{len(due)} in {time.time() - t0:.0f}s", flush=True)
                last_prog = time.time()
    new = sum(r[0] for r in res)
    notmod = sum(1 for r in res if r[3] == "notmod")
    empty = sum(1 for r in res if r[1] and r[3] != "notmod" and r[0] == 0)
    by = {}
    for n, ok_f, ty, st in res:
        if n:
            by[ty] = by.get(ty, 0) + n
    ok = sum(1 for f in feeds if _state["feeds"].get(f["id"], {}).get("ok")); bad = sum(1 for f in feeds if _state["feeds"].get(f["id"], {}).get("ok") is False)
    _state.update(ok=ok, fail=bad, n=len(feeds))
    by_s = (", by type: " + ", ".join(f"{k}={v}" for k, v in sorted(by.items(), key=lambda kv: (-kv[1], kv[0])))) if by else ""
    print(f"registry cycle: {len(due)} due of {len(feeds)} in {time.time() - t0:.0f}s, {new} items parsed (304={notmod} empty={empty}), ok={ok} fail={bad}{by_s}", flush=True)
    try:
        h = {f["id"]: {k: v for k, v in _state["feeds"].get(f["id"], {}).items() if k in ("ok", "n", "err", "fails", "last_ok", "last_items")} for f in feeds}
        tmp = HEALTH + ".tmp"; json.dump({"t": time.time(), "ok": ok, "fail": bad, "feeds": h}, open(tmp, "w")); os.replace(tmp, HEALTH)
    except Exception: pass

def _loop():
    print("registry: feed thread started", flush=True)
    for _ in range(45):                      # let the scanner finish importing before the first cycle
        if hasattr(S, "scan"): break
        time.sleep(1)
    # After a restart the first scan grabs SCAN_LOCK a moment later. If we start a 600-feed
    # first pass in that gap, the cycle log only prints at the end (often 4-8 min) and it
    # contends with the scan. Wait for that first scan (bounded: v5.1 waited forever if
    # scans overlapped and never released the lock), with a liveness line every 20 s.
    deadline = time.time() + 90
    saw = False
    while time.time() < deadline:
        if _scan_busy():
            saw = True
            _wait_scan(
                timeout=SCAN_WAIT_S,
                waiting="registry: waiting for the current scan to finish before the first cycle",
                still="registry: still waiting for the scan to finish",
                done="registry: scan finished; starting feed cycles",
                timedout="registry: first scan still running after 180s; starting feed cycles anyway",
            )
            break
        time.sleep(0.5)
    if not saw:
        print("registry: no scan lock seen; starting feed cycles", flush=True)
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
