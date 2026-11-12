"""Story report layer for /wire/<cluster_id> pages (story.py). v1 Nov 12 2026 (t1276u); v2 bottom-line brief Nov 12 2026 (t1324u).

Every story page gets a concise brief under the headline, in seven numbered parts plus a "Bottom line" card:
  1 What happened            desk note (newsletter analyst, sourced) or the scanner's own WHAT + source count + quoted headlines
  2 Why it matters / what we see   desk analysis (first 3 sentences) + counted facts: 24 h trend, related stories, source mix
  3 Why we ranked it         plain reading of the rank rules (scoring.RANKS: reach, confirmation needed), confirmation, speed,
                             with the generated "Signal snapshot" graphic (0-10 scale, sources, official sources, reports, time to alert)
  4 Risk factor              Low (0-3) / Medium (4-6) / High (7-10) from the rank band, or a desk override with its sourced reason
  5 If true / if overblown   desk outlook / if_true / if_false, else signposts by kind of story (conditional, never facts)
  6 What you should do       desk tip + 2-4 steps linking official guidance (Ready.gov, CDC, CISA, NWS, State Dept, FDIC)
  7 Sources                  desk sources + the story's own source links (official first, social last, deduped)
Visuals: rights-cleared image (USGS ShakeMap, Commons, U.S. federal) as the lead; else an outlet share card the desk approved
(link preview, credited); the Signal snapshot is always drawn. Key facts, locator map and charts sit in the side column; key moments
are collapsed. Stories without a desk note are labelled "Quick brief, built automatically".
Precomputed input: data/story_reports.json (tools/story_reports/build.py on the box, pushed with a signed one-file push).
No LLM, no network, no DB writes at request time (related-story count reads blackout.db via mode=ro).
"""
import os, re, json, html
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

BASE = os.path.dirname(os.path.abspath(__file__))
REPORTS = os.environ.get("BN_STORY_REPORTS", os.path.join(BASE, "data", "story_reports.json"))
ET = ZoneInfo("America/New_York"); UTC = timezone.utc
E = lambda s: html.escape(str(s if s is not None else ""), quote=True)
_RC = {"mt": None, "v": {}}
CAT = {"war/conflict": "War and conflict", "natural disaster": "Natural disaster", "disease": "Disease and outbreaks", "cyber": "Cyber",
       "political": "Political", "space weather": "Space weather", "financial": "Financial", "infrastructure": "Infrastructure",
       "nuclear": "Nuclear", "civil unrest": "Civil unrest", "terrorism": "Terrorism", "other": "Other"}

# ---------------------------------------------------------------- SVG icons (no emoji on the site)
_P = {
    "news": '<path d="M4 5h13v14H6a2 2 0 0 1-2-2V5Z"/><path d="M17 9h3v8a2 2 0 0 1-2 2"/><path d="M7 9h7M7 12h7M7 15h4"/>',
    "facts": '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M8 9h8M8 12h8M8 15h5"/>',
    "analysis": '<path d="M4 19V5"/><path d="M4 19h16"/><path d="m7 15 4-4 3 3 5-6"/>',
    "watch": '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
    "shield": '<path d="M12 3 5 6v6c0 4.4 3 7.7 7 9 4-1.3 7-4.6 7-9V6l-7-3Z"/><path d="m9 12 2 2 4-4"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "link": '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
    "chart": '<path d="M5 20V10M10 20V4M15 20v-7M20 20v-4"/>',
    "image": '<rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="9" cy="10" r="1.6"/><path d="m21 16-5-5-8 8"/>',
    "up": '<path d="M5 17 11 11l3 3 6-6"/><path d="M15 8h5v5"/>',
    "down": '<path d="m5 7 6 6 3-3 6 6"/><path d="M15 16h5v-5"/>',
    "flat": '<path d="M4 12h15"/><path d="m15 8 4 4-4 4"/>',
    "ext": '<path d="M14 4h6v6"/><path d="M20 4 11 13"/><path d="M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5"/>',
    "play": '<path d="M8 5v14l11-7L8 5Z"/>',
    "star": '<path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9L12 3Z"/>',
}
def icon(name, cls="sr-i"):
    return (f'<svg class="{cls}" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">{_P[name]}</svg>')

# ---------------------------------------------------------------- data
def reports():
    try: mt = os.path.getmtime(REPORTS)
    except OSError: _RC.update(mt=None, v={}); return {}
    if _RC["mt"] != mt:
        try:
            with open(REPORTS, encoding="utf-8") as f: v = json.load(f)
            _RC.update(mt=mt, v=v if isinstance(v, dict) else {})
        except Exception: _RC.update(mt=mt, v={})
    return _RC["v"]

def reports_mtime():
    try: return os.path.getmtime(REPORTS)
    except OSError: return 0

def _dt(iso):
    try: return datetime.strptime(str(iso)[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=UTC)
    except Exception:
        try: return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone(UTC)
        except Exception: return None

def et(iso, short=False):
    d = _dt(iso)
    if not d: return ""
    d = d.astimezone(ET); z = "EDT" if d.dst() else "EST"
    return d.strftime("%b %-d, %-I:%M %p ") + z if short else d.strftime("%b %-d, %Y, %-I:%M %p ") + z

_ATTR = re.compile(r"\[([^\[\]]{2,200})\]")
def brief_facts(brief):
    """(clean WHAT sentence, [(label, value)]) from the scanner brief. Values are copied, never computed."""
    m = re.search(r"WHAT:\s*(.*?)\s*(?:WHERE:|WHEN:|CONFIDENCE:|VERIFY:|$)", brief or "", re.S)
    what = (m.group(1) if m else "").strip()
    facts = []
    for blk in _ATTR.findall(what):
        for part in blk.split(";"):
            if ":" not in part: continue
            k, v = [x.strip() for x in part.split(":", 1)]
            if not k or not v or len(k) > 40 or len(v) > 80 or k.lower() in ("sea",): continue
            facts.append((k[:1].upper() + k[1:], v))
    what = re.sub(r"\s+", " ", _ATTR.sub("", what)).strip().rstrip(". ")
    return what, facts[:6]

_EMO = re.compile("[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\uFE0F\u200D\u2B50\u2B55\u231A-\u231B\u23E9-\u23FA]")
def txt(t):
    """Headline text as the site shows it: hype prefixes and emoji removed (SVG-only rule), whitespace collapsed."""
    try:
        import site_page as S; t = S.clean_title(t)
    except Exception: pass
    t = _EMO.sub("", t or "")
    t = re.sub(r"\s+", " ", t).strip(" -–—|:")
    return t

def _fam(a): return (a.get("family") or a.get("source") or "").strip()
def _famname(f): return "Social media" if f.lower() == "social" else f
_STOP = set("""the and for with from that this have has had will would could should into over after amid about against their there where which while what when were been being than then they them said says say report reports reported news live breaking update updates latest video watch footage
 attack attacks attacked explosion explosions blast killed kills dead death deaths people new more most warns warning alert alerts official officials just today yesterday week month year near amid during under amid least another other also hits hit
 fire strike strikes struck major huge massive local state national world global government police source sources
 outbreak outbreaks case cases tops total number rises rising confirmed health disease virus earthquake quake magnitude storm""".split())
def tokens(t):
    return {w for w in re.findall(r"[a-z\u00c0-\u024f]{4,}", (t or "").lower()) if w not in _STOP}
def _relevant(a, anchor):
    """Shares at least one distinctive word with the story's own headline / summary (keeps misclustered items out of Key moments)."""
    return not anchor or bool(tokens(a.get("title")) & anchor)
def _tk(a): return re.sub(r"[^a-z0-9]+", " ", txt(a.get("title")).lower())[:48].strip()
def _solid(a):
    """Good enough to headline a key moment: not a social post and not a hashtag string."""
    return _fam(a).lower() != "social" and (a.get("title") or "").count("#") < 3 and len(txt(a.get("title"))) >= 12

def moments(rows, anchor=None):
    """Earliest report, earliest official source, earliest report from each new source family, latest report. Rows are time-ordered.
    Only items that share a distinctive word with the story headline/summary qualify (scanner clusters can hold stray items)."""
    out, fams, off, shown = [], set(), False, set()
    for a in rows:
        f = _fam(a); lab = None; ok = _relevant(a, anchor) and _tk(a) not in shown
        if not out: lab = "Earliest report"
        elif a.get("official") and not off and ok: lab = "Earliest official source"
        elif f and f not in fams and _solid(a) and ok and sum(1 for x in out if x[0] == "New source") < 3: lab = "New source"
        if a.get("official") and ok: off = True
        if f: fams.add(f)
        if lab: out.append((lab, a)); shown.add(_tk(a))
    last = next((a for a in reversed(rows) if _solid(a) and _relevant(a, anchor) and _tk(a) not in shown), None)
    if last is not None and all(last is not x[1] for x in out): out.append(("Latest report", last))
    return out

def _buckets(rows):
    ts = sorted(d for d in (_dt(a.get("first_seen")) for a in rows) if d)
    if len(ts) < 3: return None
    span = ts[-1] - ts[0]
    if span <= timedelta(hours=48):
        step, start = timedelta(hours=1), ts[0].replace(minute=0, second=0)
        lab = lambda d: d.astimezone(ET).strftime("%b %-d, %-I %p")
        unit = "hour"
    else:
        step = timedelta(days=1); s = ts[0].astimezone(ET).replace(hour=0, minute=0, second=0, microsecond=0); start = s.astimezone(UTC)
        lab = lambda d: d.astimezone(ET).strftime("%b %-d")
        unit = "day"
    n = min(int((ts[-1] - start) / step) + 1, 60)
    if n < 2: return None
    c = [0] * n
    for d in ts:
        i = min(int((d - start) / step), n - 1); c[i] += 1
    return {"counts": c, "start": start, "step": step, "lab": lab, "unit": unit}

def chart_time(rows):
    if len(rows) < 5: return ""
    b = _buckets(rows)
    if not b: return ""
    c, n = b["counts"], len(b["counts"]); mx = max(c) or 1
    W, H = 600, 120
    bw = W / n
    bars = "".join(f'<rect x="{i * bw + bw * .14:.1f}" y="{H - (v / mx) * (H - 4):.1f}" width="{max(1.0, bw * .72):.1f}" height="{max(1.5, (v / mx) * (H - 4)):.1f}" rx="1.5">'
                   f'<title>{v} report{"" if v == 1 else "s"}</title></rect>' for i, v in enumerate(c) if v)
    first = b["lab"](b["start"]); last = b["lab"](b["start"] + b["step"] * (n - 1))
    total = sum(c)
    return (f'<figure class="sr-chart"><figcaption class="sr-h3">{icon("chart")}Reports over time</figcaption>'
            f'<p class="sr-peak">Peak: {mx} report{"" if mx == 1 else "s"} in one {b["unit"]}</p>'
            f'<svg class="sr-plot" viewBox="0 0 {W} {H}" role="img" aria-label="{total} reports by {b["unit"]}, from {E(first)} to {E(last)} Eastern Time; peak {mx} in one {b["unit"]}" preserveAspectRatio="none">{bars}</svg>'
            f'<div class="sr-axis"><span>{E(first)} ET</span><span>{E(last)} ET</span></div>'
            f'<p class="sr-note">Reports BLACKOUT.NETWORK logged for this story, by {b["unit"]}. Volume is not severity.</p></figure>')

def chart_sources(rows):
    cnt = {}
    for a in rows:
        f = _fam(a)
        if f: f = _famname(f); cnt[f] = cnt.get(f, 0) + 1
    if len(cnt) < 2: return ""
    top = sorted(cnt.items(), key=lambda x: (-x[1], x[0].lower()))[:8]; mx = top[0][1]
    li = "".join(f'<li><span class="sr-bl">{E(k)}</span><span class="sr-bar"><span class="sr-fill" style="width:{max(4, round(100 * v / mx))}%"></span></span><span class="sr-bn">{v}</span></li>' for k, v in top)
    more = len(cnt) - len(top)
    return (f'<figure class="sr-chart"><figcaption class="sr-h3">{icon("facts")}Who is reporting</figcaption><ul class="sr-bars">{li}</ul>'
            + (f'<p class="sr-note">Plus {more} more source famil{"y" if more == 1 else "ies"}.</p>' if more > 0 else "") + '</figure>')

def figure(im, lead=False):
    try: w, h = int(im["w"]), int(im["h"])
    except Exception: return ""
    src, link = im.get("src") or "", im.get("link") or ""
    if not re.match(r"^https://", src) or not re.match(r"^https?://", link): return ""
    cap = (im.get("caption") or "").strip()
    return (f'<figure class="sr-fig{" sr-lead" if lead else ""}"><a href="{E(link)}" target="_blank" rel="noopener">'
            f'<img src="{E(src)}" alt="{E(im.get("alt") or cap)}" width="{w}" height="{h}" loading="lazy" decoding="async" referrerpolicy="no-referrer"></a>'
            f'<figcaption>{E(cap)} <span class="sr-cr">Image: {E(im.get("credit") or "")}. {E(im.get("license") or "")}. '
            f'<a href="{E(link)}" target="_blank" rel="noopener">Source{icon("ext", "sr-i sr-i-s")}</a></span></figcaption></figure>')

TRAJ_ICON = {"Rising": "up", "Easing": "down", "Steady": "flat"}

# ---------------------------------------------------------------- v2 brief (t1324u): bottom-line, newsletter-style, every story
# Seven numbered parts: what happened, why it matters / what we see, why we ranked it, risk, if true / if overblown, what you should
# do, sources. Desk notes (newsletter analyst notes, sourced) are used when the desk wrote one; otherwise every part is built only from
# the scanner's own fields and published rules (scoring.RANKS), labelled as an automatic quick brief. Nothing is invented: numbers are
# counted from the rows on the page, guidance links are official pages (Ready.gov, CDC, CISA, NWS, State Dept, FDIC, WHO).
RISK = ((7, "High", "#ff3b3b"), (4, "Medium", "var(--sr-y)"), (0, "Low", "#3fa66a"))
RANK_NAME = {0: "Noise", 1: "Background", 2: "Minor", 3: "Minor regional", 4: "Regional", 5: "Significant", 6: "Serious", 7: "Major",
             8: "Severe", 9: "Critical", 10: "Catastrophic"}

def _ranks():
    try:
        import scoring; return scoring.RANKS
    except Exception: return {}

def risk(rank):
    for k, lab, col in RISK:
        if int(rank or 0) >= k: return lab, col
    return "Low", "#3fa66a"

def _sents(s, n):
    xs = [x for x in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"\u201c'(])", (s or "").strip()) if x.strip()]
    return " ".join(xs[:n])

def _plural(n, one, many=None): return f"{n} {one if n == 1 else (many or one + 's')}"

def _join(xs):
    xs = [x for x in xs if x]
    return xs[0] if len(xs) == 1 else (", ".join(xs[:-1]) + " and " + xs[-1] if xs else "")

def confirmation(officials, eff):
    if officials: return f"confirmed by official sources ({_join(officials[:3])}{' and others' if len(officials) > 3 else ''})"
    if eff >= 3: return f"reported by {eff} independent sources, none of them official yet"
    if eff == 2: return "reported by two independent sources, no official confirmation yet"
    return "a single source so far, so treat it as unconfirmed"

# Guidance: (keyword regex on title+what+category, [(step text, official URL)]). First match wins; generic last.
_KIT = ("Keep a basic emergency kit (water, food, medicine, chargers) ready at home.", "https://www.ready.gov/kit")
_ALERTS = ("Turn on emergency alerts on your phone so official warnings reach you.", "https://www.ready.gov/alerts")
_TRAVEL = ("If you plan to travel to the area, check the State Department advisory first.", "https://travel.state.gov/content/travel/en/traveladvisories/traveladvisories.html")
GUIDE = [
    (r"ebola|bundibugyo|marburg", [("Check CDC travel health notices before any trip to the affected countries.", "https://wwwnc.cdc.gov/travel/notices"),
                                   ("Learn how Ebola spreads (direct contact with body fluids, not through the air) from the CDC.", "https://www.cdc.gov/ebola/")]),
    (r"measles", [("Check that you and your kids are up to date on the measles (MMR) vaccine.", "https://www.cdc.gov/measles/"),
                  ("Check CDC travel health notices before international trips.", "https://wwwnc.cdc.gov/travel/notices")]),
    (r"bird flu|avian|h5n1|h9n2|h5n5", [("Avoid touching sick or dead birds and raw milk; the CDC lists who is at risk.", "https://www.cdc.gov/bird-flu/")]),
    (r"yellow fever", [("If you travel to the region, check the CDC page on yellow fever vaccination.", "https://www.cdc.gov/yellow-fever/"),
                       ("Check CDC travel health notices before you go.", "https://wwwnc.cdc.gov/travel/notices")]),
    (r"cholera", [("If you travel to the region, drink only safe water; the CDC explains how cholera spreads.", "https://www.cdc.gov/cholera/about/index.html")]),
    (r"earthquake|\bquake|\bm ?\d\.\d|magnitude|tsunami", [("Learn Drop, Cover, and Hold On so you react fast if the ground shakes where you are.", "https://www.ready.gov/earthquakes"),
                                                        ("If you are on a coast and an official tsunami warning is issued, move inland or uphill.", "https://www.ready.gov/tsunamis")]),
    (r"hurricane|typhoon|cyclone|tropical storm", [("If you are in the path, follow your local officials and know your evacuation zone.", "https://www.ready.gov/hurricanes"), _ALERTS]),
    (r"tornado", [("Know where your safe room or lowest interior room is.", "https://www.ready.gov/tornadoes"), _ALERTS]),
    (r"flood", [("Never drive into flood water; turn around.", "https://www.ready.gov/floods"), _ALERTS]),
    (r"wildfire|bushfire|forest fire", [("If you live near the fire, be ready to leave early when officials say so.", "https://www.ready.gov/wildfires"), _ALERTS]),
    (r"heat ?wave|extreme heat|heatstroke|\bheat\b", [("Learn the signs of heat illness and stay cool and hydrated.", "https://www.ready.gov/heat")]),
    (r"volcan|eruption", [("If you live near the volcano, follow local evacuation orders and protect your lungs from ash.", "https://www.ready.gov/volcanoes")]),
    (r"solar|geomagnetic|space weather|\bcme\b|aurora", [("Check NOAA's Space Weather Prediction Center for current storm levels.", "https://www.swpc.noaa.gov/"),
                                                         ("Keep a power bank charged; strong storms can affect GPS, radio and, rarely, power grids.", "https://www.ready.gov/space-weather")]),
    (r"nuclear|radiolog|radiation|uranium|warhead|icbm", [("Know the basics if a radiation emergency ever happens: get inside, stay inside, stay tuned.", "https://www.ready.gov/radiation"), _KIT]),
    (r"power (outage|cut)|blackout|grid|substation|power plant|electricity", [("Plan for a power cut: keep a flashlight, a power bank and a few days of water.", "https://www.ready.gov/power-outages")]),
    (r"cyber|hack|ransomware|vulnerab|zero-day|cve-|exploit|malware|ddos", [("Install updates for your devices and apps as soon as they are offered.", "https://www.cisa.gov/secure-our-world"),
                                                                            ("If you run IT, check CISA's list of actively exploited flaws.", "https://www.cisa.gov/known-exploited-vulnerabilities-catalog")]),
    (r"bank|deposit|withdrawal|bank run|insolven|crypto|exchange halts", [("Check that your bank deposits are within FDIC insurance limits.", "https://www.fdic.gov/resources/deposit-insurance"),
                                                                        ("Keep some cash and a backup way to pay for a few days.", "https://www.ready.gov/financial-preparedness")]),
    (r"shooting|gunman|stabbing|bomb|terror|attack on (a |the )?(crowd|market|concert)", [("Know how to react at a crowded event: run, hide, fight.", "https://www.ready.gov/mass-gatherings-incidents"),
                                                                                          ("Report suspicious activity to local authorities.", "https://www.dhs.gov/see-something-say-something")]),
    (r"war|strike|missile|drone|troops|military|invasion|ceasefire|shelling|airstrike|houthi|hormuz|tanker|blockade", [_TRAVEL]),
    (r"protest|riot|unrest|coup|martial law", [_TRAVEL]),
    (r"outbreak|virus|disease|epidemic|pandemic|infection|cases", [("Check CDC travel health notices before international trips.", "https://wwwnc.cdc.gov/travel/notices"),
                                                                   ("Wash your hands often; it stops many infections.", "https://www.cdc.gov/clean-hands/about/index.html")]),
]
US_LOC = re.compile(r"united states|\bu\.?s\.?a?\b|america|puerto rico|guam|washington,? d\.?c|" + "|".join([
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado", "connecticut", "delaware", "florida", "georgia, us", "hawaii", "idaho",
    "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana", "maine", "maryland", "massachusetts", "michigan", "minnesota", "mississippi",
    "missouri", "montana", "nebraska", "nevada", "new hampshire", "new jersey", "new mexico", "new york", "north carolina", "north dakota", "ohio",
    "oklahoma", "oregon", "pennsylvania", "rhode island", "south carolina", "south dakota", "tennessee", "texas", "utah", "vermont", "virginia",
    "washington", "west virginia", "wisconsin", "wyoming"]) + r"|, [A-Z]{2}$", re.I)
FUEL = r"hormuz|tanker|oil (price|field|pipeline|facility)|pipeline|refiner|gas field|brent|opec"

# Signposts for "if true / if overblown": what to look for next, by kind of story. Conditional analysis, never facts.
SIGNS = [
    (r"ebola|bundibugyo|marburg|measles|cholera|yellow fever|mpox|outbreak|bird flu|avian|h5n1|h9n2|virus|disease|epidemic",
     "Expect official case and death counts from WHO or the health ministry to keep rising, more districts or countries reporting cases, and travel screening or health notices.",
     "Official updates show case counts levelling off, no new areas reporting, and health agencies lowering their alert level."),
    (r"heat ?wave|heat[- ]related|heat illness|heat exhaustion|sickened|hospitali[sz]ed",
     "Expect officials to confirm the cause, and more people treated if the conditions continue.",
     "Officials confirm a one-off cause, no new people fall ill, and there is no wider risk."),
    (r"earthquake|\bquake|magnitude|tsunami",
     "Expect damage and casualty reports from local officials over the next day, possible aftershocks, and USGS raising its PAGER impact estimate.",
     "Local officials report little or no damage, USGS keeps a low PAGER alert, and no tsunami warning is issued."),
    (r"hurricane|typhoon|cyclone|tropical storm|flood|tornado|wildfire|storm",
     "Expect official warnings to widen, evacuation orders, and power outages in the affected area.",
     "Forecasts weaken, warnings are lifted, and outage numbers stay small."),
    (r"cyber|hack|ransomware|vulnerab|zero-day|cve-|exploit|malware|ddos",
     "Expect more organisations to report break-ins, emergency patch deadlines from CISA, and vendors confirming active attacks.",
     "Vendors ship fixes quickly, no new victims are named, and CISA does not escalate."),
    (r"nuclear|radiolog|uranium|warhead|icbm",
     "Expect formal statements from governments or the IAEA, changes in military readiness, and emergency diplomacy.",
     "Officials walk back the claims, inspectors report no change, and talks continue."),
    (r"bank|deposit|withdrawal|insolven|crypto|market|currency",
     "Expect regulators to step in, withdrawal limits, and other firms reporting the same strain.",
     "Customers get access to their money, regulators say the system is stable, and the story fades within days."),
    (r"war|strike|missile|drone|troops|military|invasion|shelling|airstrike|houthi|hormuz|tanker|blockade|attack",
     "Expect more strikes or retaliation, official casualty figures, and knock-on effects such as higher fuel prices or travel warnings.",
     "Officials deny it or give lower figures, no further attacks follow, and talks or a pause hold."),
    (r"protest|riot|unrest|coup|martial law|shooting|gunman|bomb|terror",
     "Expect police or government statements, more arrests or casualties confirmed, and security alerts in the area.",
     "Authorities report the situation under control, with no further incidents."),
]
SIGN_DEFAULT = ("Expect official confirmation and more independent outlets reporting the same facts over the next 24 hours.",
                "Official sources stay silent or deny it, and no new outlets pick it up.")

def _first(table, text, default=None):
    for rx, *v in table:
        if re.search(rx, text, re.I): return v
    return default

def _related(cid, r):
    """(count, [(cid, title, rank)]) of other ranked stories in the same category sharing 2+ distinctive headline words, past 7 days.
    Read-only (sqlite URI mode=ro). Counts only: the reader can open each one."""
    try:
        import sqlite3
        db = os.path.join(BASE, "blackout.db")
        since = (datetime.now(UTC) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
        c = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
        try:
            q = c.execute("SELECT cluster_id,title,rank FROM clusters WHERE category=? AND cluster_id!=? AND updated>=? AND rank>=3 "
                          "ORDER BY rank DESC, updated DESC LIMIT 400", (r.get("category") or "", cid, since)).fetchall()
        finally: c.close()
    except Exception: return 0, []
    me = tokens(r.get("title"))
    if len(me) < 2: return 0, []
    def ok(t):
        o = tokens(t); i = len(o & me)
        return i >= 3 or (i >= 2 and i / max(1, len(o | me)) >= 0.25)
    hits = [(x[0], txt(x[1]), int(x[2] or 0)) for x in q if ok(x[1])]
    return len(hits), hits[:2]

def _trend(rows):
    now = datetime.now(UTC); a = b = 0
    for x in rows:
        d = _dt(x.get("first_seen"))
        if not d: continue
        if now - d <= timedelta(hours=24): a += 1
        elif now - d <= timedelta(hours=48): b += 1
    return a, b

def snapshot(rank, rows, officials, eff, high_at=None, first=None):
    """Generated context graphic, always available: where the story sits on our 0-10 scale, plus how many sources and how fast."""
    rank = int(rank or 0); lab, col = risk(rank)
    W, H, x0, x1 = 600, 46, 4, 596
    seg = (x1 - x0) / 11
    cells = []
    for i in range(11):
        c = "#3fa66a" if i <= 3 else ("var(--sr-y)" if i <= 6 else "#ff3b3b")
        cells.append(f'<rect x="{x0 + i * seg + 2:.1f}" y="18" width="{seg - 4:.1f}" height="24" rx="5" fill="{c}" opacity="{1 if i <= rank else .18}"/>')
    mx = x0 + rank * seg + seg / 2
    svg = (f'<svg class="sr-snap" viewBox="0 0 {W} {H}" role="img" aria-label="Rank {rank} of 10 on the BLACKOUT.NETWORK scale ({RANK_NAME.get(rank, "")}); risk {lab.lower()}">'
           f'{"".join(cells)}<path d="M{mx - 9:.1f} 2 L{mx + 9:.1f} 2 L{mx:.1f} 14 Z" fill="currentColor"/></svg>'
           '<div class="sr-snap-ax"><span>0 Low</span><span>Medium</span><span>High 10</span></div>')
    stats = [(str(rank) + "/10", RANK_NAME.get(rank, "")), (str(eff), "independent sources"), (str(len(officials)), "official sources"), (str(len(rows)), "reports logged")]
    d1, d2 = _dt(first), _dt(high_at)
    if d1 and d2 and d2 >= d1:
        hrs = (d2 - d1).total_seconds() / 3600
        stats.append(("under 1 h" if hrs < 1 else f"{hrs:.0f} h", "to reach our alert line"))
    li = "".join(f'<li><b>{E(a)}</b><span>{E(b)}</span></li>' for a, b in stats)
    return (f'<figure class="sr-snapfig"><figcaption class="sr-h3">{icon("chart")}Signal snapshot</figcaption>{svg}<ul class="sr-stats">{li}</ul>'
            f'<p class="sr-note">Built from the reports BLACKOUT.NETWORK logged for this story. Rank rules: <a href="/scoring">How we score</a>.</p></figure>')

def share_card(sh):
    """Outlet share image shown as a link-preview card (credited, links to the article). Only cards the desk approved render."""
    src, link = sh.get("src") or "", sh.get("link") or ""
    if not re.match(r"^https://", src) or not re.match(r"^https?://", link): return ""
    t = (sh.get("title") or "").strip(); site = (sh.get("site") or "").strip()
    return (f'<a class="sr-share" href="{E(link)}" target="_blank" rel="noopener"><img src="{E(src)}" alt="{E(sh.get("alt") or t)}" loading="lazy" decoding="async" referrerpolicy="no-referrer">'
            f'<span class="sr-share-b"><span class="sr-share-s">{E(site)}</span><span class="sr-share-t">{E(t)}</span>'
            f'<span class="sr-cr">Image: {E(site)}, shown as a link preview. Opens the article{icon("ext", "sr-i sr-i-s")}</span></span></a>')

_SOC = re.compile(r"^(?:bluesky|mastodon|telegram|reddit|x|twitter|threads|tiktok|youtube|facebook|instagram)\b|@|(?:google news: )?(?:facebook|instagram|youtube|tiktok|reddit|x\.com|threads)\b", re.I)
def _is_social(a): return _fam(a).lower() == "social" or bool(_SOC.search(a.get("source") or ""))
_HYPE = re.compile(r"\b(?:BREAKING(?: NEWS)?|JUST IN|URGENT|DEVELOPING|What Happened)\b\s*[:!\u2014-]*\s*", re.I)
_BANNED = re.compile(r"\bverified\b|before the news|\bfirst to (?:report|break)|anniversar", re.I)
def _clean_hl(t):
    """Third-party headline shown on the page: hype labels removed (word rules apply to what we display, quotes included)."""
    return re.sub(r"\s+", " ", _HYPE.sub("", html.unescape(txt(t or "")))).strip(" -\u2013\u2014:;,")
def _sname(n):
    """Source label: 'Google News: ' prefix and site taglines (' - Breaking News, Latest News ...') dropped."""
    n = re.sub(r"^Google News: ", "", n or "")
    return re.sub(r"\s+[-|\u2013\u2014]\s+.*$", "", n).strip() or n
def _q(t, n=170):
    """Headline as a clean quote: entities decoded, links, bare domain paths, hashtag tails and arrows removed, cut at a word."""
    t = _clean_hl(t)
    t = re.sub(r"https?://\S+|\b[\w-]+(?:\.[\w-]+)+/\S*", "", t)
    t = re.sub(r"(?:\s*#\w+)+\s*$", "", t); t = re.sub(r"\s*(?:->|\u2192|\|)\s*.*$", "", t)
    t = re.sub(r"\s+", " ", t).strip(" -\u2013\u2014:;,")
    if len(t) > n: t = t[:n].rsplit(" ", 1)[0].rstrip(" ,;:-\u2013") + "\u2026"
    return t
def _cut(t, n=90):
    t = t or ""
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0].rstrip(" ,;:-\u2013") + "\u2026"
def _norm(t): return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()

def _srclist(note, rows, anchor=None, desk=False):
    out, seen = [], set()
    for s in (note or {}).get("sources") or []:
        u = s.get("url") or ""
        if re.match(r"^https?://", u) and u not in seen: seen.add(u); out.append((u, s.get("domain") or "", ""))
    rs = [a for a in rows if _relevant(a, anchor) and _solid(a)] or [a for a in rows if _solid(a)] or list(rows)   # never leave a story without its sources
    rs = sorted(rs, key=lambda a: (0 if a.get("official") else (2 if _is_social(a) else 1)))
    extra = 0
    for a in rs:
        u = a.get("source_url") or ""
        if not re.match(r"^https?://", u) or u in seen: continue
        if desk and (extra >= 3 or _is_social(a)): continue
        qt = _q(a.get("title"), 120)
        if _norm(qt) in seen: continue
        seen.add(u); seen.add(_norm(qt)); out.append((u, a.get("source") or "", qt)); extra += 1
        if len(out) >= 8: break
    return out[:8]

def render(cid, r, rows, rank, tname, title, what, loc, officials, eff, fams, locator=""):
    """Returns (html, dek_override). rows: deduped alerts in time order."""
    R = reports(); notes = R.get("notes") or {}
    note = notes.get(cid) or notes.get((R.get("alias") or {}).get(cid) or "")
    imgs = [i for i in (R.get("images") or {}).get(cid) or [] if isinstance(i, dict)]
    shares = [s for s in (R.get("shares") or {}).get(cid) or [] if isinstance(s, dict) and (s.get("ok") or (R.get("share_policy") or {}).get("auto"))]
    what_b, bfacts = brief_facts(r.get("brief"))
    anchor = tokens(" ".join([title or "", what or "", what_b or "", (note or {}).get("headline") or ""]))
    rank = int(rank or 0); RK = _ranks().get(rank) or (RANK_NAME.get(rank, ""), "", "", "", "")
    rname, radius, rule = RK[0] or RANK_NAME.get(rank, ""), (RK[1] or "").lower(), RK[2] or ""
    lab, col = risk(rank)
    ov = (note or {}).get("risk") if (note or {}).get("risk") in ("Low", "Medium", "High") else ""
    if ov:   # desk override (sourced note), shown as such; never above the story's colour band (pre-publish A14)
        order = ["Low", "Medium", "High"]
        ov = order[min(order.index(ov), order.index(lab))]
        lab, col = ov, {"High": "#ff3b3b", "Medium": "var(--sr-y)", "Low": "#3fa66a"}[ov]
    cat = (r.get("category") or "").lower(); catn = CAT.get(cat, cat.title() or "News")
    text = " ".join([title or "", what_b or "", what or "", cat, (note or {}).get("headline") or ""])
    if not (rows or note or what_b or (what and what != title)): return "", ""
    conf = confirmation(officials, eff)
    desk = bool(note and note.get("what_happened"))
    # ---- 1 What happened
    if desk:
        wh = [note["what_happened"]]; dek = note.get("headline") or ""
    else:
        dek = ""; wh = []
        w = what_b or what
        tn = _norm(title)
        if w and _norm(w) != tn: wh.append(w.rstrip(". ") + ".")
        cnt = f"{_plural(eff, 'independent source')} {'is' if eff == 1 else 'are'} reporting this" if eff else ""
        if cnt: wh.append(cnt[:1].upper() + cnt[1:] + (f", including {_plural(len(officials), 'official source')} ({_join(officials[:3])}{' and others' if len(officials) > 3 else ''})" if officials else ", none of them official yet") + ".")
        qs, seenq = [], {tn}
        for a in sorted([a for a in rows if _solid(a) and _relevant(a, anchor) and not _is_social(a)], key=lambda a: (0 if a.get("official") else 1, a.get("first_seen") or "")):
            q = _q(a.get("title")); k = _norm(q)
            if len(q) < 25 or k in seenq or any(k[:40] == x[:40] for x in seenq): continue
            seenq.add(k); qs.append(f"{re.sub(r'^Google News: ', '', a.get('source') or 'One source')} reported at {et(a.get('first_seen'), True)}: \u201c{q.rstrip('.')}{'' if q.endswith('\u2026') else '.'}\u201d")
            if len(qs) >= 2: break
        if not qs:
            same = list(dict.fromkeys(re.sub(r"^Google News: ", "", a.get("source") or "") for a in rows if _solid(a) and not _is_social(a) and _norm(_q(a.get("title"))) == tn))
            if same and title: wh.append(f"{_join(same[:3])} reported: \u201c{_q(title).rstrip('.')}.\u201d")
        if qs: wh.append(" ".join(qs))
        if not wh and rows: wh.append(f"BLACKOUT.NETWORK has logged {_plural(len(rows), 'report')} on this story.")
    # ---- bottom line (top card)
    if desk and note.get("why_it_matters"): bl = note["why_it_matters"]
    else: bl = f"A {rname.lower()} {catn.lower()} story{(' in ' + loc) if loc else ''}, {conf}."
    head = (f'<section class="sr-bline" aria-label="Bottom line"><div class="sr-bline-top"><span class="sr-k">{icon("star")}Bottom line</span>'
            f'<span class="sr-risk" style="--rc:{col}"><span class="sr-dot"></span>Risk: {lab}</span></div><p class="sr-bline-p">{E(bl)}</p>'
            + ('' if desk else '<p class="sr-auto">Quick brief, built automatically from the reports we track. Our analysts have not written this story up yet.</p>')
            + (f'<p class="sr-auto">{E(note.get("edition") or "BLACKOUT.NETWORK brief")}, written {E(et(note.get("generated_at"), True))} from the sources listed below.'
               + (" The story has had new reports since." if (_dt(r.get("updated")) or datetime.min.replace(tzinfo=UTC)) > (_dt(note.get("generated_at")) or datetime.max.replace(tzinfo=UTC)) else "")
               + '</p>' if desk else '') + '</section>')
    S = []
    def sec(n, key, ic, h, body):
        if body: S.append(f'<section class="sr-sec sr-n" aria-labelledby="sr_{key}"><h2 class="sr-k" id="sr_{key}"><span class="sr-num">{n}</span>{icon(ic)}{h}</h2>{body}</section>')
    sec(1, "what", "news", "What happened", "".join(('<p class="sr-lede">' if i == 0 else "<p>") + f'{E(p)}</p>' for i, p in enumerate(wh[:3])))
    # ---- 2 Why it matters / what we see
    b2 = []
    if desk:
        if note.get("analysis"): b2.append(f'<p>{E(_sents(note["analysis"], 3))}</p>')
        if note.get("pattern"): b2.append(f'<p>{E(note["pattern"])}</p>')
    see = []
    a24, b24 = _trend(rows)
    if a24 or b24:
        mv = "rising" if a24 > b24 * 1.25 and a24 - b24 >= 2 else ("easing" if b24 > a24 * 1.25 and b24 - a24 >= 2 else "steady")
        if a24 == 0: see.append(f"No new reports in the last 24 hours; {_plural(b24, 'report')} the day before.")
        else: see.append(f"Coverage is {mv}: {_plural(a24, 'report')} in the last 24 hours, against {b24} the day before.")
    n_rel, rel = _related(cid, r)
    if n_rel:
        see.append(f"It is one of {n_rel + 1} related {catn.lower()} stories on our board in the past 7 days.")
    srcmix = {"official": len([a for a in rows if a.get("official")]), "social": len([a for a in rows if _is_social(a)])}
    if rows and not desk:
        see.append(f"Of {_plural(len(rows), 'report')}, {srcmix['official']} came from official sources and {srcmix['social']} from social media.")
    if see: b2.append("<ul class=\"sr-ul\">" + "".join(f"<li>{E(s)}</li>" for s in see) + "</ul>")
    if rel: b2.append('<p class="sr-rel">Related: ' + " · ".join(f'<a href="/wire/{E(c)}">{E(_cut(t))}</a>' for c, t, _ in rel) + "</p>")
    sec(2, "why", "analysis", "Why it matters" if desk else "What we see", "".join(b2))
    # ---- 3 Why we ranked it this way
    b3 = [f'<li><b>{rank}/10, {E(rname)}.</b> That is our level for stories whose reach is {E(radius or "limited")}.</li>',
          f'<li><b>Confirmation:</b> {E(conf[:1].upper() + conf[1:])}.' + (f' This rank needs: {E(rule[:1].lower() + rule[1:])}.' if rule else "") + '</li>']
    if desk and note.get("rank_why"): b3.insert(0, f'<li><b>Our read:</b> {E(note["rank_why"])}</li>')
    d1, d2 = _dt(r.get("first_seen")), _dt(r.get("high_at"))
    if d1 and d2 and d2 >= d1 and rank >= 4:
        hrs = (d2 - d1).total_seconds() / 3600
        b3.append(f'<li><b>Speed:</b> it crossed our alert line {"within an hour of" if hrs < 1 else "about " + _plural(round(hrs), "hour") + " after"} the first report.</li>')
    if str(r.get("rising") or "0") not in ("0", "", "None", "False") and eff >= 2: b3.append('<li><b>Spreading:</b> new independent sources were still joining at the last scan, which adds a point.</li>')
    if not officials and eff <= 1 and rank <= 4: b3.append('<li>Unconfirmed single-source stories are capped at 4 until a second source or an official one confirms them.</li>')
    sec(3, "rank", "chart", "Why we ranked it this way", f'<ul class="sr-ul">{"".join(b3)}</ul>' + snapshot(rank, rows, officials, eff, r.get("high_at"), r.get("first_seen")))
    # ---- 4 Risk factor
    rw = {"High": "A major event with wide impact", "Medium": "A significant event, mostly regional for now", "Low": "Limited or local impact so far"}[lab]
    meter = "".join(f'<span class="sr-m{" on" if l == lab else ""}" style="--rc:{c}">{l}</span>' for _, l, c in reversed(RISK))
    rline = (f"Our analysts rate this {lab.lower()}: {(note.get('risk_why') or '').rstrip('.')}".rstrip(": ") + "." if ov else f"{rw}, {conf}.")
    sec(4, "risk", "shield", "Risk factor", f'<div class="sr-meter" role="img" aria-label="Risk {lab}">{meter}</div><p>{E(rline)}</p>')
    # ---- 5 If true / if overblown
    st = _first(SIGNS, text.replace(cat, " "), list(SIGN_DEFAULT))
    t_true = (note or {}).get("if_true") or ((note or {}).get("outlook") if desk else "") or st[0]
    t_false = (note or {}).get("if_false") or st[1]
    if desk and note.get("confidence"):
        t_false += f" Our confidence in the reporting is {note['confidence'].lower()}" + (f": {note['confidence_why']}" if note.get("confidence_why") else ".")
    sec(5, "if", "watch", "If it\u2019s true, if it\u2019s overblown",
        f'<div class="sr-if"><div><h3 class="sr-h3">If it\u2019s true</h3><p>{E(t_true)}</p></div><div><h3 class="sr-h3">If it\u2019s overblown</h3><p>{E(t_false)}</p></div></div>')
    # ---- 6 What you should do
    steps = []
    if desk and note.get("what_to_do"): steps.append((note["what_to_do"], ""))
    g = _first(GUIDE, text, [[_KIT, _ALERTS]])[0]
    # A desk brief's own advice leads; generic tips are added only when the desk did not rate the story Low or say no action is needed.
    quiet = desk and bool(note.get("what_to_do")) and (lab == "Low" or re.match(r"\s*no action is needed", note["what_to_do"], re.I))
    if not quiet:
        if re.search(FUEL, text, re.I) and not any("fuel" in s[0].lower() for s in steps):
            steps.append(("Fuel prices can jump on news like this; there is no need to panic-buy, but don't let your tank run near empty.", ""))
        steps += [s for s in g if s[0] not in {x[0] for x in steps}]
        if len(steps) < 2: steps.append(_KIT if _KIT not in steps else _ALERTS)
    lead6 = ""
    if loc and cat not in ("cyber", "financial", "space weather") and not US_LOC.search(loc) and lab != "High":
        lead6 = f'<p>If you are not in or traveling to {E(loc)}, you don\u2019t need to do anything today beyond staying informed.</p>'
    li6 = "".join(f'<li>{E(t)}' + (f' <a href="{E(u)}" target="_blank" rel="noopener">{E(re.sub(r"^www[.]|^wwwnc[.]", "", u.split("/")[2]))}{icon("ext", "sr-i sr-i-s")}</a>' if u else "") + '</li>' for t, u in steps[:4])
    sec(6, "do", "shield", "What you should do", lead6 + f'<ol class="sr-ol">{li6}</ol>')
    # ---- 7 Sources
    src = _srclist(note, rows, anchor, desk)
    if src:
        sec(7, "src", "link", "Sources", '<ol class="sr-src">' + "".join(
            f'<li><a href="{E(u)}" target="_blank" rel="noopener">{E(t or d or u.split("/")[2].removeprefix("www."))}{icon("ext", "sr-i sr-i-s")}</a>' + (f' <span class="sr-ms">{E(d)}</span>' if t and d else "") + '</li>' for u, d, t in [(u, _sname(d), t) for u, d, t in src]) + "</ol>")
    # ---- visuals: rights-cleared image, else approved outlet share card, else locator map (snapshot graphic always in part 3)
    figs = [x for x in (figure(im, i == 0) for i, im in enumerate(imgs[:3])) if x]
    cards = [x for x in (share_card(s) for s in shares[:2]) if x]
    lead_vis = figs[0] if figs else (cards[0] if cards else "")
    more_vis = figs[1:] + (cards if figs else cards[1:])
    gallery = (f'<section class="sr-sec" aria-labelledby="sr_img"><h2 class="sr-k" id="sr_img">{icon("image")}Images</h2><div class="sr-gal">{"".join(more_vis)}</div></section>' if more_vis else "")
    # ---- details (collapsed): key facts, key moments, charts
    f = [("Rank", f"{rank}/10, {rname}")]
    if cat: f.append(("Category", catn))
    if loc: f.append(("Where", loc))
    if r.get("event_time"): f.append(("Event time", et(r["event_time"], True)))
    if r.get("first_seen"): f.append(("Logged here since", et(r["first_seen"], True)))
    if r.get("updated"): f.append(("Last update", et(r["updated"], True)))
    f.append(("Official sources", (", ".join(officials[:5]) + (" and others" if len(officials) > 5 else "")) if officials else "None yet"))
    f += bfacts
    facts = (f'<section class="sr-card" aria-labelledby="sr_facts"><h2 class="sr-k" id="sr_facts">{icon("facts")}Key facts</h2><dl class="sr-dl">'
             + "".join(f"<div><dt>{E(k)}</dt><dd>{E(v)}</dd></div>" for k, v in f) + "</dl></section>")
    km = moments(rows, anchor) if len(rows) >= 2 else []
    kmh = ""
    if km:
        li = []
        for lb, a in km:
            u = a.get("source_url") or ""; t = _clean_hl(a.get("title"))[:200]
            if not t or _BANNED.search(t): continue
            tl = f'<a href="{E(u)}" target="_blank" rel="noopener">{E(t)}</a>' if re.match(r"^https?://", u) else E(t)
            li.append(f'<li><span class="sr-mk">{E(lb)}</span><time datetime="{E(a.get("first_seen") or "")}">{E(et(a.get("first_seen"), True))}</time>'
                      f'<p>{tl}</p><span class="sr-ms">{E(_sname(a.get("source")))}{" · official source" if a.get("official") else ""}</span></li>')
        kmh = "" if not li else f'<details class="sr-more"><summary>{icon("clock")}Key moments ({len(li)})</summary><ol class="sr-tl">{"".join(li)}</ol></details>'
    g = chart_time(rows) + chart_sources(rows)
    graphics = f'<section class="sr-card sr-graphics" aria-label="Graphics">{g}</section>' if g else ""
    main = head + (lead_vis if lead_vis else "") + "".join(S) + gallery + kmh
    side = (f'<div class="sr-loc">{locator}</div>' if locator else "") + facts + graphics
    return (f'<style>{CSS}</style><article class="sr sr2" aria-label="Story brief"><div class="sr-grid"><div class="sr-main">{main}</div>'
            f'<aside class="sr-side" aria-label="Key facts and graphics">{side}</aside></div></article>'), dek

CSS = """
.sr{--sr-y:var(--a-y,#FFC21A);--sr-ink:var(--a-ink,var(--tx,#e6e9ee));--sr-ink2:var(--a-ink2,#D2D2D7);--sr-mu:var(--a-mu,var(--mu,#8a94a3));
 --sr-sf:var(--a-sf,var(--pn,#16181C));--sr-ln:var(--a-ln,var(--bd,#2A2D33));--sr-sh:var(--a-sh,0 0 0 1px #23262B);margin:18px 0 24px;color:var(--sr-ink)}
html[data-theme="light"] .sr{--sr-y:#C97B00}
html body main .sr h2.sr-k,html[data-theme] body main .sr h2.sr-k,html body main .sr .sr-mk{color:var(--sr-y)!important;-webkit-text-fill-color:var(--sr-y)}
html body main .sr h2.sr-k .sr-i{stroke:var(--sr-y)}
.sr-grid{display:grid;grid-template-columns:minmax(0,1fr) 352px;gap:36px;align-items:start}
.sr-main{min-width:0}.sr-side{position:sticky;top:84px;display:flex;flex-direction:column;gap:16px;min-width:0}
.sr-k{display:flex;align-items:center;gap:8px;font:700 13px/1.2 Inter,system-ui,sans-serif!important;letter-spacing:.09em!important;text-transform:uppercase;color:var(--sr-y)!important;margin:0 0 12px!important}
.sr-i{flex:none;vertical-align:-3px}.sr-i-s{width:13px;height:13px;margin-left:4px;opacity:.7}
.sr-sec{margin:0 0 30px;padding-top:2px}
.sr-sec+.sr-sec{border-top:1px solid var(--sr-ln);padding-top:24px}
.sr-sec p{font-size:17px;line-height:1.65;margin:0 0 14px;color:var(--sr-ink2);overflow-wrap:anywhere}
.sr p.sr-lede{font-size:19px;line-height:1.6;color:var(--sr-ink)}
.sr-h3{display:flex;align-items:center;flex-wrap:wrap;gap:8px;font:600 17px/1.35 Inter,system-ui,sans-serif;margin:20px 0 8px;color:var(--sr-ink)}
.sr-why{font-weight:500;color:var(--sr-ink)!important;border-left:3px solid var(--sr-y);padding-left:14px}
.sr-asof{font-size:13.5px!important;color:var(--sr-mu)!important;margin:-4px 0 6px!important}
.sr-traj{display:inline-flex;align-items:center;gap:5px;font:600 12px/1 Inter,system-ui,sans-serif;letter-spacing:.04em;text-transform:uppercase;border:1px solid var(--sr-ln);border-radius:999px;padding:5px 10px;color:var(--sr-ink2)}
.sr-traj .sr-i{width:14px;height:14px}
.sr-src{margin:0;padding-left:22px}.sr-src li{margin:0 0 6px;font-size:15px}
.sr-card{background:var(--sr-sf);border-radius:18px;box-shadow:var(--sr-sh);padding:18px 20px}
.sr-card .sr-k{margin-bottom:10px!important}
.sr-dl{margin:0;display:grid;gap:0}.sr-dl>div{display:grid;grid-template-columns:118px minmax(0,1fr);gap:10px;padding:8px 0;border-top:1px solid var(--sr-ln)}
.sr-dl>div:first-child{border-top:0;padding-top:2px}
.sr-dl dt{font-size:12.5px;color:var(--sr-mu);line-height:1.4}.sr-dl dd{margin:0;font-size:14px;line-height:1.4;color:var(--sr-ink);overflow-wrap:anywhere}
.sr-graphics{display:flex;flex-direction:column;gap:18px}
.sr-chart{margin:0}.sr-chart .sr-h3{margin:0 0 8px;font-size:14.5px}
.sr-plot{display:block;width:100%;height:110px;color:var(--sr-y);border-bottom:1px solid var(--sr-ln)}.sr-plot rect{fill:currentColor}
.sr-axis{display:flex;justify-content:space-between;font-size:11.5px;color:var(--sr-mu);margin-top:5px}.sr-peak{font-size:12px!important;color:var(--sr-mu)!important;margin:0 0 6px!important}
.sr-note{font-size:12px!important;color:var(--sr-mu)!important;margin:6px 0 0!important;line-height:1.4!important}
.sr-bars{list-style:none;margin:0;padding:0}.sr-bars li{display:grid;grid-template-columns:minmax(0,40%) minmax(0,1fr) 28px;gap:8px;align-items:center;font-size:13px;padding:3px 0}
.sr-bl{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--sr-ink2)}.sr-bn{text-align:right;color:var(--sr-mu);font-variant-numeric:tabular-nums}
.sr-bar{height:8px;border-radius:99px;background:color-mix(in srgb,var(--sr-ln) 70%,transparent);overflow:hidden}.sr-fill{display:block;height:100%;background:var(--sr-y);border-radius:99px}
.sr-fig{margin:0 0 30px}.sr-fig>a{display:block;border-radius:14px;overflow:hidden;background:var(--sr-sf);box-shadow:var(--sr-sh)}
.sr-fig img{display:block;width:100%;height:auto;max-height:560px;object-fit:contain;background:#fff}
.sr-fig figcaption{font-size:13.5px;line-height:1.5;color:var(--sr-ink2);margin-top:8px}.sr-cr{display:block;color:var(--sr-mu);font-size:12.5px}
.sr-cr a{color:var(--sr-mu)}
html:not([data-theme="light"]) .sr a:not([class]){color:var(--a-lk,#FFC21A)}
.sr-gal{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(260px,100%),1fr));gap:16px}.sr-gal .sr-fig{margin:0}
.sr-tl{list-style:none;margin:0;padding:0}
.sr-tl li{position:relative;padding:0 0 18px 22px;border-left:2px solid var(--sr-ln);margin-left:5px}
.sr-tl li:last-child{padding-bottom:2px}
.sr-tl li:before{content:"";position:absolute;left:-7px;top:3px;width:12px;height:12px;border-radius:50%;background:var(--sr-sf);border:2px solid var(--sr-y)}
.sr-mk{display:inline-block;font:700 11.5px/1 Inter,system-ui,sans-serif;letter-spacing:.07em;text-transform:uppercase;color:var(--sr-y);margin-right:10px}
.sr-tl time{font-size:13px;color:var(--sr-mu)}
.sr-tl p{margin:4px 0 2px!important;font-size:15.5px!important;line-height:1.45!important}
.sr-ms{font-size:12.5px;color:var(--sr-mu)}
.sr-loc .bng-loc{margin:0}
@media(max-width:980px){.sr-grid{display:block}.sr-side{position:static;margin-top:8px}}
@media(max-width:520px){.sr-sec p{font-size:16.5px}.sr p.sr-lede{font-size:17.5px}.sr-card{padding:16px}.sr-dl>div{grid-template-columns:104px minmax(0,1fr)}}
@media print{.sr-side{position:static}}
.sr2 .sr-sec{margin:0 0 26px}.sr2 .sr-sec+.sr-sec{border-top:1px solid var(--sr-ln);padding-top:22px}
.sr-num{display:inline-flex;align-items:center;justify-content:center;min-width:22px;height:22px;border-radius:50%;border:1.5px solid var(--sr-y);font:700 12px/1 Inter,system-ui,sans-serif;letter-spacing:0;margin-right:2px}
.sr-bline{background:var(--sr-sf);border-radius:18px;box-shadow:var(--sr-sh);padding:16px 18px;margin:0 0 22px;border-left:4px solid var(--sr-y)}
.sr-bline-top{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-bottom:8px}.sr-bline-top .sr-k{margin:0!important}
.sr-risk{display:inline-flex;align-items:center;gap:7px;font:700 12.5px/1 Inter,system-ui,sans-serif;letter-spacing:.06em;text-transform:uppercase;border:1px solid var(--sr-ln);border-radius:999px;padding:6px 11px;color:var(--sr-ink)}
.sr-dot{width:9px;height:9px;border-radius:50%;background:var(--rc)}
.sr p.sr-bline-p{font-size:18px;line-height:1.5;font-weight:600;color:var(--sr-ink);margin:0}
.sr p.sr-auto{font-size:13px;line-height:1.45;color:var(--sr-mu);margin:8px 0 0}
.sr-ul,.sr-ol{margin:0 0 12px;padding-left:20px}.sr-ul li,.sr-ol li{font-size:16px;line-height:1.55;color:var(--sr-ink2);margin:0 0 7px;overflow-wrap:anywhere}
.sr-ul b{color:var(--sr-ink)}.sr p.sr-rel{font-size:14px;color:var(--sr-mu)}
.sr-meter{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin:2px 0 12px;max-width:420px}
.sr-m{text-align:center;font:700 12px/1 Inter,system-ui,sans-serif;letter-spacing:.06em;text-transform:uppercase;padding:9px 0;border-radius:8px;background:color-mix(in srgb,var(--sr-ln) 60%,transparent);color:var(--sr-mu)}
.sr-m.on{background:var(--rc);color:#111}
.sr-if{display:grid;grid-template-columns:1fr 1fr;gap:12px}.sr-if>div{background:var(--sr-sf);box-shadow:var(--sr-sh);border-radius:14px;padding:12px 14px}
.sr-if .sr-h3{margin:0 0 6px;font-size:15px}.sr-if p{font-size:15.5px!important;margin:0!important}
.sr-snapfig{margin:14px 0 0;background:var(--sr-sf);box-shadow:var(--sr-sh);border-radius:14px;padding:12px 14px}.sr-snapfig .sr-h3{margin:0 0 6px;font-size:14.5px}
.sr-snap{display:block;width:100%;max-width:560px;height:auto;color:var(--sr-ink)}.sr-snap-ax{display:flex;justify-content:space-between;max-width:560px;font:700 11px/1 Inter,system-ui,sans-serif;letter-spacing:.06em;text-transform:uppercase;color:var(--sr-mu);margin-top:6px}
.sr-stats{list-style:none;margin:8px 0 0;padding:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(104px,1fr));gap:8px}
.sr-stats li{display:flex;flex-direction:column;gap:2px;border-top:1px solid var(--sr-ln);padding-top:6px}.sr-stats b{font:700 18px/1.1 Inter,system-ui,sans-serif;color:var(--sr-ink)}.sr-stats span{font-size:12px;color:var(--sr-mu);line-height:1.3}
.sr-share{display:grid;grid-template-columns:minmax(0,42%) minmax(0,1fr);gap:0;border-radius:14px;overflow:hidden;background:var(--sr-sf);box-shadow:var(--sr-sh);margin:0 0 24px;text-decoration:none!important;color:var(--sr-ink)!important}
.sr-share img{width:100%;height:100%;min-height:120px;max-height:220px;object-fit:cover;display:block}
.sr-share-b{display:flex;flex-direction:column;gap:6px;padding:12px 14px;min-width:0}.sr-share-s{font:700 11.5px/1 Inter,system-ui,sans-serif;letter-spacing:.07em;text-transform:uppercase;color:var(--sr-y)}
.sr-share-t{font-size:15px;line-height:1.4;font-weight:600;overflow-wrap:anywhere}
.sr-more{margin:0 0 26px;border-top:1px solid var(--sr-ln);padding-top:14px}.sr-more summary{cursor:pointer;display:flex;align-items:center;gap:8px;font:700 13px/1.2 Inter,system-ui,sans-serif;letter-spacing:.09em;text-transform:uppercase;color:var(--sr-y);list-style:none}
.sr-more summary::-webkit-details-marker{display:none}.sr-more[open] summary{margin-bottom:14px}
.sr2 .sr-fig.sr-lead{margin-bottom:24px}.sr2 .sr-fig img{max-height:420px}
@media(max-width:600px){.sr-if{grid-template-columns:1fr}.sr-share{grid-template-columns:1fr}.sr-share img{max-height:200px}.sr p.sr-bline-p{font-size:17px}.sr-ul li,.sr-ol li{font-size:15.5px}}

"""
