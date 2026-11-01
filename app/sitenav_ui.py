"""BLACKOUT.NETWORK top bar + sidebar menu markup (t320/t321/t323). Data (tabs, groups, labels, pages) comes from sitenav.py.

Layout: a minimal top bar (logo left; on wide screens The Wire / Sources / Newsletter text links; Follow us on YouTube / X;
search, light/dark toggle, settings (dashboard) and the menu button right). The menu button opens a sidebar that lists every
tab grouped into collapsible sections, with search, the follow links and the theme toggle inside.
Works without JavaScript: the menu button is a link to #bn-menu and the sidebar opens with CSS :target, the sections are
<details>. With JavaScript (/sitenav.js) the sidebar becomes a modal dialog (focus trap, Escape, scrim tap, scroll lock).
Look and feel: every color, font, size and radius is a CSS custom property at the top of static/sitenav.css (design tokens).
The logo is ONE element (LOGO_HTML below): swap it there (e.g. for an <img>) and every page follows."""
import html, re

E = lambda s: html.escape(str(s if s is not None else ""), quote=True)

# The single, swappable logo element (bar + sidebar). Styled only via the --bn-logo-* tokens in sitenav.css.
LOGO_HTML = ('<svg class="bn-icon" viewBox="0 0 96 96" aria-hidden="true" focusable="false"><rect x=".6" y=".6" width="94.8" height="94.8" rx="17.4" style="fill:var(--bn-mark-bg,#0B0D10);stroke:var(--bn-mark-line,#252B33);stroke-width:1.2"/><g style="fill:var(--bn-mark-fg,#FFFFFF)"><path d="M14.51 62.0V31.2H30.96Q37.34 31.2 40.38 33.47Q43.42 35.73 43.42 39.25Q43.42 41.58 42.14 43.39Q41.04 44.93 39.19 45.9Q39.28 45.94 39.41 45.98Q42.01 47 43.44 48.91Q44.87 50.82 44.87 53.51Q44.87 57.51 41.55 59.76Q38.22 62.0 31.84 62.0ZM24.72 54.74H30.96Q32.68 54.74 33.54 54.12Q34.4 53.51 34.4 52.32Q34.4 51.13 33.54 50.52Q32.68 49.9 30.96 49.9H24.72ZM24.72 43.04H29.56Q31.32 43.04 32.13 42.44Q32.94 41.85 32.94 40.75Q32.94 39.6 32.13 39.03Q31.32 38.46 29.56 38.46H24.72Z"/><path d="M46.52 62.0V31.2H55.06L66.76 45.19V31.2H76.88V62.0H68.34L56.64 48.01V62.0Z"/></g><rect x="14" y="76" width="5.2" height="8" rx="1" fill="#2BB673"/><rect x="21" y="76" width="5.2" height="8" rx="1" fill="#2BB673"/><rect x="28" y="76" width="5.2" height="8" rx="1" fill="#2BB673"/><rect x="35" y="76" width="5.2" height="8" rx="1" fill="#F5A524"/><rect x="42" y="76" width="5.2" height="8" rx="1" fill="#F5A524"/><rect x="49" y="76" width="5.2" height="8" rx="1" fill="#F5A524"/><rect x="56" y="76" width="5.2" height="8" rx="1" fill="#FF4D4F"/><rect x="63" y="76" width="5.2" height="8" rx="1" fill="#FF4D4F" opacity=".28"/><rect x="70" y="76" width="5.2" height="8" rx="1" fill="#FF4D4F" opacity=".28"/><rect x="77" y="76" width="5.2" height="8" rx="1" fill="#FF4D4F" opacity=".28"/></svg>'
             '<span class="bn-word" aria-label="BLACKOUT.NETWORK">B<span style="font-size:.83em">LACKOUT.</span><b>N<span style="font-size:.83em">ETWORK</span></b></span>')  # BN master tile (outlined, t333) + small domain, B/N full caps

# Text links shown in the bar on wide screens (everything is also in the sidebar).
PRIMARY = [("threat", "/#wire", "The Wire"), ("sources", "/sources", "Sources"), ("newsletter", "/newsletter", "Newsletter")]

_SVG = 'aria-hidden="true" focusable="false" width="20" height="20" viewBox="0 0 24 24"'
I_MENU = f'<svg {_SVG}><path d="M3 6h18M3 12h18M3 18h18" stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none"/></svg>'
I_CLOSE = f'<svg {_SVG}><path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none"/></svg>'
I_SEARCH = f'<svg {_SVG}><circle cx="11" cy="11" r="6.5" stroke="currentColor" stroke-width="2" fill="none"/><path d="M16 16l4.5 4.5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>'
I_GEAR = (f'<svg {_SVG}><circle cx="12" cy="12" r="3.2" stroke="currentColor" stroke-width="1.8" fill="none"/><path fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" '
          'd="M12 2.8l1.6 2.3 2.7-.7.7 2.7 2.3 1.6-1.2 2.5 1.2 2.5-2.3 1.6-.7 2.7-2.7-.7L12 21.2l-1.6-2.3-2.7.7-.7-2.7-2.3-1.6L5.9 12 4.7 9.5 7 7.9l.7-2.7 2.7.7z"/></svg>')
I_SUN = (f'<svg class="bn-sun" {_SVG}><circle cx="12" cy="12" r="4.2" fill="none" stroke="currentColor" stroke-width="1.8"/><path stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
         'd="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.3 5.3l1.6 1.6M17.1 17.1l1.6 1.6M5.3 18.7l1.6-1.6M17.1 6.9l1.6-1.6"/></svg>')
I_MOON = f'<svg class="bn-moon" {_SVG}><path fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/></svg>'
I_YT = ('<svg class="bn-ico" aria-hidden="true" focusable="false" width="20" height="14" viewBox="0 0 24 17"><rect width="24" height="17" rx="4" fill="#FF0033"/>'
        '<path d="M9.6 4.9v7.2l6.2-3.6z" fill="#fff"/></svg>')
I_X = ('<svg class="bn-ico" aria-hidden="true" focusable="false" width="15" height="15" viewBox="0 0 24 24"><path fill="currentColor" '
       'd="M18.901 1.153h3.68l-8.04 9.19L24 22.846h-7.406l-5.8-7.584-6.638 7.584H.474l8.6-9.83L0 1.154h7.594l5.243 6.932ZM17.61 20.644h2.039L6.486 3.24H4.298Z"/></svg>')

# Sidebar sections (brand A "Signal" menu). Keys are sitenav.NAV keys. A NAV tab not listed here goes into the section of the
# tab listed before it in NAV (so a new tab added next to Politics/Government lands in Politics & Government), else the first section.
MENU = [
 ("Live", ["threat", "noise", "thread", "bcast", "streams", "radio", "trends", "heatmap"]),
 ("Threat categories", ["net", "grid", "ai", "solar_seismic", "weather", "finance", "jets", "spacex", "intel", "elon"]),
 ("Politics & Government", ["politics", "gov"]),
 ("Community", ["ranked", "@social", "newsletter"]),
 ("Reference", ["res", "maps", "bush", "med", "preppers"]),
 ("Play", ["games"]),
 ("About", ["@scoring", "sources", "tips"]),
]

def menu_sections(sn):
    items = [it for g, its in sn.NAV for it in its if not (len(it) > 5 and it[5])]
    where = {k: i for i, (_, ks) in enumerate(MENU) for k in ks}
    secs = [[] for _ in MENU]; prev = 0
    for it in items:
        i = where.get(it[0], prev); secs[i].append(it); prev = i
    for i, (_, ks) in enumerate(MENU):        # keep MENU order inside a section; unlisted tabs follow their NAV neighbour
        order = {k: n for n, k in enumerate(ks)}
        out = sorted((it for it in secs[i] if it[0] in order), key=lambda it: order[it[0]])
        for it in secs[i]:
            if it[0] not in order:
                j = next((n for n, x in enumerate(out) if x is not None and x[0] == _nav_prev(items, it)), len(out) - 1)
                out.insert(j + 1, it)
        secs[i] = out
    return [(MENU[i][0], s) for i, s in enumerate(secs) if s]

def _nav_prev(items, it):
    i = items.index(it)
    return items[i - 1][0] if i else None

def plain(label):
    """'📡 The Wire' -> 'The Wire' (emoji/symbol prefix removed) for titles."""
    return re.sub(r"^[^\w(]+", "", label or "").strip()

def follow_links(sn, cls="bn-follow"):
    def a(href, ico, net):
        return (f'<a class="{cls}" href="{E(href)}" target="_blank" rel="noopener me" aria-label="Follow us on {net} {sn.HANDLE} (opens in a new tab)">'
                f'{ico}<span class="bn-fl"><span class="bn-fl-pre">Follow us on </span>{net} <b>{sn.HANDLE}</b></span></a>')
    return a(sn.YT_URL, I_YT, "YouTube") + a(sn.X_URL, I_X, "X")

def theme_btn(cls):
    return (f'<button type="button" class="bn-ib bn-theme {cls}" data-bn-theme aria-label="Switch to light mode" title="Light / dark mode">'
            f'{I_SUN}{I_MOON}<span class="bn-tl">Light mode</span></button>')

def topbar(sn, active="", ctl_html=""):
    """<header class="bn-top"> for every page. ctl_html = page-specific controls for the settings popover (dashboard: scan status,
    refresh, interval); add-ons that look for "header .ctl" (translate, live indicator) also land there."""
    prim = "".join(f'<a href="{E(h)}" data-tab="{E(k)}"' + (' aria-current="page"' if k == active else "") + f'>{E(l)}</a>' for k, h, l in PRIMARY)
    return ('<header class="bn-top" id="bn_topbar"><div class="bn-tbar">'
            f'<a class="bn-logo" href="/" aria-label="{sn.BRAND} home">{LOGO_HTML}</a>'
            f'<nav class="bn-primary" aria-label="Primary">{prim}</nav>'
            f'<div class="bn-acts"><span class="bn-follows">{follow_links(sn)}</span>'
            f'<a class="bn-ib bn-js-only bn-searchbtn" href="#bn-menu" role="button" aria-label="Search" title="Search (/)">{I_SEARCH}</a>'
            + theme_btn("bn-js-only bn-theme-bar") +
            f'<button type="button" class="bn-ib bn-js-only bn-gear" aria-label="Settings and scan status" aria-expanded="false" aria-controls="bn_settings" title="Settings">{I_GEAR}</button>'
            f'<a class="bn-ib bn-burger" href="#bn-menu" role="button" aria-label="Open menu" aria-controls="bn-menu" aria-expanded="false" aria-haspopup="dialog">{I_MENU}<span class="bn-bl">Menu</span></a>'
            '</div></div>'
            '<div class="bn-pop" id="bn_settings" role="dialog" aria-label="Settings" hidden><div class="bn-pop-h">Settings</div>'
            f'<div class="ctl">{ctl_html}</div></div></header>')

def drawer(sn, active=""):
    """The sidebar menu (<div id="bn-menu">): search slot, follow links, every tab by group, theme toggle, legal links."""
    out = ['<div class="bn-drawer" id="bn-menu"><a class="bn-scrim" href="#_" tabindex="-1" aria-hidden="true"></a>'
           '<nav class="bn-panel" aria-label="Site menu"><div class="bn-ph">'
           f'<a class="bn-logo" href="/" tabindex="-1">{LOGO_HTML}</a>'
           f'<a class="bn-ib bn-close" href="#_" role="button" aria-label="Close menu">{I_CLOSE}</a></div>'
           '<div class="bn-dsearch bn-js-only" id="bn_dsearch"></div>']
    secs = menu_sections(sn)
    act = next((n for n, its in secs for it in its if it[0] == active), None)
    for name, its in secs:
        op = " open" if (name == act or name == "Live") else ""
        out.append(f'<details class="bn-grp" data-grp="{E(name)}"{op}><summary>{E(name)}</summary><ul>')
        for it in its:
            key, h, label = it[0], it[1], it[2]
            href = h if h.startswith("/") else "/#" + h
            cur = ' aria-current="page"' if key == active else ""
            out.append(f'<li><a href="{E(href)}" data-tab="{E(key)}"{cur}>{E(plain(label))}</a></li>')
        out.append('</ul></details>')
    out.append(f'<div class="bn-dfollow">{follow_links(sn, "bn-follow bn-follow-row")}</div>')
    out.append('<div class="bn-dtools">' + theme_btn("bn-js-only bn-theme-row") +
               '<button type="button" class="bn-mrow bn-js-only bn-gear-row" aria-controls="bn_settings">' + I_GEAR + '<span>Settings &amp; scan status</span></button></div>'
               '<p class="bn-dfoot"><a href="/scoring">How we score</a><a href="/privacy">Privacy</a><a href="/tos">Terms</a><a href="/report-status">Report status</a></p>'
               '</nav></div>')
    return "".join(out)

def pagehead(title, desc):
    return (f'<div class="bn-pagehead"><h1 class="bn-ptitle" id="bn_ptitle">{E(title)}</h1>'
            f'<p class="bn-tabdesc" id="bn_tabdesc">{E(desc)}</p></div>')

def meter_html(rank, size=""):
    """Server-side Rank Meter (same markup as window.bnMeter in sitenav.js; styles in sitenav.css)."""
    try: r = max(0, min(10, int(round(float(rank)))))
    except Exception: r = 0
    sz = f" bn-meter-{size}" if size else ""
    return (f'<span class="bn-meter bn-r{r}{sz}" role="img" aria-label="Rank {r} of 10" title="Rank {r} of 10"><span class="bn-segs" aria-hidden="true">'
            + "<i></i>" * 10 + f'</span><b class="bn-num" aria-hidden="true">{r}<small>/10</small></b></span>')
