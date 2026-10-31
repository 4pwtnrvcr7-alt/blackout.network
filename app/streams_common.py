"""Shared Live Streams pieces: curated channel list, streams.db schema, keyword matching (keywords.json, shared with Live
Broadcasts) and segment scoring that mirrors scanner.py's rules (regexes are read from scanner.py's source, never modified)."""
import ast, json, math, os, re, sqlite3, time
from collections import Counter
BASE = os.path.dirname(os.path.abspath(__file__)); SDB = os.path.join(BASE, "streams.db")
# Channel IDs verified Oct 30 2026 against YouTube channel search (exact channel name match).
CHANNELS = [
 ("UCNye-wNBqNL5ZzHSJj3l8Bg", "Al Jazeera English", "International"), ("UCknLrEdhRCp1aegoMqRaCZg", "DW News", "International"),
 ("UCQfwfsi5VrQ8yKZ-UWmAEFg", "FRANCE 24 English", "International"), ("UCoMdktPbSTixAyNGwb-UYkQ", "Sky News", "International"),
 ("UC16niRr50-MSBwiO3YDb3RA", "BBC News", "International"), ("UChqUTb7kYRX8-EiaN3XFrSQ", "Reuters", "International"),
 ("UC52X5wxOL_s5yw0dQk7NtgA", "Associated Press", "International"), ("UCSrZ3UV4jOidv8ppoVuvW9Q", "euronews", "International"),
 ("UC7fWeaHhqgM4Ry-RMpM2YYw", "TRT World", "International"), ("UCSPEjw8F2nQDtmUKPFNF7_A", "NHK WORLD-JAPAN", "International"),
 ("UC83jt4dlz1Gjl58fzQrrKZg", "CNA", "International"), ("UC_gUM8rL-Lrg6O3adPW9K1g", "WION", "International"),
 ("UCvHDpsWKADrDia0c99X37vg", "i24NEWS English", "International"), ("UCIALMKvObZNtJ6AmdCLP7Lg", "Bloomberg Television", "International"),
 ("UCBi2mrWuNuyYy4gbM6fU18Q", "ABC News", "US national"), ("UCeY0bbntWzzVIaj2z3QigXg", "NBC News", "US national"),
 ("UC8p1vwvWtl6T73JiExfWs1g", "CBS News", "US national"), ("UCJg9wBPyKMNA5sRDnvzmkdg", "LiveNOW from FOX", "US national"),
 ("UCD9nZ3qeRGbPuHJaJduiQxA", "WESH 2 News", "Central Florida"), ("UCz9D4t90tb8B2en9i_ffVeQ", "WFTV Channel 9", "Central Florida"),
 ("UCuXT13wiqK56NR7QSfDWpvg", "FOX 35 Orlando", "Central Florida"), ("UCjpzEgbbDUg4YC6vpSrzsyg", "WKMG News 6 ClickOrlando", "Central Florida"),
 ("UCFb8BfmiCVj_xAEMoSN2b0A", "Spectrum Bay News 9", "Florida"), ("UCgVZ0mrM3liHNhRYC5Mchgg", "WPLG Local 10", "Florida"),
 ("UCLA_DiR1FfKNvjuUpBHmylQ", "NASA", "Space Coast"), ("UCoLdERT4-TJ82PJOHSrsZLQ", "Spaceflight Now", "Space Coast"),
 ("UCSUu1lih2RifWkKtDOJdsBA", "NASASpaceflight", "Space Coast")]
CH = {c[0]: {"id": c[0], "name": c[1], "region": c[2]} for c in CHANNELS}
def db(ro=False):
    if ro:
        if not os.path.exists(SDB): db().close()
        c = sqlite3.connect(f"file:{SDB}?mode=ro", uri=True, timeout=20)
    else:
        c = sqlite3.connect(SDB, timeout=30); c.execute("PRAGMA journal_mode=WAL")
        c.executescript("""CREATE TABLE IF NOT EXISTS live(channel_id TEXT, video_id TEXT, title TEXT, viewers INTEGER, checked_at TEXT, live INTEGER, PRIMARY KEY(channel_id, video_id));
        CREATE TABLE IF NOT EXISTS checks(channel_id TEXT PRIMARY KEY, checked_at TEXT, ok INTEGER, error TEXT, n_live INTEGER);
        CREATE TABLE IF NOT EXISTS segments(id INTEGER PRIMARY KEY AUTOINCREMENT, channel_id TEXT, video_id TEXT, t_start TEXT, t_end TEXT, text TEXT, matches TEXT,
            cats TEXT, score INTEGER, rank INTEGER, confidence TEXT, confirmed_by TEXT, watchlist INTEGER, high INTEGER, scored_at TEXT);
        CREATE INDEX IF NOT EXISTS ix_seg_t ON segments(t_start); CREATE INDEX IF NOT EXISTS ix_seg_ch ON segments(channel_id, t_start);
        CREATE TABLE IF NOT EXISTS state(k TEXT PRIMARY KEY, v TEXT);""")
    c.row_factory = sqlite3.Row; return c
def _scanner_consts():
    t = ast.parse(open(os.path.join(BASE, "scanner.py")).read()); out = {}
    for n in t.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and getattr(n.targets[0], "id", "") in ("BOOST_RX", "THREAT_RX", "TRIVIA_RX"):
            out[n.targets[0].id] = ast.literal_eval(n.value)
    return out
RX = _scanner_consts()
def keywords():
    try: return json.load(open(os.path.join(BASE, "keywords.json")))
    except Exception: return {"categories": []}
def kw_regex(kw):
    ws = sorted({w for c in kw["categories"] for w in c["words"]}, key=len, reverse=True)
    return re.compile(r"(?<![A-Za-z0-9])(" + "|".join(r"\s+".join(map(re.escape, w.split())) for w in ws) + r")(?![A-Za-z0-9])", re.I) if ws else None
def match(text, kw=None):
    kw = kw or keywords(); cat = {w.lower(): c["id"] for c in kw["categories"] for w in c["words"]}; rx = kw_regex(kw)
    if not rx: return []
    return [{"w": m.group(1).lower(), "cat": cat.get(re.sub(r"\s+", " ", m.group(1).lower()), "")} for m in rx.finditer(text)]
STOP = set("the a an of in on at to for and or with by from is are was were has have be this that as it its we you they he she i our their will would can could about "
           "just so but not no yes there here what which who when where how all more some any been into out up down over after before than then also very said says "
           "going know think people like get got one two now new today right well really see time back".split())
def toks(s): return {w for w in re.findall(r"[a-z][a-z'\-]{3,}", (s or "").lower()) if w not in STOP}
def jacc(a, b): return len(a & b) / max(1, len(a | b))
def score_segment(text, confirmed_n):
    """Mirror of scanner.py rules for a news-only source: base from threat signal, 2+ independent sources add the news confirmation bonus,
    single-source (Low confidence) capped at 45, news-only capped at 70, no crisis phrasing (BOOST_RX) capped at 55; rank = min(8, round(score/12))."""
    t = (text or "").lower()
    threat = len(re.findall(RX["THREAT_RX"], t)); trivia = len(re.findall(RX["TRIVIA_RX"], t)); boost = bool(re.search(RX["BOOST_RX"], t, re.I))
    base = 0 if threat == 0 else min(60, 20 + 8 * threat) - 6 * min(trivia, 3)
    if boost: base += 15
    nf = 1 + confirmed_n; score = base
    if nf >= 3: score += 15
    elif nf == 2: score += 8
    conf = "Medium" if nf >= 2 else "Low"
    if conf == "Low": score = min(score, 45)
    score = min(score, 70)
    if not boost: score = min(score, 55)
    score = max(0, min(100, int(score))); rank = min(8, round(score / 12))
    return score, rank, conf, nf
