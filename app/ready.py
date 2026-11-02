"""/ready: Everyday Readiness, the five printable one-page guides (static/ready/NN-slug.pdf) on one indexable page.
The printed short link on every guide is blackout.network/ready. Intros are written from each PDF's own text; nothing else is claimed."""
import os, json
import site_page as S

PATH = "/ready"; SITE = S.SITE; BRAND = "BLACKOUT.NETWORK"
DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "ready")
TITLE = "Everyday Readiness Guides, Free PDFs"
DESC = ("Five free one-page printable guides: a 72-hour home kit, water at home, power outages, a family contact plan "
        "and first aid basics, each with a checklist.")

# Icons: 24px line icons, stroke currentColor (no emoji).
_I = {
    "kit": '<path d="M4 8h16v11a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1z"/><path d="M3 5h18v3H3z"/><path d="M10 12h4"/>',
    "water": '<path d="M12 3s6 6.4 6 11a6 6 0 0 1-12 0c0-4.6 6-11 6-11z"/>',
    "power": '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
    "family": '<circle cx="9" cy="8" r="3"/><circle cx="17" cy="9" r="2.5"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6"/><path d="M15 15.5c2.8-.6 6 1.2 6 4.5"/>',
    "aid": '<rect x="3" y="6" width="18" height="14" rx="2"/><path d="M9 6V4h6v2"/><path d="M12 10v6M9 13h6"/>',
    "down": '<path d="M12 4v11"/><path d="m7 10 5 5 5-5"/><path d="M5 20h14"/>',
}
def icon(k, cls="rd-ic"):
    return (f'<svg class="{cls}" aria-hidden="true" focusable="false" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{_I[k]}</svg>')

GUIDES = [
    {"id": "home-kit", "n": "01", "file": "01-72-hour-home-kit", "icon": "kit", "title": "Your 72-Hour Home Kit", "short": "Home kit",
     "intro": ["A few days of basics in one bin turns a storm or outage into an inconvenience you already planned for.",
               "The checklist starts with water at one gallon per person per day, shelf-stable food your household already eats, a flashlight with spare batteries, "
               "a battery or hand-crank radio with the NOAA weather band and a basic first aid kit, with a typical price beside each item.",
               "A four-step weekend plan gets it done in one store run."]},
    {"id": "water", "n": "02", "file": "02-water-at-home", "icon": "water", "title": "Water at Home, Sorted", "short": "Water",
     "intro": ["Taps can stop after a storm or a main break, and a little stored water keeps the house running calmly.",
               "The guide sets the target at one gallon per person per day for several days, plus extra for pets, and lists a food-grade refill container, "
               "unscented household bleach and a portable filter as backups.",
               "For treatment steps it sends you to Ready.gov's water page rather than reprinting them."]},
    {"id": "power", "n": "03", "file": "03-power-outage-readiness", "icon": "power", "title": "When the Lights Go Out", "short": "Power outage",
     "intro": ["Many outages are short, and a few things on hand make the wait comfortable instead of stressful.",
               "The list covers lanterns, charged power banks, a battery-powered carbon monoxide alarm, a fridge thermometer and a written plan for medical devices that need power.",
               "It carries Ready.gov's food rules: a closed fridge keeps food cold about 4 hours, a full freezer about 48, and generators run only outdoors, at least 20 feet from windows."]},
    {"id": "family", "n": "04", "file": "04-family-communication-plan", "icon": "family", "title": "Our Family Contact Plan", "short": "Family plan",
     "intro": ["When phones are busy or people are apart, a plan written down together tells each person who to call and where to meet.",
               "It walks through one out-of-area contact everyone can text, two meeting places and ICE contacts saved in each phone.",
               "The bottom of the page is a cut-out contact card, one per person, with lines to fill in."]},
    {"id": "first-aid", "n": "05", "file": "05-first-aid-and-medication-basics", "icon": "aid", "title": "First Aid and Medicine Basics", "short": "First aid",
     "intro": ["A stocked kit and a current medicine list make small injuries simpler and help anyone caring for your family.",
               "The checklist covers the kit itself, a written list of each person's medicines, doses and allergies, and what to ask your pharmacist about extra supply and refrigerated medicines.",
               "It ends with a pointer to a Red Cross first aid class."]},
]
RELATED = [("/preppers", "Preppers", "Kits, suppliers and checklists"), ("/grid", "Power grid", "Live US grid status and outages"),
           ("/weather", "Weather", "Official alerts and forecast"), ("/guides/medical.html", "First aid", "The full first aid guide"),
           ("/resources", "Local help", "Emergency services near you"), ("/newsletter", "Newsletter", "The free morning and evening brief")]

def _pages(f):
    try:
        with open(f, "rb") as fh: b = fh.read()
        import re
        n = len(re.findall(rb"/Type\s*/Page(?!s)", b)); return max(n, 1)
    except Exception: return 1

def _size(n): return f"{n / 1024:.0f} KB" if n < 1024 * 1024 else f"{n / 1048576:.1f} MB"

def guide_files():
    out = []
    for g in GUIDES:
        pdf = os.path.join(DIR, g["file"] + ".pdf")
        out.append({**g, "pdf": f"/static/ready/{g['file']}.pdf", "thumb": f"/static/ready/{g['file']}.webp",
                    "bytes": os.path.getsize(pdf), "pages": _pages(pdf)})
    return out

CSS = """
.rd{--rd-acc:#FFC21A;--rd-acc-ink:#0B0D10;--rd-red:#C8102E;--rd-card:var(--pn,#14181d);--rd-bd:var(--bd,#252b33);--rd-mu:var(--mu,#8b95a3)}
html[data-theme="light"] .rd{--rd-acc:#C97B00;--rd-acc-ink:#0B0D10;--rd-card:#ffffff;--rd-bd:#e4e1da;--rd-mu:#3a4250}
.rd h1{font-family:Montserrat,Inter,system-ui,sans-serif;font-weight:800;letter-spacing:-.02em;font-size:clamp(30px,4.6vw,48px);line-height:1.08;margin:.2em 0 .3em}
.rd .kick{font:700 12px/1.4 Inter,system-ui,sans-serif;letter-spacing:.14em;text-transform:uppercase;color:var(--rd-acc)}
.rd .dek{font-size:17px;line-height:1.6;max-width:62ch}
.rd-jump{position:sticky;top:0;z-index:5;display:flex;gap:8px;overflow-x:auto;padding:10px 0;margin:14px 0 6px;background:var(--bg,#0b0d10);border-bottom:1px solid var(--rd-bd)}
html[data-theme="light"] .rd-jump{background:#f6f7f9}
.rd-jump a{display:inline-flex;align-items:center;gap:6px;white-space:nowrap;padding:7px 12px;border:1px solid var(--rd-bd);border-radius:999px;color:inherit;text-decoration:none;font:600 14px/1 Inter,system-ui,sans-serif}
.rd-jump a:hover,.rd-jump a:focus-visible{border-color:var(--rd-acc);color:var(--rd-acc)}
.rd-jump .rd-ic{width:16px;height:16px;color:var(--rd-acc)}
.rd-g{display:grid;grid-template-columns:170px 1fr;gap:22px;align-items:start;padding:22px;margin:18px 0;border:1px solid var(--rd-bd);border-left:4px solid var(--rd-acc);border-radius:12px;background:var(--rd-card);scroll-margin-top:70px}
.rd-g img{width:170px;height:auto;aspect-ratio:340/440;border-radius:6px;border:1px solid var(--rd-bd);background:#fff;display:block}
.rd-g h2{font-family:Montserrat,Inter,system-ui,sans-serif;font-weight:700;font-size:clamp(21px,2.4vw,26px);margin:2px 0 8px;display:flex;align-items:center;gap:10px}
.rd-g h2 .rd-ic{color:var(--rd-acc);flex:none}
.rd-g .num{font:700 12px/1 Inter,system-ui,sans-serif;letter-spacing:.12em;color:var(--rd-mu)}
.rd-g p{margin:0 0 14px;line-height:1.6;max-width:64ch}
.rd-dl{display:inline-flex;align-items:center;gap:8px;padding:11px 16px;border-radius:10px;background:var(--rd-acc);color:var(--rd-acc-ink);font:700 15px/1 Inter,system-ui,sans-serif;text-decoration:none}
.rd-dl:hover,.rd-dl:focus-visible{filter:brightness(1.08);outline:2px solid var(--rd-acc);outline-offset:2px}
.rd-dl .rd-ic{width:18px;height:18px}
.rd-meta{display:block;margin-top:8px;font-size:13.5px;color:var(--rd-mu)}
.rd-rel{margin:30px 0 10px;padding-top:16px;border-top:1px solid var(--rd-bd)}
.rd-rel ul{list-style:none;padding:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:10px}
.rd-rel a{display:block;padding:12px 14px;border:1px solid var(--rd-bd);border-radius:10px;color:inherit;text-decoration:none}
.rd-rel a:hover,.rd-rel a:focus-visible{border-color:var(--rd-acc)}
.rd-rel b{display:block;color:var(--rd-acc);font-size:13px;letter-spacing:.04em}
@media (max-width:640px){.rd-g{grid-template-columns:1fr;padding:16px}.rd-g img{width:140px}}
@media (prefers-reduced-motion:no-preference){
 .rd-g{animation:rd-in .5s cubic-bezier(.2,.7,.2,1) both}
 .rd-g:nth-of-type(2){animation-delay:.06s}.rd-g:nth-of-type(3){animation-delay:.12s}.rd-g:nth-of-type(4){animation-delay:.18s}.rd-g:nth-of-type(5){animation-delay:.24s}
 @keyframes rd-in{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}
}
"""
# Consent-aware: window.bnTrack only sends once GA loaded with permission (see seo/ga4-events.md). GA4 enhanced measurement also logs
# the standard file_download for .pdf links; this adds which guide it was.
JS = ("<script>document.addEventListener('click',function(e){var a=e.target&&e.target.closest&&e.target.closest('a[data-guide]');"
      "if(a&&window.bnTrack)window.bnTrack('guide_download',{guide_id:a.getAttribute('data-guide'),file_name:a.getAttribute('data-file'),file_extension:'pdf'});});</script>")

def render():
    gs = guide_files()
    jump = '<nav class="rd-jump" aria-label="Guides on this page">' + "".join(
        f'<a href="#{g["id"]}">{icon(g["icon"])}{S.E(g["short"])}</a>' for g in gs) + '</nav>'
    secs = "".join(
        f'<section class="rd-g" id="{g["id"]}" aria-labelledby="{g["id"]}-h">'
        f'<a href="{g["pdf"]}" tabindex="-1" aria-hidden="true"><img src="{g["thumb"]}" loading="lazy" decoding="async" width="170" height="220" '
        f'alt="First page of the printable guide {S.E(g["title"])}"></a>'
        f'<div><span class="num">GUIDE {g["n"]}</span><h2 id="{g["id"]}-h">{icon(g["icon"])}{S.E(g["title"])}</h2>'
        + "".join(f'<p>{S.E(" ".join(g["intro"]))}</p>' for _ in [0])
        + f'<a class="rd-dl" href="{g["pdf"]}" data-guide="{g["id"]}" data-file="{g["file"]}.pdf" type="application/pdf">{icon("down")}Download PDF</a>'
        f'<span class="rd-meta">PDF, {_size(g["bytes"])}, {g["pages"]} page{"s" if g["pages"] != 1 else ""}, US Letter</span></div></section>'
        for g in gs)
    rel = ('<section class="rd-rel" aria-labelledby="rd-rel-h"><h2 id="rd-rel-h">More on BLACKOUT.NETWORK</h2><ul>'
           + "".join(f'<li><a href="{u}"><b>{S.E(h)}</b>{S.E(t)}</a></li>' for u, h, t in RELATED) + '</ul></section>')
    body = ('<div class="rd"><p class="kick">Everyday Readiness</p><h1>Everyday Readiness guides</h1>'
            '<p class="dek">Five one-page guides to print and keep: a checklist with typical prices, four steps for this weekend and trusted links on each. '
            'Free to download, print and share.</p>' + jump + secs + rel + '</div>'
            + f'<style>{CSS}</style>' + JS)
    org = {"@type": "Organization", "@id": SITE + "/#org", "name": BRAND, "url": SITE + "/"}
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "CollectionPage", "@id": SITE + PATH + "#page", "url": SITE + PATH, "name": TITLE, "description": DESC, "inLanguage": "en",
         "isPartOf": {"@id": SITE + "/#website"}, "publisher": org, "primaryImageOfPage": SITE + gs[0]["thumb"],
         "mainEntity": {"@type": "ItemList", "numberOfItems": len(gs), "itemListElement": [
             {"@type": "ListItem", "position": i + 1, "url": SITE + PATH + "#" + g["id"],
              "item": {"@type": "DigitalDocument", "name": g["title"], "url": SITE + g["pdf"], "encodingFormat": "application/pdf",
                       "description": g["intro"][0], "thumbnailUrl": SITE + g["thumb"], "publisher": {"@id": SITE + "/#org"}, "inLanguage": "en"}}
             for i, g in enumerate(gs)]}},
        {"@type": "BreadcrumbList", "itemListElement": [{"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"},
                                                        {"@type": "ListItem", "position": 2, "name": "Everyday Readiness", "item": SITE + PATH}]}]}
    return S.page(TITLE, DESC, body, PATH, "preppers", jsonld=ld, og_type="website")

def handle_get(path, qs):
    if path != PATH: return 404, {"error": "not found"}   # /ready/ and friends: server.py not_found_page sends a 301 to /ready
    return 200, render(), "text/html"
