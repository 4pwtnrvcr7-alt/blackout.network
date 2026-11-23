"""Network status board (/network, Nov 23 2026, pt1758u): "Down for me" reports, the incident timeline, 24 h history and
documented chain reactions. Matt asked for a Downdetector-style board that is more useful than the map.

Storage: tables in votes.db (Render-owned, so the box mirrors it and restores it after a restart, same as visitor votes).
  net_reports(svc, ts, zip, st, tok)   one row per tap. ZIP is optional and is the only thing stored about the visitor.
  net_hours(svc, hr, lv)               worst level per service per UTC hour, written by each /api/netmap/data build.
  net_timeline(key, ...)               what broke, when, and when it recovered. Reused by the newsletter network section.
  net_open(svc, ...)                   problems this node detected itself (feeds with no incident list), until they recover.
Per-IP limits are in memory only, keyed by a salted hash; IPs never reach disk or logs. Never touches blackout.db or scoring."""
import hashlib, os, re, secrets, sqlite3, sys, threading, time
from datetime import datetime, timezone, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
def _path(): return os.environ.get("BN_NETBOARD_DB") or os.path.join(BASE, "votes.db")
_SALT = secrets.token_hex(16); _RL = {}; _LK = threading.Lock(); _INIT = set()
KEEP_S = 8 * 86400

def db():
    p = _path(); c = sqlite3.connect(p, timeout=20); c.row_factory = sqlite3.Row
    try: key = (p, os.stat(p).st_ino)   # votes.db can be swapped in by the deploy handoff restore: create the tables again then
    except OSError: key = (p, 0)
    if key not in _INIT:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS net_reports(id INTEGER PRIMARY KEY, svc TEXT, ts INTEGER, zip TEXT, st TEXT, tok TEXT);
        CREATE INDEX IF NOT EXISTS ix_nr_svc_ts ON net_reports(svc, ts);
        CREATE TABLE IF NOT EXISTS net_hours(svc TEXT, hr INTEGER, lv INTEGER, PRIMARY KEY(svc, hr));
        CREATE TABLE IF NOT EXISTS net_timeline(key TEXT PRIMARY KEY, svc TEXT, name TEXT, title TEXT, start TEXT, end TEXT, level INTEGER, src TEXT, upd TEXT);
        CREATE INDEX IF NOT EXISTS ix_nt_start ON net_timeline(start);
        CREATE TABLE IF NOT EXISTS net_open(svc TEXT PRIMARY KEY, start TEXT, level INTEGER, title TEXT);""")
        _INIT.add(key)
    return c

def writable():
    """Same gate render_app.py puts on visitor votes: no writes to votes.db while a deploy hands it over or before it is restored."""
    m = sys.modules.get("__main__"); fr = getattr(m, "FREEZE", None); sy = getattr(m, "SYNC", None)
    if isinstance(fr, dict) and fr.get("until", 0) > time.time(): return False
    if isinstance(sy, dict) and getattr(m, "SYNC_SECRET", "") and not sy.get("restored") and time.time() - float(getattr(m, "BOOTED", 0) or 0) < 900: return False
    return True

def now(): return datetime.now(timezone.utc)
def iso(d): return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if d else None
def pts(s):
    if not s: return None
    try: return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception: return None

# ---------------------------------------------------------------- ZIP -> state (USPS 3-digit prefixes)
_Z3 = [(5, 5, "NY"), (6, 7, "PR"), (8, 8, "VI"), (9, 9, "PR"), (10, 27, "MA"), (28, 29, "RI"), (30, 38, "NH"), (39, 49, "ME"), (50, 54, "VT"), (55, 55, "MA"),
       (56, 59, "VT"), (60, 69, "CT"), (70, 89, "NJ"), (100, 149, "NY"), (150, 196, "PA"), (197, 199, "DE"), (200, 200, "DC"), (201, 201, "VA"), (202, 205, "DC"),
       (206, 219, "MD"), (220, 246, "VA"), (247, 268, "WV"), (270, 289, "NC"), (290, 299, "SC"), (300, 319, "GA"), (320, 339, "FL"), (341, 349, "FL"), (350, 369, "AL"),
       (370, 385, "TN"), (386, 397, "MS"), (398, 399, "GA"), (400, 427, "KY"), (430, 459, "OH"), (460, 479, "IN"), (480, 499, "MI"), (500, 528, "IA"), (530, 549, "WI"),
       (550, 567, "MN"), (569, 569, "DC"), (570, 577, "SD"), (580, 588, "ND"), (590, 599, "MT"), (600, 629, "IL"), (630, 658, "MO"), (660, 679, "KS"), (680, 693, "NE"),
       (700, 714, "LA"), (716, 729, "AR"), (730, 731, "OK"), (733, 733, "TX"), (734, 749, "OK"), (750, 799, "TX"), (800, 816, "CO"), (820, 831, "WY"), (832, 838, "ID"),
       (840, 847, "UT"), (850, 865, "AZ"), (870, 884, "NM"), (885, 885, "TX"), (889, 898, "NV"), (900, 961, "CA"), (967, 968, "HI"), (969, 969, "GU"), (970, 979, "OR"),
       (980, 994, "WA"), (995, 999, "AK")]
def zip_state(z):
    if not re.fullmatch(r"\d{5}", z or ""): return None
    p = int(z[:3])
    for a, b, st in _Z3:
        if a <= p <= b: return st
    return None

# ---------------------------------------------------------------- documented chain reactions (only well-reported ones)
# up: upstream network id. down: tracked network ids that went down with it. also: untracked apps reported in the same outage.
DEPS = [
 dict(up="aws", region="us-east-1", down=["coinbase", "reddit", "ring", "zoom", "chime", "square"],
      also=["Snapchat", "Venmo", "Robinhood", "Slack", "Signal", "Roblox", "Fortnite", "Alexa", "Prime Video", "Duolingo"],
      why="These all failed together in the AWS us-east-1 outage of Oct 20, 2025",
      src="https://www.nbcnews.com/news/us-news/amazon-web-services-outage-websites-offline-rcna238594"),
 dict(up="cloudflare", region="", down=["openai", "discord", "shopify", "coinbase"],
      also=["X", "Spotify", "Canva", "Uber", "Claude", "Indeed", "Perplexity"],
      why="These all failed together in the Cloudflare outage of Nov 18, 2025",
      src="https://www.cnbc.com/2025/11/18/cloudflare-down-outage-traffic-spike-x-chatgpt.html"),
 dict(up="gcp", region="", down=["cloudflare", "discord", "workspace"],
      also=["Spotify", "Snapchat", "Character.AI", "Etsy"],
      why="Cloudflare Workers KV, Access and WARP, plus these apps, failed in the Google Cloud outage of Jun 12, 2025",
      src="https://blog.cloudflare.com/cloudflare-service-outage-june-12-2025/"),
 dict(up="azure", region="", down=["m365"],
      also=["Xbox", "Minecraft"],
      why="Microsoft 365, Xbox and Minecraft failed in the Azure Front Door outage of Oct 29, 2025",
      src="https://azure.status.microsoft/en-us/status/history/"),
]
DEP_IDS = {d["up"] for d in DEPS}

# ---------------------------------------------------------------- reports
def _ipk(ip): return hashlib.sha256((_SALT + str(ip or "?")).encode()).hexdigest()[:20]
def _limited(ip, svc):
    t = time.time(); k = _ipk(ip)
    with _LK:
        if len(_RL) > 50000: _RL.clear()
        h = [x for x in _RL.get(k, []) if t - x[0] < 3600]; _RL[k] = h
        if any(s == svc and t - ts < 900 for ts, s in h): return "You already reported this one. Thanks, it counts for 15 minutes."
        if len(h) >= 12: return "That is a lot of reports from one connection. Try again in a while."
        h.append((t, svc)); return None

def post(d, ip, valid):
    """POST /api/vote/netdown {svc, zip?} or {tok, zip} to add a ZIP to the report just made."""
    d = d if isinstance(d, dict) else {}
    tok = str(d.get("tok") or ""); z = str(d.get("zip") or "").strip()
    if z and not re.fullmatch(r"\d{5}", z): return 400, {"error": "ZIP must be 5 digits"}
    if tok:
        if not re.fullmatch(r"[a-f0-9]{16}", tok) or not z: return 400, {"error": "bad request"}
        st = zip_state(z)
        if not st: return 400, {"error": "That ZIP is not a U.S. ZIP we can place"}
        c = db()
        try:
            n = c.execute("UPDATE net_reports SET zip=?, st=? WHERE tok=? AND zip IS NULL AND ts>=?", (z, st, tok, int(time.time()) - 900)).rowcount; c.commit()
        finally: c.close()
        return (200, {"status": "ok", "st": st}) if n else (404, {"error": "That report can no longer be changed"})
    svc = str(d.get("svc") or "")
    if svc not in valid: return 400, {"error": "unknown service"}
    if not writable(): return 503, {"error": "The site is updating. Please try again in a minute."}
    why = _limited(ip, svc)
    if why: return 429, {"error": why}
    st = zip_state(z) if z else None; tok = secrets.token_hex(8); t = int(time.time())
    c = db()
    try:
        c.execute("INSERT INTO net_reports(svc, ts, zip, st, tok) VALUES(?,?,?,?,?)", (svc, t, z or None, st, tok))
        if secrets.randbelow(50) == 0: c.execute("DELETE FROM net_reports WHERE ts<?", (t - KEEP_S,))
        c.commit()
    finally: c.close()
    _AGG["t"] = 0
    return 200, {"status": "ok", "tok": tok, "st": st}

_AGG = {"t": 0, "v": None}
def reports():
    """{svc: {h1, h24, hrs[24] oldest first, base (avg per hour over 7 days), surge, states{st: n} for the last 3 h}}."""
    if _AGG["v"] is not None and time.time() - _AGG["t"] < 20: return _AGG["v"]
    t = int(time.time()); h0 = t - t % 3600; out = {}
    c = db()
    try:
        for r in c.execute("SELECT svc, ts, st FROM net_reports WHERE ts>=?", (t - 7 * 86400,)):
            o = out.setdefault(r["svc"], dict(h1=0, h24=0, hrs=[0] * 24, wk=0, states={}))
            age = t - r["ts"]; o["wk"] += 1
            if age < 3600: o["h1"] += 1
            if age < 86400:
                o["h24"] += 1; k = 23 - (h0 - (r["ts"] - r["ts"] % 3600)) // 3600
                if 0 <= k < 24: o["hrs"][k] += 1
            if age < 3 * 3600 and r["st"]: o["states"][r["st"]] = o["states"].get(r["st"], 0) + 1
    finally: c.close()
    for o in out.values():
        o["base"] = round(o.pop("wk") / (7 * 24), 2)
        o["surge"] = o["h1"] >= max(5, 4 * o["base"])   # 5+ reports in an hour and 4x the usual rate
    _AGG.update(t=time.time(), v=out); return out

# ---------------------------------------------------------------- history + timeline (called from netmap.build)
def _fmt_title(n, t):
    t = re.sub(r"\s+", " ", str(t or "")).strip()
    return t[:160] if t else ("Outage signal" if n.get("kind") == "asn" else "Problem reported")

def record(nets):
    """Store this build's levels per hour, provider incidents and self-detected problems. Returns nothing; never raises."""
    if not writable(): return
    try:
        n0 = now(); hr = int(n0.timestamp()) // 3600; s_now = iso(n0); rep = reports()
        c = db()
        try:
            for n in nets:
                if n.get("link_only") or n.get("level", -1) < 0: continue
                c.execute("INSERT INTO net_hours(svc, hr, lv) VALUES(?,?,?) ON CONFLICT(svc, hr) DO UPDATE SET lv=MAX(lv, excluded.lv)", (n["id"], hr, int(n["level"])))
                for i in n.get("recent") or []:   # provider incident list (Statuspage, AWS, Azure, Google) and IODA events
                    if not i.get("s") or int(i.get("lv") or 0) < 1: continue
                    key = f"{n['id']}:{i['s']}:{hashlib.sha1(str(i.get('t')).encode()).hexdigest()[:6]}"
                    c.execute("""INSERT INTO net_timeline(key, svc, name, title, start, end, level, src, upd) VALUES(?,?,?,?,?,?,?,?,?)
                                 ON CONFLICT(key) DO UPDATE SET end=excluded.end, level=MAX(level, excluded.level), title=excluded.title, upd=excluded.upd""",
                              (key, n["id"], n["name"], _fmt_title(n, i.get("t")), i["s"], i.get("e"), int(i["lv"]), n.get("basis") or "status page", s_now))
                if not n.get("recent_ok"):   # feeds with no incident list (Stripe): this node notes when a problem starts and ends
                    o = c.execute("SELECT * FROM net_open WHERE svc=?", (n["id"],)).fetchone()
                    if n["level"] >= 2 and not o:
                        c.execute("INSERT INTO net_open VALUES(?,?,?,?)", (n["id"], s_now, n["level"], _fmt_title(n, (n.get("incidents") or [{}])[0].get("t") or n.get("status"))))
                        o = c.execute("SELECT * FROM net_open WHERE svc=?", (n["id"],)).fetchone()
                    if o:
                        end = None if n["level"] >= 2 else s_now
                        c.execute("""INSERT INTO net_timeline VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET end=excluded.end, level=MAX(level, excluded.level), upd=excluded.upd""",
                                  (f"det:{n['id']}:{o['start']}", n["id"], n["name"], o["title"], o["start"], end, max(o["level"], n["level"]), "status page (checked every 5 min)", s_now))
                        if end: c.execute("DELETE FROM net_open WHERE svc=?", (n["id"],))
                r = rep.get(n["id"])
                if r and r.get("surge"):   # a spike in our own "Down for me" reports is part of the log too
                    h = datetime.fromtimestamp(hr * 3600, timezone.utc)
                    c.execute("""INSERT INTO net_timeline VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET title=excluded.title, upd=excluded.upd""",
                              (f"rep:{n['id']}:{hr}", n["id"], n["name"], f"{r['h1']} people reported it down in an hour", iso(h), iso(h + timedelta(hours=1)), 1, "BLACKOUT.NETWORK user reports", s_now))
            if secrets.randbelow(30) == 0:
                c.execute("DELETE FROM net_hours WHERE hr<?", (hr - 8 * 24,))
                c.execute("DELETE FROM net_timeline WHERE start<?", (iso(n0 - timedelta(days=30)),))
            c.commit()
        finally: c.close()
    except Exception:
        pass

def hours(ids):
    """{svc: [24 worst levels, oldest first]} from the stored per-hour history (-1 = no reading that hour)."""
    hr = int(time.time()) // 3600; out = {}
    try:
        c = db()
        try:
            for r in c.execute("SELECT svc, hr, lv FROM net_hours WHERE hr>?", (hr - 24,)):
                if r["svc"] in ids: out.setdefault(r["svc"], [-1] * 24)[23 - (hr - r["hr"])] = r["lv"]
        finally: c.close()
    except Exception: pass
    return out

def timeline(hours_back=72, limit=60):
    """Newest first. Each: svc, name, title, start, end (None = still going), level, src, mins."""
    try:
        c = db()
        try:
            rows = [dict(r) for r in c.execute("SELECT svc, name, title, start, end, level, src FROM net_timeline WHERE start>=? OR (end IS NULL AND start>=?) ORDER BY start DESC LIMIT ?",
                                                (iso(now() - timedelta(hours=hours_back)), iso(now() - timedelta(days=7)), limit * 3))]
        finally: c.close()
    except Exception: return []
    out = []; seen = set()
    for r in rows:
        s, e = pts(r["start"]), pts(r["end"])
        if not s: continue
        if e and e < s: e = s
        k = (r["svc"], r["title"].lower()[:60], r["start"][:13])
        if k in seen: continue
        seen.add(k); r["mins"] = int(((e or now()) - s).total_seconds() // 60); out.append(r)
    return out[:limit]
