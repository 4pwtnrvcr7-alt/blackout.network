"""Banks, card networks and payment apps with no public machine-readable status feed (Nov 23 2026, pt1785u).

Matt: "Wells Fargo has an outage right now and when I search Wells Fargo on that page, it just shows up as something that we aren't
tracking." None of the big U.S. banks or card networks publish a status page we can read, so each one gets the signals we can
legitimately collect, and the page says which ones were used:
  1. News headlines that name the service AND an outage phrase (Google News RSS search, two batched queries every 15 min).
  2. Wire items from our own scanner (blackout.db, read-only) that name the service and an outage phrase.
  3. A TLS handshake with the service's public website (it says the edge answers, nothing about logins or card payments).
  4. "Down for me" reports from people on this page (netboard.py), applied in netmap.build.
Nothing here guesses a user count. Also: PayPal (its own public RSS incident feed) and Apple Pay (Apple's public system status JSON).
Never touches the scanner, scoring, push or the QA gate."""
import email.utils, json, os, re, socket, ssl, sqlite3, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
UA = "BlackoutNetwork-status/2.0 (+https://blackout.network/network; cached, polite)"
NEWS_HOT_H = 6      # a matching headline this recent marks a disruption
NEWS_KEEP_H = 48    # headlines this recent are listed on the detail page

# id -> (search name, website host, title regex for the name, optional negative regex)
W = {
 "wellsfargo": ("Wells Fargo", "www.wellsfargo.com", r"\bWells Fargo\b", None),
 "chase": ("Chase", "www.chase.com", r"\b(?:Chase(?! down| after| the)|JPMorgan Chase|JPMorgan)\b", r"\bchase[sd]?\b(?! bank| app| customers| online| mobile| outage)"),
 "bofa": ("Bank of America", "www.bankofamerica.com", r"\b(?:Bank of America|BofA)\b", None),
 "citi": ("Citi", "www.citi.com", r"\b(?:Citi|Citibank|Citigroup)\b", None),
 "capitalone": ("Capital One", "www.capitalone.com", r"\bCapital One\b", None),
 "usbank": ("U.S. Bank", "www.usbank.com", r"\bU\.?S\.? Bank\b", None),
 "pnc": ("PNC", "www.pnc.com", r"\bPNC\b", None),
 "truist": ("Truist", "www.truist.com", r"\bTruist\b", None),
 "td": ("TD Bank", "www.td.com", r"\bTD Bank\b", None),
 "navyfederal": ("Navy Federal", "www.navyfederal.org", r"\bNavy Federal\b", None),
 "usaa": ("USAA", "www.usaa.com", r"\bUSAA\b", None),
 "ally": ("Ally Bank", "www.ally.com", r"\bAlly (?:Bank|Financial)\b", None),
 "regions": ("Regions Bank", "www.regions.com", r"\bRegions Bank\b", None),
 "citizens": ("Citizens Bank", "www.citizensbank.com", r"\bCitizens Bank\b", None),
 "fifththird": ("Fifth Third", "www.53.com", r"\bFifth Third\b", None),
 "schwab": ("Charles Schwab", "www.schwab.com", r"\b(?:Charles )?Schwab\b", None),
 "fidelity": ("Fidelity", "www.fidelity.com", r"\bFidelity(?! National| Investments? Fund)\b", None),
 "vanguard": ("Vanguard", "investor.vanguard.com", r"\bVanguard\b", None),
 "amex": ("American Express", "www.americanexpress.com", r"\b(?:American Express|Amex)\b", None),
 "discover": ("Discover", "www.discover.com", r"\bDiscover (?:Card|Bank|Financial|card|customers|app)\b", None),
 "visa": ("Visa", "www.visa.com", r"\bVisa\b", r"\bvisas?\b.{0,30}\b(?:appointment|application|interview|processing|bulletin|holders?|applicants?|travel|immigra|student|H-1B)"),
 "mastercard": ("Mastercard", "www.mastercard.com", r"\bMastercard\b", None),
 "zelle": ("Zelle", "www.zellepay.com", r"\bZelle\b", None),
 "venmo": ("Venmo", "venmo.com", r"\bVenmo\b", None),
 "googlepay": ("Google Pay", "pay.google.com", r"\b(?:Google Pay|Google Wallet|GPay)\b", None),
}
OUT = re.compile(r"\b(?:outages?|is down|are down|was down|went down|goes down|down for (?:some|many|thousands|users|customers)|not working|stopped working|service (?:disruption|interruption|issues?)|"
                 r"technical (?:issues?|difficulties|glitch)|glitch(?:es)?|app (?:issues?|problems?|down|crash)|login (?:issues?|problems?)|can(?:'|no)t (?:log ?in|access|sign in|pay|use)|"
                 r"report(?:s|ing)? (?:problems?|issues?)|unable to (?:log ?in|access|sign in|pay|use)|declined (?:cards?|transactions?)|payments? (?:failing|failed|delayed)|deposits? (?:delayed|missing|not showing))\b", re.I)
NOT_OUT = re.compile(r"\b(?:prepare for|how to|what to do|stocks?|shares|price target|earnings|analysts?|lawsuit settlement|percent|this year|quarter|profits?|revenue|issuance)\b|\d+(?:\.\d+)?\s?%", re.I)

def _now(): return datetime.now(timezone.utc)
def iso(d): return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if d else None
def _get(url, timeout=12, cap=3_000_000):
    rq = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(rq, timeout=timeout) as r: return r.read(cap)

def match(sid, title):
    """True when a headline names this service and reports an outage (not a 'how to prepare' explainer or a stock story)."""
    nm, _h, rx, neg = W[sid]; t = title or ""
    if not re.search(rx, t) or not OUT.search(t) or NOT_OUT.search(t): return False
    if neg and re.search(neg, t, re.I) and not re.search(r"\b(?:bank|card|payment|app|customers)\b", t, re.I): return False
    return True

# ---------------------------------------------------------------- news (two batched Google News RSS searches)
def _q(names):
    return "(" + " OR ".join(f'"{n}"' for n in names) + ') (outage OR down OR "not working" OR glitch OR "technical issues") when:2d'
NEWS_STATE = {"ok": None}
def news_fetch():
    names = [v[0] for v in W.values()]; half = (len(names) + 1) // 2; items = []; ok = 0
    for part in (names[:half], names[half:]):
        u = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": _q(part), "hl": "en-US", "gl": "US", "ceid": "US:en"})
        try: root = ET.fromstring(_get(u, timeout=12)); ok += 1
        except Exception: continue
        for it in root.iter("item"):
            t = (it.findtext("title") or "").strip(); src = (it.findtext("source") or "").strip()
            if src and t.endswith(" - " + src): t = t[: -len(src) - 3]
            try: pd = email.utils.parsedate_to_datetime(it.findtext("pubDate") or "")
            except Exception: pd = None
            if pd and pd.tzinfo is None: pd = pd.replace(tzinfo=timezone.utc)
            items.append(dict(t=t[:200], src=src[:60], url=(it.findtext("link") or "")[:600], at=iso(pd) if pd else None))
    NEWS_STATE["ok"] = ok == 2
    if ok == 0: raise RuntimeError("news search unavailable")   # keep the last good copy (swr) instead of reporting "no news"
    return items

def wire_fetch():
    """Our own scanner's Wire items from the last 2 days (blackout.db, read-only)."""
    out = []; since = iso(_now() - timedelta(hours=NEWS_KEEP_H))
    try:
        c = sqlite3.connect(f"file:{BASE}/blackout.db?mode=ro", uri=True, timeout=10); c.row_factory = sqlite3.Row
        try:
            for r in c.execute("SELECT cluster_id, title, first_seen FROM clusters WHERE first_seen>=? ORDER BY first_seen DESC LIMIT 4000", (since,)):
                t = r["title"] or ""
                if OUT.search(t): out.append(dict(t=t[:200], src="BLACKOUT.NETWORK Wire", url=f"/story/{r['cluster_id']}", at=r["first_seen"]))
        finally: c.close()
    except Exception: pass
    return out

# ---------------------------------------------------------------- website edge check (TLS handshake only, no page scraping)
def tls_ok(host, timeout=6):
    t0 = time.time()
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=timeout) as s:
            with ctx.wrap_socket(s, server_hostname=host): pass
        return True, int((time.time() - t0) * 1000)
    except Exception:
        return False, None

_FAILS = {}
def watch_one(sid, swr):
    """Status for one feedless service. level 0 = no outage found, 2 = news or our Wire reports one, or the site stopped answering."""
    nm, host, _rx, _neg = W[sid]
    allnews = (swr("watch:news", 900, news_fetch, wait=True) or []) + (swr("watch:wire", 900, wire_fetch, wait=True) or [])
    n0 = _now(); seen = set(); hits = []
    for it in allnews:
        if not match(sid, it.get("t")): continue
        k = re.sub(r"\W+", " ", it["t"].lower())[:70]
        if k in seen: continue
        seen.add(k)
        try: at = datetime.fromisoformat(str(it.get("at")).replace("Z", "+00:00"))
        except Exception: at = None
        if at and n0 - at <= timedelta(hours=NEWS_KEEP_H): hits.append(dict(it, age_h=round((n0 - at).total_seconds() / 3600, 1)))
    hits.sort(key=lambda x: x.get("at") or "", reverse=True)
    ok, ms = swr("watch:tls:" + host, 240, lambda: tls_ok(host), wait=True) or (None, None)
    f = _FAILS.get(sid, 0) + 1 if ok is False else 0; _FAILS[sid] = f
    hot = [h for h in hits if h["age_h"] <= NEWS_HOT_H]
    lvl = 0; status = "No outage reported in the news or on this site"
    if hot: lvl = 2; status = "News reports a problem: " + hot[0]["t"][:120]
    if f >= 2: lvl = max(lvl, 2); status = f"{nm}'s website is not answering" + (" and the news reports a problem" if hot else "")
    sig = dict(news=len(hot), news48=len(hits), news_ok=NEWS_STATE.get("ok"), web=("answers" if ok else "not answering" if ok is False else "unknown"), web_ms=ms)
    inc = [dict(t=h["t"][:160], since=h["at"]) for h in hot[:3]]
    return dict(level=lvl, status=status, incidents=inc, days=None, uptime=None, watch=True, sig=sig, news=hits[:8],
                basis="no public status page; news reports, our Wire, a website check and reports on this page")

# ---------------------------------------------------------------- PayPal (public RSS incident feed)
PP_RSS = "https://www.paypal-status.com/feed/rss"
def paypal_one(_feed, bars, hrs, recent):
    root = ET.fromstring(_get(PP_RSS, timeout=12)); by = {}
    for it in root.iter("item"):
        t = (it.findtext("title") or "").strip(); m = re.search(r"\((PP-[A-Z]+-\d+)\)", t)
        try: pd = email.utils.parsedate_to_datetime(it.findtext("pubDate") or "")
        except Exception: pd = None
        if not m or not pd: continue
        by.setdefault(m.group(1), []).append((pd, t, it.findtext("link") or ""))
    spans = []; act = []; rec = []
    for k, ev in by.items():
        ev.sort(); first, last = ev[0], ev[-1]
        title = re.sub(r"^(?:(?:Initial Notification|Detected Resolved|Resolved|Completed|Rescheduled|Update|Investigating|Identified|Monitoring|Detected):\s*)+", "", last[1]).strip()
        maint = "maintenance" in title.lower() or "Completed" in last[1]
        if maint: continue
        done = bool(re.match(r"^(?:Detected Resolved|Resolved)", last[1]))
        s = first[0]; e = last[0] if done else None
        if done and e <= s: title += " (resolution notice; start not published)"   # never invent an incident start or duration
        spans.append((s, e, 2))
        if not done: act.append(dict(t=title[:160], since=iso(s)))
        rec.append((title, s, e, 2))
    days, up = bars(spans)
    lvl = 2 if act else 0
    return dict(level=lvl, status="Incident reported" if act else "No open incidents", incidents=act[:4], days=days, uptime=None, h24=hrs(spans), recent=recent(rec),
                recent_ok=True, basis="PayPal status feed (covers PayPal, Braintree and Venmo checkout)")

# ---------------------------------------------------------------- Apple Pay (Apple's public system status JSON)
APPLE = "https://www.apple.com/support/systemstatus/data/system_status_en_US.js"
AP_LV = {"Outage": 3, "Issue": 2, "Performance": 2, "Maintenance": 0}
def apple_one(svc, bars, hrs, recent):
    t = _get(APPLE, timeout=12).decode("utf-8", "replace"); d = json.loads(t[t.index("{"): t.rindex("}") + 1])
    s = next((x for x in d.get("services") or [] if x.get("serviceName") == svc), None)
    if s is None: raise ValueError("service missing")
    spans = []; act = []; rec = []; aff = None
    for e in s.get("events") or []:
        a = datetime.fromtimestamp(int(e.get("epochStartDate") or 0) / 1000, timezone.utc) if e.get("epochStartDate") else None
        b = datetime.fromtimestamp(int(e.get("epochEndDate")) / 1000, timezone.utc) if e.get("epochEndDate") else None
        lv = AP_LV.get(e.get("statusType"), 1)
        if not a or lv == 0: continue
        spans.append((a, None if e.get("eventStatus") == "ongoing" else b, lv)); rec.append((e.get("message"), a, None if e.get("eventStatus") == "ongoing" else b, lv))
        if e.get("eventStatus") == "ongoing": act.append(dict(t=(e.get("message") or "")[:160], since=iso(a))); aff = e.get("usersAffected") or aff
    days, up = bars(spans)
    lvl = max([AP_LV.get(e.get("statusType"), 1) for e in s.get("events") or [] if e.get("eventStatus") == "ongoing"] or [0])
    r = dict(level=lvl, status="Apple reports a problem" if lvl else "Available (Apple System Status)", incidents=act, days=days, uptime=up, h24=hrs(spans),
             recent=recent(rec), recent_ok=True, basis="Apple System Status")
    if aff: r["affected"] = dict(text=aff, src="Apple System Status")
    return r
