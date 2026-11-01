"""Sources catalog add-on: GET /sources (catalog page), /sources/admin, /api/sources/* (catalog JSON, queue, dashboard card, static);
POST /api/sources/submit (public "Submit a source" form) and /api/sources/admin[/login] (same admin passcode + session as /newsletter/admin).
Catalog data lives in sources.db (box-owned, built by sources_catalog.py --refresh); public submissions, approvals, discards and
rate-limit state live in source_submissions.db (Render-owned, copied back to the box). blackout.db is only read, via file:blackout.db?mode=ro, by the builder.
Never touches scanner.py, scoring, push.py, jets.py or config.json. Submitter emails are stored for follow-up only and are never shown publicly."""
import os, re, sys, json, time, html, hmac, hashlib, threading, urllib.parse
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path: sys.path.insert(0, BASE)
import sources_catalog as SC
import sources_directory as SD, importlib as _il
SD = _il.reload(SD)   # hot-reload servers: pick up a changed sources_directory.py together with this file

E = lambda s: html.escape(str(s if s is not None else ""), quote=True)
BRAND = "blackout.network"
TAGLINE = "Know first. Be ready."
STATIC = os.path.join(BASE, "sources_static")
TYPES = ["Agency feed", "News outlet", "Research center", "Disease surveillance", "RSS feed", "X account", "Telegram channel", "Mastodon account",
         "Bluesky account", "YouTube channel", "Reddit community", "Other"]
CATS = SC.CATEGORIES
LIMITS = {"name": 120, "url": 500, "why": 1000, "email": 254}
RATE = {"ip_hour": 3, "ip_day": 8, "global_day": 60}
MIN_FILL_S = 3
REFRESH_EVERY_S = 1800

def NL():
    import newsletter
    return newsletter

def now_iso(): return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def h(s, n=16): return hashlib.sha256((s or "").encode()).hexdigest()[:n]

# ---------------------------------------------------------------- background refresh (keeps the catalog current without blocking a request)
_RL = getattr(sys, "_bn_sources_lock", None)
if _RL is None: _RL = sys._bn_sources_lock = threading.Lock()
def maybe_refresh(force=False):
    try:
        k = SC.db(); r = k.execute("SELECT v FROM meta WHERE k='refreshed'").fetchone(); k.close()
        last = datetime.fromisoformat(r[0].replace("Z", "+00:00")).timestamp() if r else 0
    except Exception: last = 0
    if not force and time.time() - last < REFRESH_EVERY_S: return False
    if not _RL.acquire(blocking=False): return False
    def run():
        try: SC.refresh(quiet=True)
        except Exception as ex: print("sources refresh failed:", ex)
        finally: _RL.release()
    if last == 0: run()
    else: threading.Thread(target=run, daemon=True).start()
    return True

# ---------------------------------------------------------------- submission: validation, spam / relevance filter, dedupe, rate limit
ADULT_RX = re.compile(r"\b(porn\w*|xxx|sex(y|cam|chat)?|nsfw|onlyfans|escort\w*|hentai|nude\w*|naked|camgirl\w*|fetish|milf|erotic\w*|adult (site|video|content)|hookup|stripchat|chaturbate|xvideos|pornhub|xhamster|redtube|brazzers|fansly)\b", re.I)
GAMBLING_RX = re.compile(r"\b(casino\w*|betting|sportsbook|bet365|1xbet|stake\.com|rainbet|roobet|slots?|poker|jackpot|roulette|blackjack|baccarat|gambl\w*|bookmaker|free spins|parlay)\b", re.I)
CRYPTO_RX = re.compile(r"(\b(airdrop|presale|pre-sale|memecoin|meme coin|shitcoin|pump(\.fun)?|100x|1000x|to the moon|guaranteed (returns|profit)|double your|free (crypto|btc|bitcoin|eth|usdt)|token launch|ico\b|giveaway|wallet connect|claim (your )?(tokens?|reward))\b)", re.I)
OFFTOPIC_RX = re.compile(r"\b(recipe\w*|fashion|makeup|skincare|dating|horoscope\w*|astrology|celebrity gossip|coupon\w*|discount code|promo code|seo (services|agency)|backlinks?|buy (followers|likes|views)|essay writing|weight loss|diet pills|viagra|cialis|replica watches|loan offer|payday loan|cbd gumm\w*|forex signals?)\b", re.I)
MALWARE_RX = re.compile(r"\b(crack(ed)?|keygen|warez|serial key|free download|apk mod|mod apk|cheat engine|hack tool|account generator|iplogger|grabify)\b", re.I)
SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd", "buff.ly", "cutt.ly", "rebrand.ly", "shorturl.at", "tiny.cc", "rb.gy", "t.ly", "s.id",
              "v.gd", "bl.ink", "short.io", "lnkd.in", "trib.al", "dlvr.it", "ift.tt", "linktr.ee", "grabify.link", "iplogger.org", "iplogger.com", "2no.co", "adf.ly",
              "shorte.st", "ouo.io", "bc.vc", "qr.ae", "soo.gd", "clck.ru"}
BAD_TLDS = {"xxx", "porn", "sex", "adult", "casino", "bet", "poker", "zip", "mov", "click", "loan", "win", "gq", "tk", "ml", "cf", "ga"}
BAD_DOMAINS_RX = re.compile(r"(porn|xxx|sex|casino|bet365|1xbet|betway|slots?|poker|onlyfans|escort|hentai|camgirl|nsfw|airdrop|presale|freecrypto|crack|keygen|warez)", re.I)
BAD_EXT_RX = re.compile(r"\.(exe|scr|msi|bat|cmd|apk|dmg|jar|vbs|ps1|zip|rar|7z|iso)(\?|$)", re.I)
RELEVANT_RX = re.compile(r"\b(news|alerts?|warnings?|agency|ministry|government|official|osint|intel\w*|monitor\w*|tracker|tracking|seismic\w*|seismolog\w*|earthquakes?|quakes?|"
                         r"tsunami|volcan\w*|weather|storms?|hurricanes?|typhoons?|cyclones?|floods?|wildfires?|disasters?|emergenc\w*|relief|humanitarian|security|cyber\w*|"
                         r"vulnerabilit\w*|cve|ransomware|malware|threats?|hack\w*|breach\w*|defen[cs]e|military|war|conflicts?|strikes?|missiles?|drones?|frontline|"
                         r"geopolit\w*|terror\w*|health|outbreaks?|epidem\w*|pandemic|disease\w*|virus\w*|pathogens?|surveillance|biosecurity|vaccin\w*|"
                         r"space weather|solar|geomagnetic|aurora|noaa|nasa|usgs|who|cdc|cisa|fema|election\w*|parliament|congress|senate|white house|policy|politic\w*|"
                         r"campaign|party|governor|minister|president|sanctions?|markets?|banks?|banking|financ\w*|econom\w*|central bank|currency|stocks?|bonds?|"
                         r"crisis|crises|unrest|protests?|riots?|coup|reporting|reporter|journalis\w*|wire|broadcaster|newspaper|analysis|analyst|research|institute|"
                         r"observatory|center|centre|feed|rss|bulletin|advisor(y|ies))\b", re.I)

def clean_text(s, n):
    s = s if isinstance(s, str) else ""
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", s).strip()
    return re.sub(r"[ \t]+", " ", s), len(s) > n

def validate(d):
    """-> (clean, None) or (None, friendly error). Format checks only; the spam / relevance filter runs after this."""
    d = d or {}
    out = {}
    for f in ("name", "url", "why", "email"):
        v, too_long = clean_text(d.get(f), LIMITS[f])
        if too_long: return None, f"The {f if f != 'why' else 'reason'} field is too long (max {LIMITS[f]} characters)."
        out[f] = v
    if len(out["name"]) < 2: return None, "Enter the source's name."
    if not out["url"]: return None, "Enter the source's link."
    un = SC.norm_url(out["url"])
    if not un: return None, "That link isn't a valid web address (use http:// or https://)."
    host = SC.domain_of(un)
    if re.fullmatch(r"[\d.]+|\[[0-9a-f:]+\]", host): return None, "Please use the source's domain name, not an IP address."
    out["url_norm"] = un; out["host"] = host
    t = str(d.get("type") or "").strip()
    if t not in TYPES: return None, "Pick a source type from the list."
    c = str(d.get("category") or "").strip()
    if c not in CATS: return None, "Pick the threat category it covers."
    out["type"], out["category"] = t, c
    if len(out["why"]) < 10: return None, "Tell us briefly why it's useful (at least 10 characters)."
    if out["email"]:
        e = out["email"].lower()
        if not re.fullmatch(r"[a-z0-9._%+'-]+@[a-z0-9-]+(\.[a-z0-9-]+)+", e): return None, "That email address doesn't look valid (or leave it blank)."
        out["email"] = e
    return out, None

def spam_reason(c):
    """-> None if acceptable, else a short reason. Matches are discarded silently (the submitter sees the normal thank-you)."""
    text = " ".join([c["name"], c["why"], urllib.parse.unquote(c["url_norm"])])
    host = c["host"]; tld = host.rsplit(".", 1)[-1]
    if any(host == s or host.endswith("." + s) for s in SHORTENERS): return "link shortener / redirector"
    if tld in BAD_TLDS: return f"blocked TLD .{tld}"
    if BAD_DOMAINS_RX.search(host): return "blocked domain keyword"
    if BAD_EXT_RX.search(c["url_norm"]): return "executable or archive download"
    if ADULT_RX.search(text): return "adult content"
    if GAMBLING_RX.search(text): return "gambling"
    if CRYPTO_RX.search(text): return "crypto promotion"
    if MALWARE_RX.search(text): return "malware / piracy"
    if OFFTOPIC_RX.search(text): return "off-topic commercial"
    if len(re.findall(r"https?://", c["why"])) > 2: return "link stuffing"
    if not RELEVANT_RX.search(text): return "not relevant to monitored categories"
    return None

def find_duplicate(k, un):
    """k = source_submissions.db connection; the box-owned catalog (sources.db) is checked read-only alongside it."""
    c = SC.db()
    try:
        r = c.execute("SELECT 'catalog' w, name FROM sources WHERE link_norm=? LIMIT 1", (un,)).fetchone() \
            or c.execute("SELECT 'candidate' w, name FROM candidates WHERE url_norm=? LIMIT 1", (un,)).fetchone()
    finally: c.close()
    r = r or k.execute("SELECT 'candidate' w, name FROM approved_candidates WHERE url_norm=? LIMIT 1", (un,)).fetchone() \
          or k.execute("SELECT 'queue' w, name FROM submissions WHERE url_norm=? AND status IN ('pending','approved') LIMIT 1", (un,)).fetchone()
    return (r["w"], r["name"]) if r else None

def _hits(k, kind, key, win): return k.execute("SELECT COUNT(*) FROM attempts WHERE kind=? AND k=? AND ts>=?", (kind, key, time.time() - win)).fetchone()[0]
def _hit(k, kind, key):
    k.execute("INSERT INTO attempts VALUES(?,?,?)", (kind, key, time.time())); k.execute("DELETE FROM attempts WHERE ts<?", (time.time() - 3 * 86400,))

THANKS = "Thanks. Your suggestion is in the review queue. A person checks every source before it is used."
def form_token(t=None): return NL().make_token("srcform", 0, 6 * 3600, t=t, at=int(t or time.time()))
def csrf_and_form(): return NL().csrf_token(), form_token()

def submit(d, ip="", headers=None, check_tokens=True, t=None):
    """-> (http code, json). Order: rate limit, honeypot, timing, CSRF, validation, spam filter, dedupe, insert."""
    t = t or time.time(); headers = headers or {}
    k = SC.sub_db()
    try:
        ipk = h("src:" + (ip or "?"))
        if _hits(k, "sub_ip", ipk, 3600) >= RATE["ip_hour"] or _hits(k, "sub_ip", ipk, 86400) >= RATE["ip_day"]:
            return 429, {"ok": False, "message": "Too many suggestions from this connection. Please try again later."}
        if _hits(k, "sub_all", "all", 86400) >= RATE["global_day"]:
            return 429, {"ok": False, "message": "The review queue is full for today. Please try again tomorrow."}
        _hit(k, "sub_ip", ipk); _hit(k, "sub_all", "all"); k.commit()
        def discard(reason, host=""):
            k.execute("INSERT INTO discards(ts,reason,domain) VALUES(?,?,?)", (now_iso(), reason, host[:120])); k.commit()
            return 200, {"ok": True, "message": THANKS}
        if str(d.get("website") or "").strip(): return discard("honeypot")
        if check_tokens:
            if not NL().csrf_ok(d, headers): return 403, {"ok": False, "message": "This form expired. Reload the page and try again."}
            st, p = NL().read_token(d.get("ft"), "srcform", t)
            if st != "ok": return 403, {"ok": False, "message": "This form expired. Reload the page and try again."}
            if t - int(p.get("at", 0)) < MIN_FILL_S: return discard("submitted too fast")
        c, err = validate(d)
        if err: return 400, {"ok": False, "message": err}
        why = spam_reason(c)
        if why: return discard(why, c["host"])
        dup = find_duplicate(k, c["url_norm"])
        if dup:
            where = {"catalog": "already in the catalog", "candidate": "already a candidate under review", "queue": "already in the review queue"}[dup[0]]
            return 200, {"ok": True, "duplicate": True, "message": f"Thanks. That source is {where} ({dup[1]})."}
        k.execute("""INSERT INTO submissions(name,url,url_norm,type,category,why,email,ip_hash,status,created) VALUES(?,?,?,?,?,?,?,?,'pending',?)""",
                  (c["name"], c["url"], c["url_norm"], c["type"], c["category"], c["why"], c["email"] or None, ipk, now_iso()))
        k.commit()
        return 200, {"ok": True, "message": THANKS}
    finally: k.close()

# ---------------------------------------------------------------- admin (same passcode + session token as /newsletter/admin)
def admin_action(d):
    a = d.get("action")
    k = SC.sub_db()   # queue, approvals, discards: Render-owned source_submissions.db
    try:
        if a == "list":
            subs = [dict(r) for r in k.execute("SELECT id,name,url,type,category,why,email,status,created,reviewed,review_note FROM submissions ORDER BY (status='pending') DESC, id DESC LIMIT 200")]
            for s in subs: s["email"] = NL().mask_email(s["email"]) if s["email"] else ""
            disc = [dict(r) for r in k.execute("SELECT reason, COUNT(*) n FROM discards WHERE ts>=? GROUP BY reason ORDER BY n DESC",
                                               (datetime.fromtimestamp(time.time() - 7 * 86400, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),))]
            c = SC.db()
            try:
                ov = [dict(r) for r in c.execute("SELECT * FROM overrides ORDER BY updated DESC")]
                cands = [dict(r) | {"store": "catalog"} for r in c.execute("SELECT * FROM candidates ORDER BY id DESC LIMIT 200")]
            finally: c.close()
            cands = [dict(r) | {"store": "submissions"} for r in k.execute("SELECT * FROM approved_candidates ORDER BY id DESC LIMIT 200")] + cands
            return 200, {"ok": True, "submissions": subs, "discards_7d": disc, "overrides": ov, "candidates": cands}
        if a in ("approve", "reject"):
            sid = int(d.get("id") or 0)
            s = k.execute("SELECT * FROM submissions WHERE id=?", (sid,)).fetchone()
            if not s: return 404, {"ok": False, "message": "No such submission."}
            if s["status"] != "pending": return 409, {"ok": False, "message": f"Already {s['status']}."}
            note = str(d.get("note") or "")[:300]
            if a == "approve":
                k.execute("""INSERT OR IGNORE INTO approved_candidates(name,url,url_norm,type,category,why,origin,added,submission_id) VALUES(?,?,?,?,?,?,?,?,?)""",
                          (s["name"], s["url"], s["url_norm"], s["type"], s["category"], s["why"], "user submission", now_iso(), sid))
            k.execute("UPDATE submissions SET status=?, reviewed=?, review_note=? WHERE id=?", ("approved" if a == "approve" else "rejected", now_iso(), note, sid))
            k.commit()
            return 200, {"ok": True, "message": "Approved and moved to Candidate sources." if a == "approve" else "Rejected."}
        if a == "candidate_status":
            cid = int(d.get("id") or 0); st = str(d.get("status") or "")
            if st not in ("under review", "adopted", "dropped"): return 400, {"ok": False, "message": "status must be under review, adopted or dropped"}
            if d.get("store") == "catalog":
                c = SC.db(); n = c.execute("UPDATE candidates SET status=? WHERE id=?", (st, cid)).rowcount; c.commit(); c.close()
            else:
                n = k.execute("UPDATE approved_candidates SET status=? WHERE id=?", (st, cid)).rowcount; k.commit()
            return (200, {"ok": True}) if n else (404, {"ok": False, "message": "No such candidate."})
        if a in ("override", "clear_override"):   # box-owned catalog setting (sources.db)
            k.close(); k = SC.db()
            key = str(d.get("key") or "")
            if not k.execute("SELECT 1 FROM sources WHERE key=?", (key,)).fetchone(): return 404, {"ok": False, "message": "No such source."}
            if a == "override":
                try: r = int(d.get("rating"))
                except Exception: r = -1
                if not 0 <= r <= 10: return 400, {"ok": False, "message": "rating must be 0-10"}
                k.execute("INSERT OR REPLACE INTO overrides VALUES(?,?,?,?)", (key, r, str(d.get("note") or "")[:300], now_iso()))
            else: k.execute("DELETE FROM overrides WHERE key=?", (key,))
            k.commit(); k.close(); k = None
            SC.refresh(quiet=True)
            return 200, {"ok": True}
        return 400, {"ok": False, "message": "unknown action"}
    finally:
        if k: k.close()

# ---------------------------------------------------------------- read APIs
BANDS = {"red": (0, 3), "amber": (4, 6), "green": (7, 8), "blue": (9, 10)}
SORTS = {"items": "n_items DESC, rating DESC", "rating": "rating IS NULL, rating DESC, n_items DESC", "rating_asc": "rating IS NULL, rating ASC, n_items DESC",
         "name": "name COLLATE NOCASE", "recent": "last_seen IS NULL, last_seen DESC"}
def band(r):
    if r is None: return "na"
    return "red" if r <= 3 else "amber" if r <= 6 else "green" if r <= 8 else "blue"

def monitor_label(d):
    """Monitored catalog vs directory-only: how the system actually uses this source."""
    st = (d.get("status") or "").lower()
    if st.startswith("disabled"): return "Catalog · feed disabled"
    if d.get("origin") == "scanner config": return "Monitored · scanner feed"
    if d.get("origin") == "political": return "Monitored · political watch list"
    if d.get("origin") == "youtube watch": return "Monitored · YouTube watch"
    return "Monitored · seen in scanned items"

def catalog(qs):
    g = lambda k, dflt="": ((qs.get(k) or [dflt])[0] or dflt)
    where, args = [], []
    q = g("q").strip()[:80]
    if q:
        where.append("(name LIKE ? OR profile LIKE ? OR link LIKE ? OR role LIKE ?)"); args += [f"%{q}%"] * 4
    if g("type"): where.append("type=?"); args.append(g("type"))
    if g("cat"): where.append("categories LIKE ?"); args.append('%"' + g("cat").replace('"', "") + '"%')
    b = g("band")
    if b in BANDS: where.append("rating BETWEEN ? AND ?"); args += list(BANDS[b])
    elif b == "na": where.append("rating IS NULL")
    o = g("origin")
    if o == "political": where.append("origin='political'")
    elif o == "youtube": where.append("key LIKE 'YouTube: %'")
    elif o == "config": where.append("origin='scanner config'")
    elif o == "db": where.append("n_items>0")
    if g("profiled") == "1": where.append("profile_status!='pending'")
    sql_w = (" WHERE " + " AND ".join(where)) if where else ""
    try: page = max(1, min(500, int(g("page", "1"))))
    except Exception: page = 1
    try: per = max(10, min(100, int(g("per", "40"))))
    except Exception: per = 40
    order = SORTS.get(g("sort", "items"), SORTS["items"])
    k = SC.db()
    try:
        total = k.execute("SELECT COUNT(*) FROM sources" + sql_w, args).fetchone()[0]
        rows = k.execute(f"""SELECT key,name,type,link,n_items,first_seen,last_seen,categories,profile,profile_status,rating,rating_auto,rating_reason,overridden,
                             origin,role,party,grp,status FROM sources{sql_w} ORDER BY {order} LIMIT ? OFFSET ?""", args + [per, (page - 1) * per]).fetchall()
        types = [dict(r) for r in k.execute("SELECT type, COUNT(*) n FROM sources GROUP BY type ORDER BY n DESC")]
        meta = dict(k.execute("SELECT k, v FROM meta").fetchall())
    finally: k.close()
    items = []
    for r in rows:
        d = dict(r); d["categories"] = json.loads(d["categories"] or "{}"); d["reason"] = json.loads(d["rating_reason"] or "[]"); del d["rating_reason"]
        d["band"] = band(d["rating"]); d["sid"] = SD.catalog_sid(d["key"]); d["monitor"] = monitor_label(d); items.append(d)
    try:
        V = SD.votes_mod()
        voter = g("voter"); gr = V.source_grades([i["sid"] for i in items], voter if re.fullmatch(r"[a-f0-9]{32}", voter or "") else None)
        for i in items: i["grade"] = gr.get(i["sid"])
    except Exception as ex: print("source grades unavailable:", ex)
    return {"total": total, "page": page, "per": per, "items": items, "types": types, "categories": CATS, "refreshed": meta.get("refreshed")}

def summary():
    k = SC.db()
    try:
        tot = k.execute("SELECT COUNT(*), SUM(n_items), SUM(profile_status!='pending'), MIN(first_seen), MAX(last_seen) FROM sources").fetchone()
        bands = {b: 0 for b in ("blue", "green", "amber", "red", "na")}
        for r in k.execute("SELECT rating FROM sources"): bands[band(r[0])] += 1
        pol = k.execute("SELECT COUNT(*) FROM sources WHERE origin='political'").fetchone()[0]
        yt = k.execute("SELECT COUNT(*) FROM sources WHERE key LIKE 'YouTube: %'").fetchone()[0]
        top = [dict(r) for r in k.execute("SELECT name,type,link,n_items,rating FROM sources WHERE n_items>0 AND rating>=9 ORDER BY n_items DESC LIMIT 6")]
        cands = [dict(r) for r in k.execute("SELECT name,url,type,category,why,origin,added,status FROM candidates WHERE status='under review' ORDER BY id DESC LIMIT 100")]
        meta = dict(k.execute("SELECT k, v FROM meta").fetchall())
    finally: k.close()
    q = SC.sub_db()   # public queue is read from source_submissions.db (Render-owned), never from sources.db
    try:
        queue = [dict(r) for r in q.execute("SELECT name,type,category,created FROM submissions WHERE status='pending' ORDER BY id DESC LIMIT 100")]
        cands = [dict(r) for r in q.execute("SELECT name,url,type,category,why,origin,added,status FROM approved_candidates WHERE status='under review' ORDER BY id DESC LIMIT 100")] + cands
    finally: q.close()
    return {"sources": tot[0] or 0, "items": tot[1] or 0, "profiles": tot[2] or 0, "first": tot[3], "last": tot[4], "bands": bands, "political": pol,
            "youtube": yt, "top": top, "queue": queue, "candidates": cands, "refreshed": meta.get("refreshed")}

# ---------------------------------------------------------------- pages
def et(s, with_date=True):
    try:
        from zoneinfo import ZoneInfo
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(ZoneInfo("America/New_York"))
        return d.strftime("%b %-d, %Y %-I:%M %p %Z" if with_date else "%-I:%M %p %Z")
    except Exception: return "—"

def shell(title, body, robots="index", wide=True):
    return ('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta name="robots" content="{robots}"><title>Know first. Be ready.</title>'
            '<meta name="description" content="Every source blackout.network has used, with item counts, profiles and a transparent 0–10 confidence rating. Suggest a source for review.">'
            '<link rel="stylesheet" href="/theme.css"><link rel="icon" href="/favicon.ico" sizes="any"><link rel="stylesheet" href="/api/sources/app.css">'
            '<link rel="stylesheet" href="/api/translate/app.css"></head><body class="sc-page"><a class="skip" href="#main">Skip to content</a>'
            f'<header><h1>BLACKOUT.<b>NETWORK</b> · {E(title)}<small>{E(TAGLINE)}</small></h1>'
            '<nav class="sc-nav" aria-label="Site"><a href="/#wire">← Dashboard</a><a href="/scoring">How we score</a><a href="/sources" class="on"><span class="sc-ni" data-ico="book-open" aria-hidden="true"></span>Sources</a><a href="/newsletter"><span class="sc-ni" data-ico="mail" aria-hidden="true"></span>Newsletter</a></nav></header>'
            f'<div class="sc-wrap" id="main" role="main">{body}</div>'
            f'<footer>Research-only data · {BRAND} · <a href="/#wire">Dashboard</a> · <a href="/scoring">How we score</a> · <a href="/sources">Sources</a> · <a href="/newsletter">Newsletter</a>'
            '<span id="sc_foot_range"></span></footer>'
            '<script src="/api/sources/app.js"></script><script src="/api/translate/app.js"></script><script src="/api/search/app.js"></script></body></html>')

def legend_html():
    return ('<div class="sc-legend" aria-label="Confidence rating colors">'
            '<span><i class="sc-r b-blue">9–10</i> Official / fully trusted</span><span><i class="sc-r b-green">7–8</i> Reliable</span>'
            '<span><i class="sc-r b-amber">4–6</i> Mixed: confirm first</span><span><i class="sc-r b-red">0–3</i> Unverified / low trust</span>'
            '<span><i class="sc-r b-na">n/a</i> Collector, not a source</span></div>')

def form_html():
    csrf, ft = csrf_and_form()
    opt = lambda xs: "".join(f'<option value="{E(x)}">{E(x)}</option>' for x in xs)
    return ('<form id="sc_form" class="sc-form" method="post" action="/api/sources/submit" novalidate>'
            f'<input type="hidden" name="csrf" value="{E(csrf)}"><input type="hidden" name="ft" value="{E(ft)}">'
            '<div class="sc-grid2"><label>Source name<input name="name" required maxlength="120" placeholder="e.g. Philippine Institute of Volcanology (PHIVOLCS)"></label>'
            '<label>Link<input name="url" type="url" required maxlength="500" inputmode="url" placeholder="https://…"></label>'
            f'<label>Type<select name="type" required><option value="">Choose…</option>{opt(TYPES)}</select></label>'
            f'<label>Main category<select name="category" required><option value="">Choose…</option>{opt(CATS)}</select></label></div>'
            '<label>Why is it useful?<textarea name="why" required maxlength="1000" rows="3" placeholder="What does it cover, how fast is it, does it cite primary sources?"></textarea></label>'
            '<label>Your email <span class="mu">(optional, only so we can follow up; never shown)</span><input name="email" type="email" maxlength="254" autocomplete="email"></label>'
            '<div class="sc-hp" aria-hidden="true"><label>Leave this empty<input name="website" tabindex="-1" autocomplete="off"></label></div>'
            '<button class="sc-pri" type="submit">Submit for review</button> <span class="sc-msg" role="status" aria-live="polite"></span>'
            '<p class="sc-sm mu">Every suggestion is reviewed by a person before it is used. Adult, gambling, crypto-promotion, link-shortener and off-topic '
            'submissions are discarded. Limit: 3 per hour.</p></form>')

def dir_intro_html(monitored):
    d = SD.summary()
    if not d.get("ready"):
        return '<p class="sc-sm mu">The global reference directory is loading and will appear below shortly.</p>'
    return (f'<p class="sc-total"><b>{monitored + d["total"]:,}</b> sources listed: <b>{monitored:,}</b> monitored by the system and '
            f'<b>{d["total"]:,}</b> reference sources worldwide in the <a href="#directory">global directory</a>, each from a published registry.</p>')

def directory_html():
    d = SD.summary()
    if not d.get("ready"):
        return ('<section class="sc-card" id="directory" aria-labelledby="h-d"><h2 id="h-d">Global directory</h2>'
                '<p class="sc-sm mu" id="sd_count">The directory is being prepared. Reload in a minute.</p><div id="sd_list"></div></section>')
    cats = "".join(f'<option value="{E(c)}">{E(c)} ({n:,})</option>' for c, n in d["by_category"])
    regs = "".join(f'<option value="{E(r)}">{E(r)} ({n:,})</option>' for r, n in d["by_registry"])
    ccs = json.dumps(d["countries"])
    chips = "".join(f'<li><button type="button" class="cc" data-cat="{E(c)}" data-ccat="{E(c)}" data-cico title="Show only {E(c)}"><span class="sd-cl"><b>{n:,}</b> {E(c)}</span></button></li>' for c, n in d["by_category"])
    return ('<section class="sc-card" id="directory" aria-labelledby="h-d"><h2 id="h-d">Global directory</h2>'
            f'<p class="sc-sm">{d["total"]:,} real reference sources from around the world: security teams, police and emergency agencies, radar and weather '
            'stations, seismic networks, satellites, river gauges, government data feeds, news outlets, research institutions and public scanner audio. '
            'Every entry comes from a published registry and links to the real page. <b>These are reference entries, not live monitor inputs</b>: '
            'the scanner does not read them, and they never change an alert\'s score or rank.</p>'
            f'<ul class="sd-cats" aria-label="Directory categories (color key; select one to filter)">{chips}</ul>'
            '<form class="sc-filters" id="sd_filters" role="search" onsubmit="return false">'
            '<label class="sc-q"><span class="sr">Search the directory</span><input id="sd_q" type="search" placeholder="Search name, link, type or place…" maxlength="80"></label>'
            f'<label><span class="sr">Category</span><select id="sd_cat"><option value="">All categories</option>{cats}</select></label>'
            f'<label><span class="sr">Country</span><select id="sd_cc" data-cc=\'{E(ccs)}\'><option value="">All countries</option></select></label>'
            f'<label><span class="sr">Registry</span><select id="sd_reg"><option value="">All registries</option>{regs}</select></label>'
            '<label class="sc-chk"><input type="checkbox" id="sd_rated"> Rated by visitors</label></form>'
            '<p class="sc-sm mu" id="sd_count" aria-live="polite">Loading…</p><div id="sd_list" class="sc-list"></div>'
            '<nav class="sd-pager" id="sd_pager" aria-label="Directory pages"></nav>'
            f'<p class="sc-sm mu">Registries: ' + ", ".join(f'<a href="{E(v.get("url", ""))}" target="_blank" rel="noopener noreferrer">{E(k)}</a>'
                                                       + (f' ({E(v["licence"])})' if v.get("licence") else "") for k, v in d["registries"].items()) +
            (f'. Links spot-checked {E(d["checked"].get("date", ""))}: {d["checked"].get("checked", 0)} sampled, {d["checked"].get("dead", 0)} dead removed.' if d.get("checked") else "") +
            '</p></section>')

def grades_html():
    V = SD.votes_mod()
    cuts = ", ".join(f"<b>{g}</b> {c}+" for c, g in V.GRADE_CUTS[:-1]) + f", <b>F</b> below {V.GRADE_CUTS[-2][0]}"
    return ('<section class="sc-card" id="grades" aria-labelledby="h-g"><h2 id="h-g">How the reliability grade works</h2>'
            '<p class="sc-sm">Every source, monitored or directory, has a <b>reliability grade from visitors</b>. Tap 1 to 5 stars on any source to rate how '
            'accurate and dependable it has been for you.</p><ul class="sc-rules">'
            f'<li><b>Fair start.</b> Each source begins from a neutral starting point based on its type (official observing networks start higher than unverified streams). '
            f'That starting point counts as {V.GRADE_C} votes, so a few ratings can\'t swing a grade to an extreme.</li>'
            '<li><b>Score.</b> (starting point × 5 + the sum of visitor stars) ÷ (5 + number of votes), shown from 0 to 100.</li>'
            f'<li><b>Letter.</b> {cuts}. A grade appears after {V.GRADE_MIN} votes; before that the source shows “Not yet rated”.</li>'
            '<li><b>One vote per browser per source.</b> Rating again replaces your earlier rating. Each connection has a rate limit; no accounts and no personal data are kept.</li>'
            '<li><b>Separate from alerts.</b> Grades never change an alert\'s score, rank or The Wire. The 0–10 confidence rating on monitored sources is a separate, fixed rule (below).</li>'
            '</ul></section>')

def page_html():
    s = summary()
    b = s["bands"]
    P = []
    a = P.append
    a('<section class="sc-card sc-intro"><h2>Every source we use, rated</h2>'
      '<p>This catalog lists every source the monitor has drawn on: official agencies, news outlets, social accounts and channels, the scanner\'s own feeds, '
      'the YouTube channels it watches and the public accounts on the political watch list. Each entry shows how many items it produced, when, what kind, '
      'and a <b>confidence rating from 0 to 10</b> computed by the fixed rule below. Select a rating to see exactly why.</p>'
      + dir_intro_html(s["sources"]) +
      f'<div class="sc-stats"><div><b>{s["sources"]:,}</b><span>monitored sources</span></div><div><b>{s["items"]:,}</b><span>items stored</span></div>'
      f'<div><b>{b["blue"] + b["green"]:,}</b><span>rated 7+</span></div><div><b>{s["profiles"]:,}</b><span>written profiles</span></div>'
      f'<div><b>{s["political"]}</b><span>political watch accounts</span></div><div><b>{s["youtube"]}</b><span>YouTube channels</span></div></div>'
      f'<p class="sc-sm mu" id="sc_range" data-first="{E(s["first"])}" data-last="{E(s["last"])}">Data range: {E(et(s["first"]))} – {E(et(s["last"]))} · '
      f'catalog refreshed {E(et(s["refreshed"]))}</p>' + legend_html() +
      '<nav class="sc-toc" aria-label="On this page"><a href="#catalog">Monitored catalog</a><a href="#directory">Global directory</a><a href="#grades">Reliability grades</a><a href="#method">How ratings work</a><a href="#candidates">Candidate sources</a>'
      '<a href="#queue">Review queue</a><a href="#submit">Submit a source</a></nav></section>')
    a('<section class="sc-card" id="catalog" aria-labelledby="h-cat"><h2 id="h-cat">Monitored catalog</h2>'
      '<p class="sc-sm mu">Sources the monitor actually uses: the scanner\'s feeds, outlets seen in scanned items, and the watch lists.</p>'
      '<form class="sc-filters" id="sc_filters" role="search" onsubmit="return false">'
      '<label class="sc-q"><span class="sr">Search sources</span><input id="sc_q" type="search" placeholder="Search name, profile, handle or role…" maxlength="80"></label>'
      '<label><span class="sr">Type</span><select id="sc_type"><option value="">All types</option></select></label>'
      '<label><span class="sr">Category</span><select id="sc_cat"><option value="">All categories</option>' + "".join(f'<option>{E(c)}</option>' for c in CATS) + '</select></label>'
      '<label><span class="sr">Rating</span><select id="sc_band"><option value="">All ratings</option><option value="blue">9–10 official / trusted</option><option value="green">7–8 reliable</option>'
      '<option value="amber">4–6 mixed</option><option value="red">0–3 low trust</option><option value="na">n/a collectors</option></select></label>'
      '<label><span class="sr">Group</span><select id="sc_origin"><option value="">All sources</option><option value="db">Used in stored items</option><option value="political">Political watch list</option>'
      '<option value="youtube">YouTube watch</option><option value="config">Scanner feeds</option></select></label>'
      '<label><span class="sr">Sort</span><select id="sc_sort"><option value="items">Most items</option><option value="rating">Highest rating</option><option value="rating_asc">Lowest rating</option>'
      '<option value="recent">Most recent</option><option value="name">Name A–Z</option></select></label>'
      '<label class="sc-chk"><input type="checkbox" id="sc_prof"> With profile</label></form>'
      '<ul class="sc-catleg" aria-label="Category colors">' + "".join(f'<li class="cc" data-ccat="{E(c)}" data-cico>{E(c)}</li>' for c in CATS) + '</ul>'
      '<p class="sc-sm mu" id="sc_count" aria-live="polite">Loading…</p><div id="sc_list" class="sc-list"></div>'
      '<div class="sc-more"><button type="button" id="sc_more" hidden>Show more</button></div>'
      '<noscript><p>The catalog needs JavaScript. The raw data is at <a href="/api/sources/catalog?per=100">/api/sources/catalog</a>.</p></noscript></section>')
    a(directory_html()); a(grades_html())
    a('<section class="sc-card" id="method" aria-labelledby="h-m"><h2 id="h-m">How the confidence rating works</h2>'
      '<p class="sc-sm">The rating estimates how far you can trust a source <i>before</i> anyone else confirms it. It is computed the same way for every source, '
      'and the steps for each one are shown when you select its rating. It never changes a story\'s score or rank: those come from the scanner\'s own rules '
      '(<a href="/scoring">How we score</a>).</p><ol class="sc-rules">' +
      "".join(f'<li><b>{E(t)}</b> {E(x)}</li>' for t, x in SC.RULE_DOC) + '</ol>'
      '<p class="sc-sm mu">Profiles marked “Profile pending” have not been written yet. They are not guessed. Political watch accounts are public accounts '
      'of officials, party organizations and campaign figures in both parties, monitored read-only. Nothing is ever posted or replied to.</p></section>')
    a('<section class="sc-card" id="candidates" aria-labelledby="h-c"><h2 id="h-c">Candidate sources (under review)</h2>')
    if s["candidates"]:
        a('<ul class="sc-q-list">' + "".join(
            f'<li><a href="{E(c["url"])}" target="_blank" rel="noopener noreferrer nofollow">{E(c["name"])}</a> <span class="sc-chip">{E(c["type"] or "?")}</span>'
            f'<span class="sc-chip cat cc" data-ccat="{E(c["category"] or "")}">{E(c["category"] or "?")}</span><span class="mu sc-sm"> · {E(c["origin"])} · added {E(et(c["added"]))}</span>'
            + (f'<div class="sc-sm mu">{E(c["why"][:240])}</div>' if c.get("why") else "") + '</li>' for c in s["candidates"]) + '</ul>')
    else:
        a('<p class="sc-sm mu">None right now. New candidates come from the hourly source search and from approved suggestions.</p>')
    a('</section><section class="sc-card" id="queue" aria-labelledby="h-q"><h2 id="h-q">Review queue</h2>')
    if s["queue"]:
        a('<ul class="sc-q-list">' + "".join(f'<li><b>{E(q["name"])}</b> <span class="sc-chip">{E(q["type"])}</span><span class="sc-chip cat cc" data-ccat="{E(q["category"])}">{E(q["category"])}</span>'
                                              f'<span class="mu sc-sm"> · submitted {E(et(q["created"]))}</span></li>' for q in s["queue"]) + '</ul>')
    else:
        a('<p class="sc-sm mu">The queue is empty. Suggest a source below.</p>')
    a('</section><section class="sc-card" id="submit" aria-labelledby="h-s"><h2 id="h-s">Submit a source</h2>'
      '<p class="sc-sm">Know a fast, credible source for war and conflict, disease, natural disasters, cyber, space weather, politics or financial stress? Suggest it here.</p>'
      + form_html() + '</section>')
    return shell("Sources", "".join(P))

def card_html():
    s = summary(); b = s["bands"]
    rows = "".join(f'<li><span class="sc-r b-{band(t["rating"])}">{t["rating"]}</span> <a href="{E(t["link"])}" target="_blank" rel="noopener noreferrer">{E(t["name"])}</a>'
                   f'<span class="mu"> · {E(t["type"])} · {t["n_items"]:,} items</span></li>' for t in s["top"])
    dsum = SD.summary(); dtot = dsum.get("total", 0) if dsum.get("ready") else 0
    return (f'<div class="sc-cardin"><p>{s["sources"]:,} monitored sources, {s["items"]:,} stored items, each with a 0–10 confidence rating'
            + (f', plus {dtot:,} reference sources worldwide in the global directory' if dtot else '') + '. '
            f'<b>{b["blue"]}</b> official or fully trusted, <b>{b["green"]}</b> reliable, <b>{b["amber"]}</b> mixed, <b>{b["red"]}</b> low trust.</p>'
            + legend_html() + f'<h3>Most-used trusted sources</h3><ul class="sc-top">{rows}</ul>'
            f'<p><a class="sc-pri" href="sources">Open the full catalog →</a> <a class="sc-ghost" href="sources#submit">Submit a source</a> '
            f'<span class="mu sc-sm">{len(s["queue"])} in the review queue · {len(s["candidates"])} candidates</span></p></div>')

def admin_page():
    body = ('<section class="sc-card" id="sca_login"><h2>Sources admin</h2><p>Enter the dashboard admin passcode (the same one used by the newsletter admin).</p>'
            '<form id="sca_form" class="sc-form" autocomplete="off"><label>Admin passcode<input type="password" id="sca_pass" autocomplete="current-password" required></label>'
            '<button class="sc-pri" type="submit">Unlock</button> <span class="sc-msg" role="status" aria-live="polite"></span></form></section>'
            '<div id="sca_app" hidden></div><script src="/api/sources/admin.js"></script>')
    return shell("Sources admin", body, robots="noindex")

def handle_get(path, qs):
    if "/admin" in path: return 404, {"error": "not found"}   # admin is not part of the public node
    if path.startswith("/api/sources/"):
        name = path[len("/api/sources/"):]
        if name in ("app.js", "app.css"):
            with open(os.path.join(STATIC, name), "rb") as f: return 200, f.read(), ("application/javascript" if name.endswith(".js") else "text/css")
        maybe_refresh()
        if name == "catalog": return 200, catalog(qs)
        if name == "directory": return SD.query(qs)
        if name == "directory_summary": return 200, SD.summary()
        if name == "summary": return 200, summary()
        if name == "card": return 200, card_html(), "text/html"
        if name == "meta":
            csrf, ft = csrf_and_form(); return 200, {"csrf": csrf, "ft": ft, "types": TYPES, "categories": CATS}
        return 404, {"error": "not found"}
    if path == "/api/sources": return 200, {"ok": True, "pages": ["/sources"], "api": ["catalog", "directory", "directory_summary", "summary", "card", "meta"]}
    if path.rstrip("/") == "/sources": maybe_refresh(); return 200, page_html(), "text/html"
    if path == "/sources/admin": return 200, admin_page(), "text/html"
    return 404, {"error": "not found"}

def _form(raw):
    try: return {k: v[0] for k, v in urllib.parse.parse_qs((raw or b"").decode("utf-8", "replace"), keep_blank_values=True).items()}
    except Exception: return {}

def handle_post(path, d, ip=None, qs=None, headers=None, raw=None):
    if "/admin" in path: return 404, {"error": "not found"}   # admin is not part of the public node
    headers = {k.lower(): v for k, v in (headers or {}).items()}
    html_mode = False
    if not d and raw:
        d = _form(raw); html_mode = "x-www-form-urlencoded" in (headers.get("content-type") or "")
    if path == "/api/sources/submit":
        code, body = submit(d, ip or "", headers)
        if html_mode:
            return code, shell("Sources", f'<section class="sc-card"><h2>{"Received" if body.get("ok") else "Not submitted"}</h2><p>{E(body["message"])}</p>'
                                         '<p><a href="/sources#submit">Back to Sources</a></p></section>'), "text/html"
        return code, body
    if not NL().origin_ok(headers): return 403, {"ok": False, "message": "Cross-site request blocked."}
    if path == "/api/sources/admin/login": return NL().admin_login(d, ip or "")
    if path == "/api/sources/admin":
        if not NL().admin_ok(d): return 401, {"ok": False, "message": "Admin session expired. Unlock again."}
        return admin_action(d)
    return 404, {"error": "not found"}
