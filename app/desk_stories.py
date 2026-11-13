"""Desk stories (t1330u): editor-written story pages for sourced, scheduled events the scanner has no cluster for yet
(first one: the FEMA/FCC nationwide Emergency Alert System test on Nov. 17, 2026).

Data: data/desk_stories.json (committed with the code; a signed data push of the same path can update it, see render_rules
SYNC_DIRS "data"). One entry per 16-hex cluster_id, so the story lives at /wire/<cluster_id> like every scanner story.
  - rank/score: what scanner.rebuild_cluster gives the listed official reports (scoring itself is never changed here).
  - brief: the 7-part desk brief, same fields as story_reports desk/briefs.json. It is only a fallback: when the pushed
    data/story_reports.json carries a note for this id, that note wins (story_report.render).
  - sections: the long-form breakdown shown under the brief. Inline links use [text](url); urls must be https:// or /path.
  - notice: optional homepage featured notice shown only between show_from and show_until (UTC ISO). Since Nov 13 it is the
    green card in position 2 of the top row (feature_card -> /api/apple/home "feature"); the block under the first group of
    widgets (notice_html) is off unless BN_DESK_NOTICE_BLOCK=1.
Read-only: never writes anything, never opens blackout.db, never touches scanner.py scoring, push.py, jets.py or config.json.
Every public function fails closed (returns None / "") so a bad file can never take a page down. Off with BN_DESK_STORIES=0.
"""
import html, json, os, re, time
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
PATH = os.environ.get("BN_DESK_STORIES_FILE", os.path.join(BASE, "data", "desk_stories.json"))
CID = re.compile(r"^[0-9a-f]{16}$")
E = lambda s: html.escape(str(s if s is not None else ""), quote=True)
_C = {"mt": None, "v": {}}
NOTE_KEYS = ("headline", "why_it_matters", "what_happened", "analysis", "pattern", "rank_why", "risk", "risk_why", "if_true",
             "if_false", "what_to_do", "confidence", "confidence_why")
BANNED = re.compile(r"\b(?:un)?verified\b|\bverif(?:y|ies|ying)\b|\bfirst to\b|\bbefore the news\b|\banniversar|\bbreaking\b|\btoday in history\b", re.I)

def enabled():
    return os.environ.get("BN_DESK_STORIES", "1") != "0"

def _load():
    if not enabled(): return {}
    try: mt = os.path.getmtime(PATH)
    except OSError: return {}
    if _C["mt"] != mt:
        try:
            with open(PATH, encoding="utf-8") as fh: d = json.load(fh)
            st = d.get("stories") if isinstance(d, dict) else None
            _C["v"] = {k: v for k, v in (st or {}).items() if CID.match(str(k)) and isinstance(v, dict) and v.get("title")}
        except Exception:
            _C["v"] = {}
        _C["mt"] = mt
    return _C["v"]

def get(cid):
    return _load().get(cid) if CID.match(str(cid or "")) else None

def ids():
    return sorted(_load())

def cluster(cid):
    """(cluster_row, report_rows) shaped like story.load() returns from blackout.db, or (None, [])."""
    s = get(cid)
    if not s: return None, []
    rows = []
    for a in s.get("reports") or []:
        u = a.get("source_url") or ""
        if not (isinstance(a, dict) and a.get("title") and re.match(r"^https://", u)): continue
        rows.append({"source": a.get("source") or "", "family": a.get("family") or "", "title": a["title"], "source_url": u,
                     "first_seen": a.get("first_seen") or "", "official": 1 if a.get("official") else 0, "location": s.get("location")})
    rows.sort(key=lambda a: (a["first_seen"], -a["official"]))
    fams = list(dict.fromkeys(s.get("families") or [a["family"] for a in rows if a["family"]]))
    rank = max(0, min(10, int(s.get("rank") or 0)))
    r = {"cluster_id": cid, "title": s["title"], "category": s.get("category") or "other", "location": s.get("location") or "",
         "lat": None, "lon": None, "event_time": s.get("event_time"), "first_seen": s.get("first_seen") or (rows[0]["first_seen"] if rows else ""),
         "updated": s.get("updated") or "", "score": int(s.get("score") or 0), "confidence": s.get("confidence") or "",
         "n_items": len(rows), "n_families": len(fams), "families": ",".join(fams), "links": json.dumps([{"source": a["source"], "url": a["source_url"]} for a in rows]),
         "watchlist": 0, "brief": None, "high_at": None, "rising": 0, "mentions_3h": 0, "eff_families": len(fams), "rank": rank,
         "pushed_at": None, "desk_story": True}
    return r, rows

def note(cid):
    """Fallback 7-part brief in the story_reports note format, or None. Same word rules as the box builder."""
    s = get(cid); b = (s or {}).get("brief")
    if not isinstance(b, dict) or not b.get("what_happened"): return None
    srcs = [u for u in (b.get("sources") or []) if isinstance(u, str) and re.match(r"^https?://[^\s<>\"]+$", u)]
    if not srcs: return None
    n = {}
    for k in NOTE_KEYS:
        v = b.get(k) or ""
        if k not in ("risk", "confidence"):
            v = " ".join(x for x in re.split(r"(?<=[.!?])\s+", str(v)) if x and not BANNED.search(x))
        n[k] = v
    n["risk"] = b.get("risk") if b.get("risk") in ("Low", "Medium", "High") else ""
    n["confidence"] = b.get("confidence") if b.get("confidence") in ("High", "Medium", "Low") else ""
    n["trajectory"] = ""
    n["sources"] = [{"url": u, "domain": re.sub(r"^www\.", "", u.split("/")[2].lower())} for u in srcs[:8]]
    n.update(generated_at=b.get("written_at") or "", edition="BLACKOUT.NETWORK desk brief", desk=True)
    return n

# ---------------------------------------------------------------- inline text
_LINK = re.compile(r"\[([^\[\]]{1,200})\]\(((?:https://|/)[^\s()<>\"]{0,400})\)")
def inline(t):
    """Escape text and turn [text](url) into links. External links open in a new tab."""
    out, i = [], 0
    for m in _LINK.finditer(t or ""):
        out.append(E(t[i:m.start()]))
        u = m.group(2)
        ext = u.startswith("https://")
        out.append(f'<a href="{E(u)}"' + (' target="_blank" rel="noopener"' if ext else "") + f'>{E(m.group(1))}</a>')
        i = m.end()
    out.append(E((t or "")[i:]))
    return "".join(out)

# ---------------------------------------------------------------- graphics (built from the FCC report numbers, no external images)
TESTS = [  # year, received %, relayed %, note  (FCC PSHSB nationwide test reports)
    ("2016", 95.4, 85.8, ""), ("2017", 95.8, 91.9, ""), ("2018", 95.7, 92.1, ""),
    ("2019", 82.5, 79.8, "broadcast only"), ("2021", 89.3, 87.1, "broadcast only"), ("2023", 96.6, 93.6, "")]

def chart_tests(credit=""):
    W, H, L, B, T = 640, 300, 44, 238, 30
    lo, hi = 70.0, 100.0
    y = lambda v: B - (v - lo) / (hi - lo) * (B - T)
    n = len(TESTS); slot = (W - L - 16) / n; bw = slot * 0.30
    g = []
    for v in (70, 80, 90, 100):
        g.append(f'<line x1="{L}" y1="{y(v):.1f}" x2="{W - 8}" y2="{y(v):.1f}" class="ds-grid"/><text x="{L - 8}" y="{y(v) + 4:.1f}" text-anchor="end" class="ds-ax">{v}%</text>')
    for i, (yr, rc, rl, nt) in enumerate(TESTS):
        x0 = L + i * slot + slot * 0.18
        g.append(f'<rect x="{x0:.1f}" y="{y(rc):.1f}" width="{bw:.1f}" height="{B - y(rc):.1f}" rx="3" class="ds-b1"><title>{yr}: {rc}% received</title></rect>')
        g.append(f'<rect x="{x0 + bw + 4:.1f}" y="{y(rl):.1f}" width="{bw:.1f}" height="{B - y(rl):.1f}" rx="3" class="ds-b2"><title>{yr}: {rl}% relayed</title></rect>')
        g.append(f'<text x="{x0 + bw / 2:.1f}" y="{y(rc) - 6:.1f}" text-anchor="middle" class="ds-v">{rc:g}</text>')
        g.append(f'<text x="{x0 + bw * 1.5 + 4:.1f}" y="{y(rl) - 6:.1f}" text-anchor="middle" class="ds-v">{rl:g}</text>')
        g.append(f'<text x="{x0 + bw + 2:.1f}" y="{B + 20}" text-anchor="middle" class="ds-yr">{yr}</text>')
        if nt: g.append(f'<text x="{x0 + bw + 2:.1f}" y="{B + 36}" text-anchor="middle" class="ds-ax">{nt}</text>')
    svg = (f'<svg class="ds-svg" viewBox="0 0 {W} {H}" role="img" aria-labelledby="ds_t1 ds_d1"><title id="ds_t1">Nationwide EAS tests: share of stations and providers that received and relayed the alert</title>'
           f'<desc id="ds_d1">' + "; ".join(f"{a}: {b}% received, {c}% relayed" for a, b, c, _ in TESTS) + '. Scale starts at 70%.</desc>' + "".join(g) + '</svg>')
    leg = '<p class="ds-leg"><span class="ds-k ds-k1"></span>Received the alert <span class="ds-k ds-k2"></span>Relayed it to the public <span class="ds-mu">Scale starts at 70%. 2011 used a different method and is not comparable; the Nov. 17, 2026 results come later.</span></p>'
    return (f'<figure class="sr-fig ds-fig"><figcaption class="ds-cap"><b>How past nationwide tests went</b></figcaption>{svg}{leg}'
            f'<figcaption><span class="sr-cr">{E(credit or "Graphic: BLACKOUT.NETWORK, built from FCC nationwide EAS test reports.")} Sources: '
            '<a href="https://docs.fcc.gov/public/attachments/DOC-350223A1.pdf" target="_blank" rel="noopener">2017</a>, '
            '<a href="https://docs.fcc.gov/public/attachments/DOC-356902A1.pdf" target="_blank" rel="noopener">2018</a>, '
            '<a href="https://docs.fcc.gov/public/attachments/DOC-378861A1.pdf" target="_blank" rel="noopener">2021</a>, '
            '<a href="https://docs.fcc.gov/public/attachments/DOC-403500A1.pdf" target="_blank" rel="noopener">2023</a> reports (the 2016 and 2019 figures are the comparisons given in the 2017 and 2021 reports).</span></figcaption></figure>')

def chart_chain():
    """Alert path diagram: FEMA IPAWS -> CAP over the internet, and the broadcast daisy chain via PEP stations (FCC/FEMA descriptions)."""
    box = lambda x, y, w, t1, t2, cls="ds-n": (f'<rect x="{x}" y="{y}" width="{w}" height="54" rx="10" class="{cls}"/>'
                                                f'<text x="{x + w / 2}" y="{y + 23}" text-anchor="middle" class="ds-nt">{t1}</text>'
                                                f'<text x="{x + w / 2}" y="{y + 41}" text-anchor="middle" class="ds-ns">{t2}</text>')
    arr = lambda x1, y1, x2, y2, cls="ds-a": f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" class="{cls}" marker-end="url(#ds_ah)"/>'
    p = ['<defs><marker id="ds_ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" class="ds-ah"/></marker></defs>',
         box(10, 118, 150, "FEMA", "IPAWS, sends the test"),
         box(220, 30, 190, "IPAWS-OPEN feed", "CAP 1.2 message, internet"),
         box(220, 206, 190, "PEP stations (77)", "satellite link, generators"),
         box(220, 290, 190, "Local Primary stations", "monitor the PEPs"),
         box(470, 118, 160, "Every EAS participant", "radio, TV, cable, satellite", "ds-n ds-n2"),
         box(470, 250, 160, "You", "TV and radio, ~1 minute", "ds-n ds-n3"),
         arr(160, 135, 218, 64), arr(160, 160, 218, 226),
         arr(410, 57, 468, 132), arr(315, 260, 315, 288), arr(410, 316, 468, 160, "ds-a ds-a2"),
         arr(550, 172, 550, 248),
         '<text x="424" y="50" class="ds-ax">polls the feed</text>',
         '<text x="330" y="282" class="ds-ax">over the air</text>',
         '<text x="320" y="374" text-anchor="middle" class="ds-ax">Each participant monitors two sources.</text>',
         '<text x="320" y="392" text-anchor="middle" class="ds-ax">Alerts relayed over the air lose the CAP extras (clean audio, Spanish).</text>']
    svg = ('<svg class="ds-svg ds-chain" viewBox="0 0 640 400" role="img" aria-labelledby="ds_t2 ds_d2"><title id="ds_t2">How a nationwide EAS alert travels</title>'
           '<desc id="ds_d2">FEMA sends the alert through IPAWS. Stations get the CAP version by polling the IPAWS-OPEN internet feed, or over the air through the daisy chain: '
           'FEMA to Primary Entry Point stations by satellite, then Local Primary stations, then every other participant, then the public.</desc>' + "".join(p) + '</svg>')
    flow = ('<ol class="ds-flow">'
            '<li><b>FEMA</b> sends the test through IPAWS.</li>'
            '<li><b>Internet path:</b> the IPAWS-OPEN feed carries the CAP 1.2 message; stations\' equipment polls it.</li>'
            '<li><b>Broadcast path:</b> 77 PEP stations (satellite link, generators) air it; Local Primary stations pick it up and pass it on.</li>'
            '<li><b>Every EAS participant</b> (radio, TV, cable, satellite) relays it. Each monitors two sources.</li>'
            '<li><b>You</b> see or hear it on TV and radio for about a minute. Alerts relayed over the air lose the CAP extras (clean audio, Spanish).</li></ol>')
    return ('<figure class="sr-fig ds-fig"><figcaption class="ds-cap"><b>How the alert travels</b></figcaption>' + svg + flow +
            '<figcaption><span class="sr-cr">Graphic: BLACKOUT.NETWORK, based on the '
            '<a href="https://docs.fcc.gov/public/attachments/DOC-403500A1.pdf" target="_blank" rel="noopener">FCC 2023 test report</a> and '
            '<a href="https://www.fema.gov/emergency-managers/practitioners/integrated-public-alert-warning-system/national-public-warning-system" target="_blank" rel="noopener">FEMA\'s National Public Warning System page</a>.</span></figcaption></figure>')

def chart_timeline(s):
    """Dated timeline graphic from the story's own sourced "timeline" list ([label, text], each naming its outlet). '' when empty."""
    ev = [x for x in (s.get("timeline") or []) if isinstance(x, list) and len(x) == 2 and x[0] and x[1]][:10]
    if not ev: return ""
    W, R = 640, 46; H = 24 + R * len(ev)
    g = [f'<line x1="132" y1="18" x2="132" y2="{H - 14}" class="ds-grid"/>']
    for i, (a, b) in enumerate(ev):
        y = 30 + i * R; last = i == len(ev) - 1
        g.append(f'<circle cx="132" cy="{y - 5}" r="6" class="ds-n {"ds-n3" if last else "ds-n2"}"/>')
        g.append(f'<text x="118" y="{y}" text-anchor="end" class="ds-yr">{E(a)}</text>')
        g.append(f'<text x="148" y="{y}" class="ds-ns" style="font-size:13px">{E(b)}</text>')
    svg = (f'<svg class="ds-svg" viewBox="0 0 {W} {H}" role="img" aria-labelledby="ds_tt ds_td"><title id="ds_tt">Timeline</title>'
           f'<desc id="ds_td">' + "; ".join(f"{E(a)}: {E(b)}" for a, b in ev) + '</desc>' + "".join(g) + '</svg>')
    flow = '<ol class="ds-flow">' + "".join(f'<li><b>{E(a)}.</b> {E(b)}</li>' for a, b in ev) + '</ol>'
    return (f'<figure class="sr-fig ds-fig"><figcaption class="ds-cap"><b>Timeline</b></figcaption><div class="ds-chain">{svg}</div>{flow}'
            f'<figcaption><span class="sr-cr">{E(s.get("figure_credit") or "Graphic: BLACKOUT.NETWORK, built from the sources listed below.")}</span></figcaption></figure>')

FIGS = {"tests": lambda s: chart_tests(s.get("figure_credit")), "chain": lambda s: chart_chain(), "timeline": chart_timeline,
        "none": lambda s: ""}

def lead_html(cid):
    """Lead graphic for the brief (used by story_report when the story has no rights-cleared photo): the alert-path diagram."""
    s = get(cid)
    if not s: return ""
    try:
        k = s.get("lead_figure") or "chain"   # Nov 13: per-story lead graphic (the EAS story keeps the alert-path diagram)
        return FIGS[k](s) if k in FIGS else ""
    except Exception: return ""

CSS = """
.ds{margin:6px 0 28px}.ds-sec{margin:0 0 26px;border-top:1px solid var(--sr-ln,#2A2D33);padding-top:22px}
.ds-sec h2{font:700 21px/1.3 Inter,system-ui,sans-serif;margin:0 0 12px;color:var(--sr-ink,#e6e9ee)}
.ds-sec p,.ds-sec li{font-size:17px;line-height:1.65;color:var(--sr-ink2,#D2D2D7);overflow-wrap:anywhere}.ds-sec p{margin:0 0 14px}
.ds-sec ul{margin:0 0 14px;padding-left:20px}.ds-sec li{margin:0 0 9px}
.ds-an{background:var(--sr-sf,#16181C);box-shadow:var(--sr-sh,0 0 0 1px #23262B);border-radius:18px;padding:18px 20px;border-top:0}
.ds-lab{display:inline-block;font:700 11.5px/1 Inter,system-ui,sans-serif;letter-spacing:.08em;text-transform:uppercase;border:1px solid var(--sr-ln,#2A2D33);border-radius:999px;padding:6px 10px;margin:0 0 10px;color:var(--sr-ink,#e6e9ee)}
.ds-sec p.ds-anote{font-size:14px;color:var(--sr-mu,#8a94a3)}
.ds-scen{list-style:none;padding:0!important;margin:4px 0 16px!important;display:grid;gap:10px}
.ds-scen li{margin:0!important;border-left:3px solid var(--sr-ln,#2A2D33);padding:2px 0 2px 12px}.ds-scen b{color:var(--sr-ink,#e6e9ee)}
.ds-fig{background:var(--sr-sf,#16181C);box-shadow:var(--sr-sh,0 0 0 1px #23262B);border-radius:14px;padding:14px 16px}
.ds-svg{display:block;width:100%;height:auto;max-width:680px}.ds-cap{margin:0 0 8px!important;color:var(--sr-ink,#e6e9ee)!important;font-size:15px!important}
.ds-grid{stroke:var(--sr-ln,#2A2D33);stroke-width:1}.ds-ax{fill:var(--sr-mu,#8a94a3);font:500 12px Inter,system-ui,sans-serif}
.ds-yr{fill:var(--sr-ink,#e6e9ee);font:700 13px Inter,system-ui,sans-serif}.ds-v{fill:var(--sr-ink2,#D2D2D7);font:600 11.5px Inter,system-ui,sans-serif}
.ds-b1{fill:#6DB2B5}.ds-b2{fill:#B8B7FE}html[data-theme="light"] .ds-b1{fill:#1F6F73}html[data-theme="light"] .ds-b2{fill:#5B4BC4}
.ds-leg{font-size:13px!important;color:var(--sr-ink2,#D2D2D7)!important;margin:8px 0 4px!important;display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px}
.ds-k{display:inline-block;width:12px;height:12px;border-radius:3px}.ds-k1{background:#6DB2B5}.ds-k2{background:#B8B7FE}
html[data-theme="light"] .ds-k1{background:#1F6F73}html[data-theme="light"] .ds-k2{background:#5B4BC4}.ds-mu{color:var(--sr-mu,#8a94a3)}
.ds-n{fill:var(--sr-bg,transparent);stroke:var(--sr-ln,#3a3f47);stroke-width:1.5}.ds-n2{stroke:#6DB2B5}.ds-n3{stroke:#B8B7FE}
.ds-nt{fill:var(--sr-ink,#e6e9ee);font:700 14px Inter,system-ui,sans-serif}.ds-ns{fill:var(--sr-mu,#8a94a3);font:500 11.5px Inter,system-ui,sans-serif}
.ds-a{stroke:var(--sr-ink2,#D2D2D7);stroke-width:1.6}.ds-a2{stroke-dasharray:5 4}.ds-ah{fill:var(--sr-ink2,#D2D2D7)}
.ds-flow{display:none;margin:4px 0 6px;padding-left:20px}.ds-flow li{font-size:15px;line-height:1.5;color:var(--sr-ink2,#D2D2D7);margin:0 0 6px}.ds-flow b{color:var(--sr-ink,#e6e9ee)}
@media(max-width:600px){.ds-chain{display:none}.ds-flow{display:block}}
@media(max-width:520px){.ds-sec p,.ds-sec li{font-size:16.5px}.ds-an{padding:16px}}
"""

def sections_html(cid):
    """Long-form breakdown under the brief, or ''. The analysis section carries a visible 'Our analysis' label."""
    s = get(cid)
    if not s or not isinstance(s.get("sections"), list): return ""
    out = []
    try:
        for sec in s["sections"]:
            if not isinstance(sec, dict) or not sec.get("h"): continue
            sid = re.sub(r"[^a-z0-9_]", "", str(sec.get("id") or "x"))[:24] or "x"
            body = []
            if sec.get("label"): body.append(f'<span class="ds-lab">{E(sec["label"])}</span>')
            body.append(f'<h2 id="ds_{sid}">{E(sec["h"])}</h2>')
            if sec.get("note"): body.append(f'<p class="ds-anote">{E(sec["note"])}</p>')
            for b in sec.get("blocks") or []:
                if not isinstance(b, dict): continue
                if b.get("p"): body.append(f'<p>{inline(b["p"])}</p>')
                elif b.get("ul"): body.append('<ul>' + "".join(f'<li>{inline(x)}</li>' for x in b["ul"] if isinstance(x, str)) + '</ul>')
                elif b.get("scen"): body.append('<ul class="ds-scen">' + "".join(f'<li><b>{E(x[0])}.</b> {inline(x[1])}</li>' for x in b["scen"] if isinstance(x, list) and len(x) == 2) + '</ul>')
                elif b.get("figure") in FIGS: body.append(FIGS[b["figure"]](s))
            cls = "ds-sec ds-an" if sec.get("label") else "ds-sec"
            out.append(f'<section class="{cls}" aria-labelledby="ds_{sid}">' + "".join(body) + '</section>')
    except Exception:
        return ""
    if not out: return ""
    return (f'<style>{CSS}</style><article class="ds" id="breakdown" aria-label="Full breakdown">'
            '<p class="sr-k" style="margin:0 0 6px">Full breakdown and analysis</p>' + "".join(out) + '</article>')

# ---------------------------------------------------------------- homepage featured notice
NOTICE_CSS = """
.bna-notice{margin:0 auto 40px}.bna-notice a.bna-nt{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:14px 18px;align-items:center;
 background:var(--a-sf,#16181C);border-radius:var(--a-r,18px);box-shadow:var(--a-sh,0 0 0 1px #23262B);padding:18px 22px;text-decoration:none!important;color:var(--a-ink,#F5F5F7)!important;border-left:4px solid #3fa66a}
.bna-nt-ic{width:44px;height:44px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:rgba(63,166,106,.16);color:#3fa66a}
.bna-nt-ic svg{width:24px;height:24px}
.bna-nt-k{display:flex;flex-wrap:wrap;gap:8px;align-items:center;font:700 11.5px/1 Inter,system-ui,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--a-ink2,#86868B);margin:0 0 6px}
.bna-nt-r{border:1px solid rgba(63,166,106,.6);color:#3fa66a;border-radius:999px;padding:4px 8px}
.bna-nt h3{margin:0 0 4px;font-size:19px;line-height:1.3;font-weight:600;letter-spacing:-.01em}.bna-nt p{margin:0;font-size:15px;line-height:1.5;color:var(--a-ink2,#A1A1A6)}
.bna-nt-go{color:var(--a-lk,#FFC21A);font-weight:600;font-size:15px;white-space:nowrap;min-height:44px;display:flex;align-items:center}.bna-nt-go:after{content:"\\00a0\\203A"}
html[data-theme="light"] .bna-nt-r,html[data-theme="light"] .bna-nt-ic{color:#1d7a46}html[data-theme="light"] .bna-nt p{color:#515154}
html[data-theme="light"] .bna-nt-go{text-decoration:underline;text-decoration-color:var(--a-y,#FFC21A);text-decoration-thickness:2px;text-underline-offset:4px}
@media(max-width:640px){.bna-notice a.bna-nt{grid-template-columns:minmax(0,1fr);gap:10px;padding:16px 16px 10px}.bna-nt-ic{display:none}.bna-nt h3{font-size:17px}}
"""
_ICON = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
         '<path d="M4 9v6h4l5 4V5L8 9H4z"/><path d="M16.5 8.5a5 5 0 0 1 0 7"/><path d="M19 6a8.5 8.5 0 0 1 0 12"/></svg>')

def _ts(iso):
    try: return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone(timezone.utc).timestamp()
    except Exception: return None

def active_notices(now=None):
    now = time.time() if now is None else now
    out = []
    for cid, s in _load().items():
        n = s.get("notice")
        if not isinstance(n, dict) or not n.get("title"): continue
        a, b = _ts(n.get("show_from")), _ts(n.get("show_until"))
        if a is None or b is None or not (a <= now < b): continue
        out.append((a, cid, s, n))
    return [x[1:] for x in sorted(out, reverse=True)]

def feature_card(now=None):
    """Newest active notice as data for the homepage top row (Matt, Nov 13: "Put that alert in the 2nd box and make it green").
    Same show_from/show_until window as the notice. The link has no #fragment so the story opens at the top. None when off/expired."""
    try:
        act = active_notices(now)
        if not act: return None
        cid, s, n = act[0]
        return {"cluster_id": cid, "href": f"/wire/{cid}", "title": str(n["title"]), "text": str(n.get("text") or ""),
                "kicker": str(n.get("kicker") or "Featured notice"), "tag": str(n.get("tag") or ""),
                "link_text": str(n.get("link_text") or "Read more"), "rank": max(0, min(10, int(s.get("rank") or 0))),
                "show_until": str(n.get("show_until") or "")}
    except Exception:
        return None

# ---------------------------------------------------------------- homepage pinned story (card 1 of the top row)
def pins_enabled():
    return os.environ.get("BN_HOME_PIN", "1") != "0"

def pin_cards(now=None, limit=3):
    """Every active pinned desk story, in card order (Matt, Nov 13 4:39 PM ET: the FAA nationwide ground stop leads, the Hamas
    story moves to card 2, the green EAS card follows). Sort: pin.order ascending (default 50), then newest pin.from first.
    Same window rule as before (pin.from <= now < pin.until, UTC ISO), titles verbatim, kill switch BN_HOME_PIN=0. [] on error."""
    if not pins_enabled(): return []
    try:
        now = time.time() if now is None else now
        act = []
        for cid, s in _load().items():
            p = s.get("pin")
            if not isinstance(p, dict) or not (p.get("title") or s.get("title")): continue
            a, b = _ts(p.get("from")), _ts(p.get("until"))
            if a is None or b is None or not (a <= now < b): continue
            try: o = int(p.get("order", 50))
            except Exception: o = 50
            act.append((o, -a, cid, s, p))
        act.sort(key=lambda x: (x[0], x[1], x[2]))
        return [{"cluster_id": cid, "href": f"/wire/{cid}", "title": str(p.get("title") or s["title"]), "text": str(p.get("text") or ""),
                 "kicker": str(p.get("kicker") or "Featured story"), "tag": str(p.get("tag") or ""),
                 "link_text": str(p.get("link_text") or "Read the full story"), "rank": max(0, min(10, int(s.get("rank") or 0))),
                 "show_until": str(p.get("until") or ""), "pinned": True} for _, _, cid, s, p in act[:max(1, int(limit))]]
    except Exception:
        return []

def pin_card(now=None):
    """Matt, Nov 13 (t1349u): the desk story pinned as card 1 of the homepage top row (the first of pin_cards), or None when off,
    expired or on any error. The green featured card (feature_card) follows the pinned cards."""
    try:
        p = pin_cards(now)
        return p[0] if p else None
    except Exception:
        return None

def notice_html(now=None):
    """Homepage featured notice (newest active one), or ''. Links to the story page with no #fragment so it opens at the top."""
    try:
        act = active_notices(now)
        if not act: return ""
        cid, s, n = act[0]
        rank = max(0, min(10, int(s.get("rank") or 0))); tag = f' · {E(n["tag"])}' if n.get("tag") else ""
        return (f'<style>{NOTICE_CSS}</style><div class="bna-wrap bna-notice" data-desk="{E(cid)}" role="region" aria-label="{E(n.get("kicker") or "Featured notice")}">'
                f'<a class="bna-nt" href="/wire/{E(cid)}"><span class="bna-nt-ic">{_ICON}</span><span><span class="bna-nt-k">{E(n.get("kicker") or "Featured notice")}'
                f'<span class="bna-nt-r">Rank {rank}/10{tag}</span></span><h3>{E(n["title"])}</h3><p>{E(n.get("text") or "")}</p></span>'
                f'<span class="bna-nt-go">{E(n.get("link_text") or "Read more")}</span></a></div>')
    except Exception:
        return ""
