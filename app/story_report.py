"""Story report layer for /wire/<cluster_id> pages (story.py), Nov 12 2026 (t1276u).

Turns every story page linked from the homepage into a news report under the headline:
  What's happening   the analyst note's summary when the newsletter desk wrote one, else a factual summary built only from the
                     scanner's own fields (brief WHAT, location, times, source counts, latest report headline)
  Key facts          rank, category, place, times, sources, official sources, measured values from the scanner brief
  Graphics           reports-over-time bars and sources-reporting bars (SVG, drawn from the alerts rows already loaded)
  Our analysis       why it matters, analysis, what to watch, confidence (only from a sourced analyst note; dated to its brief)
  Key moments        first report, first official source, each new source family, latest report
  Images             only with clear rights, precomputed on the box (USGS ShakeMap, Wikimedia Commons free licenses)
Precomputed input: data/story_reports.json (tools/story_reports/build.py on the box, pushed with a signed one-file push).
No LLM, no network, no DB writes at request time. Every section is dropped, never padded, when its data is missing.
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

def render(cid, r, rows, rank, tname, title, what, loc, officials, eff, fams, locator=""):
    """Returns (html, dek_override). rows: deduped alerts in time order."""
    R = reports(); note = (R.get("notes") or {}).get(cid); imgs = [i for i in (R.get("images") or {}).get(cid) or [] if isinstance(i, dict)]
    what_b, bfacts = brief_facts(r.get("brief"))
    anchor = tokens(" ".join([title or "", what or "", what_b or "", (note or {}).get("headline") or ""]))
    # ---- What's happening
    if note and note.get("what_happened"):
        wh = f'<p class="sr-lede">{E(note["what_happened"])}</p>'
        dek = note.get("headline") or ""
    else:
        parts = []
        w = what_b or what
        if w and w.rstrip(". ") != (title or "").rstrip(". "): parts.append(w.rstrip(". ") + ".")
        n = len(rows)
        if n:
            src = f"{eff} independent source famil{'y' if eff == 1 else 'ies'}" if eff else "one source"
            parts.append(f"BLACKOUT.NETWORK has logged {n} report{'' if n == 1 else 's'} on this story from {src}"
                         + (f", including official sources ({', '.join(officials[:5])}{' and others' if len(officials) > 5 else ''})" if officials else "") + ".")
            last = next((a for a in reversed(rows) if _solid(a) and _relevant(a, anchor)), rows[-1])
            lt = txt(last.get("title")) if _solid(last) and _relevant(last, anchor) else ""
            if n > 1 and lt and (last.get("source") or ""):
                t = lt if len(lt) <= 180 else lt[:180].rsplit(" ", 1)[0].rstrip(" ,;:-–") + "…"
                parts.append(f"The latest report, from {last['source']} at {et(last.get('first_seen'), True)}, is headlined \u201c{t}{'' if re.search(r'[.!?…]$', t) else '.'}\u201d")
        wh = "".join(f"<p>{E(p)}</p>" for p in parts)
        dek = ""
    sec_what = (f'<section class="sr-sec" aria-labelledby="sr_what"><h2 class="sr-k" id="sr_what">{icon("news")}What\u2019s happening</h2>{wh}</section>' if wh else "")
    # ---- Key facts
    f = [("Rank", f"{rank}/10, {tname}")]
    if r.get("category"): f.append(("Category", CAT.get((r.get("category") or "").lower(), (r.get("category") or "").title())))
    if loc: f.append(("Where", loc))
    if r.get("event_time"): f.append(("Event time", et(r["event_time"], True)))
    if r.get("first_seen"): f.append(("Logged here since", et(r["first_seen"], True)))
    if r.get("updated"): f.append(("Last update", et(r["updated"], True)))
    fl = [("social media" if x.lower() == "social" else x) for x in fams]
    if eff: f.append(("Independent sources", f"{eff}" + (f" ({', '.join(fl[:3])}{', and others' if len(fl) > 3 else ''})" if fl else "")))
    f.append(("Official sources", (", ".join(officials[:5]) + (" and others" if len(officials) > 5 else "")) if officials else "None yet"))
    if rows: f.append(("Reports logged", str(len(rows))))
    f += bfacts
    facts = (f'<section class="sr-card" aria-labelledby="sr_facts"><h2 class="sr-k" id="sr_facts">{icon("facts")}Key facts</h2><dl class="sr-dl">'
             + "".join(f"<div><dt>{E(k)}</dt><dd>{E(v)}</dd></div>" for k, v in f) + "</dl></section>")
    # ---- Graphics
    g = chart_time(rows) + chart_sources(rows)
    graphics = f'<section class="sr-card sr-graphics" aria-label="Graphics">{g}</section>' if g else ""
    # ---- Our analysis (sourced note only)
    ana = ""
    if note and (note.get("why_it_matters") or note.get("analysis")):
        stale = (_dt(r.get("updated")) or datetime.min.replace(tzinfo=UTC)) > (_dt(note.get("generated_at")) or datetime.max.replace(tzinfo=UTC))
        lab = f'From the {E(note.get("edition") or "BLACKOUT.NETWORK brief")}, written {E(et(note.get("generated_at"), True))} from the sources listed below.'
        if stale: lab += " The story has had new reports since; the timeline below is current."
        b = [f'<p class="sr-asof">{lab}</p>']
        if note.get("why_it_matters"): b.append(f'<h3 class="sr-h3">Why it matters</h3><p class="sr-why">{E(note["why_it_matters"])}</p>')
        if note.get("analysis"): b.append(f'<h3 class="sr-h3">Analysis</h3><p>{E(note["analysis"])}</p>')
        if note.get("outlook"):
            tr = note.get("trajectory") or ""
            pill = (f'<span class="sr-traj">{icon(TRAJ_ICON[tr])}{E(tr)}</span>' if tr in TRAJ_ICON else "")
            b.append(f'<h3 class="sr-h3">{icon("watch")}What to watch {pill}</h3><p>{E(note["outlook"])}</p>')
        if note.get("confidence"):
            b.append(f'<h3 class="sr-h3">{icon("shield")}Confidence: {E(note["confidence"])}</h3>' + (f'<p>{E(note["confidence_why"])}</p>' if note.get("confidence_why") else ""))
        srcs = [s for s in note.get("sources") or [] if re.match(r"^https?://", s.get("url") or "")]
        if srcs:
            b.append(f'<h3 class="sr-h3">{icon("link")}Sources for this analysis</h3><ol class="sr-src">' + "".join(
                f'<li><a href="{E(s["url"])}" target="_blank" rel="noopener">{E(s.get("domain") or s["url"])}{icon("ext", "sr-i sr-i-s")}</a></li>' for s in srcs) + "</ol>")
        ana = (f'<section class="sr-sec sr-ana" aria-labelledby="sr_ana"><h2 class="sr-k" id="sr_ana">{icon("analysis")}BLACKOUT.NETWORK analysis</h2>' + "".join(b) + "</section>")
    # ---- Key moments
    km = moments(rows, anchor) if len(rows) >= 2 else []
    kmh = ""
    if km:
        li = []
        for lab, a in km:
            u = a.get("source_url") or ""; t = txt(a.get("title"))[:200]
            tl = f'<a href="{E(u)}" target="_blank" rel="noopener">{E(t)}</a>' if re.match(r"^https?://", u) else E(t)
            li.append(f'<li><span class="sr-mk">{E(lab)}</span><time datetime="{E(a.get("first_seen") or "")}">{E(et(a.get("first_seen"), True))}</time>'
                      f'<p>{tl}</p><span class="sr-ms">{E(a.get("source") or "")}{" · official source" if a.get("official") else ""}</span></li>')
        kmh = f'<section class="sr-sec" aria-labelledby="sr_km"><h2 class="sr-k" id="sr_km">{icon("clock")}Key moments</h2><ol class="sr-tl">{"".join(li)}</ol></section>'
    # ---- Images
    figs = [x for x in (figure(im, i == 0) for i, im in enumerate(imgs[:3])) if x]
    lead_fig = figs[0] if figs else ""; more_figs = figs[1:]
    gallery = (f'<section class="sr-sec" aria-labelledby="sr_img"><h2 class="sr-k" id="sr_img">{icon("image")}Images</h2><div class="sr-gal">{"".join(more_figs)}</div></section>' if more_figs else "")
    if not (sec_what or ana or km or figs): return "", dek
    main = sec_what + lead_fig + ana + kmh + gallery
    side = facts + (f'<div class="sr-loc">{locator}</div>' if locator else "") + graphics
    return (f'<style>{CSS}</style><article class="sr" aria-label="Story report"><div class="sr-grid"><div class="sr-main">{main}</div>'
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
@media(max-width:980px){.sr-grid{display:flex;flex-direction:column;gap:0}.sr-main,.sr-side{display:contents}
 .sr-sec,.sr-fig,.sr-card,.sr-loc{order:5;margin-bottom:22px}
 .sr-main>.sr-sec:first-child{order:1}.sr-lead{order:2}.sr-side>.sr-card:first-child{order:3}.sr-ana{order:4}.sr-graphics{order:6}.sr-loc{order:7}
 .sr-sec+.sr-sec{border-top:0;padding-top:0}.sr-side{position:static}}
@media(max-width:520px){.sr-sec p{font-size:16.5px}.sr p.sr-lede{font-size:17.5px}.sr-card{padding:16px}.sr-dl>div{grid-template-columns:104px minmax(0,1fr)}}
@media print{.sr-side{position:static}}
"""
