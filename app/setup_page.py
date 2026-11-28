"""GET /setup — the BLACKOUT.NETWORK app page: install it, turn on alerts, see what you get.

Matt 8:48 AM ET Nov 28 (redesign): graphically pleasing and feature rich, in the spacex.com language of the homepage intro (#354):
full-bleed licensed photographs (the same graded-grey stills the intro uses, credited on /credits), huge thin uppercase type, hairline
pills, minimal words, dark, no yellow. Static page: no Refresh control. Never says peer-to-peer.

Sections: hero (Install App / Turn On Alerts) · what you get (only things the site really has) · alerts (what triggers one, and a lock-screen
sample built from the latest real rank 7+ story on The Wire, fetched in the browser from /api/new_high, clearly labelled sample) ·
step-by-step install for iPhone/iPad, Android and desktop as drawn UI scenes (original SVG, Phosphor icons) with the visitor's own OS shown first ·
closing call to action. #install and #notifications are the menu's anchors. The buttons call BN.installApp / BN.showNotifyGuide / BN.enableAlerts
from static/pwa/install-guide.js and static/alerts/alerts.js (loaded on tap, never a pop-up on load).
No images of maps or satellites. Never touches scanner core.
"""
import html
import sitenav
from setup_icons import SPRITE

E = lambda s: html.escape(str(s if s is not None else ""), quote=True)

# ---------------------------------------------------------------- media (the intro's stills, served by theme.py at /bnt/media)
HERO = ("sxheat-d.jpg", "sxheat-m.jpg")      # firefighters, FEMA, public domain
ALERT = ("sxgrid-d.jpg", "sxgrid-m.jpg")     # transmission pylon, CC BY-SA 2.0
CLOSE = ("sxbrief-d.jpg", "sxbrief-m.jpg")   # US Capitol at night, public domain


def _mv():
    try:
        import theme
        return theme.versions()[1]
    except Exception:
        return "1"


def _pic(pair, mv, eager=False):
    d, m = pair
    return (f'<picture><source media="(max-width:700px)" srcset="/bnt/media/{m}?v={mv}">'
            f'<img src="/bnt/media/{d}?v={mv}" alt="" decoding="async"'
            + (' fetchpriority="high"' if eager else ' loading="lazy"') + '></picture>')


def _ic(n, cls="ic"):
    return f'<svg class="{cls}" aria-hidden="true" focusable="false"><use href="#{n}"/></svg>'


# ---------------------------------------------------------------- drawn UI scenes (original SVG; icons are Phosphor)
def _u(n, x, y, s, cls="ig"):
    return f'<use class="{cls}" href="#r-{n}" x="{x}" y="{y}" width="{s}" height="{s}"/>'


def _t(x, y, s, size=9, cls="tx", anchor="start", w=500):
    return f'<text class="{cls}" x="{x}" y="{y}" font-size="{size}" font-weight="{w}" text-anchor="{anchor}">{E(s)}</text>'


def _rring(x, y, w, h, r):
    return (f'<rect class="ring" x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}"/>'
            f'<rect class="ring r2" x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}"/>')


def _ring(cx, cy, r=15):
    return f'<circle class="ring" cx="{cx}" cy="{cy}" r="{r}"/><circle class="ring r2" cx="{cx}" cy="{cy}" r="{r}"/>'


ICON = "/icons/icon-192.png?v=5"


def _phone(inner, android=False):
    nav = '<rect class="mu2" x="72" y="386" width="56" height="3" rx="1.5"/>'
    return ('<svg class="scn" viewBox="0 0 200 400" role="img" focusable="false" xmlns="http://www.w3.org/2000/svg">'
            '<rect class="pf" x="1" y="1" width="198" height="398" rx="32"/>'
            '<g clip-path="url(#su-scr)"><rect class="sc" x="6" y="6" width="188" height="388"/>' + inner + nav + '</g>'
            '<rect class="pn" x="76" y="12" width="48" height="8" rx="4"/></svg>')


def _page(y0=36, rows=5):
    """A stand-in for the site: logo line, big title bar, ranked rows as bars. No invented headlines."""
    o = _t(16, y0 + 12, "blackout.network", 11, "tx", w=700)
    o += '<rect class="ln" x="160" y="%d" width="16" height="2" rx="1"/><rect class="ln" x="160" y="%d" width="16" height="2" rx="1"/><rect class="ln" x="160" y="%d" width="16" height="2" rx="1"/>' % (y0 + 5, y0 + 10, y0 + 15)
    o += '<rect class="ln" x="16" y="%d" width="110" height="14" rx="2"/>' % (y0 + 34)
    for i in range(rows):
        y = y0 + 66 + i * 38
        o += f'<rect class="ln" x="16" y="{y}" width="18" height="18" rx="9"/><rect class="ln" x="42" y="{y}" width="132" height="5" rx="2.5"/><rect class="ln2" x="42" y="{y + 11}" width="96" height="5" rx="2.5"/>'
    return o


def _safari_bar(hl=None):
    o = '<rect class="bar" x="0" y="296" width="200" height="100"/>'
    o += '<rect class="pill" x="14" y="304" width="172" height="28" rx="14"/>' + _u("lock-simple", 62, 312, 11, "ig mu") + _t(78, 322, "blackout.network", 10, "tx")
    xs = {"back": 28, "fwd": 62, "share": 100, "book": 138, "tabs": 172}
    o += _u("caret-left", xs["back"] - 9, 345, 18, "ig mu") + _u("caret-right", xs["fwd"] - 9, 345, 18, "ig mu")
    o += _u("export", xs["share"] - 9, 345, 18, "ig") + _u("book-open", xs["book"] - 9, 345, 18, "ig mu") + _u("squares-four", xs["tabs"] - 9, 345, 18, "ig mu")
    if hl == "url":
        o += _rring(10, 300, 180, 36, 18)
    if hl == "share":
        o += _ring(xs["share"], 354, 15)
    return o


def _ios1():
    return _phone(_page() + _safari_bar("url"))


def _ios2():
    return _phone(_page() + _safari_bar("share"))


def _sheet_row(y, label, icon, hl=False):
    o = ""
    if hl:
        o += f'<rect class="hlr" x="14" y="{y - 14}" width="172" height="28" rx="9"/>'
    o += _t(26, y + 4, label, 9.5, "tx" if hl else "mu", w=600 if hl else 500)
    if icon:
        o += _u(icon, 158, y - 8, 16, "ig" if hl else "ig mu")
    return o


def _ios3():
    o = _page() + '<rect class="dim" x="0" y="0" width="200" height="400"/>'
    o += '<rect class="shl" x="0" y="124" width="200" height="280" rx="22"/><rect class="ln" x="86" y="132" width="28" height="3" rx="1.5"/>'
    o += f'<image href="{ICON}" x="16" y="148" width="30" height="30" preserveAspectRatio="xMidYMid slice" class="appico"/>'
    o += _t(54, 160, "BLACKOUT.NETWORK", 9, "tx", w=700) + _t(54, 172, "blackout.network", 8, "mu")
    o += '<rect class="ln2" x="14" y="190" width="172" height="1"/>'
    o += _sheet_row(212, "Copy", None)
    o += _sheet_row(246, "Add to Bookmarks", "book-open")
    o += _sheet_row(282, "Add to Home Screen", "plus-square", True)
    o += _sheet_row(318, "Find on Page", None)
    o += _ring(158, 282, 17)
    return _phone(o)


def _ios4():
    o = _page() + '<rect class="dim" x="0" y="0" width="200" height="400"/>'
    o += '<rect class="shl" x="0" y="96" width="200" height="320" rx="22"/>'
    o += _t(18, 130, "Cancel", 9, "mu") + _t(100, 130, "Add to Home Screen", 8.5, "tx", "middle", 700)
    o += '<rect class="btnw" x="150" y="118" width="34" height="18" rx="9"/>' + _t(167, 130, "Add", 8.5, "dk", "middle", 700)
    o += f'<image href="{ICON}" x="18" y="156" width="44" height="44" preserveAspectRatio="xMidYMid slice" class="appico"/>'
    o += '<rect class="pill" x="72" y="160" width="112" height="36" rx="8"/>' + _t(80, 182, "BLACKOUT.NETWORK", 8.5, "tx", w=600)
    o += _t(18, 226, "blackout.network", 8, "mu") + '<rect class="ln2" x="18" y="240" width="164" height="4" rx="2"/><rect class="ln2" x="18" y="252" width="120" height="4" rx="2"/>'
    o += _ring(167, 127, 18)
    return _phone(o)


def _home(android=False):
    o = ""
    shape = (lambda x, y: f'<circle class="ap" cx="{x + 17}" cy="{y + 17}" r="17"/>') if android else (lambda x, y: f'<rect class="ap" x="{x}" y="{y}" width="34" height="34" rx="9"/>')
    for r in range(4):
        for c in range(4):
            x, y = 14 + c * 44, 54 + r * 62
            if (r, c) == (1, 2):
                continue
            o += shape(x, y)
            o += f'<rect class="ln2" x="{x + 4}" y="{y + 40}" width="26" height="3" rx="1.5"/>'
    x, y = 14 + 2 * 44, 54 + 62
    clip = f'<clipPath id="su-ac{"a" if android else "i"}"><rect x="{x}" y="{y}" width="34" height="34" rx="{17 if android else 9}"/></clipPath>'
    o += clip + f'<image href="{ICON}" x="{x}" y="{y}" width="34" height="34" preserveAspectRatio="xMidYMid slice" clip-path="url(#su-ac{"a" if android else "i"})"/>'
    o += _t(x + 17, y + 46, "BLACKOUT", 6.5, "tx", "middle", 600)
    o += _ring(x + 17, y + 17, 25)
    o += '<rect class="dock" x="10" y="326" width="180" height="50" rx="18"/>'
    for c in range(4):
        o += shape(20 + c * 42, 334).replace('width="34" height="34"', 'width="32" height="32"').replace('r="17"', 'r="16"')
    return _phone(o, android)


def _chrome_top(hl=None):
    o = '<rect class="bar" x="0" y="0" width="200" height="80"/>'
    o += '<rect class="pill" x="12" y="34" width="150" height="28" rx="14"/>' + _u("lock-simple", 20, 42, 11, "ig mu") + _t(36, 52, "blackout.network", 10, "tx")
    o += _u("dots-three-vertical", 168, 40, 20, "ig")
    if hl == "url":
        o += _rring(8, 30, 158, 36, 18)
    if hl == "menu":
        o += _ring(178, 50, 15)
    return o


def _and1():
    return _phone(_page(92, 4) + _chrome_top("url"), True)


def _and2():
    return _phone(_page(92, 4) + _chrome_top("menu"), True)


def _and3():
    o = _page(92, 4) + _chrome_top() + '<rect class="dim" x="0" y="0" width="200" height="400"/>'
    o += '<rect class="shl" x="46" y="40" width="146" height="196" rx="14"/>'
    for i, (lab, hl) in enumerate((("New tab", 0), ("Bookmarks", 0), ("Install app", 1), ("Share…", 0), ("Settings", 0))):
        y = 72 + i * 36
        if hl:
            o += f'<rect class="hlr" x="52" y="{y - 16}" width="134" height="30" rx="9"/>'
        o += _t(64, y + 3, lab, 9.5, "tx" if hl else "mu", w=600 if hl else 500)
    o += _ring(160, 108, 18)
    return _phone(o, True)


def _and4():
    o = _page(92, 4) + _chrome_top() + '<rect class="dim" x="0" y="0" width="200" height="400"/>'
    o += '<rect class="shl" x="20" y="130" width="160" height="150" rx="22"/>'
    o += f'<image href="{ICON}" x="34" y="148" width="34" height="34" preserveAspectRatio="xMidYMid slice" class="appico"/>'
    o += _t(76, 163, "Install app?", 10, "tx", w=700) + _t(76, 177, "BLACKOUT.NETWORK", 8, "mu")
    o += '<rect class="ln2" x="34" y="196" width="132" height="4" rx="2"/><rect class="ln2" x="34" y="208" width="96" height="4" rx="2"/>'
    o += _t(104, 260, "Cancel", 9, "mu", "end") + '<rect class="btnw" x="116" y="244" width="52" height="24" rx="12"/>' + _t(142, 260, "Install", 9, "dk", "middle", 700)
    o += _ring(142, 256, 22)
    return _phone(o, True)


def _win(inner, vh=210, title=None, bar=True):
    return ('<svg class="scn wide" viewBox="0 0 320 %d" role="img" focusable="false" xmlns="http://www.w3.org/2000/svg">' % vh
            + '<rect class="pf" x="1" y="1" width="318" height="%d" rx="12"/>' % (vh - 2) + '<g clip-path="url(#su-win)">'
            + f'<rect class="sc" x="6" y="6" width="308" height="{vh - 12}"/>' + inner + '</g></svg>')


def _dpage(y0):
    o = _t(24, y0 + 22, "blackout.network", 11, "tx", w=700) + '<rect class="ln" x="24" y="%d" width="150" height="14" rx="2"/>' % (y0 + 38)
    for i in range(3):
        y = y0 + 70 + i * 26
        o += f'<rect class="ln" x="24" y="{y}" width="16" height="16" rx="8"/><rect class="ln" x="48" y="{y}" width="220" height="5" rx="2.5"/><rect class="ln2" x="48" y="{y + 9}" width="160" height="5" rx="2.5"/>'
    return o


def _dtop(hl=None, tip=False):
    o = '<rect class="bar" x="6" y="6" width="308" height="62"/>'
    for i in range(3):
        o += f'<circle class="ln" cx="{22 + i * 12}" cy="19" r="3.4"/>'
    o += '<rect class="tab" x="76" y="10" width="92" height="20" rx="7"/>' + _t(88, 23, "BLACKOUT.NETWORK", 6.5, "tx", w=600)
    o += '<rect class="pill" x="16" y="36" width="288" height="24" rx="12"/>' + _u("lock-simple", 26, 42, 11, "ig mu") + _t(42, 52, "blackout.network", 9, "tx")
    o += _u("download-simple", 280, 41, 14, "ig")
    if hl == "url":
        o += _rring(12, 33, 296, 30, 15)
    if hl == "install":
        o += _ring(287, 48, 15)
    return o


def _dsk1():
    return _win(_dpage(70) + _dtop("url"))


def _dsk2():
    o = _dpage(70) + _dtop("install")
    o += '<rect class="shl" x="164" y="66" width="146" height="100" rx="12"/>'
    o += f'<image href="{ICON}" x="176" y="78" width="26" height="26" preserveAspectRatio="xMidYMid slice" class="appico"/>'
    o += _t(210, 89, "Install app?", 9, "tx", w=700) + _t(210, 100, "BLACKOUT.NETWORK", 7, "mu")
    o += _t(228, 148, "Cancel", 8, "mu", "end") + '<rect class="btnw" x="236" y="134" width="64" height="22" rx="11"/>' + _t(268, 148, "Install", 8.5, "dk", "middle", 700)
    return _win(o)


def _dsk3():
    o = '<rect class="bar" x="6" y="6" width="308" height="22"/>' + _t(160, 20, "BLACKOUT.NETWORK", 7.5, "mu", "middle", 600)
    for i in range(3):
        o += f'<circle class="ln" cx="{22 + i * 12}" cy="17" r="3.4"/>'
    o += _dpage(24)
    o += '<rect class="dock" x="96" y="170" width="128" height="30" rx="12"/>'
    for i in range(4):
        o += f'<rect class="ap" x="{106 + i * 28}" y="174" width="22" height="22" rx="6"/>' if i != 1 else (
            f'<clipPath id="su-acd"><rect x="{106 + i * 28}" y="174" width="22" height="22" rx="6"/></clipPath><image href="{ICON}" x="{106 + i * 28}" y="174" width="22" height="22" clip-path="url(#su-acd)" preserveAspectRatio="xMidYMid slice"/>')
    o += _ring(106 + 28 + 11, 185, 16)
    return _win(o)


CLIPS = '<svg width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false"><defs><clipPath id="su-scr"><rect x="6" y="6" width="188" height="388" rx="27"/></clipPath><clipPath id="su-win"><rect x="6" y="6" width="308" height="198" rx="8"/></clipPath></defs></svg>'

STEPS = {
    "ios": [("Open in Safari", "Go to blackout.network.", _ios1), ("Tap Share", "The square with the arrow.", _ios2),
            ("Add to Home Screen", "Scroll the sheet if needed.", _ios3), ("Tap Add", "Keep the name.", _ios4),
            ("Open the icon", "Alerts work from here.", lambda: _home(False))],
    "android": [("Open in Chrome", "Go to blackout.network.", _and1), ("Tap the menu", "Three dots, top right.", _and2),
                ("Install app", "Or Add to Home screen.", _and3), ("Tap Install", "Then confirm.", _and4),
                ("Open the icon", "Find it on your Home screen.", lambda: _home(True))],
    "desktop": [("Open in Chrome or Edge", "Go to blackout.network.", _dsk1), ("Click Install", "The icon in the address bar.", _dsk2),
                ("Open the app", "It gets its own window.", _dsk3)],
}
TABS = (("ios", "iPhone & iPad", "l-device-mobile"), ("android", "Android", "l-device-mobile"), ("desktop", "Desktop", "r-monitor"))
NOTES = {
    "ios": ("Safari is the browser that installs web apps on iPhone and iPad. In Chrome, Edge or Firefox, use that browser’s Share sheet, then Add to Home Screen; if it isn’t listed, open the page in Safari.",
            "Alerts on iPhone and iPad need iOS 16.4 or later and the Home Screen icon."),
    "android": ("Chrome shows Install app when the site can be installed, or Add to Home screen otherwise.", "Alerts work in Chrome and in the installed app."),
    "desktop": ("Safari on Mac: File, then Add to Dock. Firefox doesn’t install web apps; use Chrome or Edge for an app window. Alerts still work in Firefox.",
                "Alerts need notifications allowed for blackout.network. If nothing happens, check the site settings."),
}

# ---------------------------------------------------------------- what you get: only things the site has (intro_sx.PANELS, menu, alerts, manifest)
FEATURES = (
    ("l-pulse", "The Wire", "/wire", "Every signal from official agencies, sensors and wires, ranked 0 to 10 the moment it lands."),
    ("l-fire", "Heat Map", "/map", "Every story with a place, pinned live."),
    ("l-cloud-lightning", "Weather", "/weather", "Warnings, radar and storm paths for anywhere you search."),
    ("l-plugs-connected", "The Grid", "/grid", "Outages on power, internet, cloud, cables and water, as they happen."),
    ("l-chart-line-up", "Markets", "/markets", "Index moves, bank stress and the money stories behind them."),
    ("l-envelope-simple", "Newsletter", "/newsletter", "The brief, ranked and sourced. 7 AM and 7 PM ET. Free."),
    ("l-bell-ringing", "Alerts", "#notifications", "A push the moment a rank 7 or higher story is confirmed by two or more sources."),
    ("l-device-mobile", "Home Screen app", "#install", "Full screen with no browser bar, one tap from your Home Screen."),
)

TRIGGERS = (("7+", "Rank 7 or higher", "On the Wire’s 0 to 10 scale."),
            ("2+", "Two or more sources", "Independent, confirmed before it is sent."),
            ("1", "One tap to turn on", "Permission is asked only when you tap, never on page load."))

CSS = r"""
html{background:#000;scroll-behavior:smooth}
body{margin:0;background:#000}
.sp{--ink:#F0F0FA;--i8:rgba(240,240,250,.82);--i6:rgba(240,240,250,.62);--i4:rgba(240,240,250,.42);--ln:rgba(240,240,250,.16);--f:"Inter","Helvetica Neue",Arial,sans-serif;
 color:var(--ink);font:400 16px/1.55 var(--f);background:#000;overflow:hidden}
.sp *{box-sizing:border-box}
.sp .ic{width:28px;height:28px;fill:currentColor;flex:none}
.sp a{color:inherit}
.sp-s{position:relative;isolation:isolate;scroll-margin-top:64px}
.sp-bg{position:absolute;inset:0;z-index:-1;background:#000}
.sp-bg picture,.sp-bg img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;display:block}
.sp-bg img{filter:grayscale(1) contrast(1.06) brightness(.82)}
.sp-a .sp-bg img{filter:grayscale(1) contrast(1.05) brightness(.5)}
.sp-bg::after{content:"";position:absolute;inset:0;background:linear-gradient(0deg,rgba(0,0,0,.9) 0%,rgba(0,0,0,.55) 38%,rgba(0,0,0,.2) 70%,rgba(0,0,0,.45) 100%),linear-gradient(90deg,rgba(0,0,0,.6) 0%,rgba(0,0,0,0) 62%)}
.sp-w{width:100%;max-width:1280px;margin:0 auto;padding:0 clamp(20px,5.5vw,96px)}
.sp-eb{display:flex;align-items:center;gap:14px;margin:0 0 18px;font:500 12px/1 var(--f);letter-spacing:.24em;text-transform:uppercase;color:var(--i8)}
.sp-eb i{font-style:normal;color:var(--i4);font-variant-numeric:tabular-nums}
.sp-h{margin:0 0 16px;font:700 clamp(36px,6vw,84px)/1 var(--f);letter-spacing:.01em;text-transform:uppercase;color:#fff;text-wrap:balance}
.sp-l{margin:0 0 28px;max-width:540px;font:400 clamp(15px,1.2vw,18px)/1.55 var(--f);color:var(--i8)}
/* hero */
.sp-hero{min-height:min(100svh,960px);display:flex;align-items:flex-end;padding:96px 0 clamp(56px,9vh,110px)}
.sp-hero h1{margin:0 0 22px;font-weight:700;text-transform:uppercase;color:#fff;letter-spacing:.01em}
.sp-hero h1 span{display:block}
.sp-hero .k{font-size:clamp(22px,7.1vw,52px);line-height:1.1;letter-spacing:.07em;margin-bottom:10px;color:var(--i8);font-weight:500}
.sp-hero .b{font-size:clamp(42px,11.6vw,132px);line-height:.96;text-wrap:balance}
.sp-hero .sp-l{margin-bottom:30px}
.sp-cue{margin-top:44px;display:flex;align-items:center;gap:12px;font:500 11px/1 var(--f);letter-spacing:.24em;text-transform:uppercase;color:var(--i6)}
.sp-cue i{width:1px;height:34px;background:linear-gradient(var(--i6),transparent);animation:sp-c 2.4s ease-in-out infinite}
@keyframes sp-c{0%{transform:scaleY(.2);transform-origin:top}50%{transform:scaleY(1);transform-origin:top}51%{transform-origin:bottom}100%{transform:scaleY(.2);transform-origin:bottom}}
/* pills: every button is a 40px pill */
.sp .su-btn{appearance:none;-webkit-appearance:none;display:inline-flex;align-items:center;justify-content:center;gap:10px;height:40px;min-height:40px;padding:0 22px;border:1px solid rgba(240,240,250,.85);border-radius:9999px;background:rgba(0,0,0,.18);color:#fff;
 font:500 11px/1 var(--f);letter-spacing:.2em;text-transform:uppercase;text-decoration:none;cursor:pointer;white-space:nowrap;transition:background .25s,color .25s,border-color .25s;-webkit-tap-highlight-color:transparent}
.sp .su-btn .ic{width:18px;height:18px}
.sp .su-btn:hover,.sp .su-btn:focus-visible{background:#F0F0FA;color:#000;border-color:#F0F0FA}
.sp .su-btn.p{background:#F0F0FA;color:#000;border-color:#F0F0FA}
.sp .su-btn.p:hover,.sp .su-btn.p:focus-visible{background:transparent;color:#fff;border-color:rgba(240,240,250,.85)}
.sp .su-btn:focus-visible,.sp .su-tab:focus-visible{outline:1px solid #fff;outline-offset:4px}
.sp-acts{display:flex;flex-wrap:wrap;gap:12px}
.su-app .su-inst{display:none}
/* features: a hairline grid, no boxes */
.sp-f{padding:clamp(72px,12vh,150px) 0;background:#030304}
.sp-f .sp-h{max-width:900px}
.sp-fg{display:grid;grid-template-columns:repeat(2,1fr);margin:clamp(32px,6vh,64px) 0 0;border-top:1px solid var(--ln)}
.sp-fi{display:flex;flex-direction:column;gap:12px;padding:26px 18px 28px 0;border-bottom:1px solid var(--ln);text-decoration:none;color:var(--ink);transition:color .25s}
.sp-fi:nth-child(2n){padding-left:18px;border-left:1px solid var(--ln);padding-right:0}
.sp-fi .ic{width:34px;height:34px;color:#fff;stroke:none}
.sp-fi b{font:600 13px/1.2 var(--f);letter-spacing:.2em;text-transform:uppercase;color:#fff}
.sp-fi span{font:400 14px/1.5 var(--f);color:var(--i6)}
a.sp-fi:hover span,a.sp-fi:focus-visible span{color:var(--i8)}
a.sp-fi:focus-visible{outline:1px solid #fff;outline-offset:-1px}
/* alerts */
.sp-a{padding:clamp(72px,12vh,150px) 0}
.sp-a .sp-w{display:grid;grid-template-columns:1fr;gap:56px;align-items:center}
.sp-tr{margin:0 0 30px;padding:0;list-style:none;max-width:540px;border-top:1px solid var(--ln)}
.sp-tr li{display:flex;align-items:baseline;gap:18px;padding:14px 0;border-bottom:1px solid var(--ln)}
.sp-tr b{flex:none;width:58px;font:300 34px/1 var(--f);color:#fff;letter-spacing:.01em}
.sp-tr strong{display:block;font:600 12px/1.3 var(--f);letter-spacing:.18em;text-transform:uppercase;color:#fff}
.sp-tr span{display:block;margin-top:4px;font-size:14px;color:var(--i6)}
.sp-note{margin:18px 0 0;max-width:540px;font-size:13px;line-height:1.55;color:var(--i6)}
/* lock-screen mock (CSS/HTML): sample notification from the latest real rank 7+ story */
.sp-ph{position:relative;justify-self:center;width:min(290px,76vw);aspect-ratio:9/18.6;border:1px solid rgba(240,240,250,.32);border-radius:40px;padding:14px;background:linear-gradient(180deg,#14161b 0%,#050506 70%);box-shadow:0 30px 90px rgba(0,0,0,.7)}
.sp-ph::before{content:"";position:absolute;top:14px;left:50%;width:76px;height:20px;margin-left:-38px;border-radius:12px;background:#000;border:1px solid rgba(240,240,250,.1)}
.sp-lk{position:absolute;left:0;right:0;top:64px;text-align:center}
.sp-lk small{display:block;font:500 12px/1 var(--f);letter-spacing:.06em;color:var(--i6);min-height:12px}
.sp-lk b{display:block;margin-top:6px;font:200 66px/1 var(--f);letter-spacing:-.01em;color:#fff;min-height:66px;font-variant-numeric:tabular-nums}
.sp-nt{position:absolute;left:12px;right:12px;bottom:46px;display:flex;flex-direction:column;gap:8px}
.sp-n{padding:11px 13px 12px;border-radius:18px;background:rgba(60,64,74,.62);-webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px);border:1px solid rgba(240,240,250,.1);text-align:left;min-height:84px}
.sp-n[hidden]{display:none}
.sp-n+.sp-n{opacity:.78;transform:scale(.97)}
.sp-nh{display:flex;align-items:center;gap:7px;margin:0 0 6px;font:500 10px/1 var(--f);letter-spacing:.04em;text-transform:uppercase;color:var(--i6)}
.sp-nh img{width:16px;height:16px;border-radius:4px;display:block}
.sp-nh em{margin-left:auto;font-style:normal;letter-spacing:.04em;text-transform:none}
.sp-n strong{display:block;font:600 12.5px/1.3 var(--f);color:#fff;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.sp-n span{display:-webkit-box;margin-top:3px;font:400 11.5px/1.35 var(--f);color:var(--i8);-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.sp-hm{position:absolute;left:50%;bottom:10px;width:90px;height:4px;margin-left:-45px;border-radius:2px;background:rgba(240,240,250,.5)}
.sp-smp{display:block;margin:16px auto 0;text-align:center;font:500 10px/1.5 var(--f);letter-spacing:.18em;text-transform:uppercase;color:var(--i4);max-width:290px}
/* install: tabs + drawn steps */
.sp-i{padding:clamp(72px,12vh,150px) 0;background:#030304}
.sp-tabs{display:flex;flex-wrap:wrap;gap:10px;margin:clamp(24px,4vh,40px) 0 0;padding:0}
.sp .su-tab{appearance:none;-webkit-appearance:none;display:inline-flex;align-items:center;gap:9px;height:40px;min-height:40px;padding:0 20px;border:1px solid var(--ln);border-radius:9999px;background:transparent;color:var(--i8);
 font:500 11px/1 var(--f);letter-spacing:.18em;text-transform:uppercase;cursor:pointer;transition:background .25s,color .25s,border-color .25s;-webkit-tap-highlight-color:transparent}
.sp .su-tab .ic{width:18px;height:18px}
.sp .su-tab:hover{border-color:rgba(240,240,250,.6);color:#fff}
.sp .su-tab[aria-selected=true]{background:#F0F0FA;color:#000;border-color:#F0F0FA}
.sp .su-tab small{font:500 9px/1 var(--f);letter-spacing:.14em;opacity:.6}
.sp-p{margin-top:clamp(28px,5vh,56px)}
.js .sp-p[hidden]{display:none}
.sp-st{display:grid;grid-template-columns:repeat(2,1fr);gap:32px 16px;margin:0;padding:0;list-style:none}
.sp-st li{display:flex;flex-direction:column;gap:12px;min-width:0}
.sp-st .n{font:200 clamp(44px,5vw,64px)/1 var(--f);color:#fff;letter-spacing:-.01em;font-variant-numeric:tabular-nums}
.sp-st h3{margin:0;font:700 clamp(13px,1.1vw,15px)/1.25 var(--f);letter-spacing:.14em;text-transform:uppercase;color:#fff}
.sp-st p{margin:-6px 0 0;font-size:14px;line-height:1.45;color:var(--i6)}
.sp-st .scn{display:block;width:100%;max-width:230px;height:auto;margin:0 0 4px}
@media(max-width:699px){
 .sp-st,.sp-p[data-os=desktop] .sp-st{display:flex;gap:22px;overflow-x:auto;scroll-snap-type:x mandatory;-webkit-overflow-scrolling:touch;margin:0 calc(-1*clamp(20px,5.5vw,96px));padding:0 clamp(20px,5.5vw,96px) 14px;scroll-padding:0 clamp(20px,5.5vw,96px);scrollbar-width:none}
 .sp-st::-webkit-scrollbar{display:none}
 .sp-st li{flex:0 0 min(64vw,250px);scroll-snap-align:start}
 .sp-p[data-os=desktop] .sp-st li{flex-basis:84vw}
 .sp-st .scn{max-width:none}
}
.sp-st .scn.wide{max-width:none}
.sp-p[data-os=desktop] .sp-st{grid-template-columns:1fr}
.sp-note2{margin:34px 0 0;max-width:720px;font-size:13px;line-height:1.6;color:var(--i6)}
.sp-note2 p{margin:0 0 8px}
/* drawn scene paint */
.scn .pf{fill:#050506;stroke:rgba(240,240,250,.3);stroke-width:1.5}.scn .sc{fill:#0c0d10}.scn .pn{fill:#000;stroke:rgba(240,240,250,.14)}
.scn .tx{fill:#F0F0FA;font-family:Inter,"Helvetica Neue",Arial,sans-serif}.scn .mu{fill:rgba(240,240,250,.55);font-family:Inter,"Helvetica Neue",Arial,sans-serif}
.scn .dk{fill:#000;font-family:Inter,"Helvetica Neue",Arial,sans-serif}.scn .mu2{fill:rgba(240,240,250,.4)}
.scn .ln{fill:rgba(240,240,250,.17)}.scn .ln2{fill:rgba(240,240,250,.09)}.scn .bar{fill:#14161a}.scn .pill{fill:rgba(240,240,250,.1)}.scn .tab{fill:rgba(240,240,250,.1)}
.scn .dim{fill:rgba(0,0,0,.58)}.scn .shl{fill:#1b1d22;stroke:rgba(240,240,250,.12)}.scn .hlr{fill:rgba(240,240,250,.12);stroke:rgba(240,240,250,.5)}
.scn .btnw{fill:#F0F0FA}.scn .ap{fill:rgba(240,240,250,.12)}.scn .dock{fill:rgba(240,240,250,.1)}
.scn .ig{fill:#F0F0FA}.scn .ig.mu{fill:rgba(240,240,250,.55)}
.scn .ring{fill:none;stroke:#fff;stroke-width:1.6}.scn .ring.r2{opacity:.7;animation:sp-r 2.2s ease-out infinite;transform-box:fill-box;transform-origin:center}
@keyframes sp-r{0%{transform:scale(.7);opacity:.9}100%{transform:scale(1.7);opacity:0}}
/* closing */
.sp-z{min-height:min(86svh,780px);display:flex;align-items:center;padding:96px 0}
.sp-z .sp-h{font-size:clamp(38px,7.4vw,108px)}
.sp-foot{padding:26px 0 44px;background:#000;border-top:1px solid var(--ln);font:500 10px/1.6 var(--f);letter-spacing:.16em;text-transform:uppercase;color:var(--i4)}
.sp-foot a{color:var(--i6);text-decoration:none;margin-right:18px}.sp-foot a:hover{color:#fff}
.sp-in{opacity:0;transform:translateY(16px);transition:opacity .8s ease,transform .8s cubic-bezier(.2,.7,.2,1)}
.sp-in.sp-on,.no-js .sp-in{opacity:1;transform:none}
@media(min-width:700px){
 .sp-fg{grid-template-columns:repeat(4,1fr)}
 .sp-fi,.sp-fi:nth-child(2n){padding:30px 22px 34px;border-left:0;border-right:0}
 .sp-fi{border-left:1px solid var(--ln)}.sp-fi:nth-child(4n+1){border-left:0;padding-left:0}
 .sp-st{grid-template-columns:repeat(5,1fr);gap:28px 20px}
 .sp-p[data-os=desktop] .sp-st{grid-template-columns:repeat(3,1fr)}
}
@media(min-width:960px){
 .sp-a .sp-w{grid-template-columns:1.1fr .9fr;gap:80px}
}
@media(prefers-reduced-motion:reduce){.sp-in{opacity:1;transform:none;transition:none}.scn .ring.r2,.sp-cue i{animation:none}html{scroll-behavior:auto}}
"""

JS = r"""
<script>
(function(){
document.documentElement.classList.add("js");
var $=function(s,r){return (r||document).querySelector(s)},$$=function(s,r){return [].slice.call((r||document).querySelectorAll(s))};
/* buttons: BN.installApp / BN.showNotifyGuide / BN.enableAlerts (loaded on tap, never on load) */
function load(src,cb){var x=document.querySelector('script[src^="'+src+'"]');if(x){if(cb)x.addEventListener("load",cb);return}
var t=document.createElement("script");t.src=src;t.onload=cb||function(){};document.head.appendChild(t)}
function css(){if(document.querySelector('link[href*="install-guide.css"]'))return;var l=document.createElement("link");l.rel="stylesheet";l.href="/install-guide.css";document.head.appendChild(l)}
function go(k){
  var B=window.BN||{};
  if(k==="install"){if(B.installApp){B.installApp();return true}if(B.showInstallGuide){B.showInstallGuide();return true}return false}
  if(B.showNotifyGuide){B.showNotifyGuide();return true}
  if(B.enableAlerts){B.enableAlerts({});return true}
  return false;
}
function run(k){if(go(k))return;css();load("/alerts.js",function(){load("/install-guide.js",function(){go(k)})})}
document.addEventListener("click",function(e){var b=e.target.closest&&e.target.closest("[data-su]");if(!b)return;e.preventDefault();run(b.getAttribute("data-su"))});
/* installed already: hide Install App */
try{if((window.matchMedia&&matchMedia("(display-mode: standalone)").matches)||navigator.standalone)document.documentElement.classList.add("su-app")}catch(e){}
/* OS auto-detect: the visitor's steps first, the others one tap away */
function detect(){
  var u=navigator.userAgent||"",p=navigator.platform||"",t=navigator.maxTouchPoints||0;
  if(/iPhone|iPad|iPod/i.test(u)||(p==="MacIntel"&&t>1))return "ios";
  if(/Android/i.test(u))return "android";
  return "desktop";
}
var q=(location.search.match(/[?&]os=(ios|android|desktop)/)||[])[1],mine=q||detect(),tl=$("#su_tabs");
function pick(os,focus){
  $$(".su-tab",tl).forEach(function(b){var on=b.getAttribute("data-os")===os;b.setAttribute("aria-selected",on?"true":"false");b.tabIndex=on?0:-1;if(on&&focus)b.focus()});
  $$(".sp-p").forEach(function(p){p.hidden=p.getAttribute("data-os")!==os});
  var i=$("#install");if(i)i.setAttribute("data-os",os);
}
if(tl){
  var mt=$('.su-tab[data-os="'+mine+'"]',tl);if(mt){tl.insertBefore(mt,tl.firstChild);var s=document.createElement("small");s.textContent="Your device";mt.appendChild(s)}
  tl.addEventListener("click",function(e){var b=e.target.closest(".su-tab");if(b)pick(b.getAttribute("data-os"))});
  tl.addEventListener("keydown",function(e){
    var k=e.key,bs=$$(".su-tab",tl),i=bs.indexOf(document.activeElement);if(i<0)return;
    if(k==="ArrowRight"||k==="ArrowLeft"){e.preventDefault();var n=bs[(i+(k==="ArrowRight"?1:bs.length-1))%bs.length];pick(n.getAttribute("data-os"),true)}
  });
  pick(mine);
}
/* sample alert: the latest real rank 7+ stories on The Wire, labelled sample */
function cat(c){return ({"war/conflict":"War & conflict","natural disaster":"Natural disaster",political:"Politics",disease:"Disease",cyber:"Cyber",financial:"Financial","space weather":"Space weather"})[String(c||"").toLowerCase()]||"Alert"}
function first(t){t=String(t||"").split(/\n/)[0].replace(/\s+/g," ").trim();return t.length>150?t.slice(0,147).replace(/\s+\S*$/,"")+"…":t}
function setN(el,it,ex){
  if(!el)return;
  var n=it.eff_families||0,where=it.location&&String(it.location).length>3?it.location+". ":"";
  $("strong",el).textContent=first(it.title);
  $("span",el).textContent=ex?"Example only. Real alerts carry the story, where, and how many independent sources confirm it.":where+(n?"Confirmed by "+n+" independent source"+(n===1?"":"s")+". ":"")+"Tap for every source.";
  $("em",el).textContent=ex?"example":"now";el.hidden=false;
}
var sn=$$(".sp-n"),smp=$("#su_smp");
function clock(){var d=new Date();$("#su_t").textContent=d.toLocaleTimeString([],{hour:"numeric",minute:"2-digit"}).replace(/\s?[AP]M/i,"");$("#su_d").textContent=d.toLocaleDateString([],{weekday:"long",month:"long",day:"numeric"})}
try{clock()}catch(e){}
var since=new Date(Date.now()-14*864e5).toISOString().slice(0,19)+"Z";
fetch("/api/new_high?mode=alert&since="+since,{cache:"no-store"}).then(function(r){if(!r.ok)throw 0;return r.json()}).then(function(j){
  var its=(j.items||[]).filter(function(x){return x.rank>=7&&x.title}).sort(function(a,b){return (b.high_at||"").localeCompare(a.high_at||"")}).slice(0,2);
  if(!its.length)throw 0;
  its.forEach(function(it,i){setN(sn[i],it,false)});
  if(smp)smp.textContent="Sample · the latest rank 7+ stories on The Wire";
}).catch(function(){
  setN(sn[0],{title:"Major hurricane makes landfall; storm surge warnings in effect",eff_families:3,location:"Example City"},true);
  if(smp)smp.textContent="Sample · illustration only";
});
/* reveal on scroll (no-js shows everything) */
if("IntersectionObserver" in window){
  var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){e.target.classList.add("sp-on");io.unobserve(e.target)}})},{rootMargin:"0px 0px -8% 0px"});
  $$(".sp-in").forEach(function(el){io.observe(el)});
}else{$$(".sp-in").forEach(function(el){el.classList.add("sp-on")})}
})();
</script>
"""


def _steps(os_key):
    items = STEPS[os_key]
    li = "".join(f'<li><span class="n">{i + 1:02d}</span>{fn()}<h3>{E(t)}</h3><p>{E(d)}</p></li>' for i, (t, d, fn) in enumerate(items))
    n1, n2 = NOTES[os_key]
    return (f'<div class="sp-p" role="tabpanel" id="su_p_{os_key}" aria-labelledby="su_t_{os_key}" data-os="{os_key}">'
            f'<ol class="sp-st">{li}</ol><div class="sp-note2"><p>{E(n1)}</p><p>{E(n2)}</p></div></div>')


def _body():
    mv = _mv()
    feats = "".join(
        f'<a class="sp-fi sp-in" href="{E(h)}">{_ic(i)}<b>{E(t)}</b><span>{E(d)}</span></a>' for i, t, h, d in FEATURES)
    trig = "".join(f'<li><b>{E(a)}</b><div><strong>{E(b)}</strong><span>{E(c)}</span></div></li>' for a, b, c in TRIGGERS)
    tabs = "".join(
        f'<button type="button" class="su-tab" role="tab" id="su_t_{k}" data-os="{k}" aria-controls="su_p_{k}" aria-selected="{"true" if k == "ios" else "false"}">{_ic(ic)}{E(lab)}</button>'
        for k, lab, ic in TABS)
    panels = "".join(_steps(k) for k, _, _ in TABS)
    nt = (f'<div class="sp-n" hidden><p class="sp-nh"><img src="{ICON}" alt="" width="16" height="16" loading="lazy">BLACKOUT.NETWORK<em>now</em></p><strong></strong><span></span></div>')
    return f"""
<div class="sp" id="sp">
<section class="sp-s sp-hero" aria-labelledby="su_h1">
<div class="sp-bg" aria-hidden="true">{_pic(HERO, mv, True)}</div>
<div class="sp-w">
<p class="sp-eb"><i>01</i><span>The app</span></p>
<h1 id="su_h1"><span class="k">BLACKOUT.NETWORK</span><span class="b">on your home screen</span></h1>
<p class="sp-l">Live threats, outages and storms. Ranked, sourced, one tap away.</p>
<div class="sp-acts">
<a class="su-btn p su-inst" href="#install" data-su="install">{_ic("l-download-simple")}Install App</a>
<a class="su-btn" href="#notifications" data-su="notify">{_ic("l-bell-ringing")}Turn On Alerts</a>
</div>
<p class="sp-cue"><i></i><span>Scroll</span></p>
</div>
</section>

<section class="sp-s sp-f" aria-labelledby="su_h2">
<div class="sp-w">
<p class="sp-eb"><i>02</i><span>What you get</span></p>
<h2 class="sp-h" id="su_h2">The whole network. One icon.</h2>
<div class="sp-fg">{feats}</div>
</div>
</section>

<section class="sp-s sp-a" id="notifications" aria-labelledby="su_h3">
<div class="sp-bg" aria-hidden="true">{_pic(ALERT, mv)}</div>
<div class="sp-w">
<div class="sp-in">
<p class="sp-eb"><i>03</i><span>Alerts</span></p>
<h2 class="sp-h" id="su_h3">Know first.</h2>
<p class="sp-l">A push to your lock screen when something serious is confirmed. Nothing else.</p>
<ul class="sp-tr">{trig}</ul>
<div class="sp-acts"><a class="su-btn p" href="#notifications" data-su="notify">{_ic("l-bell-ringing")}Turn On Alerts</a></div>
<p class="sp-note">On iPhone and iPad, install the app first (iOS 16.4 or later), open it from the Home Screen, then tap Turn On Alerts. You can turn alerts off any time in your device or browser settings.</p>
</div>
<div class="sp-in">
<div class="sp-ph" role="img" aria-label="Sample lock screen with a BLACKOUT.NETWORK alert">
<div class="sp-lk"><small id="su_d"></small><b id="su_t"></b></div>
<div class="sp-nt">{nt}{nt}</div>
<i class="sp-hm"></i>
</div>
<span class="sp-smp" id="su_smp">Sample</span>
</div>
</div>
</section>

<section class="sp-s sp-i" id="install" data-os="ios" aria-labelledby="su_h4">
<div class="sp-w">
<p class="sp-eb"><i>04</i><span>Install</span></p>
<h2 class="sp-h" id="su_h4">Three taps to the Home Screen.</h2>
<p class="sp-l">Pick your device. It opens full screen like any app.</p>
<div class="sp-tabs" id="su_tabs" role="tablist" aria-label="Your device">{tabs}</div>
{panels}
<div class="sp-acts" style="margin-top:34px"><a class="su-btn p su-inst" href="#install" data-su="install">{_ic("l-download-simple")}Install App</a></div>
</div>
</section>

<section class="sp-s sp-z" aria-labelledby="su_h5">
<div class="sp-bg" aria-hidden="true">{_pic(CLOSE, mv)}</div>
<div class="sp-w sp-in">
<h2 class="sp-h" id="su_h5">Be the first to know.</h2>
<p class="sp-l">Free. No account.</p>
<div class="sp-acts">
<a class="su-btn p su-inst" href="#install" data-su="install">{_ic("l-download-simple")}Install App</a>
<a class="su-btn" href="#notifications" data-su="notify">{_ic("l-bell-ringing")}Turn On Alerts</a>
</div>
</div>
</section>
<div class="sp-foot"><div class="sp-w"><a href="/credits">Image credits</a><a href="/privacy">Privacy</a><a href="/tos">Terms</a><span>Icons: Phosphor, MIT</span></div></div>
</div>
"""


def page():
    body = (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1,viewport-fit=cover\">"
        + sitenav.head_html("setup", "/setup")
        + "<link rel=\"stylesheet\" href=\"/theme.css\"><link rel=\"icon\" href=\"/favicon.ico?v=5\" sizes=\"any\">"
        f"<style>{CSS}</style></head>"
        "<body><a class=\"skip\" href=\"#main\">Skip to content</a>"
        + sitenav.header_html(sitenav.PAGES["setup"][0])
        + SPRITE + CLIPS
        + "<div id=\"su_main\"><main id=\"main\">" + _body() + "</main></div>"
        + JS
        + "</body></html>"
    )
    low = body.lower()
    if "peer-to-peer" in low or "peer to peer" in low:
        raise RuntimeError("setup page copy must not say peer-to-peer")
    return body


def handle_get(path, qs):
    p = (path or "").rstrip("/") or "/setup"
    if p != "/setup":
        return 404, {"error": "not found"}
    return 200, page().encode("utf-8"), "text/html"
