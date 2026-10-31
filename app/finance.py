"""Finance add-on (tab "💹 Finance", MONITOR group, deep link #finance). Informational only: it never touches scanner.py,
scoring, push.py, jets.py, config.json or blackout.db, and nothing here changes a threat score or rank.
Free, no-key public sources (all verified live with curl on 2026-10-31):
  Yahoo Finance chart/spark API (query2.finance.yahoo.com v7 spark + v8 chart) - indices, ETFs, stocks, futures, FX, VIX family, MOVE, DXY,
      crypto charts. Delayed (exchange-dependent, typically 10-20 min; some feeds near real time).
  CoinGecko free API (api.coingecko.com /api/v3/global, /coins/markets) - total crypto market cap, BTC dominance, market caps, ATH drawdown.
  US Treasury daily par yield curve CSV (home.treasury.gov) - end of day.
  Deutsche Bundesbank statistics API (10-year Bund, daily), Japan MOF JGB yield CSV (daily) - end of day.
  Cboe: daily options market statistics (put/call ratios, previous session) and VIX/VIX3M history CSVs.
  Frankfurter (api.frankfurter.dev, ECB euro reference rates, daily ~16:00 CET).
Caching: quotes 3 min, detail charts 2-30 min, CoinGecko 3 min, yields/put-call 1-6 h; one batched spark call per 20 symbols, so a full refresh
is ~5 Yahoo calls. Last good data is kept in finance.db and served (marked stale) if a source fails.
Daily closes: finance.db `closes` (permanent) and the shared Live Archive log (live_archive.db, section "finance"), written on the box only."""
import builtins, csv, io, json, os, re, sqlite3, sys, threading, time, urllib.parse, urllib.request, gzip
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

BASE = os.path.dirname(os.path.abspath(__file__)); DB = os.path.join(BASE, "finance.db"); LADB = os.path.join(BASE, "live_archive.db")
STATIC = os.path.join(BASE, "finance_static"); FILES = {"app.js": "application/javascript", "app.css": "text/css", "lwc.js": "application/javascript", "LWC_LICENSE.txt": "text/plain"}
ET = ZoneInfo("America/New_York"); UA = "Mozilla/5.0 (compatible; blackout.network finance tab; cached 3-min poll)"
WEB_ONLY = bool(os.environ.get("BN_WEB_ONLY"))
Q_TTL = 180; CG_TTL = 180; SLOW_TTL = 3600; VERY_SLOW = 6 * 3600
YQ = ["https://query2.finance.yahoo.com", "https://query1.finance.yahoo.com"]

# group id, label, note, [(yahoo symbol, label, extra)]
G = [
 ("idx", "Global stock indices", "Delayed index levels from Yahoo Finance", [
  ("^GSPC", "S&P 500", "US"), ("^DJI", "Dow Jones", "US"), ("^IXIC", "Nasdaq Composite", "US"), ("^RUT", "Russell 2000", "US"),
  ("^GSPTSE", "S&P/TSX", "Canada"), ("^BVSP", "Bovespa", "Brazil"), ("^MXX", "IPC Mexico", "Mexico"), ("^FTSE", "FTSE 100", "UK"),
  ("^GDAXI", "DAX", "Germany"), ("^FCHI", "CAC 40", "France"), ("^STOXX50E", "Euro Stoxx 50", "Eurozone"), ("^IBEX", "IBEX 35", "Spain"),
  ("FTSEMIB.MI", "FTSE MIB", "Italy"), ("^N225", "Nikkei 225", "Japan"), ("^HSI", "Hang Seng", "Hong Kong"), ("000001.SS", "Shanghai Composite", "China"),
  ("^KS11", "KOSPI", "S. Korea"), ("^TWII", "Taiwan Weighted", "Taiwan"), ("^AXJO", "S&P/ASX 200", "Australia"), ("^BSESN", "BSE Sensex", "India"),
  ("^NSEI", "Nifty 50", "India")]),
 ("etf", "Key ETFs", "US-listed exchange-traded funds", [
  ("SPY", "SPDR S&P 500", "US large cap"), ("QQQ", "Invesco QQQ", "Nasdaq-100"), ("IWM", "iShares Russell 2000", "US small cap"), ("DIA", "SPDR Dow", "Dow 30"),
  ("EFA", "iShares MSCI EAFE", "Developed ex-US"), ("EEM", "iShares MSCI EM", "Emerging mkts"), ("TLT", "iShares 20+Y Treasury", "Long bonds"),
  ("IEF", "iShares 7-10Y Treasury", "Mid bonds"), ("HYG", "iShares High Yield", "Junk bonds"), ("LQD", "iShares IG Corporate", "IG credit"),
  ("GLD", "SPDR Gold", "Gold"), ("SLV", "iShares Silver", "Silver"), ("USO", "US Oil Fund", "Crude oil"), ("UNG", "US Natural Gas Fund", "Nat gas"),
  ("XLE", "Energy Select", "Energy"), ("XLF", "Financial Select", "Banks"), ("SMH", "VanEck Semiconductor", "Chips"), ("VIXY", "ProShares VIX Short-Term", "VIX futures")]),
 ("stk", "Mega-cap stocks", "Largest listed companies", [
  ("AAPL", "Apple", ""), ("MSFT", "Microsoft", ""), ("NVDA", "Nvidia", ""), ("GOOGL", "Alphabet", ""), ("AMZN", "Amazon", ""), ("META", "Meta", ""),
  ("TSLA", "Tesla", ""), ("AVGO", "Broadcom", ""), ("BRK-B", "Berkshire Hathaway", ""), ("JPM", "JPMorgan Chase", ""), ("LLY", "Eli Lilly", ""),
  ("TSM", "TSMC (ADR)", ""), ("ASML", "ASML", ""), ("XOM", "Exxon Mobil", "")]),
 ("rates", "Bond yields (intraday)", "CBOE Treasury yield indices via Yahoo, in %; official end-of-day curve below", [
  ("^IRX", "US 13-week T-bill", ""), ("^FVX", "US 5-year", ""), ("^TNX", "US 10-year", ""), ("^TYX", "US 30-year", "")]),
 ("vol", "Volatility & options", "Cboe volatility indices via Yahoo; put/call ratios from Cboe daily statistics below", [
  ("^VIX", "VIX (S&P 500 30-day)", ""), ("^VIX9D", "VIX9D (9-day)", ""), ("^VIX3M", "VIX3M (3-month)", ""), ("^VIX6M", "VIX6M (6-month)", ""),
  ("^VVIX", "VVIX (vol of VIX)", ""), ("^SKEW", "Cboe SKEW (tail risk)", ""), ("^MOVE", "ICE BofA MOVE (bond vol)", "")]),
 ("fx", "Forex", "Spot FX via Yahoo (delayed); ECB reference rates below", [
  ("DX-Y.NYB", "US Dollar Index (DXY)", ""), ("EURUSD=X", "EUR/USD", ""), ("JPY=X", "USD/JPY", ""), ("GBPUSD=X", "GBP/USD", ""), ("CHF=X", "USD/CHF", ""),
  ("AUDUSD=X", "AUD/USD", ""), ("CAD=X", "USD/CAD", ""), ("NZDUSD=X", "NZD/USD", ""), ("CNY=X", "USD/CNY", ""), ("MXN=X", "USD/MXN", ""), ("INR=X", "USD/INR", "")]),
 ("crypto", "Crypto", "Prices/charts via Yahoo; market caps and drawdowns via CoinGecko", [
  ("BTC-USD", "Bitcoin", "bitcoin"), ("ETH-USD", "Ethereum", "ethereum"), ("SOL-USD", "Solana", "solana"), ("XRP-USD", "XRP", "ripple"),
  ("BNB-USD", "BNB", "binancecoin"), ("DOGE-USD", "Dogecoin", "dogecoin"), ("ADA-USD", "Cardano", "cardano"), ("AVAX-USD", "Avalanche", "avalanche-2")]),
 ("cmd", "Commodities", "Front-month futures via Yahoo (CME/ICE, delayed)", [
  ("CL=F", "WTI crude oil", "$/bbl"), ("BZ=F", "Brent crude", "$/bbl"), ("NG=F", "Natural gas (Henry Hub)", "$/MMBtu"), ("RB=F", "RBOB gasoline", "$/gal"),
  ("GC=F", "Gold", "$/oz"), ("SI=F", "Silver", "$/oz"), ("PL=F", "Platinum", "$/oz"), ("HG=F", "Copper", "$/lb"), ("ZW=F", "Wheat", "¢/bu"), ("ZC=F", "Corn", "¢/bu")]),
]
SYM = {s: (gid, lab, ex) for gid, _, _, items in G for s, lab, ex in items}
EXCH = [  # name, representative symbol, venue note
 ("NYSE / Nasdaq", "^GSPC"), ("Toronto (TSX)", "^GSPTSE"), ("São Paulo (B3)", "^BVSP"), ("London (LSE)", "^FTSE"), ("Frankfurt (Xetra)", "^GDAXI"),
 ("Paris (Euronext)", "^FCHI"), ("Tokyo (TSE)", "^N225"), ("Hong Kong (HKEX)", "^HSI"), ("Shanghai (SSE)", "000001.SS"), ("Korea (KRX)", "^KS11"),
 ("India (NSE/BSE)", "^NSEI"), ("Sydney (ASX)", "^AXJO"), ("CME futures (oil)", "CL=F")]
RANGES = {"1d": ("1d", "5m", 120), "5d": ("5d", "15m", 300), "1mo": ("1mo", "60m", 1800), "6mo": ("6mo", "1d", 3600), "1y": ("1y", "1d", 3600)}
UST_COLS = ["1 Mo", "2 Mo", "3 Mo", "4 Mo", "6 Mo", "1 Yr", "2 Yr", "3 Yr", "5 Yr", "7 Yr", "10 Yr", "20 Yr", "30 Yr"]
CITES = {
 "vix": ("Cboe: VIX Index", "https://www.cboe.com/tradable_products/vix/"),
 "vix3m": ("Cboe: VIX3M Index (term structure)", "https://www.cboe.com/us/indices/dashboard/vix3m/"),
 "curve": ("NY Fed (Estrella & Mishkin): The Yield Curve as a Predictor of U.S. Recessions", "https://www.newyorkfed.org/research/current_issues/ci2-7.html"),
 "dxy": ("BIS Working Paper 695: The dollar exchange rate as a global risk factor", "https://www.bis.org/publ/work695.htm"),
 "bear": ("Investor.gov (SEC): Bear market — a fall of 20% or more", "https://www.investor.gov/introduction-investing/investing-basics/glossary/bear-market"),
 "pcr": ("Cboe: daily options market statistics", "https://www.cboe.com/us/options/market_statistics/daily/"),
}
ST = getattr(builtins, "_bn_finance", None)
if ST is None: ST = builtins._bn_finance = {"mem": {}, "locks": {}, "started": False, "last_tick": None, "err": {}}
_glock = threading.Lock()

def iso(d=None): return (d or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
def db():
    c = sqlite3.connect(DB, timeout=15); c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE IF NOT EXISTS cache(k TEXT PRIMARY KEY, ts REAL, payload TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS closes(sym TEXT, day TEXT, label TEXT, grp TEXT, close REAL, prev REAL, chg_pct REAL, market_time TEXT, final INTEGER, src TEXT, PRIMARY KEY(sym, day))")
    c.execute("CREATE TABLE IF NOT EXISTS fetchlog(ts TEXT, src TEXT, ok INTEGER, ms INTEGER, error TEXT)")
    return c

def http(url, timeout=25, accept="application/json"):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept, "Accept-Encoding": "gzip"})
    t0 = time.time(); err = None
    try:
        r = urllib.request.urlopen(req, timeout=timeout); b = r.read(30_000_000)
        if r.headers.get("Content-Encoding") == "gzip": b = gzip.decompress(b)
        return b
    except Exception as ex: err = str(ex)[:200]; raise
    finally:
        try:
            c = db(); c.execute("INSERT INTO fetchlog VALUES(?,?,?,?,?)", (iso(), urllib.parse.urlsplit(url).netloc, 0 if err else 1, int((time.time() - t0) * 1000), err))
            c.execute("DELETE FROM fetchlog WHERE rowid NOT IN (SELECT rowid FROM fetchlog ORDER BY rowid DESC LIMIT 2000)"); c.commit(); c.close()
        except Exception: pass

def yahoo(path):
    last = None
    for h in YQ:
        try: return json.loads(http(h + path))
        except Exception as ex: last = ex
    raise last

def cached(key, ttl, fn, force=False):
    """Memory -> finance.db -> upstream. On failure returns the last good payload flagged stale."""
    m = ST["mem"].get(key)
    if m and not force and time.time() - m[0] < ttl: return m[1]
    with _glock: lk = ST["locks"].setdefault(key, threading.Lock())
    with lk:
        m = ST["mem"].get(key)
        if m and not force and time.time() - m[0] < ttl: return m[1]
        if not m:
            try:
                c = db(); r = c.execute("SELECT ts, payload FROM cache WHERE k=?", (key,)).fetchone(); c.close()
                if r: m = (r["ts"], json.loads(r["payload"])); ST["mem"][key] = m
                if m and not force and time.time() - m[0] < ttl: return m[1]
            except Exception: pass
        fl = ST.setdefault("fail", {}).get(key)
        if not force and fl and time.time() - fl < min(ttl, 900):     # back off after a failure (no hammering a down/403ing source)
            return (dict(m[1], stale=True) if m and isinstance(m[1], dict) else (m[1] if m else None))
        try:
            v = fn(); now = time.time(); ST["fail"].pop(key, None); ST["mem"][key] = (now, v); ST["err"].pop(key, None)
            try: c = db(); c.execute("INSERT OR REPLACE INTO cache VALUES(?,?,?)", (key, now, json.dumps(v))); c.commit(); c.close()
            except Exception: pass
            return v
        except Exception as ex:
            ST["fail"][key] = time.time()
            ST["err"][key] = f"{type(ex).__name__}: {str(ex)[:160]}"
            if m:
                v = m[1]
                if isinstance(v, dict): v = dict(v, stale=True, stale_since=iso(datetime.fromtimestamp(m[0], timezone.utc)))
                return v
            return None

# ------------------------------------------------------------------ quotes (batched spark)
def _down(xs, n=72):
    if len(xs) <= n: return xs
    step = len(xs) / n; return [xs[int(i * step)] for i in range(n)] + [xs[-1]]

def _spark(syms):
    out = {}
    for i in range(0, len(syms), 20):
        part = syms[i:i + 20]
        j = yahoo("/v7/finance/spark?" + urllib.parse.urlencode({"symbols": ",".join(part), "range": "1d", "interval": "5m"}))
        for x in (j.get("spark") or {}).get("result") or []:
            try:
                r = x["response"][0]; m = r["meta"]; cl = (r.get("indicators", {}).get("quote") or [{}])[0].get("close") or []
                ts = r.get("timestamp") or []
                pts = [[t, round(v, 6)] for t, v in zip(ts, cl) if v is not None]
                price = m.get("regularMarketPrice"); prev = m.get("chartPreviousClose") or m.get("previousClose")
                ctp = (m.get("currentTradingPeriod") or {})
                out[x["symbol"]] = {"price": price, "prev": prev, "chg": (price - prev) if price is not None and prev else None,
                    "chg_pct": ((price / prev - 1) * 100) if price is not None and prev else None, "cur": m.get("currency"),
                    "market_time": iso(datetime.fromtimestamp(m["regularMarketTime"], timezone.utc)) if m.get("regularMarketTime") else None,
                    "tz": m.get("exchangeTimezoneName"), "exch": m.get("fullExchangeName") or m.get("exchangeName"),
                    "hi52": m.get("fiftyTwoWeekHigh"), "lo52": m.get("fiftyTwoWeekLow"), "day_hi": m.get("regularMarketDayHigh"), "day_lo": m.get("regularMarketDayLow"),
                    "spark": [p[1] for p in _down(pts)], "period": {k: ctp.get(k) for k in ("pre", "regular", "post")}}
            except Exception: continue
    return out

def quotes(force=False):
    def f():
        q = _spark(list(SYM))
        if len(q) < len(SYM) * 0.5: raise RuntimeError(f"Yahoo spark returned only {len(q)}/{len(SYM)} symbols")
        return {"fetched": iso(), "q": q}
    return cached("quotes", Q_TTL, f, force)

# ------------------------------------------------------------------ CoinGecko
def coingecko(force=False):
    ids = [ex for s, (g, l, ex) in SYM.items() if g == "crypto"]
    def f():
        gl = json.loads(http("https://api.coingecko.com/api/v3/global"))["data"]
        mk = json.loads(http("https://api.coingecko.com/api/v3/coins/markets?" + urllib.parse.urlencode({"vs_currency": "usd", "ids": ",".join(ids), "price_change_percentage": "24h,7d"})))
        return {"fetched": iso(), "total_mcap": gl["total_market_cap"].get("usd"), "total_vol": gl["total_volume"].get("usd"),
                "mcap_chg_24h": gl.get("market_cap_change_percentage_24h_usd"), "btc_dom": gl["market_cap_percentage"].get("btc"), "eth_dom": gl["market_cap_percentage"].get("eth"),
                "coins": {c["id"]: {"price": c.get("current_price"), "mcap": c.get("market_cap"), "rank": c.get("market_cap_rank"), "ath": c.get("ath"),
                          "ath_date": c.get("ath_date"), "ath_chg": c.get("ath_change_percentage"), "chg24": c.get("price_change_percentage_24h"),
                          "chg7d": c.get("price_change_percentage_7d_in_currency")} for c in mk}}
    return cached("coingecko", CG_TTL, f, force)

# ------------------------------------------------------------------ yields
def _ust_year(y):
    url = f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{y}/all?type=daily_treasury_yield_curve&field_tdr_date_value={y}&page&_format=csv"
    rows = list(csv.DictReader(io.StringIO(http(url, accept="text/csv").decode("utf-8-sig"))))
    out = []
    for r in rows:
        try: d = datetime.strptime(r["Date"], "%m/%d/%Y").strftime("%Y-%m-%d")
        except Exception: continue
        out.append({"date": d, **{k: (float(r[k]) if r.get(k) not in (None, "") else None) for k in UST_COLS}})
    return sorted(out, key=lambda x: x["date"])

def ust(force=False):
    def f():
        y = datetime.now(ET).year; rows = _ust_year(y)
        try: rows = _ust_year(y - 1) + rows
        except Exception: pass
        return {"fetched": iso(), "rows": rows[-300:], "src": "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve"}
    return cached("ust", SLOW_TTL, f, force)

def bund(force=False):
    def f():
        t = http("https://api.statistiken.bundesbank.de/rest/data/BBSIS/D.I.ZAR.ZI.EUR.S1311.B.A604.R10XX.R.A.A._Z._Z.A?format=csv&lastNObservations=300&lang=en", accept="text/csv").decode("utf-8", "replace")
        pts = []
        for line in t.splitlines():
            m = re.match(r"^(\d{4}-\d{2}-\d{2}),(-?\d+(?:\.\d+)?)\s*(?:,|$)", line)
            if m: pts.append([m.group(1), float(m.group(2))])
        if not pts: raise RuntimeError("no Bundesbank observations")
        return {"fetched": iso(), "pts": pts, "src": "https://www.bundesbank.de/en/statistics/money-and-capital-markets/interest-rates-and-yields"}
    return cached("bund10", SLOW_TTL, f, force)

def _mof(url):
    t = http(url, accept="text/csv").decode("utf-8", "replace"); pts = []
    for row in csv.reader(io.StringIO(t)):
        if len(row) > 10 and re.match(r"^\d{4}/\d{1,2}/\d{1,2}$", row[0]) and re.match(r"^-?\d+(?:\.\d+)?$", row[10] or ""):
            pts.append([datetime.strptime(row[0], "%Y/%m/%d").strftime("%Y-%m-%d"), float(row[10])])
    return pts

def jgb(force=False):
    def hist():
        cut = (datetime.now(ET) - timedelta(days=400)).strftime("%Y-%m-%d")
        return {"pts": [p for p in _mof("https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv") if p[0] >= cut]}
    def f():
        h = cached("jgb_hist", 24 * 3600, hist) or {"pts": []}
        cur = _mof("https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv")
        d = {p[0]: p[1] for p in h["pts"]}; d.update({p[0]: p[1] for p in cur})
        if not d: raise RuntimeError("no MOF observations")
        return {"fetched": iso(), "pts": sorted([[k, v] for k, v in d.items()])[-300:], "src": "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/index.htm"}
    return cached("jgb10", SLOW_TTL, f, force)

# ------------------------------------------------------------------ Cboe put/call, ECB FX, VIX long-run mean
def pcr(force=False):
    def f():
        d = datetime.now(ET)
        for back in range(0, 8):
            day = (d - timedelta(days=back))
            if day.weekday() > 4: continue
            if back == 0 and d.hour < 18: continue          # today's file is complete after the close
            try: j = json.loads(http(f"https://cdn.cboe.com/data/us/options/market_statistics/daily/{day:%Y-%m-%d}_daily_options"))
            except Exception: continue
            rat = {x["name"]: float(x["value"]) for x in j.get("ratios") or [] if re.match(r"^[\d.]+$", str(x.get("value", "")))}
            if rat: return {"fetched": iso(), "date": f"{day:%Y-%m-%d}", "ratios": rat, "src": CITES["pcr"][1]}
        raise RuntimeError("no Cboe daily statistics in the last week")
    v = cached("pcr", SLOW_TTL, f, force)
    if v and v.get("date") and not WEB_ONLY:
        try:
            c = db()
            for k, x in v["ratios"].items():
                c.execute("INSERT OR IGNORE INTO closes VALUES(?,?,?,?,?,?,?,?,?,?)", ("PCR:" + k, v["date"], k.title(), "vol", x, None, None, v["date"], 1, "Cboe"))
            c.commit(); c.close()
        except Exception: pass
    return v

def ecb(force=False):
    def f():
        j = json.loads(http("https://api.frankfurter.dev/v1/latest?from=USD"))
        return {"fetched": iso(), "date": j.get("date"), "rates": j.get("rates"), "src": "https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html"}
    return cached("ecb", SLOW_TTL, f, force)

def vix_hist(force=False):
    def f():
        rows = list(csv.DictReader(io.StringIO(http("https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv", accept="text/csv").decode())))
        cl = [float(r["CLOSE"]) for r in rows if r.get("CLOSE")]
        return {"fetched": iso(), "mean": sum(cl) / len(cl), "n": len(cl), "since": rows[0]["DATE"], "pct_above_30": 100 * sum(1 for x in cl if x > 30) / len(cl),
                "pct_above_20": 100 * sum(1 for x in cl if x > 20) / len(cl)}
    return cached("vixhist", VERY_SLOW, f, force)

# ------------------------------------------------------------------ market status (ET)
def _fmt_et(ts):
    if not ts: return None
    d = datetime.fromtimestamp(ts, timezone.utc).astimezone(ET); return d.strftime("%a %-I:%M %p ") + d.tzname()

def markets(q):
    now = time.time(); out = []
    for name, sym in EXCH:
        x = q.get(sym) or {}; p = x.get("period") or {}; reg = p.get("regular") or {}; pre = p.get("pre") or {}; post = p.get("post") or {}
        s, e = reg.get("start"), reg.get("end")
        if s and e and s <= now < e: st = "open"
        elif pre.get("start") and pre.get("end") and pre["start"] <= now < pre["end"]: st = "pre-market"
        elif post.get("start") and post.get("end") and post["start"] <= now < post["end"]: st = "after-hours"
        else: st = "closed"
        out.append({"name": name, "sym": sym, "status": st, "session": f"{_fmt_et(s)} – {_fmt_et(e)}" if s else None,
                    "last_trade": x.get("market_time"), "note": "session per Yahoo's exchange calendar (holidays included)"})
    d = datetime.now(ET); wd = d.weekday(); h = d.hour + d.minute / 60
    fx_open = not (wd == 5 or (wd == 4 and h >= 17) or (wd == 6 and h < 17))
    out.append({"name": "Forex (OTC, 24/5)", "sym": "EURUSD=X", "status": "open" if fx_open else "closed", "session": "Sun 5:00 PM – Fri 5:00 PM ET", "last_trade": (q.get("EURUSD=X") or {}).get("market_time")})
    out.append({"name": "Crypto (24/7)", "sym": "BTC-USD", "status": "open", "session": "always open", "last_trade": (q.get("BTC-USD") or {}).get("market_time")})
    return out

# ------------------------------------------------------------------ stress panel (informational only)
def stress(q, cg, u, vh, p):
    out = []
    v = (q.get("^VIX") or {}).get("price"); v3 = (q.get("^VIX3M") or {}).get("price")
    if v is not None:
        lvl = "high" if v >= 30 else "elevated" if v >= 20 else "calm"
        note = f"long-run mean {vh['mean']:.1f} since {vh['since']} (Cboe history; above 30 on {vh['pct_above_30']:.0f}% of days)" if vh else ""
        out.append({"k": "VIX", "value": f"{v:.2f}", "level": lvl, "rule": "calm < 20 ≤ elevated < 30 ≤ high", "detail": note, "cite": CITES["vix"]})
    if v and v3:
        r = v / v3; out.append({"k": "VIX / VIX3M", "value": f"{r:.2f}", "level": "high" if r >= 1.0 else "elevated" if r >= 0.95 else "calm",
            "rule": "< 0.95 contango (normal) · ≥ 1.00 backwardation (near-term fear above 3-month)", "detail": f"VIX {v:.2f} vs VIX3M {v3:.2f}", "cite": CITES["vix3m"]})
    if u and u.get("rows"):
        r = u["rows"][-1]
        if r.get("10 Yr") is not None and r.get("2 Yr") is not None:
            s = r["10 Yr"] - r["2 Yr"]; s3 = (r["10 Yr"] - r["3 Mo"]) if r.get("3 Mo") is not None else None
            out.append({"k": "2s10s curve", "value": f"{s * 100:+.0f} bp", "level": "high" if s < 0 else "elevated" if s < 0.25 else "calm",
                "rule": "< 0 bp inverted · 0–25 bp flat · > 25 bp normal", "detail": f"10Y {r['10 Yr']:.2f}% − 2Y {r['2 Yr']:.2f}% (Treasury, {r['date']})" + (f"; 10Y−3M {s3 * 100:+.0f} bp (NY Fed's preferred recession signal)" if s3 is not None else ""),
                "cite": CITES["curve"]})
    d = q.get("DX-Y.NYB") or {}
    if d.get("price"):
        out.append({"k": "DXY", "value": f"{d['price']:.2f}", "level": None, "rule": "a rapidly strengthening dollar tightens global financial conditions (see 3-month change in the chart)",
                    "detail": f"day {d['chg_pct']:+.2f}% · 52-wk range {d.get('lo52') or 0:.1f}–{d.get('hi52') or 0:.1f}" if d.get("chg_pct") is not None else "", "cite": CITES["dxy"], "sym": "DX-Y.NYB"})
    b = ((cg or {}).get("coins") or {}).get("bitcoin")
    if b and b.get("ath_chg") is not None:
        dd = b["ath_chg"]; out.append({"k": "BTC drawdown", "value": f"{dd:.1f}%", "level": "high" if dd <= -50 else "elevated" if dd <= -20 else "calm",
            "rule": "> −20% normal · ≤ −20% bear-market territory · ≤ −50% severe", "detail": f"vs all-time high ${b['ath']:,.0f} ({(b.get('ath_date') or '')[:10]}, CoinGecko)", "cite": CITES["bear"]})
    if p and p.get("ratios"):
        t = p["ratios"].get("TOTAL PUT/CALL RATIO")
        if t is not None:
            out.append({"k": "Put/call (total)", "value": f"{t:.2f}", "level": "high" if t >= 1.2 else "elevated" if t >= 1.0 else "calm",
                "rule": "< 1.00 normal · ≥ 1.00 heavy hedging · ≥ 1.20 extreme", "detail": f"Cboe session {p['date']}; equity-only {p['ratios'].get('EQUITY PUT/CALL RATIO', '—')}", "cite": CITES["pcr"]})
    return out

# ------------------------------------------------------------------ daily-close archive (box only)
def archive(q):
    if WEB_ONLY or not q: return 0
    n = 0; now = time.time(); c = db()
    try:
        la = sqlite3.connect(LADB, timeout=15)
        la.execute("""CREATE TABLE IF NOT EXISTS sessions(id INTEGER PRIMARY KEY AUTOINCREMENT, section TEXT, key TEXT, title TEXT, channel TEXT,
                      url TEXT, status TEXT, first_seen TEXT, last_seen TEXT, ended INTEGER DEFAULT 0)""")
    except Exception: la = None
    try:
        for s, x in q.items():
            if s not in SYM or x.get("price") is None or not x.get("market_time"): continue
            gid, lab, _ = SYM[s]; reg = (x.get("period") or {}).get("regular") or {}
            tz = ZoneInfo(x["tz"]) if x.get("tz") else ET
            mt = datetime.strptime(x["market_time"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            day = mt.astimezone(tz).strftime("%Y-%m-%d")
            final = 1 if (gid != "crypto" and reg.get("end") and now >= reg["end"]) else 0
            c.execute("INSERT OR REPLACE INTO closes VALUES(?,?,?,?,?,?,?,?,?,?)", (s, day, lab, gid, x["price"], x.get("prev"), x.get("chg_pct"), x["market_time"], final, "Yahoo Finance (delayed)"))
            if la is not None:
                key = f"fin:{s}:{day}"; st = f"{'close' if final else 'last'} {x['price']:,.4g} ({x['chg_pct']:+.2f}%)" if x.get("chg_pct") is not None else f"last {x['price']}"
                r = la.execute("SELECT id FROM sessions WHERE section='finance' AND key=?", (key,)).fetchone()
                first = iso(datetime.fromtimestamp(reg["start"], timezone.utc)) if reg.get("start") and gid != "crypto" else iso(mt.astimezone(tz).replace(hour=0, minute=0, second=0).astimezone(timezone.utc))
                url = "https://finance.yahoo.com/quote/" + urllib.parse.quote(s)
                if r: la.execute("UPDATE sessions SET status=?, last_seen=?, ended=? WHERE id=?", (st + " · Yahoo, delayed", x["market_time"], final, r[0]))
                else: la.execute("INSERT INTO sessions(section,key,title,channel,url,status,first_seen,last_seen,ended) VALUES('finance',?,?,?,?,?,?,?,?)",
                                 (key, f"{lab} ({s})", dict((g[0], g[1]) for g in G)[gid], url, st + " · Yahoo, delayed", first, x["market_time"], final))
            n += 1
        c.commit()
        if la is not None: la.commit(); la.close()
    finally: c.close()
    return n

def tick():
    q = quotes(); ST["last_tick"] = iso()
    if q and not q.get("stale"): archive(q["q"])
    pcr()

def _loop():
    time.sleep(30)
    while True:
        try: sys.modules.get("finance", sys.modules[__name__]).tick()
        except Exception as ex: print("finance tick:", ex, flush=True)
        time.sleep(600)
if not ST["started"] and not WEB_ONLY:
    ST["started"] = True; threading.Thread(target=_loop, daemon=True, name="finance-archive").start()

# ------------------------------------------------------------------ API
def summary(force=False):
    q = quotes(force) or {"q": {}}; Q = q.get("q") or {}
    cg = coingecko(force); u = ust(); bd = bund(); jg = jgb(); p = pcr(); fx = ecb(); vh = vix_hist()
    groups = []
    for gid, glab, note, items in G:
        rows = []
        for s, lab, ex in items:
            x = dict(Q.get(s) or {}); x.pop("period", None)
            row = {"sym": s, "label": lab, "sub": ex if gid != "crypto" else "", **x}
            if gid == "crypto" and cg:
                cc = (cg.get("coins") or {}).get(ex) or {}; row.update({"mcap": cc.get("mcap"), "ath_chg": cc.get("ath_chg"), "chg7d": cc.get("chg7d"), "rank": cc.get("rank")})
            rows.append(row)
        groups.append({"id": gid, "label": glab, "note": note, "items": rows})
    curve = None
    if u and u.get("rows"):
        last = u["rows"][-1]; prev = u["rows"][-2] if len(u["rows"]) > 1 else None
        ago = next((r for r in reversed(u["rows"]) if r["date"] <= (datetime.strptime(last["date"], "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")), None)
        curve = {"date": last["date"], "tenors": UST_COLS, "now": [last.get(k) for k in UST_COLS], "prev": [prev.get(k) for k in UST_COLS] if prev else None,
                 "month_ago": [ago.get(k) for k in UST_COLS] if ago else None, "month_ago_date": ago["date"] if ago else None, "src": u["src"], "stale": u.get("stale")}
    intl = []
    for k, lab, v in (("BUND10", "Germany 10-year Bund", bd), ("JGB10", "Japan 10-year JGB", jg)):
        if v and v.get("pts"):
            pts = v["pts"]; intl.append({"sym": k, "label": lab, "date": pts[-1][0], "price": pts[-1][1], "prev": pts[-2][1] if len(pts) > 1 else None,
                                         "spark": [x[1] for x in pts[-60:]], "src": v["src"], "stale": v.get("stale")})
    if u and u.get("rows"):
        for col, k, lab in (("2 Yr", "UST:2 Yr", "US 2-year (Treasury)"), ("10 Yr", "UST:10 Yr", "US 10-year (Treasury)")):
            pts = [r[col] for r in u["rows"] if r.get(col) is not None]
            if pts: intl.insert(0 if col == "2 Yr" else 1, {"sym": k, "label": lab, "date": u["rows"][-1]["date"], "price": pts[-1], "prev": pts[-2] if len(pts) > 1 else None, "spark": pts[-60:], "src": u["src"]})
    return 200, {"updated": iso(), "quotes_fetched": q.get("fetched"), "stale": bool(q.get("stale")), "groups": groups, "markets": markets(Q),
                 "stress": stress(Q, cg, u, vh, p), "curve": curve, "intl_yields": intl, "pcr": p, "ecb": fx,
                 "crypto": {k: cg.get(k) for k in ("total_mcap", "total_vol", "mcap_chg_24h", "btc_dom", "eth_dom", "fetched", "stale")} if cg else None,
                 "errors": dict(ST["err"]), "cache_s": {"quotes": Q_TTL, "crypto": CG_TTL, "yields": SLOW_TTL},
                 "delay_note": "Yahoo Finance quotes are delayed (typically 10–20 min, exchange-dependent; FX and crypto near real time). Treasury, Bund, JGB and ECB are end-of-day; Cboe put/call is the previous session.",
                 "sources": [["Yahoo Finance chart API (delayed)", "https://finance.yahoo.com/"], ["CoinGecko", "https://www.coingecko.com/"],
                             ["US Treasury yield curve", "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve"],
                             ["Deutsche Bundesbank", "https://www.bundesbank.de/en/statistics"], ["Japan Ministry of Finance JGB yields", "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/index.htm"],
                             ["Cboe daily market statistics", CITES["pcr"][1]], ["ECB reference rates via Frankfurter", "https://frankfurter.dev/"]],
                 "archive_days": _archive_days()}

def _archive_days():
    try: c = db(); r = c.execute("SELECT COUNT(DISTINCT day), MIN(day) FROM closes").fetchone(); c.close(); return {"days": r[0], "since": r[1]}
    except Exception: return None

def chart(qs):
    s = ((qs.get("s") or [""])[0] or "").strip(); r = ((qs.get("r") or ["1d"])[0] or "1d").strip()
    if r not in RANGES: return 400, {"error": "r must be one of " + ", ".join(RANGES)}
    if s.startswith("UST:") or s in ("BUND10", "JGB10") or s.startswith("PCR:"):
        days = {"1d": 10, "5d": 10, "1mo": 31, "6mo": 183, "1y": 366}[r]; cut = (datetime.now(ET) - timedelta(days=days)).strftime("%Y-%m-%d")
        if s.startswith("UST:"):
            col = s[4:]; u = ust()
            if col not in UST_COLS or not u: return 404, {"error": "unknown tenor"}
            pts = [[x["date"], x[col]] for x in u["rows"] if x.get(col) is not None]; lab = "US Treasury " + col
        elif s.startswith("PCR:"):
            c = db(); pts = [[x["day"], x["close"]] for x in c.execute("SELECT day, close FROM closes WHERE sym=? ORDER BY day", (s,))]; c.close(); lab = s[4:].title()
        else:
            v = bund() if s == "BUND10" else jgb(); pts = (v or {}).get("pts") or []; lab = "Germany 10Y Bund" if s == "BUND10" else "Japan 10Y JGB"
        pts = [p for p in pts if p[0] >= cut]
        return 200, {"sym": s, "label": lab, "range": r, "daily": True, "points": [[int(datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()), v] for d, v in pts],
                     "note": "End-of-day official data; intraday ranges show recent daily points."}
    if s not in SYM: return 404, {"error": "unknown symbol"}
    rng, iv, ttl = RANGES[r]
    def f():
        j = yahoo(f"/v8/finance/chart/{urllib.parse.quote(s)}?" + urllib.parse.urlencode({"range": rng, "interval": iv, "includePrePost": "false"}))
        res = j["chart"]["result"][0]; m = res["meta"]; qq = res["indicators"]["quote"][0]
        pts = [[t, round(c, 6)] for t, c in zip(res.get("timestamp") or [], qq.get("close") or []) if c is not None]
        return {"sym": s, "label": SYM[s][1], "range": r, "interval": iv, "points": pts, "prev": m.get("chartPreviousClose"), "price": m.get("regularMarketPrice"),
                "cur": m.get("currency"), "tz": m.get("exchangeTimezoneName"), "exch": m.get("fullExchangeName"), "fetched": iso(), "src": "Yahoo Finance (delayed)"}
    v = cached(f"chart:{s}:{r}", ttl, f)
    return (200, v) if v else (502, {"error": ST["err"].get(f"chart:{s}:{r}", "upstream unavailable")})

def closes(qs):
    s = ((qs.get("s") or [""])[0] or "").strip()
    c = db()
    try:
        if s: rows = [dict(x) for x in c.execute("SELECT * FROM closes WHERE sym=? ORDER BY day DESC LIMIT 400", (s,))]
        else: rows = [dict(x) for x in c.execute("SELECT * FROM closes WHERE day=(SELECT MAX(day) FROM closes) ORDER BY grp, sym")]
    finally: c.close()
    return 200, {"sym": s or None, "rows": rows}

_last_force = {"t": 0}
def handle_get(path, qs):
    n = path[len("/api/finance/"):] if path.startswith("/api/finance/") else ""
    if n in FILES:
        with open(os.path.join(STATIC, n), "rb") as fh: return 200, fh.read(), FILES[n]
    if n == "chart": return chart(qs)
    if n == "closes": return closes(qs)
    if n == "status": return 200, {"ok": True, "last_tick": ST["last_tick"], "web_only": WEB_ONLY, "errors": ST["err"]}
    if path == "/api/finance":
        force = (qs.get("force") or [""])[0] == "1" and time.time() - _last_force["t"] > 60   # manual refresh at most once a minute
        if force: _last_force["t"] = time.time()
        return summary(force)
    return 404, {"error": "not found"}
