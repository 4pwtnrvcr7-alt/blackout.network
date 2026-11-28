"""/markets: one-screen finance overview (Nov 18 2026, pt1661u). Live tiles for metals and energy, crypto, US and global indices,
Treasury yields and the curve, FX and volatility, plus a U.S. debt clock.

Data:
  * market tiles reuse finance.summary() (Yahoo spark / CoinGecko / Treasury CSV, already cached 3 min to 6 h inside finance.py);
  * debt clock: Treasury Fiscal Data "Debt to the Penny" (official, business-daily) and "Interest Expense" (monthly), keyless;
    population from the Census Bureau population clock. Cached 1 h (debt) / 6 h (interest, population) in memory.
    The ticking number is an ESTIMATE: last official total + the average per-second change over the last ~30 days of official data.
Request-time fetches only (no background thread), so it is safe on the Render web node. Kill switch: BN_MARKETS=0."""
import json, os, re, threading, time, urllib.request
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from html import escape as E

BASE = os.path.dirname(os.path.abspath(__file__)); STATIC = os.path.join(BASE, "markets_static")
FILES = {"app.js": "application/javascript", "app.css": "text/css"}
ET = ZoneInfo("America/New_York"); UA = "Mozilla/5.0 (compatible; blackout.network markets page; cached hourly)"
FD = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"
_C, _L = {}, threading.Lock()

def on(): return os.environ.get("BN_MARKETS", "1") != "0"

def _http(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read())

def _cached(key, ttl, fn):
    now = time.time(); hit = _C.get(key)
    if hit and now - hit[0] < ttl: return hit[1]
    with _L:
        hit = _C.get(key)
        if hit and time.time() - hit[0] < ttl: return hit[1]
        try:
            v = fn(); _C[key] = (time.time(), v); return v
        except Exception as ex:
            if hit: return dict(hit[1], stale=f"{type(ex).__name__}")   # keep serving the last good copy
            return {"error": f"{type(ex).__name__}: {str(ex)[:120]}"}

def _debt():
    rows = _http(f"{FD}/v2/accounting/od/debt_to_penny?sort=-record_date&page%5Bsize%5D=45&fields=record_date,tot_pub_debt_out_amt,debt_held_public_amt,intragov_hold_amt")["data"]
    d0 = rows[0]; v0 = float(d0["tot_pub_debt_out_amt"])
    t = lambda r: datetime.fromisoformat(r["record_date"]).replace(hour=16, tzinfo=ET).timestamp()   # official totals are end-of-business-day
    ref = rows[min(len(rows) - 1, 21)]   # ~30 calendar days back
    rate = (v0 - float(ref["tot_pub_debt_out_amt"])) / max(1, t(d0) - t(ref))
    prev = float(rows[1]["tot_pub_debt_out_amt"])
    yr = next((r for r in rows if r["record_date"] <= (datetime.fromisoformat(d0["record_date"]) - timedelta(days=365)).date().isoformat()), None)
    return {"official": v0, "date": d0["record_date"], "t_official": t(d0), "rate_per_s": rate, "rate_ref_date": ref["record_date"],
            "day_change": v0 - prev, "public": float(d0["debt_held_public_amt"]), "intragov": float(d0["intragov_hold_amt"]),
            "series": [[r["record_date"], float(r["tot_pub_debt_out_amt"])] for r in rows[:30]][::-1],
            "src": "https://fiscaldata.treasury.gov/datasets/debt-to-the-penny/"}

def _interest():
    rows = _http(f"{FD}/v2/accounting/od/interest_expense?sort=-record_date&page%5Bsize%5D=100&fields=record_date,month_expense_amt,fytd_expense_amt")["data"]
    d = rows[0]["record_date"]; cur = [r for r in rows if r["record_date"] == d]
    m = sum(float(r["month_expense_amt"] or 0) for r in cur)
    days = datetime.fromisoformat(d).day
    return {"month": m, "date": d, "per_s": m / (days * 86400), "src": "https://fiscaldata.treasury.gov/datasets/interest-expense-debt-outstanding/"}

def _pop():
    j = _http("https://www.census.gov/popclock/data/population.php/us")["us"]
    return {"population": j["population"], "rate": j.get("population_rate") or 0, "t": time.time(), "src": "https://www.census.gov/popclock/"}

PICK = {  # group id -> symbols shown as tiles on /markets (the full set stays on /live#finance)
 "us": ("idx", ["^GSPC", "^DJI", "^IXIC", "^RUT"]),
 "world": ("idx", ["^N225", "^FTSE", "^GDAXI", "^HSI", "000001.SS", "^STOXX50E", "^FCHI", "^KS11", "^BSESN", "^GSPTSE", "^BVSP", "^AXJO"]),
 "metals": ("cmd", ["GC=F", "SI=F", "PL=F", "HG=F", "CL=F", "BZ=F", "NG=F", "RB=F"]),
 "crypto": ("crypto", None),
 "vol": ("vol", ["^VIX", "^MOVE", "^VVIX", "^SKEW"]),
 "fx": ("fx", ["DX-Y.NYB", "EURUSD=X", "JPY=X", "CNY=X", "GBPUSD=X", "CHF=X", "MXN=X", "INR=X"]),
}
SEVERE = {"idx": 2.0, "cmd": 3.0, "crypto": 7.0, "fx": 1.2, "vol": 20.0}

def _tiles():
    try:
        import finance
        s = finance.summary()
        if isinstance(s, tuple): s = s[-1]   # finance.summary() returns (status, body)
    except Exception as ex:
        return {"error": f"{type(ex).__name__}"}
    by = {g["id"]: {it["sym"]: it for it in g["items"]} for g in s.get("groups", [])}
    out = {}
    for key, (gid, syms) in PICK.items():
        src = by.get(gid, {}); syms = syms or list(src)
        out[key] = [{"sym": x, "label": src[x].get("label"), "sub": src[x].get("sub"), "price": src[x].get("price"), "chg_pct": src[x].get("chg_pct"),
                     "spark": (src[x].get("spark") or [])[-48:], "severe": SEVERE.get(gid)} for x in syms if x in src and src[x].get("price") is not None]
    cv = s.get("curve") or {}
    ten = cv.get("tenors") or []; now = cv.get("now") or []; prev = cv.get("prev") or []
    yl = {}
    for want in ("3 Mo", "2 Yr", "5 Yr", "10 Yr", "30 Yr"):
        if want in ten:
            i = ten.index(want); yl[want] = {"now": now[i], "prev": prev[i] if i < len(prev) else None}
    sp = lambda a, b: round((yl[a]["now"] - yl[b]["now"]) * 100) if a in yl and b in yl and yl[a]["now"] is not None and yl[b]["now"] is not None else None
    out["yields"] = {"date": cv.get("date"), "tenors": ten, "now": now, "month_ago": cv.get("month_ago"), "pts": yl,
                     "s2s10": sp("10 Yr", "2 Yr"), "s3m10": sp("10 Yr", "3 Mo"), "src": cv.get("src")}
    out["stress"] = s.get("stress") or []
    cg = s.get("crypto") or {}
    out["crypto_mkt"] = {"mcap": cg.get("total_mcap"), "chg": cg.get("mcap_chg_24h"), "btc_dom": cg.get("btc_dom")}
    out["updated"] = s.get("updated"); out["delay_note"] = s.get("delay_note"); out["stale"] = s.get("stale")
    return out

def data():
    return {"markets": _cached("tiles", 60, _tiles), "debt": _cached("debt", 3600, _debt), "interest": _cached("int", 6 * 3600, _interest),
            "pop": _cached("pop", 6 * 3600, _pop), "server_time": time.time()}

_FILE = {}
def _file(name):
    p = os.path.join(STATIC, name)
    try: mt = os.path.getmtime(p)
    except OSError: return None
    hit = _FILE.get(name)
    if hit and hit[0] == mt: return hit[1]
    b = open(p, "rb").read(); _FILE[name] = (mt, b); return b
def _ver(n):
    try: return str(int(os.path.getmtime(os.path.join(STATIC, n))))
    except OSError: return "0"

SECTIONS = [("debt", "U.S. debt clock"), ("metals", "Metals & energy"), ("crypto", "Crypto"), ("us", "U.S. stocks"), ("world", "World stocks"),
            ("yields", "Treasury yields"), ("fx", "Currencies"), ("vol", "Fear gauges")]

def page_html():
    try:
        import wire_v2; menu = wire_v2.menu_html(); w2 = wire_v2.ST
    except Exception:
        menu = ""; w2 = "/wire2/static"
    title = "Markets: metals, crypto, stocks, yields and the debt clock | BLACKOUT.NETWORK"
    desc = "Gold, silver, oil, crypto, U.S. and world stock indices, Treasury yields, the dollar, fear gauges and a live U.S. national debt clock in one dark, phone-friendly page."
    try:
        import og; ogmeta = og.tags(title=title, desc=desc, url="https://blackout.network/markets", key="finance", og_type="website")
    except Exception: ogmeta = ""
    nav = "".join(f'<a href="#{k}">{E(l)}</a>' for k, l in SECTIONS)
    secs = "".join(f'<section class="mk-sec" id="{k}" aria-labelledby="h_{k}"><div class="mk-sh"><p class="w2-eb">{i:02d}</p><h2 id="h_{k}">{E(l)}</h2></div>'
                   f'<div class="mk-body" data-sec="{k}"><div class="mk-load">Loading</div></div></section>' for i, (k, l) in enumerate(SECTIONS[1:], 2))
    return f'''<!doctype html><html lang="en" data-bn-w2><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{E(title)}</title><meta name="description" content="{E(desc)}"><link rel="canonical" href="https://blackout.network/markets">
{ogmeta}<meta name="theme-color" content="#000">
<link rel="stylesheet" href="{w2}/wire2.css?v=9"><link rel="stylesheet" href="/bn-refresh.css"><link rel="stylesheet" href="/api/markets/app.css?v={_ver("app.css")}">
<link rel="preload" as="image" href="/bnt/media/mkhero-m.jpg?v=1" media="(max-width:700px)"><link rel="preload" as="image" href="/bnt/media/mkvid-d.jpg?v=1" media="(min-width:701px)"></head>
<body class="w2 mk bn-has-ref"><header class="w2-bar" id="w2_bar"><a class="w2-wm" href="/?intro=1" aria-label="BLACKOUT.NETWORK intro">blackout.network</a>
<button type="button" class="w2-mbtn" id="w2_open" aria-label="Open menu" aria-controls="w2_menu" aria-expanded="false"><span class="bn-hx" aria-hidden="true"><span class="bn-hx-bar"></span><span class="bn-hx-bar"></span><span class="bn-hx-bar"></span></span><span class="bn-bl"><span class="bn-bl-a">Menu</span><span class="bn-bl-b">Close</span></span></button></header>
{menu}
<div class="mk-bg" aria-hidden="true"><picture><source media="(max-width:700px)" srcset="/bnt/media/mkhero-m.jpg?v=1"><img src="/bnt/media/mkvid-d.jpg?v=1" alt="" decoding="async" fetchpriority="high"></picture>
<video class="mk-vid" muted loop playsinline preload="none" disablepictureinpicture tabindex="-1" data-webm="/bnt/media/mkvid-d.webm?v=1" data-mp4="/bnt/media/mkvid-d.mp4?v=1"></video><i class="mk-veil"></i></div>
<main id="mk_main">
<section class="mk-hero" aria-label="Markets"><div class="mk-hc"><p class="w2-eb">Markets &middot; Live</p><h1 class="w2-ht">The money</h1>
<p class="w2-hl">Metals, oil, crypto, stocks, bonds, the dollar and the national debt, on one screen.</p>
<div class="mk-debt-hero" id="mk_dh" aria-label="U.S. national debt, estimated now"><p class="mk-k">U.S. national debt, estimated now</p><p class="mk-dn" id="mk_dn">&nbsp;</p>
<p class="mk-ds" id="mk_ds">&nbsp;</p></div>
<a class="w2-btn" href="#mk_start">See every market <span aria-hidden="true">&darr;</span></a></div></section>
<div id="mk_start"></div>
<nav class="mk-nav" aria-label="Sections"><div class="mk-navi">{nav}</div><button type="button" class="bn-ref mk-ref" id="mk_ref" aria-label="Refresh"><i class="tl-ref-fill bn-ref-fill" aria-hidden="true"><i class="tl-ref-sheen bn-ref-sheen"></i></i><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 12a8 8 0 1 1-2.34-5.66M20 4v5h-5" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="miter"/></svg><span class="tl-ref-lab bn-ref-lab"><span class="tl-ref-lab-a bn-ref-lab-a">Refresh</span><span class="tl-ref-lab-b bn-ref-lab-b" aria-hidden="true">Refresh</span></span></button></nav>
<p class="mk-stat" id="mk_stat" aria-live="polite"></p>
<section class="mk-sec" id="debt" aria-labelledby="h_debt"><div class="mk-sh"><p class="w2-eb">01</p><h2 id="h_debt">U.S. debt clock</h2></div><div class="mk-body" data-sec="debt"><div class="mk-load">Loading</div></div></section>
{secs}
<section class="mk-sec mk-more"><a class="w2-btn" href="/live#finance">Full markets dashboard <span aria-hidden="true">&rarr;</span></a>
<p class="mk-src">Big moves also post to <a href="/wire">the Wire</a> under Finance &amp; markets. Prices are delayed (typically 10 to 20 minutes) and refresh every minute on this page. Sources: Yahoo Finance (indices, futures, FX, volatility), CoinGecko (crypto),
U.S. Treasury (daily par yield curve; Debt to the Penny; interest expense), U.S. Census Bureau (population clock). The debt figure between official daily updates is our estimate.
Informational only, not financial advice.</p></section>
</main>
<footer class="w2-foot"><p class="w2-tag">Global threat monitoring</p><p class="w2-legal">Independent early-warning signals. Not an official alert service. <a href="/scoring">How we score</a> · <a href="/privacy">Privacy</a> · <a href="/tos">Terms</a></p></footer>
<script src="{w2}/wire2.js?v=3" defer></script><script src="/bn-refresh.js" defer></script><script src="/api/markets/app.js?v={_ver("app.js")}" defer></script></body></html>'''

def handle_get(path, qs):
    if not on(): return 404, {"error": "not found"}
    if path in ("/markets", "/markets/"):
        return 200, page_html(), "text/html"
    if path.startswith("/api/markets/"):
        n = path[len("/api/markets/"):]
        if n in FILES:
            b = _file(n)
            return (200, b, FILES[n]) if b is not None else (404, {"error": "not found"})
        if n == "data": return 200, data()
    return 404, {"error": "not found"}
