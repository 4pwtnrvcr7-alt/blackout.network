"""Analyst layer for the BLACKOUT.NETWORK brief (morning, evening, breaking).

The brief body is a deterministic template in newsletter.py. It reads blackout.db (clusters, alerts, scans)
and newsletter.db (sent_items ranks). No LLM is configured anywhere in this app, and this layer does not add one.

Cost per issue: $0. One pass over rows already on disk. LLM_CALLS_PER_ISSUE is 0.
An LLM would only rephrase these same facts. It would not be allowed to add numbers, sources, or guides.
A single capped call (about 2k input tokens and 800 output tokens on a small model) would be well under $0.01
if a key were added later. Nothing here calls a paid API.

Rules encoded below:
- A window the scanner does not cover is "not enough history", never a zero.
- An empty alerts table (cluster snapshot only) is "not enough history", never a zero.
- A real zero is used only when alert rows exist and the scanner's coverage includes that window.
- Repeated copies of the same headline, and extra domains of the same outlet, are one source.
- social and GDELT-volume never count as confirmation.
- Report volume never sets Rising or Easing. Rank, casualty or case figures, geographic spread, and official
  severity (PAGER, warning level) do.
- Inferences are labeled "Analysis:". Guide actions name a Prepare guide that exists on the site.
"""
import base64, json, os, re, sqlite3, struct, zlib
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc
ET = ZoneInfo("America/New_York")
COST_PER_ISSUE_USD = 0.0
LLM_CALLS_PER_ISSUE = 0
LLM_NOTE = ("No LLM is configured. This layer is deterministic and costs $0 per issue. "
            "A later single capped model call could rephrase the same facts for well under $0.01; "
            "it would not add numbers, sources, or guides.")
MIN_RANK = 7
MAX_ITEMS = 5
WINDOWS = (("24h", 24), ("7d", 24 * 7), ("30d", 24 * 30))

# Email palette, same hexes as newsletter.PAL, so this module does not import newsletter (cycle).
TX, MU, BODY = "#F5F5F7", "#A1A1A6", "#D2D2D7"
SURF, LINE, AC, FILL, INK = "#16181C", "#2A2D33", "#FFC21A", "#FFC21A", "#0B0D10"
FB = "Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
FH = FB

_STOP = set("a an the of in on at to for and or by with from is are was were be after as amid over into its it this that new says said near report reports".split())
_NOISE = {"social", "gdelt-volume"}
_SYN = ("yahoo", "aol", "msn.com", "msn ", "smartnews", "newsbreak", "flipboard", "tradingview", "news.google", "google news", "share.google")
_ORG = (("bbc", "bbc"), ("cidrap", "cidrap"), ("reuters", "reuters"), ("theguardian", "theguardian"), ("guardian", "guardian"))
_PAGER = {"green": 1, "yellow": 2, "orange": 3, "red": 4}
_NWS = {"statement": 1, "advisory": 2, "watch": 3, "warning": 4}
_DENY_PLACE = {"red", "gulf", "keys", "york", "washington", "america", "europe", "africa", "asia", "pacific", "atlantic",
               "arctic", "antarctica", "sri", "rico", "puerto", "kingdom", "united", "states", "county", "islands"}
_COUNTRY = {"iran", "israel", "ukraine", "russia", "china", "taiwan", "syria", "iraq", "lebanon", "gaza", "yemen",
            "florida", "utah", "arizona", "texas", "california", "chile", "greece", "turkey", "india", "pakistan"}
_PEOPLE = [
    ("Donald Trump", r"\bTrump\b"),
    ("Benjamin Netanyahu", r"\bNetanyahu\b"),
    ("Vladimir Putin", r"\bPutin\b"),
    ("Volodymyr Zelensky", r"\bZelensk(?:y|yy|iy)\b"),
    ("Katie Hobbs", r"\bHobbs\b"),
    ("Xi Jinping", r"\bXi Jinping\b|\bPresident Xi\b"),
    ("Kim Jong Un", r"\bKim Jong[\s-]?Un\b"),
    ("Elon Musk", r"\bElon Musk\b|\bMusk\b"),
]
_PLACE_NAME = {"iran": "Iran", "israel": "Israel", "gaza": "Gaza", "hormuz": "Hormuz", "ukraine": "Ukraine", "russia": "Russia",
               "florida": "Florida", "utah": "Utah", "arizona": "Arizona", "texas": "Texas", "chile": "Chile", "china": "China",
               "taiwan": "Taiwan", "syria": "Syria", "lebanon": "Lebanon", "yemen": "Yemen", "turkey": "Turkey", "kyiv": "Kyiv",
               "moscow": "Moscow", "antofagasta": "Antofagasta"}
_GUIDES = [
    {"id": "water", "name": "Prepare › Water", "path": "/ready#water",
     "rx": r"flood|hurricane|tsunami|storm surge|boil water|drinking water|flash flood|levee",
     "action": "Store one gallon of drinking water per person per day."},
    {"id": "power", "name": "Prepare › Power outage", "path": "/ready#power",
     "rx": r"\boutage\b|blackout|power grid|\bgrid\b|geomagnetic|\bKp\b|electricity",
     "action": "Charge power banks and keep the fridge closed. Any generator stays outdoors, 20 feet from windows."},
    {"id": "aid", "name": "Prepare › First aid", "path": "/ready#first-aid",
     "rx": r"earthquake|quake|killed|kills|death|deaths|injured|casualty|outbreak|influenza|flu\b|cases|wildfire|explosion",
     "action": "Check the kit and the written list of medicines, doses and allergies."},
    {"id": "family", "name": "Prepare › Family plan", "path": "/ready#family",
     "rx": r"\bstrikes?\b|missile|invasion|troops|martial|evacuat|unrest|artillery|shelling",
     "cats": {"war/conflict"},
     "action": "Write one out-of-area contact and two meeting places, and save them in each phone."},
    {"id": "kit", "name": "Prepare › Home kit", "path": "/ready#home-kit",
     "rx": r"$^",  # fallback only
     "action": "Confirm the 72-hour bin: water, food the household already eats, a flashlight and a radio."},
]
_DEAD = re.compile(r"\b(?:kills|killed|killing)\s+(\d[\d,]*)\b|\b(\d[\d,]*)\s+(?:people\s+)?(?:killed|dead|deaths?|died|fatalit(?:y|ies))\b", re.I)
_NONE_DEAD = re.compile(r"\bno (?:reported )?deaths?\b|\b0\s+deaths?\b", re.I)
_CASES = re.compile(r"\b(\d[\d,]*)\s+(?:more\s+|new\s+)?(?:confirmed\s+)?(?:[a-z]+\s+){0,3}cases?\b", re.I)
_INJ = re.compile(r"\b(\d[\d,]*)\s+(?:people\s+)?(?:injured|wounded)\b", re.I)
_MAG = re.compile(r"\bM\s*([0-9](?:\.[0-9])?)\b|\bmagnitude\s+([0-9](?:\.[0-9])?)", re.I)
_PAGER_RX = re.compile(r"\bPAGER\s+(green|yellow|orange|red)\b", re.I)
_NWS_RX = re.compile(r"\b(warning|watch|advisory|statement)\b", re.I)
_COUNTY = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\s+County)\b")
_BARS = "▁▂▃▄▅▆▇"


def cost_per_issue():
    return {"llm_calls": LLM_CALLS_PER_ISSUE, "usd": COST_PER_ISSUE_USD, "note": LLM_NOTE}


def _e(s):
    return ("" if s is None else str(s)).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _fmt(d):
    if not d: return "time not reported"
    try: return d.astimezone(ET).strftime("%b %-d, %-I:%M %p ET")
    except Exception: return "time not reported"


def _parse(s):
    if not s: return None
    if isinstance(s, datetime): return s if s.tzinfo else s.replace(tzinfo=UTC)
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=UTC)
    except Exception: return None


def _num(g):
    try: return int(str(g).replace(",", ""))
    except (TypeError, ValueError): return None


def _tokens(s):
    return [w for w in re.findall(r"[a-z0-9]+", (s or "").lower()) if w not in _STOP and len(w) > 1]


def same_wire(a, b):
    """True when two headlines are the same wire story, not two reports."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb: return False
    sa, sb = set(ta), set(tb)
    if len(sa & sb) / len(sa | sb) >= 0.55: return True
    ca = re.sub(r"\s+", " ", (a or "").lower()).strip()
    cb = re.sub(r"\s+", " ", (b or "").lower()).strip()
    n = min(len(ca), len(cb), 80)
    return n >= 40 and ca[:n] == cb[:n]


def family_key(family, source=""):
    raw = re.sub(r"^(google news|rss|bluesky|youtube|reddit|telegram|x search)\s*:\s*", "", f"{family or source or ''}".lower()).strip()
    for needle, key in _ORG:
        if needle in raw: return key
    if raw in ("nws", "noaa", "usgs", "who", "cdc", "gdacs", "cisa", "fema", "nhc"): return raw
    m = re.search(r"([a-z0-9-]{2,})\.(?:com|org|net|gov|co\.uk|edu|int|news|info)\b", raw)
    if m: return m.group(1)
    return re.sub(r"[^a-z0-9]+", "", raw)[:40] or "unknown"


def is_syndicator(family, source=""):
    s = f"{family or ''} {source or ''}".lower()
    return any(x in s for x in _SYN)


def is_noise(family):
    f = (family or "").strip().lower()
    return f in _NOISE or f == "social"


def _people():
    try:
        import figures as F
        return [(p[1], p[5]) for p in F.BASE_LIST] + [(p[1], p[4]) for p in F.POOL]
    except Exception:
        return _PEOPLE


def _places():
    try:
        import arcs
        return set(arcs.PLACES)
    except Exception:
        return set(_PLACE_NAME)


def named_people(text):
    out = []
    for name, rx in _people():
        try:
            if re.search(rx, text or "", re.I): out.append(name)
        except re.error:
            continue
    return out


def named_places(text):
    words = set(re.findall(r"[a-z]{3,}", (text or "").lower()))
    out = []
    for p in sorted(words & _places()):
        if p in _DENY_PLACE: continue
        out.append(_PLACE_NAME.get(p, p[:1].upper() + p[1:]))
    for m in _COUNTY.findall(text or ""):
        if m not in out: out.append(m)
    return out


def _death(text):
    if _NONE_DEAD.search(text or ""): return 0
    m = _DEAD.search(text or "")
    if not m: return None
    return _num(m.group(1) or m.group(2))


def _cases(text):
    m = _CASES.search(text or "")
    return _num(m.group(1)) if m else None


def _inj(text):
    m = _INJ.search(text or "")
    return _num(m.group(1)) if m else None


def _mag(text, extra):
    if extra.get("mag") not in (None, ""):
        try: return float(extra["mag"])
        except (TypeError, ValueError): pass
    m = _MAG.search(text or "")
    if not m: return None
    try: return float(m.group(1) or m.group(2))
    except (TypeError, ValueError): return None


def _pager(text, extra):
    if extra.get("pager"): return str(extra["pager"]).lower()
    m = _PAGER_RX.search(text or "")
    return m.group(1).lower() if m else None


def _nws(text, extra):
    ev = f"{extra.get('event') or ''} {extra.get('severity') or ''} {text or ''}"
    m = _NWS_RX.search(ev)
    return m.group(1).lower() if m else None


def _extra(raw):
    if isinstance(raw, dict): return raw
    try: return json.loads(raw or "{}")
    except Exception: return {}


def collapse_sources(alerts):
    """Group alerts into independent sources. Same headline or same outlet = one source.
    A group that is only syndicated copies is marked echo and does not count as confirmation.
    Returns (leaders, copy_count, usable)."""
    usable = [a for a in alerts if not is_noise(a.get("family"))]
    groups = []
    for a in usable:
        placed = False
        for g in groups:
            if same_wire(a.get("title") or "", g[0].get("title") or ""):
                g.append(a); placed = True; break
        if not placed: groups.append([a])
    leaders, seen = [], set()
    for g in groups:
        officials = [a for a in g if a.get("official")]
        originals = [a for a in g if not a.get("official") and not is_syndicator(a.get("family"), a.get("source"))]
        if officials:
            for a in officials:
                k = family_key(a.get("family"), a.get("source"))
                if k in seen: continue
                seen.add(k)
                b = dict(a); b["echo"] = False; leaders.append(b)
            continue
        if originals:
            a = originals[0]
            k = family_key(a.get("family"), a.get("source"))
            if k in seen: continue
            seen.add(k)
            b = dict(a); b["echo"] = False; leaders.append(b)
            continue
        b = dict(g[0]); b["echo"] = True; leaders.append(b)
    real_n = len([a for a in leaders if not a.get("echo")])
    echo_n = len([a for a in leaders if a.get("echo")])
    copies = max(0, len(usable) - real_n - echo_n)
    return leaders, copies, usable


def confidence_of(leaders, headlines_known):
    """-> (level, real_leaders, echo_leaders) or (level, detail_string, None) when headlines are missing."""
    if not headlines_known:
        return "Low", "Per-report headlines are not in this snapshot, so copies of one wire story cannot be separated. Independent confirmation: not enough history.", None
    real = [a for a in leaders if not a.get("echo")]
    echoes = [a for a in leaders if a.get("echo")]
    n = len(real)
    official = any(a.get("official") for a in real)
    if n >= 3 or (official and n >= 2): level = "High"
    elif n == 2 or (official and n == 1): level = "Medium"
    else: level = "Low"
    return level, real, echoes


def _series(alerts, at, hours, coverage_start, alerts_available):
    if not alerts_available or coverage_start is None or coverage_start > at - timedelta(hours=hours):
        return None
    cut = at - timedelta(hours=hours)
    return sum(1 for a in alerts if a.get("t") and cut < a["t"] <= at)


def _buckets(alerts, at, hours, n, coverage_start, alerts_available):
    if _series(alerts, at, hours, coverage_start, alerts_available) is None: return None
    span = timedelta(hours=hours) / n
    start = at - timedelta(hours=hours)
    out = []
    for i in range(n):
        a, b = start + span * i, start + span * (i + 1)
        out.append(sum(1 for x in alerts if x.get("t") and a < x["t"] <= b))
    return out


def _arrow(vals):
    if not vals or len(vals) < 2: return "→"
    k = max(1, len(vals) // 3)
    a, b = sum(vals[:k]) / k, sum(vals[-k:]) / k
    if b >= a * 1.34 and b >= a + 1: return "↑"
    if a >= b * 1.34 and a >= b + 1: return "↓"
    return "→"


def _bars(vals):
    mx = max(vals) if vals else 0
    if mx <= 0: return _BARS[0] * len(vals)
    return "".join(_BARS[min(6, int(round(v / mx * 6)))] for v in vals)


def sparkline_png(vals, w=220, h=36):
    """Small PNG bar chart. Returns None when there is no series (caller must not draw a zero line)."""
    if not vals or len(vals) < 2: return None
    bg, fg, grid = (22, 24, 28), (255, 194, 26), (42, 45, 51)
    pix = [[bg for _ in range(w)] for _ in range(h)]
    for x in range(w): pix[h - 6][x] = grid
    mx = max(vals) or 1
    gap = 3
    bw = max(3, (w - gap * (len(vals) + 1)) // len(vals))
    for i, v in enumerate(vals):
        bh = int(round((h - 12) * (v / mx))) if v else 1
        x0 = gap + i * (bw + gap)
        for x in range(x0, min(w, x0 + bw)):
            for y in range(h - 6 - bh, h - 6):
                if 0 <= y < h: pix[y][x] = fg
    raw = b"".join(b"\x00" + bytes(c for px in row for c in px) for row in pix)

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
    return png


def _guides(item, text):
    cat = item.get("category") or ""
    hits = []
    for g in _GUIDES:
        if g["id"] == "kit": continue
        if re.search(g["rx"], text or "", re.I) or cat in g.get("cats", set()):
            hits.append(g)
    if not hits and int(item.get("rank") or 0) >= MIN_RANK:
        hits = [_GUIDES[-1]]
    # de-dupe, cap 2, keep water/power/aid/family order
    out, seen = [], set()
    for g in hits:
        if g["id"] in seen: continue
        seen.add(g["id"]); out.append(g)
        if len(out) == 2: break
    return out


def _half(alerts, at):
    cut = at - timedelta(hours=12)
    early = [a for a in alerts if a.get("t") and at - timedelta(hours=24) < a["t"] <= cut]
    late = [a for a in alerts if a.get("t") and cut < a["t"] <= at]
    return early, late


def _figure_change(alerts, fn):
    """Earliest and latest alerts that state this figure. Missing is None, never coerced to 0."""
    stated = [(a["t"], fn(a.get("title") or ""), a) for a in alerts if a.get("t") and fn(a.get("title") or "") is not None]
    if len(stated) < 1: return None
    stated.sort(key=lambda x: x[0])
    if len(stated) == 1: return {"only": stated[0]}
    return {"early": stated[0], "late": stated[-1]}


def _spread(alerts):
    """Places named in the later half of the reports that were not named in the earlier half."""
    ordered = sorted([a for a in alerts if a.get("t")], key=lambda a: a["t"])
    if len(ordered) < 2: return None
    def bag(rows):
        s = set()
        for a in rows:
            s.update(named_places(f"{a.get('title') or ''} {a.get('location') or ''}"))
        return s
    span = ordered[-1]["t"] - ordered[0]["t"]
    if span.total_seconds() <= 0:
        return {"early": bag(ordered), "late": bag(ordered), "added": set(), "sample": ordered[-1]}
    mid = ordered[0]["t"] + span / 2
    early = [a for a in ordered if a["t"] <= mid]
    late = [a for a in ordered if a["t"] > mid]
    a, b = bag(early), bag(late)
    return {"early": a, "late": b, "added": b - a, "sample": late[-1]}


def analyze_item(item, alerts, at, coverage_start, alerts_available, prior_rank, past, base):
    """One critical item. Every number comes from `item`, `alerts`, `prior_rank`, or `past`."""
    alerts = sorted(alerts or [], key=lambda a: a.get("t") or at)
    headlines_known = bool(alerts)
    leaders, copies, usable = collapse_sources(alerts) if headlines_known else ([], 0, [])
    level, conf_detail, echoes = confidence_of(leaders, headlines_known)
    real_leaders = conf_detail if headlines_known else []
    if echoes is None: echoes = []
    text = " ".join(x for x in (item.get("title"), item.get("what"), item.get("where")) if x)
    if alerts:
        text += " " + " ".join((a.get("title") or "") for a in alerts[-6:])
    counts = {}
    for label, hours in WINDOWS:
        counts[label] = _series(alerts, at, hours, coverage_start, alerts_available and headlines_known)
    # A cluster with no alert rows is missing history even if the scanner date range is long.
    if not headlines_known:
        counts = {k: None for k, _ in WINDOWS}
    buckets = _buckets(alerts, at, 24, 8, coverage_start, alerts_available and headlines_known)
    if buckets is None:
        buckets = _buckets(alerts, at, 24 * 7, 7, coverage_start, alerts_available and headlines_known)
        spark_label = "7d"
    else:
        spark_label = "24h"
    deaths = _figure_change(alerts, _death) if headlines_known else None
    cases = _figure_change(alerts, _cases) if headlines_known else None
    spread = _spread(alerts) if headlines_known else None
    pagers, nwss = [], []
    for a in alerts:
        ex = a.get("extra") or {}
        p, n = _pager(a.get("title") or "", ex), _nws(a.get("title") or "", ex)
        if p: pagers.append((a["t"], p, a))
        if n: nwss.append((a["t"], n, a))

    signals = []  # ("up"|"down", sentence, url)
    def add(direction, sentence, url):
        signals.append((direction, sentence, url))

    if deaths and deaths.get("early") and deaths.get("late"):
        e, l = deaths["early"], deaths["late"]
        if l[1] > e[1]:
            add("up", f"deaths stated in the reports rose from {e[1]} to {l[1]}", l[2].get("url"))
        elif l[1] < e[1] and (l[2].get("official") or e[2].get("official")):
            add("down", f"deaths stated in the reports fell from {e[1]} to {l[1]}", l[2].get("url"))
    elif deaths and deaths.get("only") and deaths["only"][1] and len(alerts) >= 2:
        # a death figure appears later and earlier reports stated none — only when an earlier report exists with no figure
        only = deaths["only"]
        earlier = [a for a in alerts if a.get("t") and a["t"] < only[0]]
        if earlier and all(_death(a.get("title") or "") is None for a in earlier):
            add("up", f"the later report states {only[1]} death{'s' if only[1] != 1 else ''}; earlier reports in our log did not state a death figure", only[2].get("url"))
    if cases and cases.get("early") and cases.get("late"):
        e, l = cases["early"], cases["late"]
        if l[1] > e[1]:
            add("up", f"cases stated in the reports rose from {e[1]} to {l[1]}", l[2].get("url"))
        elif l[1] < e[1]:
            add("down", f"cases stated in the reports fell from {e[1]} to {l[1]}", l[2].get("url"))
    if spread and spread["added"] and len(spread["late"]) > len(spread["early"]):
        names = ", ".join(sorted(spread["added"])[:4])
        add("up", f"places named in the reports grew to include {names}", spread["sample"].get("url"))
    if len(pagers) >= 2 and _PAGER.get(pagers[-1][1], 0) and _PAGER.get(pagers[0][1], 0):
        if _PAGER[pagers[-1][1]] > _PAGER[pagers[0][1]]:
            add("up", f"USGS PAGER moved from {pagers[0][1]} to {pagers[-1][1]}", pagers[-1][2].get("url"))
        elif _PAGER[pagers[-1][1]] < _PAGER[pagers[0][1]]:
            add("down", f"USGS PAGER moved from {pagers[0][1]} to {pagers[-1][1]}", pagers[-1][2].get("url"))
    if len(nwss) >= 2 and _NWS.get(nwss[-1][1], 0) and _NWS.get(nwss[0][1], 0):
        if _NWS[nwss[-1][1]] > _NWS[nwss[0][1]]:
            add("up", f"the official level moved from {nwss[0][1]} to {nwss[-1][1]}", nwss[-1][2].get("url"))
        elif _NWS[nwss[-1][1]] < _NWS[nwss[0][1]]:
            add("down", f"the official level moved from {nwss[0][1]} to {nwss[-1][1]}", nwss[-1][2].get("url"))
    if prior_rank is not None:
        rk = int(item.get("rank") or 0)
        if rk > int(prior_rank):
            add("up", f"rank in our send ledger rose from {int(prior_rank)} to {rk}", None)
        elif rk < int(prior_rank):
            add("down", f"rank in our send ledger fell from {int(prior_rank)} to {rk}", None)

    ups = [s for s in signals if s[0] == "up"]
    downs = [s for s in signals if s[0] == "down"]
    if ups:
        trajectory = "Rising"
        reason = ups[0][1]
    elif downs:
        trajectory = "Easing"
        reason = downs[0][1]
    else:
        trajectory = "Steady"
        reason = "no change in rank, stated casualty or case figures, geographic spread, or official severity across the reports we have"
    rk = int(item.get("rank") or 0)
    if trajectory == "Rising":
        outlook = f"Over the next 24–72 hours the danger is higher than at first log: {reason}. Current rank is {rk}/10."
    elif trajectory == "Easing":
        outlook = f"Over the next 24–72 hours the danger is lower than the peak in our log: {reason}. Current rank is still {rk}/10."
    else:
        outlook = f"Over the next 24–72 hours the danger holds at rank {rk}/10. {reason[:1].upper() + reason[1:]}."

    # volume, stated separately and never used above
    vol_line = ""
    if counts.get("24h") is not None:
        early, late = _half(alerts, at)
        ea, la = len(early), len(late)
        if ea == 0 and la == 0:
            vol_line = "Report volume in our log: no reports in the last 24 hours. Volume alone does not set the danger reading."
        elif ea == 0:
            vol_line = (f"Report volume in our log: no reports in the first 12 hours of the window, then {la} in the second. "
                        "Volume alone does not set the danger reading.")
        elif la == 0:
            vol_line = (f"Report volume in our log: {ea} in the first 12 hours of the window, then none in the second. "
                        "Volume alone does not set the danger reading.")
        else:
            move = "rose" if la > ea else "fell" if la < ea else "held"
            vol_line = (f"Report volume in our log {move} from {ea} in the first 12 hours of the window to {la} in the second. "
                        "Volume alone does not set the danger reading.")

    hist_bits = []
    for label, _h in WINDOWS:
        n = counts[label]
        hist_bits.append(f"{label}: not enough history" if n is None else f"{label}: {n} report" + ("" if n == 1 else "s"))
    if prior_rank is None:
        prior_bit = "Prior rank in our send ledger: not enough history."
    elif int(prior_rank) != rk:
        prior_bit = f"Prior rank in our send ledger {'rose' if rk > int(prior_rank) else 'fell'} from {int(prior_rank)} to {rk}."
    else:
        prior_bit = f"Prior rank in our send ledger: {int(prior_rank)}. Current rank: {rk}."

    people = named_people(text)
    places = named_places(f"{item.get('title') or ''} {item.get('where') or ''} {item.get('location') or ''}")
    driver = {
        "war/conflict": "The reports describe the use of force.",
        "political": "The reports describe a government action.",
        "natural disaster": "The reports describe a natural hazard.",
        "disease": "The reports describe cases of disease.",
        "cyber": "The reports describe a disruption of a system.",
        "space weather": "The reports describe a space-weather measurement.",
        "financial": "The reports describe a market or banking event.",
    }.get(item.get("category") or "", "The reports describe the event in the headline.")
    where = item.get("where") or item.get("location") or (places[0] if places else None)
    who = ", ".join(people) if people else "No tracked public figure is named"
    officials = [a for a in leaders if a.get("official")]
    off_bit = ""
    if officials:
        o = officials[0]
        off_bit = f" Official source on record: {o.get('source') or o.get('family')}."
    times = [a["t"] for a in alerts if a.get("t")]
    when = ""
    if times:
        when = f" First logged {_fmt(min(times))}. Latest report {_fmt(max(times))}."
    elif item.get("first_seen"):
        when = f" Cluster first seen {_fmt(item.get('first_seen'))}."

    if headlines_known:
        names = ", ".join((a.get("source") or a.get("family") or "source") for a in real_leaders) or "none"
        conf_sentence = f"Confidence: {level}. {len(real_leaders)} independent source{'s' if len(real_leaders) != 1 else ''} ({names})."
        if len(real_leaders) >= 2:
            card_confidence = f"Confirmed by {len(real_leaders)} independent sources after collapsing repeated headlines"
        elif len(real_leaders) == 1 and real_leaders[0].get("official"):
            card_confidence = f"Single official source ({names}). Repeated copies of the headline are not extra confirmation"
        else:
            card_confidence = "Single source after collapsing repeated headlines, not independently confirmed"
        card_unconfirmed = len(real_leaders) < 2
        if echoes:
            conf_sentence += f" {len(echoes)} headline{'s' if len(echoes) != 1 else ''} appeared only as syndicated copies and {('are' if len(echoes) != 1 else 'is')} not independent confirmation."
        if copies:
            conf_sentence += f" {copies} other report{'s' if copies != 1 else ''} repeat those headlines or the same outlet and are not extra confirmation."
    else:
        card_confidence = None
        card_unconfirmed = None
        fams = item.get("families") or []
        nfam = item.get("eff")
        conf_sentence = (f"Confidence: {level}. The cluster record lists {item.get('n_items') or 1} reports"
                         + (f" and {nfam} source families" if nfam is not None else "")
                         + (f" ({', '.join(str(x) for x in fams[:6])})" if fams else "")
                         + ". " + conf_detail)

    past_line = ""
    if counts.get("7d") is None:
        past_line = "Similar past events: not enough history."
    elif not past:
        since = _fmt(coverage_start) if coverage_start else "the covered window"
        past_line = f"Similar past events: none logged since {since}."
    else:
        past_line = (f"Similar past event in our log: {past.get('title')}. Rank {past.get('rank')}/10, first logged {_fmt(past.get('t'))}. "
                     f"This item is rank {rk}/10.")

    # What happened: one line, numbers that are actually on the item or the alerts
    bits = []
    mag = None
    for a in alerts:
        mag = _mag(a.get("title") or "", a.get("extra") or {})
        if mag: break
    if mag is None: mag = _mag(item.get("title") or "", {})
    if mag: bits.append(f"M{mag:g}")
    title = re.sub(r"\s+", " ", item.get("title") or "").strip()
    bits.append(title[:180] if not mag else title[:140])
    if deaths and deaths.get("late"): bits.append(f"{deaths['late'][1]} deaths in the latest report that states a figure")
    elif deaths and deaths.get("only"): bits.append(f"{deaths['only'][1]} death{'s' if deaths['only'][1] != 1 else ''} stated in the reports")
    elif deaths and deaths.get("early"): bits.append(f"{deaths['early'][1]} deaths stated in the reports")
    bits.append(f"rank {rk}/10")
    if headlines_known:
        bits.append(f"{len(real_leaders)} independent source{'s' if len(real_leaders) != 1 else ''} after collapsing repeated headlines")
    happened = ". ".join(bits).rstrip(".") + "."
    # keep it one line: collapse accidental double spaces
    happened = re.sub(r"\s+", " ", happened)

    analysis = (f"Analysis: {driver}" + (f" Place named: {where}." if where else "")
                + f" Actors named: {who}." + off_bit + when + " "
                + "Scanner history " + "; ".join(hist_bits) + ". " + prior_bit + " "
                + (vol_line + " " if vol_line else "")
                + past_line)
    analysis = re.sub(r"\s+", " ", analysis).strip()

    guides = _guides(item, f"{item.get('title') or ''} {item.get('what') or ''} {item.get('category') or ''}")
    actions = [{"name": g["name"], "url": base.rstrip("/") + g["path"], "action": g["action"]} for g in guides]

    sources = []
    seen_u = set()
    pool = list(real_leaders)
    for _d, _s, url in signals:
        if url: pool.append({"url": url, "source": "report", "title": _s})
    if past and past.get("url"):
        pool.append({"url": past["url"], "source": "our log", "title": past.get("title")})
    for a in (item.get("links") or []):
        if a.get("url"): pool.append({"url": a["url"], "source": a.get("source") or "source", "title": item.get("title")})
    for a in pool:
        u = a.get("url")
        if not u or u in seen_u: continue
        seen_u.add(u)
        sources.append({"url": u, "source": a.get("source") or a.get("family") or "source", "title": (a.get("title") or "")[:140]})
        if len(sources) >= 4: break

    png = sparkline_png(buckets) if buckets else None
    return {
        "cluster_id": item.get("cluster_id"),
        "title": title,
        "rank": rk,
        "what": happened,
        "analysis": analysis,
        "trajectory": trajectory,
        "outlook": outlook,
        "confidence": level,
        "confidence_line": conf_sentence,
        "card_confidence": card_confidence,
        "card_unconfirmed": card_unconfirmed,
        "history": {k: ("not enough history" if counts[k] is None else counts[k]) for k, _ in WINDOWS},
        "spark": {"label": spark_label if buckets else None, "values": buckets,
                  "bars": _bars(buckets) if buckets else None, "arrow": _arrow(buckets) if buckets else None,
                  "png": png},
        "actions": actions,
        "sources": sources,
        "wire": base.rstrip("/") + f"/wire/{item.get('cluster_id')}",
    }


def _pick(issue):
    pool, seen = [], set()
    for sec in ("main", "follow", "updates", "politics", "near", "notable"):
        for it in issue.get(sec) or []:
            cid = it.get("cluster_id")
            if not cid or cid in seen: continue
            if it.get("section") == "watchlist" or it.get("editorial"): continue
            seen.add(cid); pool.append(it)
    crit = [it for it in pool if int(it.get("rank") or 0) >= MIN_RANK]
    crit.sort(key=lambda x: (-int(x.get("rank") or 0), -(int(x.get("score") or 0))))
    return crit[:MAX_ITEMS], pool


def _patterns(pool):
    by_p, by_n = defaultdict(list), defaultdict(list)
    for it in pool:
        if int(it.get("rank") or 0) < 5: continue
        blob = f"{it.get('title') or ''} {it.get('where') or ''} {it.get('what') or ''}"
        for p in named_places(blob):
            by_p[p].append(it)
        for n in named_people(blob):
            by_n[n].append(it)
    raw = []
    for kind, bag in (("region", by_p), ("person", by_n)):
        for name, its in bag.items():
            uniq, s = [], set()
            for it in its:
                if it["cluster_id"] in s: continue
                s.add(it["cluster_id"]); uniq.append(it)
            if len(uniq) >= 2:
                raw.append({"kind": kind, "name": name, "items": uniq, "ids": tuple(sorted(s))})
    # identical story sets: keep a country over a city, and a person as its own line
    kept = []
    for p in sorted(raw, key=lambda x: (-len(x["items"]), x["kind"] != "person", x["name"] not in { _PLACE_NAME.get(c, c.title()) for c in _COUNTRY })):
        if any(p["ids"] == k["ids"] and p["kind"] == k["kind"] for k in kept): continue
        kept.append(p)
    kept.sort(key=lambda x: (-len(x["items"]), x["name"]))
    return kept[:4]


def _coverage_start(c):
    try:
        scans = c.execute("SELECT MIN(started) a FROM scans").fetchone()
        alerts = c.execute("SELECT MIN(first_seen) a FROM alerts").fetchone()
    except sqlite3.Error:
        return None, False
    times = [ _parse(scans["a"] if scans else None), _parse(alerts["a"] if alerts else None) ]
    times = [t for t in times if t]
    try:
        n = c.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
    except sqlite3.Error:
        n = 0
    return (min(times) if times else None), bool(n)


def _load_alerts(c, ids):
    if not ids: return {}
    q = f"SELECT cluster_id, source, family, title, first_seen, official, source_url, lat, lon, location, extra FROM alerts WHERE cluster_id IN ({','.join('?'*len(ids))})"
    out = defaultdict(list)
    try:
        rows = c.execute(q, list(ids)).fetchall()
    except sqlite3.Error:
        return {}
    for r in rows:
        out[r["cluster_id"]].append({
            "family": r["family"], "source": r["source"], "title": r["title"], "t": _parse(r["first_seen"]),
            "official": bool(r["official"]), "url": r["source_url"], "lat": r["lat"], "lon": r["lon"],
            "location": r["location"], "extra": _extra(r["extra"]),
        })
    return out


def _past_for(c, item, alerts, coverage_start, at):
    if coverage_start is None or coverage_start > at - timedelta(days=7): return None
    places = set(named_places(f"{item.get('title') or ''} {item.get('where') or ''}"))
    mag = None
    for a in alerts:
        mag = _mag(a.get("title") or "", a.get("extra") or {})
        if mag: break
    try:
        rows = c.execute("""SELECT cluster_id, title, category, location, rank, first_seen FROM clusters
                            WHERE cluster_id!=? AND watchlist=0 AND first_seen>=? AND first_seen<? AND category=?
                            ORDER BY first_seen DESC LIMIT 80""",
                         (item.get("cluster_id"), coverage_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                          (_parse(item.get("first_seen")) or at).strftime("%Y-%m-%dT%H:%M:%SZ"), item.get("category") or ""))
    except sqlite3.Error:
        return None
    best = None
    for r in rows:
        blob = f"{r['title'] or ''} {r['location'] or ''}"
        share = bool(set(named_places(blob)) & places) if places else False
        close_mag = False
        if mag:
            om = _mag(r["title"] or "", {})
            close_mag = om is not None and abs(om - mag) <= 0.7
        if share or close_mag:
            best = r; break
    if not best: return None
    return {"title": re.sub(r"\s+", " ", best["title"] or "").strip()[:160], "rank": int(best["rank"] or 0),
            "t": _parse(best["first_seen"]), "url": None, "cluster_id": best["cluster_id"]}


def _prior(nl_path, cid, at):
    if not nl_path or not os.path.exists(nl_path): return None
    try:
        c = sqlite3.connect(f"file:{nl_path}?mode=ro", uri=True, timeout=5)
        row = c.execute("SELECT rank FROM sent_items WHERE cluster_id=? AND sent_at<? AND rank IS NOT NULL ORDER BY sent_at DESC LIMIT 1",
                        (cid, at.strftime("%Y-%m-%dT%H:%M:%SZ"))).fetchone()
        c.close()
    except sqlite3.Error:
        return None
    if not row or row[0] is None: return None
    return int(row[0])


def attach(issue, src_path, at, nl_path=None, base_url="https://blackout.network"):
    """Fill issue['analysis']. Reads scanner and newsletter DBs read-only. Never raises into the sender."""
    at = at or datetime.now(UTC)
    base = base_url or "https://blackout.network"
    crit, pool = _pick(issue)
    patterns = _patterns(pool)
    coverage, alerts_available = None, False
    by_id = {}
    src = None
    try:
        if src_path and os.path.exists(src_path):
            src = sqlite3.connect(f"file:{src_path}?mode=ro", uri=True, timeout=10)
            src.row_factory = sqlite3.Row
            coverage, alerts_available = _coverage_start(src)
            ids = [it.get("cluster_id") for it in crit]
            by_id = _load_alerts(src, ids)
    except sqlite3.Error:
        src = None
    items = []
    try:
        for it in crit:
            alerts = by_id.get(it.get("cluster_id")) or []
            past = _past_for(src, it, alerts, coverage, at) if src else None
            if past:
                past["url"] = base.rstrip("/") + f"/wire/{past['cluster_id']}"
            items.append(analyze_item(it, alerts, at, coverage, alerts_available, _prior(nl_path, it.get("cluster_id"), at), past, base))
    finally:
        if src is not None:
            try: src.close()
            except Exception: pass
    issue["analysis"] = {"items": items, "patterns": [
        {"kind": p["kind"], "name": p["name"], "items": [{"cluster_id": i.get("cluster_id"), "title": i.get("title"), "rank": i.get("rank"),
                                                          "wire": base.rstrip("/") + f"/wire/{i.get('cluster_id')}"} for i in p["items"]]}
        for p in patterns], "cost": cost_per_issue(),
        "coverage_start": coverage.strftime("%Y-%m-%dT%H:%M:%SZ") if coverage else None}
    return issue["analysis"]


def _p(html):
    return f'<p style="margin:0 0 8px 0;font:400 15px/1.55 {FB};color:{BODY}">{html}</p>'


def _lbl(t):
    return f'<b style="font:600 11px {FH};letter-spacing:1px;color:{TX}">{t}</b> '


def html_section(analysis, base_url="https://blackout.network"):
    if not analysis: return ""
    items = analysis.get("items") or []
    patterns = analysis.get("patterns") or []
    if not items and not patterns: return ""
    base = (base_url or "https://blackout.network").rstrip("/")
    parts = ['<tr><td class="bnpad" style="padding:28px 20px 8px 20px;text-align:left">'
             f'<div style="font:600 24px/1.2 {FH};letter-spacing:-0.4px;color:{TX}">Analyst brief</div>'
             f'<div style="font:400 15px/1.5 {FB};color:{MU};margin-top:6px">Top rank-7 items. A window we do not have is marked “not enough history”. '
             'Copies of one headline count as one source. Report volume is separate from the danger reading.</div></td></tr>']
    card_o = ('<tr><td class="bnpad" style="padding:6px 20px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
              f'<tr><td style="padding:20px 22px;background:{SURF};border-radius:18px">')
    card_c = "</td></tr></table></td></tr>"
    for it in items:
        sp = it.get("spark") or {}
        if sp.get("png") and sp.get("values") is not None:
            b64 = base64.b64encode(sp["png"]).decode()
            img = (f'<img src="data:image/png;base64,{b64}" width="220" height="36" alt="Report counts, last { _e(sp.get("label") or "24h") }" '
                   f'style="display:block;width:220px;max-width:100%;height:auto;border:0;margin:4px 0">')
            spark = (f'{_p(_lbl("REPORT COUNTS") + img)}'
                     f'{_p(_e(sp.get("bars") or "") + " " + _e(sp.get("arrow") or "") + " " + _e(sp.get("label") or "") + " volume. Volume is not a danger reading.")}')
        else:
            spark = _p(_lbl("REPORT COUNTS") + "not enough history")
        srcs = " ".join(f'<a href="{_e(s["url"])}" style="color:{TX};text-decoration:underline">{_e(s["source"])}</a>' for s in it.get("sources") or [])
        acts = "".join(
            f'{_p(_lbl("WHAT TO DO") + _e(a["action"]) + " Guide: " + f"<a href=\"{_e(a['url'])}\" style=\"color:{TX};text-decoration:underline\">{_e(a['name'])}</a>.")}'
            for a in it.get("actions") or [])
        wire = it.get("wire") or (base + "/wire/" + str(it.get("cluster_id") or ""))
        parts.append(card_o
            + f'<div style="margin:0 0 8px 0"><a href="{_e(wire)}" style="font:600 18px/1.3 {FH};color:{TX};text-decoration:none">{_e(it.get("title") or "")}</a></div>'
            + _p(_lbl("WHAT HAPPENED") + _e(it.get("what") or ""))
            + _p(_e(it.get("analysis") or ""))
            + _p(_lbl("TRAJECTORY") + _e(it.get("trajectory") or "") + ". " + _e(it.get("outlook") or ""))
            + _p(_e(it.get("confidence_line") or ""))
            + spark + acts
            + (_p(_lbl("SOURCES") + srcs) if srcs else "")
            + f'<p style="margin:8px 0 0 0"><a href="{_e(wire)}" style="display:inline-block;background:{FILL};color:{INK};font:600 15px/1.2 {FH};text-decoration:none;border-radius:999px;padding:10px 16px">Full story &amp; sources</a></p>'
            + card_c)
    if patterns:
        rows = []
        for p in patterns:
            links = "; ".join(f'<a href="{_e(i["wire"])}" style="color:{TX};text-decoration:underline">R{int(i.get("rank") or 0)} {_e((i.get("title") or "")[:80])}</a>' for i in p["items"])
            kind = "Region" if p["kind"] == "region" else "Person"
            rows.append(_p(f"<b style=\"color:{TX}\">{_e(kind)}: {_e(p['name'])}</b> — {len(p['items'])} stories in this brief ({links}). "
                           f"Analysis: the same {kind.lower()} is named across these separate clusters. Each item’s danger read is its own rank and sourced figures."))
        parts.append('<tr><td class="bnpad" style="padding:22px 20px 6px 20px">'
                     f'<div style="font:600 20px/1.2 {FH};color:{TX}">Patterns we’re watching</div></td></tr>')
        parts.append(card_o + "".join(rows) + card_c)
    elif items:
        parts.append(card_o + _p("Patterns we’re watching: no region or person is named in more than one story in this brief.") + card_c)
    return "".join(parts)


def text_section(analysis, base_url="https://blackout.network"):
    if not analysis: return []
    items = analysis.get("items") or []
    patterns = analysis.get("patterns") or []
    if not items and not patterns: return []
    T = ["ANALYST BRIEF", "Top rank-7 items. Missing history is marked 'not enough history'. Repeated headlines are one source. Volume is not a danger reading.", ""]
    for i, it in enumerate(items, 1):
        T.append(f"{i}. {it.get('title')}")
        T.append(f"   WHAT HAPPENED: {it.get('what')}")
        T.append(f"   {it.get('analysis')}")
        T.append(f"   TRAJECTORY: {it.get('trajectory')}. {it.get('outlook')}")
        T.append(f"   {it.get('confidence_line')}")
        sp = it.get("spark") or {}
        if sp.get("values") is not None:
            T.append(f"   REPORT COUNTS: {sp.get('bars')} {sp.get('arrow')} ({sp.get('label')} volume, not danger)")
        else:
            T.append("   REPORT COUNTS: not enough history")
        for a in it.get("actions") or []:
            T.append(f"   WHAT TO DO: {a['action']} Guide: {a['name']} {a['url']}")
        for s in it.get("sources") or []:
            T.append(f"   SOURCE: {s.get('source')}: {s.get('url')}")
        T.append(f"   Full story & sources: {it.get('wire')}")
        T.append("")
    T.append("PATTERNS WE'RE WATCHING")
    if not patterns:
        T.append("No region or person is named in more than one story in this brief.")
    for p in patterns:
        bits = "; ".join(f"R{int(i.get('rank') or 0)} {i.get('title')} {i.get('wire')}" for i in p["items"])
        kind = "Region" if p["kind"] == "region" else "Person"
        T.append(f"{kind}: {p['name']} — {len(p['items'])} stories. Analysis: the same {kind.lower()} is named across these clusters. {bits}")
    T.append("")
    return T


def write_demo_db(path, at):
    """Scanner-shaped fixture for tests and the sample Morning Brief. Not live news."""
    if os.path.exists(path): os.remove(path)
    c = sqlite3.connect(path)
    c.executescript("""
    CREATE TABLE alerts(id TEXT PRIMARY KEY, source TEXT, family TEXT, title TEXT, category TEXT, source_url TEXT,
      event_time TEXT, lat REAL, lon REAL, location TEXT, base INTEGER, official INTEGER, extra TEXT,
      first_seen TEXT, last_seen TEXT, cluster_id TEXT);
    CREATE TABLE clusters(cluster_id TEXT PRIMARY KEY, title TEXT, category TEXT, location TEXT, lat REAL, lon REAL,
      event_time TEXT, first_seen TEXT, updated TEXT, score INTEGER, confidence TEXT, n_items INTEGER, n_families INTEGER,
      families TEXT, links TEXT, watchlist INTEGER, brief TEXT, high_at TEXT, rising INTEGER, mentions_3h INTEGER,
      eff_families INTEGER, rank INTEGER, pushed_at TEXT);
    CREATE TABLE scans(id INTEGER PRIMARY KEY AUTOINCREMENT, started TEXT, finished TEXT, trigger TEXT,
      fetched INTEGER, new_items INTEGER, ok_sources INTEGER, failed_sources INTEGER, error TEXT);
    """)
    def iso(d): return d.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    c.execute("INSERT INTO scans(started,finished,trigger,fetched,new_items,ok_sources,failed_sources) VALUES(?,?,?,?,?,?,?)",
              (iso(at - timedelta(days=8)), iso(at - timedelta(days=8) + timedelta(minutes=3)), "scheduled", 100, 10, 40, 0))
    rows = [
        ("a11ce00000000001", "Iran missile strike near the Strait of Hormuz kills 18, Trump says he is watching",
         "war/conflict", "Strait of Hormuz", 8, 64, 6, at - timedelta(hours=20), at - timedelta(hours=6)),
        ("a11ce00000000002", "Trump says the Hormuz strikes will not change the Iran talks",
         "political", "Iran", 7, 45, 8, at - timedelta(hours=20), at - timedelta(hours=1)),
        ("a11ce00000000003", "Gov. Cox declares state of emergency after repeat flooding in Southern Utah",
         "political", "Southern Utah", 7, 55, 8, at - timedelta(hours=30), at - timedelta(hours=2)),
        ("a11ce00000000004", "Yakima County, Washington, reports 2 more avian flu cases, 1 death",
         "disease", "Yakima County, Washington", 7, 50, 2, at - timedelta(days=5), at - timedelta(hours=3)),
        ("a11ce00000000005", "M7.1 earthquake near Antofagasta, Chile, PAGER yellow",
         "natural disaster", "Antofagasta, Chile", 7, 60, 3, at - timedelta(hours=36), at - timedelta(hours=3)),
        ("a11ce00000000006", "M6.8 earthquake near Antofagasta, Chile",
         "natural disaster", "Antofagasta, Chile", 6, 40, 1, at - timedelta(days=5), at - timedelta(days=5)),
    ]
    for cid, title, cat, loc, rank, score, eff, first, high in rows:
        c.execute("""INSERT INTO clusters(cluster_id,title,category,location,lat,lon,event_time,first_seen,updated,score,confidence,
                     n_items,n_families,families,links,watchlist,brief,high_at,rising,mentions_3h,eff_families,rank)
                     VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (cid, title, cat, loc, None, None, iso(first), iso(first), iso(at), score, "Medium", eff, eff,
                   json.dumps(["fixture"]), json.dumps([{"source": "our log", "url": f"https://blackout.network/wire/{cid}"}]),
                   0, f"WHAT: {title}. WHERE: {loc}.", iso(high), 0, 1, eff, rank))
    def alert(i, cid, source, family, title, cat, when, official=0, url=None):
        c.execute("""INSERT INTO alerts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (f"al{i:03d}", source, family, title, cat, url or f"https://example.com/report/{i}",
                   iso(when), None, None, "", 20, official, "{}", iso(when), iso(when), cid))
    h = "a11ce00000000001"
    alert(1, h, "Reuters", "reuters.com", "Iran missile strike on a ship near the Strait of Hormuz kills 4", "war/conflict", at - timedelta(hours=20))
    alert(2, h, "Yahoo", "yahoo.com", "Iran missile strike on a ship near the Strait of Hormuz kills 4", "war/conflict", at - timedelta(hours=19))
    alert(3, h, "AOL", "aol.com", "Iran missile strike on a ship near the Strait of Hormuz kills 4", "war/conflict", at - timedelta(hours=18))
    alert(4, h, "Reuters", "reuters.com", "Iran missile strike on a ship near the Strait of Hormuz kills 18", "war/conflict", at - timedelta(hours=10))
    alert(5, h, "BBC", "bbc.com", "UKMTO reports a second strike near Hormuz", "war/conflict", at - timedelta(hours=9))
    alert(6, h, "BBC", "bbc.co.uk", "UKMTO reports a second strike near Hormuz", "war/conflict", at - timedelta(hours=8))
    alert(7, h, "The Guardian", "theguardian.com", "Shipping through Hormuz slows after the strikes, Trump says", "war/conflict", at - timedelta(hours=6))
    t = "a11ce00000000002"
    alert(10, t, "Reuters", "reuters.com", "Trump says the Hormuz strikes will not change the Iran talks", "political", at - timedelta(hours=20))
    for n, hours in enumerate((5, 4, 4, 3, 3, 2, 2, 1), start=11):
        fam = "yahoo.com" if n % 2 == 0 else "aol.com"
        alert(n, t, "Yahoo" if fam.startswith("yahoo") else "AOL", fam,
              "Trump says the Hormuz strikes will not change the Iran talks", "political", at - timedelta(hours=hours))
    f = "a11ce00000000003"
    alert(30, f, "NWS", "NWS", "Flood warning for Washington County, Utah", "natural disaster", at - timedelta(hours=30), official=1)
    alert(31, f, "NWS", "NWS", "Flood warning extended to Iron County and Kane County, Utah", "natural disaster", at - timedelta(hours=8), official=1)
    for n, hours in enumerate((7, 6, 5, 4, 3, 2), start=32):
        alert(n, f, "Yahoo", "yahoo.com", "Gov. Cox declares state of emergency after repeat flooding in Southern Utah", "political", at - timedelta(hours=hours))
    d = "a11ce00000000004"
    alert(40, d, "CIDRAP", "cidrap.umn.edu", "Yakima County reports 1 avian flu case", "disease", at - timedelta(days=5))
    alert(41, d, "Yakima Herald", "yakimaherald.com", "Yakima health district confirms 1 death and 2 new cases", "disease", at - timedelta(hours=4))
    q = "a11ce00000000005"
    alert(50, q, "USGS", "USGS", "M7.1 earthquake near Antofagasta, Chile, PAGER orange", "natural disaster", at - timedelta(hours=36), official=1)
    alert(51, q, "Yahoo", "yahoo.com", "M7.1 earthquake near Antofagasta, Chile, PAGER orange", "natural disaster", at - timedelta(hours=30))
    alert(52, q, "USGS", "USGS", "M7.1 earthquake near Antofagasta, Chile, PAGER yellow", "natural disaster", at - timedelta(hours=3), official=1)
    alert(53, q, "Reuters", "reuters.com", "Chile quake damages the Antofagasta port road", "natural disaster", at - timedelta(hours=2))
    c.commit(); c.close()


def embed_sparklines(msg):
    """Move analyst bar charts from data URIs onto CID attachments. No-op when the HTML has none.
    Does not change the sender, the recipient, or whether the message is delivered."""
    part = msg.get_body(preferencelist=("html",))
    if part is None: return msg
    html = part.get_content()
    if "data:image/png;base64," not in html or "Report counts" not in html: return msg
    pat = re.compile(r'src="data:image/png;base64,([A-Za-z0-9+/=]+)"([^>]*alt="Report counts[^"]*")')
    images = []

    def repl(m):
        cid = f"bn-spark-{len(images) + 1}@blackout.network"
        images.append((cid, base64.b64decode(m.group(1))))
        return f'src="cid:{cid}"{m.group(2)}'

    new = pat.sub(repl, html)
    if not images or new == html: return msg
    part.set_content(new, subtype="html", charset="utf-8")
    for cid, raw in images:
        part.add_related(raw, "image", "png", cid=f"<{cid}>", filename=cid.split("@")[0] + ".png")
    return msg
