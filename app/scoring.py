"""Scoring explainer add-on: GET /scoring (alias /about/scoring) -> one self-contained HTML page explaining the
0-100 severity score and the 0-10 rank exactly as scanner.py implements them, with live examples per rank.
Read-only: opens blackout.db only via the sqlite URI file:blackout.db?mode=ro; imports scanner only to reuse its regexes
and to cross-check the worked example with scanner.rank_cluster. Never writes anything, never changes scoring."""
import os, re, json, sqlite3, sys, time, html, threading
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "blackout.db")
TTL = 120
_C = getattr(sys, "_bn_scoring_cache", None)
if _C is None: _C = sys._bn_scoring_cache = {}
_LK = getattr(sys, "_bn_scoring_lock", None)
if _LK is None: _LK = sys._bn_scoring_lock = threading.Lock()
E = lambda s: html.escape(str(s if s is not None else ""), quote=True)

def _db():
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=10); c.row_factory = sqlite3.Row
    return c

def _cfg():
    try: return json.load(open(os.path.join(BASE, "config.json")))
    except Exception: return {}

def _S():
    import scanner
    return scanner

# ---------------------------------------------------------------- static content (mirrors scanner.py; see README "Severity rank")
COLORS = ["#3a4250", "#4b5563", "#2f7d4f", "#52c41a", "#a0d911", "#fadb14", "#faad14", "#fa8c16", "#ff4d4f", "#cf1322", "#8b0000"]
BANDS = {0: (0, 6), 1: (7, 17), 2: (18, 30), 3: (31, 41), 4: (42, 54), 5: (55, 65), 6: (66, 78), 7: (79, 89), 8: (90, 100)}
RANKS = {
 0: ("Noise", "None / local trivia", "Any; non-official items here are hidden",
     "Stored but hidden if non-official; official items stay on The Wire",
     "Local trivia caught by the noise filter (festivals, sports, council meetings, reviews), or an official item with a tiny impact score (e.g. iceberg tracking)."),
 1: ("Background", "Very local", "Any; non-official items here are hidden",
     "Official: The Wire (bottom). Non-official: stored, hidden",
     "GDACS green notification (small wildfire); a news/social post with no threat keyword at all."),
 2: ("Minor", "Local", "Single source is enough",
     "The Wire if official or confirmed; Watchlist if single-source",
     "M4.5–4.9 earthquake; NOAA G1/S1/R1 space weather; single-outlet local incident."),
 3: ("Minor regional", "One region", "Single source is enough",
     "The Wire if official or confirmed; Watchlist if single-source",
     "M5.0–5.4 earthquake; a CISA KEV vulnerability; NOAA G2 storm."),
 4: ("Regional", "One region / state", "Highest rank a single unconfirmed source can reach",
     "The Wire if official or confirmed; Watchlist if single-source",
     "M5.5–5.9 earthquake; NWS Severe warning; KEV flaw with known ransomware use; any unconfirmed rumor (capped here)."),
 5: ("Significant", "Regional / national", "Official source, or 2+ independent sources",
     "The Wire",
     "M6.0–6.9 earthquake; NWS Extreme warning; GDACS orange; WHO Disease Outbreak News; NOAA G3; coverage of a past crisis (trial, verdict)."),
 6: ("Serious", "National", "Official source, or 2+ independent sources",
     "The Wire",
     "M7.0–7.9 or PAGER yellow; tsunami advisory/watch; hurricane / tornado-emergency / storm-surge warning; CISA emergency directive; ballistic-missile launch; high-consequence pathogen confirmed by WHO or 3+ sources."),
 7: ("Major", "National / multi-country", "Official source, or 3+ independent outlets if media-only",
     "The Wire · instant push if 2+ independent sources",
     "USGS PAGER orange; GDACS red; NOAA G4; coup, martial law, assassination, bank run, mass casualty; high-consequence outbreak in several countries; grid / critical-infrastructure compromise."),
 8: ("Severe", "Multi-country / continental", "Official source, or 3+ independent outlets if media-only",
     "The Wire · instant push if 2+ independent sources",
     "M8+ earthquake or PAGER red; tsunami warning; GDACS red affecting 1 million+ people."),
 9: ("Critical", "Global / civilizational", "Requires official corroboration",
     "The Wire · instant push if 2+ independent sources",
     "NOAA G5 extreme geomagnetic storm; WHO pandemic or PHEIC declaration; nuclear strike, attack or detonation."),
 10: ("Catastrophic", "Global / civilizational", "Requires official corroboration",
     "The Wire · instant push if 2+ independent sources",
     "Only reports of an imminent nuclear war or a nuclear exchange."),
}
ILLUSTRATIVE = {
 9: "WHO declares a public health emergency of international concern (PHEIC), reported by WHO and by CIDRAP. The disease rule sets rank 9.",
 10: "Official sources report a nuclear exchange between two states. This is the only rule that produces rank 10.",
 0: "A news story about a local Halloween parade. The noise filter sets rank 0, and it is stored but hidden.",
}
BASES = [
 ("USGS earthquakes", "20 + 18 × (magnitude − 4.5); +10/20/30 for PAGER yellow/orange/red; +10 tsunami flag"),
 ("NWS alerts (Severe/Extreme)", "Extreme 55, Severe 35; +10 Immediate urgency; +5 Observed; +1 per 5 zones (max +10)"),
 ("tsunami.gov", "warning 85, threat 70, advisory 60, watch 55, information 20"),
 ("NOAA space weather", "10 + 15 × G/S/R scale level (−5 for a watch); Kp ≥ 5 gives 15 + 15 × G level"),
 ("WHO Disease Outbreak News", "45; +20 high-consequence pathogen (Ebola, Marburg, H5N1, MERS, Nipah…); +10 multi-country"),
 ("GDACS", "green 15, orange 50, red 75; +8 if more than 100,000 people affected, +15 if more than 1 million"),
 ("CISA KEV / advisories", "KEV 30, +15 known ransomware use; advisories 20, +20 for an emergency directive or active exploitation"),
 ("CIDRAP / ReliefWeb", "CIDRAP 20 (+20 for outbreak keywords); ReliefWeb disasters 35, updates 12 (+20 keywords)"),
 ("NASA EONET", "storms / volcanoes / floods 30, earthquakes 25, wildfires 12; storms +0.4 per knot above 34 (max +35)"),
 ("News, social, OSINT", "about 15–20 per item; they rely on the confirmation bonus and on crisis wording"),
]

# ---------------------------------------------------------------- live data
def _best_link(links):
    try: L = json.loads(links or "[]")
    except Exception: L = []
    for l in L:
        if "news.google.com" not in (l.get("url") or ""): return l
    return L[0] if L else None

def _examples(c):
    out = {}
    for rk in range(11):
        rows = c.execute("""SELECT cluster_id,title,category,score,rank,confidence,eff_families,watchlist,event_time,first_seen,links
                            FROM clusters WHERE rank=? AND length(title)<240 AND title NOT LIKE 'SOURCE:%'
                            ORDER BY (watchlist=2), watchlist, (links LIKE '%usgs.gov%' OR links LIKE '%gdacs.org%' OR links LIKE '%weather.gov%' OR links LIKE '%swpc.noaa%' OR links LIKE '%who.int%' OR links LIKE '%cisa.gov%' OR links LIKE '%tsunami.gov%') DESC, (confidence='High') DESC, MIN(eff_families,5) DESC, COALESCE(event_time,first_seen) DESC
                            LIMIT 1""", (rk,)).fetchall()
        if rows: out[rk] = dict(rows[0]); out[rk]["link"] = _best_link(rows[0]["links"])
    return out

def _dist(c):
    d = {r["rank"]: dict(r) for r in c.execute("""SELECT rank, COUNT(*) n, SUM(watchlist=0) wire, SUM(watchlist=1) watch,
                                                  MIN(score) lo, MAX(score) hi FROM clusters WHERE watchlist<2 GROUP BY rank""")}
    hidden = {r[0]: r[1] for r in c.execute("SELECT rank, COUNT(*) FROM clusters WHERE watchlist=2 GROUP BY rank")}
    return d, hidden

def _score_trace(S, rows, exs, rising_stored):
    """Mirror of the score lines in scanner.rebuild_cluster (read-only, for display)."""
    st = []
    fams = sorted({r["family"] for r in rows}); eff = sorted(set(fams) - {"social", "GDELT-volume"}); nf = len(eff)
    official = any(r["official"] for r in rows); tiers = {e.get("tier") for e in exs}
    news_only = not official and "news" in tiers
    top = rows[0]
    score = max(r["base"] for r in rows)
    st.append(("Blast radius (impact base)", f"{score}", f"Highest per-item base, from {top['source']}"))
    b = 0
    if news_only:
        b = 15 if nf >= 3 else 8 if nf == 2 else 0
        why = "media-only cluster: +15 for 3+ outlets, +8 for 2"
    elif nf >= 3: b = min(30, max(10, score * 0.6)); why = f"3+ independent families: min(30, max(10, 0.6 × {score}))"
    elif nf == 2: b = min(20, max(8, score * 0.5)); why = f"2 independent families: min(20, max(8, 0.5 × {score}))"
    else: why = "only 1 source family, so no bonus"
    score += b; st.append(("Independent confirmation", f"+{b:g}", f"{nf} independent source famil{'y' if nf == 1 else 'ies'}; {why}"))
    times = sorted(t for t in (S.parse_t(r["event_time"]) for r in rows) if t)
    from datetime import timedelta
    sp = 10 if (len(rows) >= 3 and nf >= 2 and times and (times[-1] - times[0]) <= timedelta(hours=3)) else 0
    span = f"{(times[-1] - times[0]).total_seconds() / 3600:.1f} h" if times else "n/a"
    score += sp; st.append(("Speed of spread", f"+{sp}", f"3+ reports from 2+ families within 3 h? Reports span {span}"))
    rb = (10 if nf >= 2 else 5) if rising_stored else 0
    score += rb; st.append(("Rising", f"+{rb}", "More reports in the last 3 h than in the 3–12 h before" if rising_stored else "not rising at last rescan"))
    conf = "High" if (nf >= 2 and official) or (nf == 1 and official) else "Medium" if nf >= 2 else "Low"
    caps = []
    if conf == "Low": score = min(score, 45); caps.append("Low confidence: capped at 45")
    if news_only: score = min(score, 70); caps.append("media-only: capped at 70")
    if not official and not re.search(S.BOOST_RX, " ".join(r["title"] for r in rows), re.I): score = min(score, 55); caps.append("no official source and no crisis phrasing: capped at 55")
    score = max(0, min(100, int(score)))
    st.append(("Caps", "—" if not caps else "applied", "; ".join(caps) or "no cap applies (official source present)"))
    return score, conf, nf, official, news_only, tiers, eff, st

def _rank_trace(S, rows, exs, score, conf, nf, official, news_only, rising, tiers):
    """Step-by-step mirror of scanner.rank_cluster; the final value is cross-checked against the real function."""
    st = []; text = " ".join(r["title"] for r in rows); cat = rows[0]["category"]; fam = {x["family"] for x in rows}
    r = min(8, round(score / 12)); st.append(("Default from score", r, f"min(8, round({score} ÷ 12))"))
    mags = [e.get("mag") for e in exs if e.get("mag")]
    if mags:
        m = max(mags); r = 2 if m < 5 else 3 if m < 5.5 else 4 if m < 6 else 5 if m < 7 else 6 if m < 8 else 8
        p = {e.get("pager") for e in exs}
        if "red" in p: r = max(r, 8)
        elif "orange" in p: r = max(r, 7)
        elif "yellow" in p: r = max(r, 6)
        st.append(("Earthquake magnitude / PAGER", r, f"M{m}, PAGER {', '.join(x for x in p if x) or 'none'}"))
    tc = {e.get("tsunami_category") for e in exs}
    if "warning" in tc or "threat" in tc: r = max(r, 8); st.append(("Tsunami warning", r, "≥ 8"))
    elif tc & {"advisory", "watch"}: r = max(r, 6); st.append(("Tsunami advisory/watch", r, "≥ 6"))
    lv = {e.get("alertlevel") for e in exs}
    if not mags and "red" in lv:
        r = max(r, 7); pm = re.search(r"is ([\d.]+) million", text)
        if pm and float(pm.group(1)) >= 1: r = max(r, 8)
        st.append(("GDACS red alert", r, "≥ 7 (≥ 8 if 1 million+ affected)"))
    elif not mags and "orange" in lv: r = max(r, 5); st.append(("GDACS orange alert", r, "≥ 5"))
    nws = [e for e in exs if e.get("event")]
    if nws:
        ev = " ".join(e["event"] for e in nws)
        r = 6 if re.search(r"Tornado Emergency|Hurricane Warning|Extreme Wind|Tsunami Warning|Storm Surge Warning", ev) else 5 if any(e.get("severity") == "Extreme" for e in nws) else 4
        if any(e.get("near_local") for e in nws): r += round(S.scope_cfg()[1])
        st.append(("NWS alert type", r, ev[:60]))
    if cat == "space weather":
        lvl = max([e.get("scale_level") or 0 for e in exs] + [0]); kp = max([e.get("kp") or 0 for e in exs] + [0])
        if kp >= 9: lvl = max(lvl, 5)
        elif kp >= 8: lvl = max(lvl, 4)
        r = {0: 1, 1: 2, 2: 3, 3: 5, 4: 7, 5: 9}[lvl]; st.append(("NOAA scale level", r, f"level {lvl}"))
    if cat == "disease":
        r0 = r
        if "WHO" in fam: r = max(r, 5)
        if re.search(S.HIGH_CONSEQ, text, re.I):
            wb = "WHO" in fam or nf >= 3
            r = max(r, 6 if wb else 5 if (official or nf >= 2) else r)
            if wb and re.search(r" and |, ", text): r = max(r, 7)
        if re.search(r"pandemic declared|declares? (a )?pandemic|PHEIC|public health emergency of international concern", text, re.I): r = max(r, 9)
        if r != r0: st.append(("Disease rule", r, "high-consequence pathogen confirmed by WHO or 3+ independent sources, in more than one country" if r == 7 else "WHO, pathogen or PHEIC rule"))
    if cat == "cyber":
        r = 3
        if any(e.get("ransomware") == "Known" for e in exs): r = 4
        if re.search(r"emergency directive", text, re.I): r = 6
        if re.search(r"nationwide (outage|blackout)|grid (attack|down)|critical infrastructure (attack|compromise)", text, re.I): r = 7
        st.append(("Cyber rule", r, "KEV 3 / ransomware 4 / emergency directive 6 / grid or infrastructure 7"))
    if re.search(S.BOOST_RX, text, re.I):
        br = 7 if not re.search(r"ballistic missile|stampede|tsunami warning", text, re.I) else 6
        if re.search(S.PAST_RX, text, re.I): br = min(br, 5)
        r = max(r, br); st.append(("Crisis phrasing", r, f"≥ {br}"))
    elif not official:
        r = min(r, 4); st.append(("No crisis phrasing, not official", r, "capped at 4"))
    if re.search(r"nuclear (war|strike|attack|detonation)", text, re.I): r = max(r, 9); st.append(("Nuclear wording", r, "≥ 9"))
    if re.search(r"nuclear war (is )?imminent|nuclear exchange", text, re.I): r = 10; st.append(("Nuclear exchange wording", r, "= 10"))
    if rising and nf >= 2: r += 1; st.append(("Speed of spread (rising + confirmed)", r, "+1"))
    if conf == "Low": r = min(r, 4); st.append(("Confirmation cap", r, "single source: max 4"))
    elif not official: r = min(r, 6 if nf < 3 else 8); st.append(("Confirmation cap", r, "media/social only: max 6, or max 8 with 3+ outlets"))
    if not official and tiers <= {"news", "social", "aggregate"} and not re.search(S.BOOST_RX, text, re.I):
        if re.search(S.TRIVIA_RX, text, re.I): r = 0; st.append(("Noise filter", r, "trivia pattern"))
        elif not re.search(S.THREAT_RX, text, re.I): r = min(r, 1); st.append(("Noise filter", r, "no threat keyword"))
    return max(0, min(10, int(r))), st

def _worked(c):
    S = _S()
    cands = c.execute("""SELECT * FROM clusters WHERE rank=7 AND watchlist=0 ORDER BY (eff_families>=2) DESC, (confidence='High') DESC,
                         n_items DESC LIMIT 6""").fetchall()
    for cl in cands:
        cl = dict(cl)
        rows = [dict(r) for r in c.execute("SELECT * FROM alerts WHERE cluster_id=? ORDER BY base DESC, event_time", (cl["cluster_id"],))]
        if not rows: continue
        exs = [json.loads(r["extra"] or "{}") for r in rows]
        score, conf, nf, official, news_only, tiers, eff, sst = _score_trace(S, rows, exs, bool(cl["rising"]))
        rk, rst = _rank_trace(S, rows, exs, score, conf, nf, official, news_only, bool(cl["rising"]), tiers)
        real = S.rank_cluster(rows, exs, score, conf, nf, official, news_only, bool(cl["rising"]), tiers)
        if score != cl["score"] or rk != real or real != cl["rank"]: continue   # only show a trace that reproduces the stored values exactly
        return dict(cl=cl, score=score, conf=conf, nf=nf, eff=eff, official=official, sst=sst, rst=rst, rank=rk, n=len(rows),
                    link=_best_link(cl["links"]), pushes=(nf >= int(_cfg().get("push_min_sources", 2))))
    return None

def _et(s):
    try:
        from zoneinfo import ZoneInfo
        d = datetime.fromisoformat((s or "").replace("Z", "+00:00"))
        return d.astimezone(ZoneInfo("America/New_York")).strftime("%b %-d, %Y %-I:%M %p %Z")
    except Exception: return s or "time not reported"

# ---------------------------------------------------------------- page
CSS = """
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
a{color:var(--ac)}a:focus-visible,button:focus-visible,summary:focus-visible{outline:2px solid var(--ac);outline-offset:2px;border-radius:4px}
.skip{position:absolute;left:-999px}.skip:focus{left:12px;top:8px;background:var(--pn);padding:6px 10px;z-index:9}
header{display:flex;flex-wrap:wrap;gap:10px;align-items:center;justify-content:space-between;padding:14px 20px;border-bottom:1px solid var(--bd)}
h1{font-size:18px;margin:0;letter-spacing:.5px}h1 b{color:var(--hi)}h1 small{display:block;font-size:12px;font-weight:400;color:var(--mu);margin-top:4px;letter-spacing:.2px}
.back{border:1px solid var(--bd2);border-radius:8px;padding:6px 12px;text-decoration:none;color:var(--tx);background:var(--pn2);font-size:13px}
.wrap{max-width:1180px;margin:0 auto;padding:16px 20px 40px}
nav.toc{display:flex;flex-wrap:wrap;gap:6px;margin:4px 0 14px}nav.toc a{font-size:12.5px;border:1px solid var(--bd);border-radius:14px;padding:3px 10px;text-decoration:none;color:var(--mu)}
nav.toc a:hover{color:var(--tx);border-color:var(--bd2)}
section{background:var(--pn);border:1px solid var(--bd);border-radius:var(--radius);padding:16px;margin:0 0 16px}
h2{font-size:17px;margin:0 0 10px}h3{font-size:13px;color:var(--mu);text-transform:uppercase;letter-spacing:.06em;margin:14px 0 6px}
.lead{font-size:15.5px;margin:0 0 10px}.mu{color:var(--mu)}.sm{font-size:12.5px}
.kv{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px;margin:10px 0 0}
.kv div{background:var(--pn2);border:1px solid var(--bd);border-radius:8px;padding:10px 12px}.kv b{display:block;font-size:13px;margin-bottom:2px}
/* scale */
.scale{display:grid;grid-template-columns:repeat(11,minmax(0,1fr));gap:3px;margin:14px 0 4px;position:relative}
.scale a{display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:64px;border-radius:6px;text-decoration:none;color:#fff;font-weight:800;font-size:22px;text-shadow:0 1px 2px rgba(0,0,0,.6);position:relative}
.scale a span{font-size:10.5px;font-weight:600;opacity:.95;text-align:center;line-height:1.1;padding:0 2px}
.scale a:hover{filter:brightness(1.15)}.scale a.push{box-shadow:inset 0 -4px 0 #fff}
.bands{display:grid;grid-template-columns:3fr 2fr 2fr 2fr 2fr;gap:3px;font-size:11.5px;color:var(--mu);text-align:center}
.bands div{border-top:2px solid var(--bd2);padding-top:3px}
.legend{display:flex;flex-wrap:wrap;gap:14px;font-size:12px;color:var(--mu);margin-top:10px}.legend i{display:inline-block;width:18px;height:4px;background:#fff;vertical-align:middle;margin-right:5px;border-radius:2px}
/* table */
table{width:100%;border-collapse:collapse;font-size:13px}th,td{border-bottom:1px solid var(--bd);padding:8px 8px;text-align:left;vertical-align:top}
th{font-size:11.5px;color:var(--mu);text-transform:uppercase;letter-spacing:.05em;position:sticky;top:0;background:var(--pn)}
tr:target td{background:#1d2530}
.rk{display:inline-flex;align-items:center;justify-content:center;width:34px;height:34px;border-radius:7px;font-weight:800;font-size:17px;color:#fff;text-shadow:0 1px 2px rgba(0,0,0,.6)}
.chip{display:inline-block;font-size:11px;border-radius:10px;padding:1px 8px;margin:1px 3px 1px 0;white-space:nowrap}
.c-wire{background:#0f2a3a;color:#69c0ff}.c-watch{background:#3a2a00;color:var(--md)}.c-push{background:#3a1010;color:#ff7875}.c-hid{background:#2c3440;color:var(--mu)}
.ex{font-size:12.5px}.ex .t{color:var(--tx)}.ill{font-size:11px;border:1px dashed var(--bd2);border-radius:8px;padding:0 6px;color:var(--mu);margin-right:4px}
.real{font-size:11px;border:1px solid #2f7d4f;color:#95de64;border-radius:8px;padding:0 6px;margin-right:4px}
/* factors */
.fx{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}
.fx article{background:var(--pn2);border:1px solid var(--bd);border-radius:8px;padding:12px}.fx h4{margin:0 0 6px;font-size:14.5px}
.fx p,.fx ul{margin:6px 0;font-size:13px}.fx ul{padding-left:18px}.fx code,.code{font:12px ui-monospace,Menlo,Consolas,monospace;background:#0f1317;border:1px solid var(--bd);border-radius:4px;padding:0 4px}
.how{border-left:3px solid var(--ac);padding-left:8px}.means{border-left:3px solid var(--lo);padding-left:8px}
.lbl{font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--mu);display:block}
details{background:var(--pn2);border:1px solid var(--bd);border-radius:8px;padding:8px 12px;margin-top:10px}summary{cursor:pointer;font-weight:600}
/* worked */
.steps{display:grid;gap:6px;margin:8px 0}.step{display:grid;grid-template-columns:minmax(150px,220px) 70px 1fr;gap:10px;align-items:baseline;background:var(--pn2);border-radius:6px;padding:7px 10px;font-size:13px}
.step b:nth-child(2){font-variant-numeric:tabular-nums;text-align:right}.step.tot{border:1px solid var(--bd2)}
.rules{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:12px}.rules div{background:var(--pn2);border:1px solid var(--bd);border-radius:8px;padding:12px;font-size:13px}
.disc{background:#0f1317;border:1px solid var(--bd);border-radius:8px;padding:12px;font-size:12.5px;color:var(--mu)}
footer{text-align:center;color:#8a93a6;font-size:12px;border-top:1px solid #2a2f3a;padding:12px;margin-top:10px}
@media(max-width:760px){
 header{padding:12px 14px}.wrap{padding:12px 12px 30px}section{padding:12px}
 .scale{grid-template-columns:repeat(6,minmax(0,1fr))}.scale a{min-height:54px;font-size:19px}.bands{display:none}
 table.rt thead{display:none}table.rt,table.rt tbody,table.rt tr,table.rt td{display:block;width:100%}
 table.rt tr{border:1px solid var(--bd);border-radius:8px;margin:0 0 10px;padding:6px 8px;background:var(--pn2)}
 table.rt td{border:0;padding:4px 0}table.rt td[data-l]:before{content:attr(data-l);display:block;font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--mu)}
 .step{grid-template-columns:1fr auto}.step span{grid-column:1/-1;color:var(--mu)}
}
"""

def _render():
    cfg = _cfg(); pr = int(cfg.get("push_min_rank", 7)); ps = int(cfg.get("push_min_sources", 2))
    scope = str(cfg.get("scope", "global")); lb = cfg.get("local_boost", 0)
    c = _db()
    try:
        ex = _examples(c); dist, hidden = _dist(c); wk = _worked(c)
        rng = c.execute("SELECT MIN(first_seen), MAX(updated) FROM clusters").fetchone()
    finally: c.close()
    total = sum(d["n"] for d in dist.values()) or 1
    P = []
    a = P.append
    a('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">')
    a('<title>How we score: blackout.network</title>')
    a('<meta name="description" content="How blackout.network scores threats: the 0–100 severity score and the 0–10 rank, factor by factor, with real examples. Research only.">')
    a('<link rel="stylesheet" href="/theme.css"><link rel="icon" href="/favicon.ico" sizes="any">')
    a(f'<style>{CSS}</style></head><body><a class="skip" href="#main">Skip to content</a>')
    a('<header><h1>BLACKOUT.<b>NETWORK</b> · How we score<small>The world\'s threats, scored and sourced, before cable news catches up.</small></h1>'
      '<span><a class="back" href="/newsletter" style="margin-right:6px">✉ Newsletter</a><a class="back" href="/#wire">← Back to the dashboard</a></span></header>')
    a('<div class="wrap" id="main" role="main">')
    a('<nav class="toc" aria-label="On this page"><a href="#why7">Why is this a 7?</a><a href="#scale">0–10 scale</a><a href="#table">Rank by rank</a>'
      '<a href="#factors">Scoring factors</a><a href="#worked">Worked example</a><a href="#rules">Watchlist &amp; alerts</a><a href="#disclaimer">Disclaimer</a></nav>')

    # --- intro
    a('<section id="why7" aria-labelledby="h-why"><h2 id="h-why">Why is this a 7?</h2>')
    a('<p class="lead">Every story is given two numbers. The <b>score (0–100)</b> measures how strong and well-confirmed the evidence is. '
      'The <b>rank (0–10)</b> measures how much of the world it could affect. A 7 means a <b>major national or multi-country event</b>, backed by an '
      'official source or by at least 3 independent outlets.</p>')
    a('<div class="kv"><div><b>1 · Blast radius</b><span class="sm mu">How many people and places could be affected. This sets the starting score and most rank rules.</span></div>'
      '<div><b>2 · Independent confirmation</b><span class="sm mu">2+ unrelated sources raise the score. A single unconfirmed source is capped at a score of 45 and a rank of 4.</span></div>'
      '<div><b>3 · Speed of spread</b><span class="sm mu">Fast, multi-source spread within 3 hours adds points, and +1 rank if confirmed.</span></div>'
      f'<div><b>Instant alert</b><span class="sm mu">Sent only when an item is rank {pr}+ <i>and</i> confirmed by {ps}+ independent sources.</span></div></div>')
    a('<p class="sm mu" style="margin:10px 0 0">The rank is <b>not</b> simply the score divided by 10. The scanner starts from the score '
      '(score ÷ 12, max 8), then category rules override it: earthquake magnitude, official alert levels, pathogen type and crisis wording. '
      'For example, an M6.4 quake confirmed by two agencies can score 74 but still rank 5. '
      f'Scope: <b>{E(scope)}</b>. Every region is ranked the same way (local boost = {E(lb)}).</p></section>')

    # --- scale
    a('<section id="scale" aria-labelledby="h-scale"><h2 id="h-scale">The 0–10 scale</h2>'
      '<p class="sm mu" style="margin:0">Select a rank to jump to its row. A white underline marks the ranks that can trigger an instant alert.</p>')
    a('<div class="scale" role="list">')
    for r in range(11):
        nm = RANKS[r][0]
        a(f'<a role="listitem" href="#rank-{r}" class="{"push" if r >= pr else ""}" style="background:{COLORS[r]}" '
          f'aria-label="Rank {r}: {E(nm)}">{r}<span>{E(nm)}</span></a>')
    a('</div><div class="bands" aria-hidden="true"><div>0–2 · noise / local</div><div>3–4 · minor regional</div><div>5–6 · significant</div>'
      '<div>7–8 · major national / multi-country</div><div>9–10 · civilizational</div></div>')
    a(f'<div class="legend"><span><i></i>can trigger an instant alert (rank {pr}+ with {ps}+ independent sources)</span>'
      '<span>Single unconfirmed sources stop at 4</span><span>Media-only reports stop at 6, or 8 with 3+ outlets</span><span>9–10 need an official source</span></div>')
    # distribution bar
    a('<h3>Last 7 days of stories by rank (live)</h3><div style="display:flex;height:14px;border-radius:7px;overflow:hidden;background:#0f1317" role="img" aria-label="Distribution of visible stories by rank over the last 7 days">')
    for r in range(11):
        n = (dist.get(r) or {}).get("n", 0)
        if n: a(f'<div title="Rank {r}: {n} stories" style="flex:{n};background:{COLORS[r]}"></div>')
    a('</div><p class="sm mu" style="margin:4px 0 0">' + " · ".join(f"rank {r}: {(dist.get(r) or {}).get('n', 0)}" for r in range(11)) +
      f' (visible stories; another {sum(hidden.values())} low-value items are stored but hidden). Most stories are minor, and that is expected.</p></section>')

    # --- table
    a('<section id="table" aria-labelledby="h-table"><h2 id="h-table">Rank by rank</h2>'
      '<p class="sm mu" style="margin:0 0 8px">The default score band is what the score alone would give. Category rules can move a story above or below it. '
      'The live examples are real stories from the database, each linked to its source. Examples marked <span class="ill">illustrative</span> show '
      'what would earn that rank and are not real events.</p>')
    a('<div style="overflow-x:auto"><table class="rt"><thead><tr><th scope="col">Rank</th><th scope="col">Meaning</th><th scope="col">Default score band · seen (7 d)</th>'
      '<th scope="col">Blast radius</th><th scope="col">Confirmation</th><th scope="col">Where it appears</th><th scope="col">What earns it · example</th></tr></thead><tbody>')
    for r in range(11):
        nm, br, cf, where, earns = RANKS[r]
        band = f"{BANDS[r][0]}–{BANDS[r][1]}" if r in BANDS else "rule only"
        d = dist.get(r)
        seen = f'{d["n"]} stories, scores {d["lo"]}–{d["hi"]}' if d else "none in the last 7 days"
        chips = []
        if r <= 1: chips += ['<span class="chip c-wire">The Wire (official)</span>', '<span class="chip c-hid">hidden (non-official)</span>']
        elif r <= 4: chips += ['<span class="chip c-wire">The Wire</span>', '<span class="chip c-watch">Watchlist if single-source</span>']
        else: chips += ['<span class="chip c-wire">The Wire</span>']
        if r >= pr: chips.append(f'<span class="chip c-push">instant alert if {ps}+ sources</span>')
        e = ex.get(r)
        if e:
            lk = e.get("link") or {}
            t = E(e["title"][:170] + ("…" if len(e["title"]) > 170 else ""))
            tt = f'<a class="t" href="{E(lk.get("url"))}" target="_blank" rel="noopener noreferrer">{t}</a>' if lk.get("url") else f'<span class="t">{t}</span>'
            place = {0: "The Wire", 1: "Watchlist", 2: "hidden"}.get(e["watchlist"], "")
            exh = (f'<span class="real">real</span>{tt}<br><span class="mu">{E(lk.get("source") or "")} · {E(e["category"])} · {E(_et(e["event_time"] or e["first_seen"]))} · '
                   f'score {e["score"]} · {e["eff_families"]} independent source{"s" if e["eff_families"] != 1 else ""} · {place}</span>')
        else:
            exh = f'<span class="ill">illustrative</span><span class="t">{E(ILLUSTRATIVE.get(r, earns))}</span>'
        a(f'<tr id="rank-{r}"><td data-l="Rank"><span class="rk" style="background:{COLORS[r]}">{r}</span></td>'
          f'<td data-l="Meaning"><b>{E(nm)}</b></td><td data-l="Default score band · seen (7 d)">{band}<br><span class="mu sm">{E(seen)}</span></td>'
          f'<td data-l="Blast radius">{E(br)}</td><td data-l="Confirmation">{E(cf)}</td><td data-l="Where it appears">{"".join(chips)}</td>'
          f'<td data-l="What earns it · example" class="ex"><div>{E(earns)}</div><div style="margin-top:5px">{exh}</div></td></tr>')
    a('</tbody></table></div><p class="sm mu">Ranks 9 and 10 never come from the score. They only come from specific rules, '
      '+1 for fast confirmed spread can lift a story one step, and any rank of 9 or higher needs an official source.</p></section>')

    # --- factors
    a('<section id="factors" aria-labelledby="h-fx"><h2 id="h-fx">Scoring factors</h2>'
      '<p class="sm mu" style="margin:0 0 10px">Each card shows <span class="how">how it is computed</span> and <span class="means">what it means</span>. '
      'The rules are fixed and work the same way every time. They are heuristics based on source data and keywords, not human judgment.</p><div class="fx">')
    a('<article><h4>1 · Blast radius</h4><p class="how"><span class="lbl">How it\'s computed</span>Each item gets an impact <b>base</b> (0–100) from the '
      'source\'s own severity fields: earthquake magnitude, PAGER level, alert level, people affected, NOAA scale and pathogen type. '
      'A story starts at the <b>highest base</b> among its reports.</p><p class="means"><span class="lbl">What it means</span>A bigger quake, a red alert or more people exposed '
      'gives a higher starting point. Most rank rules are also about blast radius.</p></article>')
    a('<article><h4>2 · Independent confirmation</h4><p class="how"><span class="lbl">How it\'s computed</span>Reports are grouped by source <b>family</b>: '
      'the agency, the publisher domain or, for social posts, the primary source they cite. Uncited social posts and volume-surge signals never count.</p><ul>'
      '<li>2 families: <code>+min(20, max(8, 0.5 × base))</code></li><li>3+ families: <code>+min(30, max(10, 0.6 × base))</code></li>'
      '<li>Media-only: +8 for 2 outlets, +15 for 3+, and a maximum score of 70</li></ul>'
      '<p class="means"><span class="lbl">What it means</span>Two or more unrelated sources score high. The bonus grows with impact, so a confirmed minor event stays minor.</p></article>')
    a('<article><h4>3 · Speed of spread</h4><p class="how"><span class="lbl">How it\'s computed</span><b>+10</b> if 3+ reports from 2+ families arrive within 3 hours. '
      '<b>Rising</b> (3+ reports from 2+ sources in the last 3 h, more than the 3–12 h before, or a 2× keyword surge): <b>+10</b> if confirmed, otherwise +5. '
      'Rising and confirmed also adds <b>+1 rank</b>.</p><p class="means"><span class="lbl">What it means</span>A story spreading quickly across unrelated sources moves up.</p></article>')
    a('<article><h4>4 · Confidence caps</h4><p class="how"><span class="lbl">How it\'s computed</span>Confidence is <b>High</b> when an official source is present, '
      '<b>Medium</b> for 2+ non-official families and <b>Low</b> for a single non-official source. Low means a maximum score of 45 and rank 4. '
      'Media or social reports with no official source and no crisis wording max out at a score of 55. Rank caps are 6 with fewer than 3 outlets and 8 with 3+.</p>'
      '<p class="means"><span class="lbl">What it means</span>Rumors cannot climb the scale until something independent confirms them.</p></article>')
    a('<article><h4>5 · Category rules</h4><p class="how"><span class="lbl">How it\'s computed</span>These override the default rank:</p><ul>'
      '<li>Earthquake: M&lt;5→2, &lt;5.5→3, &lt;6→4, &lt;7→5, &lt;8→6, 8+→8; PAGER yellow≥6, orange≥7, red≥8</li>'
      '<li>Tsunami warning ≥8, advisory/watch ≥6 · GDACS red ≥7 (≥8 if 1M+ affected), orange ≥5</li>'
      '<li>NWS: hurricane / tornado-emergency / storm-surge / extreme-wind / tsunami warning 6, Extreme 5, other 4</li>'
      '<li>Space weather: NOAA level 1→2, 2→3, 3→5, 4→7, 5→9</li>'
      '<li>Disease: WHO ≥5; dangerous pathogen ≥6, ≥7 if multi-country; pandemic/PHEIC 9</li>'
      '<li>Cyber: KEV 3, ransomware 4, emergency directive 6, grid / critical-infrastructure 7</li></ul></article>')
    a('<article><h4>6 · Crisis wording &amp; noise filter</h4><p class="how"><span class="lbl">How it\'s computed</span>Phrases such as <i>military coup, martial law declared, '
      'assassinated, bank run, sovereign default, mass casualty, invasion of</i> set ≥7. Ballistic missile, stampede and tsunami warning set ≥6. '
      'Coverage of a past event (trial, verdict, anniversary) is held to 5. Nuclear strike or detonation sets 9, and nuclear exchange sets 10. '
      'Non-official items with no crisis wording are capped at 4; trivia goes to 0, and items with no threat keyword at all are capped at 1.</p>'
      '<p class="means"><span class="lbl">What it means</span>The wording has to describe an actual crisis. Sports, festivals and opinion pieces are filtered out.</p></article>')
    a('</div><details><summary>Impact base by source (the blast-radius inputs)</summary><table style="margin-top:8px"><tbody>' +
      "".join(f'<tr><th scope="row" style="position:static;text-transform:none;font-size:13px;color:var(--tx);width:34%">{E(s)}</th><td>{E(f)}</td></tr>' for s, f in BASES) +
      '</tbody></table></details>'
      '<details><summary>Merging duplicate reports (12-hour window)</summary><p class="sm">Reports are merged into one story when they match within a 12-hour window. '
      'Earthquakes must be within 1 h, 200 km and ±0.7 magnitude. NWS alerts must share the event type and issuing office. Other reports must be within 400 km with similar titles, '
      'or share enough title words when they have no coordinates. Each merged report adds to the source count, not to the base. '
      'The hourly chat report separately skips anything already reported in the last 12 hours.</p></details></section>')

    # --- worked example
    a('<section id="worked" aria-labelledby="h-wk"><h2 id="h-wk">Worked example: a real rank-7 story</h2>')
    if wk:
        cl = wk["cl"]; lk = wk["link"] or {}
        a(f'<p style="margin:0 0 4px"><a href="{E(lk.get("url"))}" target="_blank" rel="noopener noreferrer"><b>{E(cl["title"])}</b></a></p>'
          f'<p class="sm mu" style="margin:0">{E(cl["category"])} · first seen {E(_et(cl["first_seen"]))} · {wk["n"]} reports from {wk["nf"]} independent source '
          f'famil{"y" if wk["nf"] == 1 else "ies"} ({E(", ".join(wk["eff"][:6]))}{"…" if len(wk["eff"]) > 6 else ""}) · confidence {E(wk["conf"])}</p>')
        a('<h3>Score (0–100)</h3><div class="steps">')
        for k, v, why in wk["sst"]:
            a(f'<div class="step"><b>{E(k)}</b><b>{E(v)}</b><span>{E(why)}</span></div>')
        a(f'<div class="step tot"><b>Score</b><b>{wk["score"]}</b><span>{"high (60+)" if wk["score"] >= 60 else "below the high line (60)"}</span></div></div>')
        a('<h3>Rank (0–10)</h3><div class="steps">')
        for k, v, why in wk["rst"]:
            a(f'<div class="step"><b>{E(k)}</b><b>{E(v)}</b><span>{E(why)}</span></div>')
        a(f'<div class="step tot"><b>Rank</b><b>{wk["rank"]}</b><span>{"rank " + str(pr) + "+ with " + str(wk["nf"]) + " independent sources, so it qualifies for an instant alert" if wk["pushes"] else "rank " + str(pr) + "+ but only " + str(wk["nf"]) + " source family, so it is shown on The Wire without an instant alert"}</span></div></div>')
        a('<p class="sm mu">This breakdown is recomputed live from the stored reports, and the page checks that it matches the scanner\'s own result exactly. '
          'If no rank-7 story in the database matches, this section explains with a snapshot instead. Note: syndicated copies of one wire story on different domains count as separate families.</p>')
    else:
        a('<p class="sm"><span class="ill">snapshot</span> No current rank-7 story matched the live check, so this is a snapshot from Oct 31, 2026: '
          '“Ebola outbreak in DR Congo approaches 5,000 deaths as US issues new travel rule” (CIDRAP plus 70 other independent families). '
          'It had a base of 40 (CIDRAP 20 + 20 for outbreak keywords) and a confirmation bonus of +24 (3+ families: 0.6 × 40), for a score of <b>64</b>. '
          'The default rank was 5. The disease rule raised it to 6 (Ebola confirmed by 3+ independent sources) and then to <b>7</b> (multi-country wording). '
          'It qualifies for an instant alert.</p>')
    a('</section>')

    # --- rules
    a('<section id="rules" aria-labelledby="h-rules"><h2 id="h-rules">Watchlist, UNCONFIRMED and instant alerts</h2><div class="rules">')
    a('<div><b>Watchlist (automatic)</b><br>A story with <b>Low</b> confidence (one non-official source) goes to the Watchlist instead of The Wire. Its score is capped at 45 and its rank at 4. '
      'If a second independent source confirms it on a later scan, it moves to The Wire automatically.</div>')
    a('<div><b>Hidden noise</b><br>Non-official stories ranked 0–1 are stored for the record. They are not shown on The Wire or the Watchlist.</div>')
    a(f'<div><b>Instant alert</b><br>Sent once per story, only when it is on The Wire <b>and</b> ranked <b>{pr}+</b> <b>and</b> confirmed by <b>{ps}+</b> independent source families. '
      'A single-agency rank-7 alert, such as a lone GDACS red notice, shows on The Wire but does not trigger an instant alert.</div>')
    a('<div><b>UNCONFIRMED (editorial rule)</b><br>Unconfirmed items normally stay on the Watchlist. The hourly report may still mention one '
      'if a reviewer judges it a potential <b>8+</b> with a national or civilizational blast radius. It is then clearly labeled <b>UNCONFIRMED</b>. '
      'This is a reporting rule, not part of the scanner\'s math: the scanner itself never ranks an unconfirmed item above 4.</div>')
    a('</div></section>')

    a('<section id="disclaimer" aria-labelledby="h-disc"><h2 id="h-disc">Disclaimer</h2><div class="disc">blackout.network is a research-only aggregator. Scores and ranks are '
      'automated estimates from public feeds and keyword rules, so they can be wrong, late or skewed by how sources word their reports. Always check the linked original source '
      'and follow official guidance (local emergency management, NWS, WHO, national authorities). Nothing here is a warning, an order or advice. In an emergency, call your local emergency number.</div></section>')
    a(f'</div><footer>Research-only data · blackout.network · <a href="/#wire">Dashboard</a> · <a href="/newsletter">Newsletter</a> · <a href="/privacy">Privacy</a> · <a href="/tos">Terms</a> · Data range: {E(_et(rng[0]))} – {E(_et(rng[1]))} · '
      f'Page generated {E(_et(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")))}</footer><script src="/api/search/app.js"></script><link rel="stylesheet" href="/api/translate/app.css"><script src="/api/translate/app.js"></script></body></html>')
    return "".join(P)

def handle_get(path, qs):
    if path.rstrip("/") not in ("/scoring", "/about/scoring"): return 404, {"error": "not found"}
    with _LK:
        c = _db()
        try: stamp = c.execute("SELECT MAX(updated) FROM clusters").fetchone()[0]
        finally: c.close()
        hit = _C.get("page")
        if hit and hit[0] == stamp and time.time() - hit[1] < TTL: return 200, hit[2], "text/html"
        body = _render(); _C["page"] = (stamp, time.time(), body)
    return 200, body, "text/html"
