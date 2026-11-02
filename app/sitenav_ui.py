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
LOGO_HTML = ('<svg class="bn-icon" viewBox="0 0 1024 1024" aria-hidden="true" focusable="false"><rect x="6.4" y="6.4" width="1011.2" height="1011.2" rx="192" style="fill:var(--bn-mark-bg,#0B0D10);stroke:var(--bn-mark-line,#252B33);stroke-width:12.8"/><path style="fill:var(--bn-mark-fg,#FFFFFF)" d="M527.26 681.57V342.43H606.23L755.93 523.16V342.43H849.92V681.57H770.95L621.25 500.84V681.57ZM279.21 681.57V612.29H349.46Q374.17 612.29 387.01 603.81Q399.84 595.33 399.84 577.89Q399.84 560.45 387.01 551.97Q374.17 543.49 349.46 543.49H279.21V477.12H334.93Q359.15 477.12 371.26 468.88Q383.37 460.65 383.37 444.17Q383.37 427.7 371.26 419.71Q359.15 411.71 334.93 411.71H279.21V342.43H347.52Q414.38 342.43 447.32 366.9Q480.27 391.37 480.27 431.09Q480.27 457.25 466.46 476.88Q454.56 493.79 434.38 504.58Q437.52 505.68 440.54 506.91Q467.19 517.81 481.96 538.4Q496.74 558.99 496.74 588.55Q496.74 632.63 461.13 657.1Q425.52 681.57 357.21 681.57Z"/><path style="fill:var(--bn-mark-crit,#C8102E)" d="M180.86 342.43H262.25C266 342.43 269.04 345.47 269.04 349.22V392.63C269.04 396.37 266 399.41 262.25 399.41H180.86C177.12 399.41 174.08 396.37 174.08 392.63V349.22C174.08 345.47 177.12 342.43 180.86 342.43Z"/><path style="fill:var(--bn-mark-hi,#FFC21A)" d="M180.86 483.51H262.25C266 483.51 269.04 486.55 269.04 490.3V533.7C269.04 537.45 266 540.49 262.25 540.49H180.86C177.12 540.49 174.08 537.45 174.08 533.7V490.3C174.08 486.55 177.12 483.51 180.86 483.51ZM180.86 412.97H262.25C266 412.97 269.04 416.01 269.04 419.76V463.17C269.04 466.91 266 469.95 262.25 469.95H180.86C177.12 469.95 174.08 466.91 174.08 463.17V419.76C174.08 416.01 177.12 412.97 180.86 412.97Z"/><path style="fill:var(--bn-mark-lo,#3FAE80)" d="M180.86 624.59H262.25C266 624.59 269.04 627.63 269.04 631.37V674.78C269.04 678.53 266 681.57 262.25 681.57H180.86C177.12 681.57 174.08 678.53 174.08 674.78V631.37C174.08 627.63 177.12 624.59 180.86 624.59ZM180.86 554.05H262.25C266 554.05 269.04 557.09 269.04 560.83V604.24C269.04 607.99 266 611.03 262.25 611.03H180.86C177.12 611.03 174.08 607.99 174.08 604.24V560.83C174.08 557.09 177.12 554.05 180.86 554.05Z"/></svg>'
             '<span class="bn-word" aria-label="BLACKOUT.NETWORK">BLACKOUT.<b>NETWORK</b></span>')  # logo V2-final 'Meter in the letters' (Nov 1 2026; colours via --bn-mark-* tokens, light theme = light version) + wordmark in true caps BLACKOUT.NETWORK (red NETWORK accent)

# Text links shown in the bar on wide screens (everything is also in the sidebar).
PRIMARY = [("threat", "/#wire", "The Wire"), ("sources", "/sources", "Sources"), ("newsletter", "/newsletter", "Newsletter")]

_SVG = 'aria-hidden="true" focusable="false" width="20" height="20" viewBox="0 0 24 24"'
I_MENU = f'<svg {_SVG}><path d="M3 6h18M3 12h18M3 18h18" stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none"/></svg>'
I_CLOSE = f'<svg {_SVG}><path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none"/></svg>'
I_SEARCH = f'<svg {_SVG}><circle cx="11" cy="11" r="6.5" stroke="currentColor" stroke-width="2" fill="none"/><path d="M16 16l4.5 4.5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>'
# t397: symmetrical 8-tooth gear (generated: teeth every 45°, tip r 9.5, root r 7.2, hole r 3), same 1.8 stroke as the other bar icons
I_GEAR = (f'<svg {_SVG}><path fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" '
          'd="M9.96 5.10L10.27 2.66A9.5 9.5 0 0 1 13.73 2.66L14.04 5.10A7.2 7.2 0 0 1 15.44 5.67L17.38 4.17A9.5 9.5 0 0 1 19.83 6.62L18.33 8.56A7.2 7.2 0 0 1 18.90 9.96L21.34 10.27A9.5 9.5 0 0 1 21.34 13.73L18.90 14.04A7.2 7.2 0 0 1 18.33 15.44L19.83 17.38A9.5 9.5 0 0 1 17.38 19.83L15.44 18.33A7.2 7.2 0 0 1 14.04 18.90L13.73 21.34A9.5 9.5 0 0 1 10.27 21.34L9.96 18.90A7.2 7.2 0 0 1 8.56 18.33L6.62 19.83A9.5 9.5 0 0 1 4.17 17.38L5.67 15.44A7.2 7.2 0 0 1 5.10 14.04L2.66 13.73A9.5 9.5 0 0 1 2.66 10.27L5.10 9.96A7.2 7.2 0 0 1 5.67 8.56L4.17 6.62A9.5 9.5 0 0 1 6.62 4.17L8.56 5.67A7.2 7.2 0 0 1 9.96 5.10Z"/>'
          '<circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" stroke-width="1.8"/></svg>')
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
 ("Threat categories", ["net", "grid", "ai", "solar_seismic", "weather", "@crime", "finance", "jets", "spacex", "intel"]),
 ("Politics & Government", ["politics", "gov"]),
 ("Community", ["ranked", "@social", "@stats", "newsletter"]),
 ("Reference", ["res", "maps", "bush", "med", "preppers", "figures"]),
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
            f'<div class="ctl">{ctl_html}</div></div></header>' + LOADER)

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
               '<p class="bn-dfoot"><a href="/scoring">How we score</a><a href="/privacy">Privacy</a><a href="/tos">Terms</a><a href="/stats">Stats</a><a href="/report-status">Report status</a></p>'
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

# Light/dark theme before first paint (same script as server.THEME_HEAD; the "bn_theme" marker stops a second copy).
THEME_SCRIPT = ('<script>(function(){var d=document.documentElement,t;try{t=localStorage.getItem("bn_theme")}catch(e){}'
                'if(t!=="light"&&t!=="dark")t=window.matchMedia&&matchMedia("(prefers-color-scheme: light)").matches?"light":"dark";'
                'd.setAttribute("data-theme",t);d.style.colorScheme=t})()</script>')

# If Render drops /sitenav.css or /sitenav.js during a busy load (it sometimes 502s a few of a page's ~30 files), load them again.
LOADER = ('<script>addEventListener("load",function(){var d=document,r=d.documentElement;'
          'if(!getComputedStyle(r).getPropertyValue("--bn-tbar-h")){var l=d.createElement("link");l.rel="stylesheet";l.href="/sitenav.css?retry=1";d.head.appendChild(l)}'
          'if(!window.bnSitenav)setTimeout(function(){if(window.bnSitenav)return;var s=d.createElement("script");s.src="/sitenav.js?retry=1";d.head.appendChild(s)},1500)})</script>')
