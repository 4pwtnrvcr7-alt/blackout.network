""" /welcome — first-visit onboarding for BLACKOUT.NETWORK (t1305u).

A warm, simple, conversion-focused walkthrough: what this is, interests, the Free brief
(real 7 AM / 7 PM ET slots and real interest categories), how confirmation works, how to
install it on a phone, how to turn on alerts, follow YouTube and X, then a tour of the tools.

Copy and options are drawn from existing site text and the live newsletter/PWA/push code.
No invented claims, times, or categories. No new third-party scripts. Red only for rank 7+.
"""
import html, json, os

E = lambda s: html.escape(str(s if s is not None else ""), quote=True)

FIRST_MODES = ("banner", "redirect")
VIDEO_SRC = ""  # hidden unless an approved same-origin intro exists; do not autoplay sound
YT_SUB = "https://www.youtube.com/@blkoutntw?sub_confirmation=1"
X_URL = "https://x.com/BlkoutNtw"
BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "static")

# Newsletter categories we surface as chips (exact keys from newsletter.CATEGORIES).
CHIP_CATS = [
    ("war/conflict", "War and conflict", "Armed conflict and related crises."),
    ("natural disaster", "Weather and disasters", "Storms, quakes, floods and official disaster alerts."),
    ("space weather", "Solar and space weather", "Solar flares, storms and the Kp index."),
    ("disease", "Health and outbreaks", "Disease outbreaks and public-health threats."),
    ("cyber", "Cyber", "Cyber attacks and infrastructure breaches."),
    ("political", "Politics and government", "Government actions, emergency declarations and political crises."),
]
MORE_CATS = [
    ("financial", "Markets"),
    ("ufo/uap", "UFO / UAP"),
    ("spiritual/religious", "Spiritual and religious"),
    ("other", "Other"),
]
# Site tools that are not newsletter categories — stored locally only, not sent as interests.
EXTRA_TOOLS = [
    ("grid", "Energy Grid", "/#grid"),
    ("ai", "AI Threats", "/#ai"),
]


def first_mode():
    return (os.environ.get("BN_WELCOME_FIRST") or "off").strip().lower()


def prompt_html():
    """Inline banner/redirect hook for the shared header. Empty when the flag is off (default)."""
    mode = first_mode()
    if mode not in FIRST_MODES:
        return ""
    m = json.dumps(mode)
    return (
        '<style id="bn_wel_css">'
        ".bn-welbar{box-sizing:border-box;display:flex;align-items:center;justify-content:space-between;gap:12px;"
        "padding:10px max(16px,env(safe-area-inset-right)) 10px max(16px,env(safe-area-inset-left));"
        "background:var(--bn-surface,#14181D);color:var(--bn-text,#E6E9EE);"
        "border-bottom:1px solid var(--bn-line,#252B33);font:500 15px/1.4 var(--bn-font-body,Inter,system-ui,sans-serif)}"
        ".bn-welbar a{color:var(--bn-text,#E6E9EE);font-weight:600;text-decoration:none;border-bottom:2px solid #FFC21A}"
        "html[data-theme=light] .bn-welbar a{color:var(--bn-text,#0B0D10)}"
        ".bn-welbar button{flex:none;min-width:44px;min-height:44px;margin:0;padding:0 8px;border:0;border-radius:8px;"
        "background:transparent;color:var(--bn-muted,#8B95A3);font:600 14px/1 var(--bn-font-ui,Montserrat,system-ui,sans-serif);cursor:pointer}"
        ".bn-welbar button:hover,.bn-welbar button:focus-visible{background:var(--bn-hover,rgba(255,255,255,.06));color:var(--bn-text,#E6E9EE)}"
        "</style>"
        '<script id="bn_wel_first">(function(){var MODE=' + m + ',KEY="bn_welcome_seen";'
        'function seen(){try{return localStorage.getItem(KEY)==="1"}catch(e){return false}}'
        'function mark(){try{localStorage.setItem(KEY,"1")}catch(e){}}'
        'var p=(location.pathname||"/").replace(/\\/+$/,"")||"/";'
        'if(p==="/welcome"){mark();return}'
        'if(seen())return;'
        'if(MODE==="redirect"){var h=(location.hash||"").replace(/^#/,"");'
        'if(p==="/"&&(!h||h==="home")){location.replace("/welcome");return}}'
        'function bar(){if(seen()||document.getElementById("bn_welbar"))return;'
        'var t=document.getElementById("bn_topbar");if(!t)return;'
        'var b=document.createElement("div");b.id="bn_welbar";b.className="bn-welbar";b.setAttribute("role","region");'
        'b.setAttribute("aria-label","Welcome");'
        'b.innerHTML=\'<a href="/welcome">New here? Start here</a><button type="button" aria-label="Dismiss">Dismiss</button>\';'
        'b.querySelector("button").addEventListener("click",function(){mark();b.remove()});'
        'b.querySelector("a").addEventListener("click",function(){mark()});'
        't.insertAdjacentElement("afterend",b)}'
        'if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",bar);else bar()'
        '})()</script>'
    )


def _ico(paths):
    return ('<svg class="wel-ico" viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" '
            'stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">'
            + paths + "</svg>")


ICONS = {
    "wire": _ico('<path d="M4 7h16M4 12h10M4 17h13"/><circle cx="18.5" cy="12" r="2"/>'),
    "score": _ico('<rect x="3" y="13" width="3.2" height="8" rx=".4"/><rect x="8" y="9" width="3.2" height="12" rx=".4"/>'
                  '<rect x="13" y="5" width="3.2" height="16" rx=".4"/><rect x="18" y="3" width="3.2" height="18" rx=".4"/>'),
    "alerts": _ico('<path d="M6 9a6 6 0 0 1 12 0c0 7 3 8 3 8H3s3-1 3-8"/><path d="M10 20a2 2 0 0 0 4 0"/>'),
    "brief": _ico('<rect x="3.5" y="5" width="17" height="14" rx="2"/><path d="M3.5 8h17"/><path d="m7 12 3 2 4-3"/>'),
    "grid": _ico('<path d="M13 3v7h8"/><path d="M13 10 7 21"/><path d="M9 3h10l-3 5"/>'),
    "ai": _ico('<rect x="7" y="7" width="10" height="10" rx="2"/><path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l3 3M15 15l3 3M18 6l-3 3M9 15l-3 3"/>'),
    "solar": _ico('<circle cx="12" cy="12" r="3.4"/><path d="M12 3.5v2.2M12 18.3v2.2M4.7 4.7l1.6 1.6M17.7 17.7l1.6 1.6M3.5 12h2.2M18.3 12h2.2M4.7 19.3l1.6-1.6M17.7 6.3l1.6-1.6"/>'),
    "weather": _ico('<path d="M7 16.5h11a3.5 3.5 0 0 0 0-7 5 5 0 0 0-9.6-1.4A3.6 3.6 0 0 0 7 16.5z"/>'),
    "bcast": _ico('<circle cx="12" cy="18" r="1.2" fill="currentColor" stroke="none"/>'
                  '<path d="M8.2 15.2a5.5 5.5 0 0 1 7.6 0M5.5 12.2a9 9 0 0 1 13 0M3.2 9.2a12.5 12.5 0 0 1 17.6 0"/>'),
    "net": _ico('<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>'),
    "bush": _ico('<path d="M12 21V11"/><path d="M12 14c-3-1-5-4-5-8 3 0 5 2 5 5 0-3 2-5 5-5 0 4-2 7-5 8z"/>'),
    "gov": _ico('<path d="M4 10h16M6 10v8M10 10v8M14 10v8M18 10v8M3 18h18M12 4l9 6H3z"/>'),
    "sources": _ico('<path d="M5 5.5A2.5 2.5 0 0 1 7.5 3H19v15H7.5A2.5 2.5 0 0 0 5 20.5z"/><path d="M5 5.5v15A2.5 2.5 0 0 1 7.5 18H19"/>'),
    "social": _ico('<rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="m10 9 6 3-6 3z"/>'),
}

TOOLS = [
    ("wire", "The Wire", "The live threat feed, ranked 0–10 and linked to its sources.", "/#wire"),
    ("score", "How we score", "The 0–100 score and the 0–10 rank, explained factor by factor.", "/scoring"),
    ("alerts", "Alerts", "Instant push alerts, sent only for rank 7+ stories confirmed by independent sources.", None),
    ("brief", "Free brief", "The highest-ranked events of the day, in one email. Free, double opt-in.", "/newsletter"),
    ("grid", "Energy Grid", "U.S. power grid status, local outages and weather-driven stress.", "/#grid"),
    ("ai", "AI Threats", "AI-assisted attacks, deepfake fraud and model misuse, ranked 0–10.", "/#ai"),
    ("solar", "Solar & Seismic", "Solar flares, geomagnetic storms, the Kp index and live global quakes.", "/#solar"),
    ("weather", "Weather", "Conditions, official severe-weather alerts and the forecast for any place.", "/#weather"),
    ("bcast", "Live Broadcasts", "Live wire, TV and radio, searched for threat keywords around the clock.", "/#broadcasts"),
    ("net", "Network Status", "Internet, cloud, apps and ISPs, with outage alerts and recent history.", "/#network"),
    ("bush", "Bushcraft", "A grid-down guide: water, fire, shelter, food, navigation and signaling.", "/#bushcraft"),
    ("gov", "Government", "A 0–100 U.S. government health index, plus who holds office.", "/#government"),
    ("sources", "Sources", "Every source we use, with a transparent 0–10 confidence rating.", "/sources"),
    ("social", "Videos & posts", "Our YouTube and X reports, each with a sourced write-up on this site.", "/social"),
]
ALSO = [
    ("Heat Map", "/#heatmap"), ("Local Resources", "/#resources"), ("Offline Maps", "/#maps"),
    ("First Aid", "/#medical"), ("Everyday Readiness", "/ready"), ("Crime", "/crime"),
    ("Midterms 2026", "/midterms"), ("Public stats", "/stats"),
]


def _ampm(hhmm):
    try:
        h, m = [int(x) for x in str(hhmm).split(":")[:2]]
    except Exception:
        return str(hhmm) + " ET"
    ap = "AM" if h < 12 else "PM"
    h = h % 12 or 12
    return f"{h}:{m:02d} {ap} ET"


def _asset(name, ctype):
    with open(os.path.join(STATIC, name), "rb") as f:
        return 200, f.read(), ctype


def _card(key, title, desc, href):
    ic = f'<span class="wel-ic">{ICONS[key]}</span><span><h3>{E(title)}</h3><p>{E(desc)}</p></span>'
    if href:
        return f'<a class="wel-card" href="{E(href)}">{ic}</a>'
    return f'<button type="button" class="wel-card" data-bn-alerts>{ic}</button>'


def _video():
    if not VIDEO_SRC:
        return ('<figure class="wel-video" hidden>'
                "<figcaption>A short intro can go here once one is approved. Sound will not autoplay.</figcaption></figure>")
    src = E(VIDEO_SRC)
    return (f'<figure class="wel-video is-on"><video src="{src}" playsinline controls preload="metadata" '
            f'controlslist="nodownload" aria-label="Introduction to BLACKOUT.NETWORK"></video></figure>')


def _network_art():
    return (
        '<div class="wel-plx" aria-hidden="true"><svg viewBox="0 0 800 600" preserveAspectRatio="xMidYMid slice">'
        '<g data-depth="0.06" fill="none" stroke="#FFC21A" stroke-opacity=".18" stroke-width="1.2">'
        '<path d="M400 520 L260 360 L180 300 M400 520 L540 350 L640 280 M400 520 L400 240 L520 140 M400 520 L280 200 L160 120"/>'
        '<path d="M260 360 L400 240 L540 350 M180 300 L280 200 L400 240 L640 280"/></g>'
        '<g data-depth="0.16">'
        '<circle cx="400" cy="520" r="7" fill="#FFC21A"/>'
        '<circle cx="260" cy="360" r="4.5" fill="#FFC21A" fill-opacity=".85"/>'
        '<circle cx="540" cy="350" r="4.5" fill="#FFC21A" fill-opacity=".85"/>'
        '<circle cx="430" cy="300" r="5" fill="#E6E9EE"/>'
        '<circle cx="180" cy="300" r="3.5" fill="#8B95A3"/>'
        '<circle cx="640" cy="280" r="3.5" fill="#8B95A3"/>'
        '<circle cx="120" cy="250" r="3.5" fill="#8B95A3"/>'
        '<circle cx="520" cy="140" r="3.5" fill="#8B95A3"/>'
        '<circle cx="90" cy="80" r="3" fill="#8B95A3"/>'
        '</g></svg></div>'
    )


def _phone_svg(kind):
    """Stylized phone/desktop chrome in our palette. No vendor logos."""
    if kind == "iphone":
        return (
            '<svg class="wel-ill" viewBox="0 0 200 280" role="img" aria-label="Three steps: Share, Add to Home Screen, open the app">'
            '<rect x="8" y="8" width="184" height="264" rx="28" fill="#14181D" stroke="#252B33"/>'
            '<rect x="80" y="18" width="40" height="6" rx="3" fill="#252B33"/>'
            '<circle cx="100" cy="70" r="16" fill="none" stroke="#FFC21A" stroke-width="2"/>'
            '<path d="M100 62v10m0 0l-4-4m4 4l4-4" stroke="#FFC21A" stroke-width="2" fill="none" stroke-linecap="round"/>'
            '<rect x="36" y="118" width="128" height="36" rx="8" fill="#1B2027"/>'
            '<rect x="36" y="118" width="128" height="36" rx="8" fill="none" stroke="#FFC21A"/>'
            '<text x="100" y="141" text-anchor="middle" fill="#E6E9EE" font-size="11" font-family="Inter,system-ui" font-weight="700">Add to Home Screen</text>'
            '<rect x="78" y="180" width="44" height="44" rx="10" fill="#0B0D10" stroke="#FFC21A"/>'
            '<text x="100" y="244" text-anchor="middle" fill="#8B95A3" font-size="9" font-family="Inter,system-ui">BLACKOUT</text>'
            "</svg>"
        )
    if kind == "android":
        return (
            '<svg class="wel-ill" viewBox="0 0 200 280" role="img" aria-label="Three steps: menu, Add to home screen, Allow notifications">'
            '<rect x="8" y="8" width="184" height="264" rx="22" fill="#14181D" stroke="#252B33"/>'
            '<circle cx="154" cy="36" r="3" fill="#E6E9EE"/><circle cx="166" cy="36" r="3" fill="#E6E9EE"/><circle cx="178" cy="36" r="3" fill="#E6E9EE"/>'
            '<rect x="44" y="86" width="120" height="36" rx="8" fill="#1B2027"/>'
            '<rect x="44" y="132" width="120" height="36" rx="8" fill="none" stroke="#FFC21A"/>'
            '<text x="104" y="155" text-anchor="middle" fill="#E6E9EE" font-size="10" font-family="Inter,system-ui" font-weight="700">Add to home screen</text>'
            '<rect x="44" y="186" width="120" height="36" rx="8" fill="#1B2027"/>'
            '<text x="104" y="209" text-anchor="middle" fill="#E6E9EE" font-size="10" font-family="Inter,system-ui" font-weight="700">Allow</text>'
            "</svg>"
        )
    return (
        '<svg class="wel-ill" viewBox="0 0 280 180" overflow="hidden" role="img" aria-label="A browser window with an install icon in the address bar">'
        '<rect x="8" y="8" width="264" height="164" rx="12" fill="#14181D" stroke="#252B33"/>'
        '<rect x="8" y="8" width="264" height="28" rx="12" fill="#1B2027"/>'
        '<rect x="8" y="22" width="264" height="14" fill="#1B2027"/>'
        '<circle cx="24" cy="22" r="4" fill="#3FAE80"/><circle cx="38" cy="22" r="4" fill="#F5A524"/><circle cx="52" cy="22" r="4" fill="#8B95A3"/>'
        '<rect x="68" y="14" width="160" height="16" rx="8" fill="#0B0D10"/>'
        '<rect x="214" y="15" width="14" height="14" rx="3" fill="none" stroke="#FFC21A"/>'
        '<path d="M221 20v6h-4l6 5 6-5h-4v-6z" fill="#FFC21A"/>'
        '<text x="140" y="108" text-anchor="middle" fill="#E6E9EE" font-size="13" font-family="Montserrat,system-ui" font-weight="700">Install BLACKOUT</text>'
        "</svg>"
    )


def _dots():
    labels = [("hero", "Welcome"), ("interests", "Interests"), ("brief", "The brief"),
              ("inbox", "Confirm"), ("install", "Install"), ("follow", "Follow us"), ("tools", "Tools")]
    return '<nav class="wel-dots" aria-label="Onboarding steps">' + "".join(
        f'<a href="#{k}" data-step="{k}"' + (' class="on"' if k == "hero" else "") + f">{E(lab)}</a>" for k, lab in labels
    ) + "</nav>"


def _step(sid, title, body, h=2):
    tag = "h1" if h == 1 else "h2"
    on = " is-on" if sid == "hero" else ""
    return (f'<section class="wel-step{on}" id="step-{sid}" data-step="{sid}" aria-labelledby="h-{sid}">'
            f'<{tag} id="h-{sid}">{title}</{tag}>{body}</section>')


def _render():
    import sitenav
    try:
        import newsletter as nl
        csrf = nl.csrf_token()
        freqs = nl.FREQS
        slots = (nl.cfg() or {}).get("slots") or {"morning": "07:00", "evening": "19:00"}
        ttl = int((nl.cfg() or {}).get("confirm_ttl_hours") or 48)
        from_name = (nl.cfg() or {}).get("from_name") or "BLACKOUT.NETWORK"
        from_email = (nl.cfg() or {}).get("from_email") or "hello@blackout.network"
        consent = nl.consent_line()
        track_label = getattr(nl, "TRACK_CONSENT_LABEL",
                              "Let BLACKOUT.NETWORK count when I open its emails and which links I click.")
    except Exception:
        csrf, freqs = "", {"twice": "Twice daily (morning + evening)",
                           "morning": "Once daily: morning", "evening": "Once daily: evening"}
        slots, ttl = {"morning": "07:00", "evening": "19:00"}, 48
        from_name, from_email = "BLACKOUT.NETWORK", "hello@blackout.network"
        consent = ("By tapping Get the brief, you agree to get the BLACKOUT.NETWORK brief by email from "
                   "BLACKOUT.NETWORK (hello@blackout.network). We will send a confirmation email first. "
                   "You can unsubscribe at any time. See our Privacy Policy and Terms.")
        track_label = "Let BLACKOUT.NETWORK count when I open its emails and which links I click."
    morn, eve = _ampm(slots.get("morning", "07:00")), _ampm(slots.get("evening", "19:00"))
    freq_help = {"twice": f"{morn} and {eve}", "morning": morn, "evening": eve}

    chips = "".join(
        f'<button type="button" class="wel-chip" data-cat="{E(k)}" aria-pressed="false">{E(lab)}<small>{E(hint)}</small></button>'
        for k, lab, hint in CHIP_CATS)
    more = "".join(
        f'<button type="button" class="wel-chip" data-cat="{E(k)}" aria-pressed="false">{E(lab)}</button>'
        for k, lab in MORE_CATS)
    extras = "".join(
        f'<button type="button" class="wel-chip" data-extra="{E(k)}" aria-pressed="false">{E(lab)}<small>On the site</small></button>'
        for k, lab, _h in EXTRA_TOOLS)
    hidden_ints = "".join(
        f'<input type="checkbox" name="interests" value="{E(k)}" hidden>'
        for k, *_rest in list(CHIP_CATS) + [(a, b) for a, b in MORE_CATS])
    freq_radios = "".join(
        f'<label><input type="radio" name="frequency" value="{E(k)}"'
        f'{" checked" if k == "twice" else ""}><span>{E(v)}'
        f'<small>({E(freq_help[k])})</small></span></label>'
        for k, v in freqs.items())
    cards = "".join(_card(*row) for row in TOOLS)
    also = " · ".join(f'<a href="{E(h)}">{E(t)}</a>' for t, h in ALSO)

    hero = _step("hero", "Welcome in.",
        '<p class="wel-lede">This is BLACKOUT.NETWORK — a free, sourced early-warning feed for real threats, '
        "ranked as they happen, and a set of tools you can use when you need them.</p>"
        '<p class="wel-by">Created by humans. Powered by Superintelligence. Signal over noise.</p>'
        + _video()
        + '<ul class="wel-goals">'
        "<li><p>We track outbreaks, earthquakes, space weather, severe weather, cyber attacks, infrastructure "
        "outages and conflict, rank every story 0–10 with published rules, and link every report to its original source.</p></li>"
        "<li><p>An instant alert goes out only when a story is <span class=\"wel-r7\">rank 7+</span> and confirmed by independent sources.</p></li>"
        "<li><p>The data is for research and situational awareness only. This is not an official warning service. "
        "Follow official agencies for instructions in an emergency.</p></li></ul>"
        '<p class="wel-cta"><button type="button" class="wel-btn" data-next>Get started</button>'
        '<a class="wel-btn wel-btn-2" href="/#wire">Skip to The Wire</a></p>', 1)

    interests = _step("interests", "What should we watch for you?",
        "<p class=\"wel-lede\">Pick any that matter. If you skip this, you will get every category in the brief. You can change it later.</p>"
        f'<div class="wel-chips" role="group" aria-label="Brief topics">{chips}</div>'
        f'<details class="wel-more"><summary>More topics</summary><div class="wel-chips">{more}</div></details>'
        '<p class="wel-kicker" style="margin-top:22px">On the site</p><p class="wel-note">These two are tools on the site. The brief does not have a separate category for them yet.</p>'
        f'<div class="wel-chips" role="group" aria-label="Site tools">{extras}</div>'
        '<div class="wel-loc"><p class="wel-lede" style="font-size:16px;margin-top:20px">Want a Near you section in the brief?</p>'
        '<p class="wel-note">Type a US ZIP code, a city (for example Denver, CO) or a country. We store only the place name and a rough location, never a street address. Nothing is filled in until you choose.</p>'
        '<label class="wel-el" for="wel_loc">Your area (optional)</label>'
        '<input id="wel_loc" type="text" name="location" form="wel_form" maxlength="80" autocomplete="postal-code" placeholder="e.g. 80202, Denver, CO or Germany">'
        "</div>"
        '<p class="wel-cta"><button type="button" class="wel-btn" data-next>Continue</button>'
        '<button type="button" class="wel-btn wel-btn-2" data-next>Skip — I will get every category</button></p>')

    brief = _step("brief", "Get the Free brief.",
        f'<p class="wel-lede">The highest-ranked events of the day, in one email. Morning at {E(morn)}, evening at {E(eve)}, or both. Free, and you confirm before anything arrives.</p>'
        f'<form id="wel_form" class="wel-form" method="post" action="/api/newsletter/subscribe" novalidate>'
        f'<input type="hidden" name="csrf" value="{E(csrf)}"><input type="hidden" name="source" value="welcome">{hidden_ints}'
        '<label class="wel-el" for="wel_email">Email address</label>'
        '<input id="wel_email" type="email" name="email" required maxlength="254" autocomplete="email" inputmode="email" placeholder="you@example.org" aria-describedby="wel_msg">'
        f'<fieldset class="wel-freq"><legend>When should it arrive?</legend>{freq_radios}</fieldset>'
        '<div class="wel-crime" hidden><label class="wel-chip" style="flex-direction:row;align-items:center;gap:8px;margin-top:10px">'
        '<input type="checkbox" name="crime_brief" value="1"> Include a local crime summary in my briefs</label>'
        '<label class="wel-chip" style="flex-direction:row;align-items:center;gap:8px">'
        '<input type="checkbox" name="crime_alerts" value="1"> Real-time crime alerts for my area (cities with live police data)</label></div>'
        f'<div class="wel-trk nl-trk" hidden><label>'
        f'<input type="checkbox" name="track_consent" value="1"> {E(track_label)}</label></div>'
        '<div class="wel-hp" aria-hidden="true"><label>Leave this empty <input type="text" name="website" tabindex="-1" autocomplete="off"></label></div>'
        '<p class="wel-msg" id="wel_msg" role="status" aria-live="polite"></p>'
        '<p class="wel-cta"><button class="wel-btn" type="submit">Get the brief</button></p>'
        f'<p class="wel-priv">{consent} Research only. Not an official warning service.</p>'
        "</form>")

    inbox = _step("inbox", "Check your inbox.",
        "<p class=\"wel-lede\">Almost done. If that address can be subscribed, a confirmation email is on its way. Nothing else is sent until you confirm.</p>"
        '<div class="wel-mail" aria-label="What the confirmation email looks like">'
        f'<p class="from">From: {E(from_name)} &lt;{E(from_email)}&gt;</p>'
        f'<p class="subj">Confirm your BLACKOUT.NETWORK newsletter subscription</p>'
        '<p class="fake-btn" aria-hidden="true">Confirm subscription</p>'
        "</div>"
        '<ol class="wel-steps3">'
        "<li><span class=\"wel-n\" aria-hidden=\"true\">1</span><div><h3 style=\"margin:2px 0 4px;font:700 16px/1.25 var(--bn-font-ui,Montserrat,system-ui,sans-serif)\">Open that email</h3>"
        f"<p style=\"margin:0;color:var(--bn-text-2,#c9d0d9)\">Look for {E(from_name)} at {E(from_email)}. The subject is “Confirm your BLACKOUT.NETWORK newsletter subscription.”</p></div></li>"
        "<li><span class=\"wel-n\" aria-hidden=\"true\">2</span><div><h3 style=\"margin:2px 0 4px;font:700 16px/1.25 var(--bn-font-ui,Montserrat,system-ui,sans-serif)\">Tap Confirm subscription</h3>"
        f"<p style=\"margin:0;color:var(--bn-text-2,#c9d0d9)\">The link expires in {ttl} hours. If you did not ask for this, you can ignore the email and nothing will be sent.</p></div></li>"
        "<li><span class=\"wel-n\" aria-hidden=\"true\">3</span><div><h3 style=\"margin:2px 0 4px;font:700 16px/1.25 var(--bn-font-ui,Montserrat,system-ui,sans-serif)\">Do not see it?</h3>"
        "<p style=\"margin:0;color:var(--bn-text-2,#c9d0d9)\">Check spam or Promotions. After you confirm, the brief starts with the next scheduled morning or evening send.</p></div></li>"
        "</ol>"
        '<p class="wel-cta"><button type="button" class="wel-btn" data-next>Next: add it like an app</button></p>')

    install = _step("install", "Add it like an app.",
        '<p class="wel-lede">It is free, and there is no app-store download. Pick your device if we guessed wrong, then follow the short steps.</p>'
        '<div class="wel-install" data-device="desktop">'
        '<div class="wel-devs" role="group" aria-label="Your device">'
        '<button type="button" class="wel-dev" data-device="iphone">iPhone</button>'
        '<button type="button" class="wel-dev" data-device="android">Android</button>'
        '<button type="button" class="wel-dev" data-device="desktop">Computer</button>'
        "</div>"
        '<div class="wel-guide" data-for="iphone">'
        + _phone_svg("iphone")
        + '<ol class="wel-steps3">'
        "<li><span class=\"wel-n\" aria-hidden=\"true\">1</span><div><p style=\"margin:0\">In Safari, tap <b>Share</b>.</p></div></li>"
        "<li><span class=\"wel-n\" aria-hidden=\"true\">2</span><div><p style=\"margin:0\">Tap <b>Add to Home Screen</b>, then <b>Add</b>. If you do not see it, scroll down or tap View More.</p></div></li>"
        "<li><span class=\"wel-n\" aria-hidden=\"true\">3</span><div><p style=\"margin:0\">Open BLACKOUT from your Home Screen, then tap <b>Turn on alerts</b>. "
        "Notifications need iOS 16.4 or newer, and they only work when you open the site from that Home Screen icon, not from a Safari tab.</p></div></li>"
        "</ol></div>"
        '<div class="wel-guide" data-for="android" hidden>'
        + _phone_svg("android")
        + '<ol class="wel-steps3">'
        "<li><span class=\"wel-n\" aria-hidden=\"true\">1</span><div><p style=\"margin:0\">In Chrome, tap the menu (three dots).</p></div></li>"
        "<li><span class=\"wel-n\" aria-hidden=\"true\">2</span><div><p style=\"margin:0\">Tap <b>Add to home screen</b> or <b>Install app</b>.</p></div></li>"
        "<li><span class=\"wel-n\" aria-hidden=\"true\">3</span><div><p style=\"margin:0\">Tap <b>Turn on alerts</b> and choose <b>Allow</b>.</p></div></li>"
        "</ol></div>"
        '<div class="wel-guide" data-for="desktop" hidden>'
        + _phone_svg("desktop")
        + '<ol class="wel-steps3">'
        "<li><span class=\"wel-n\" aria-hidden=\"true\">1</span><div><p style=\"margin:0\">In Chrome or Edge, click the install icon in the address bar, or open the menu and choose Install. "
        "In Safari on a Mac, choose <b>File</b>, then <b>Add to Dock</b>.</p></div></li>"
        "<li><span class=\"wel-n\" aria-hidden=\"true\">2</span><div><p style=\"margin:0\">Open it from your Dock or applications list, then click <b>Turn on alerts</b> and choose <b>Allow</b>.</p></div></li>"
        "</ol></div>"
        '<p class="wel-cta"><button type="button" class="wel-btn wel-alerts-btn" data-bn-alerts>Turn on alerts</button>'
        '<button type="button" class="wel-btn wel-btn-2" data-install-guide>Show me how</button></p>'
        '<p class="wel-alerts-status">Alerts are sent only for <span class="wel-r7">rank 7+</span> stories confirmed by independent sources.</p>'
        '<p class="wel-cta"><button type="button" class="wel-btn" data-next>Continue</button></p>'
        "</div>")

    follow = _step("follow", "Keep the signal close.",
        '<p class="wel-lede">A short follow means you will see the same sourced reports when they go out on YouTube and X.</p>'
        '<div class="wel-follow-row">'
        f'<a href="{E(YT_SUB)}" target="_blank" rel="noopener me">YouTube @BlkoutNtw<span>Opens a subscribe confirmation for the BLACKOUT.NETWORK channel.</span></a>'
        f'<a href="{E(X_URL)}" target="_blank" rel="noopener me">X @BlkoutNtw<span>Follow the same reports on X.</span></a>'
        "</div>"
        '<p class="wel-cta"><button type="button" class="wel-btn" data-next>See the tools</button></p>')

    tools = _step("tools", "The tools, in one place.",
        '<p class="wel-lede">Everything below is live on this site. Open any of them, or start on The Wire — the live feed, ranked as it happens.</p>'
        f'<div class="wel-grid">{cards}</div>'
        f'<p class="wel-also">Also in the menu: {also}.</p>'
        '<p class="wel-cta"><a class="wel-btn" href="/#wire">Open The Wire</a>'
        '<a class="wel-btn wel-btn-2" href="/newsletter">Newsletter page</a></p>')

    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        + sitenav.head_html("welcome")
        + '<link rel="stylesheet" href="/theme.css"><link rel="stylesheet" href="/welcome.css">'
        '<link rel="icon" href="/favicon.ico?v=3" sizes="any"></head><body>'
        '<a class="skip" href="#main">Skip to content</a>'
        + sitenav.header_html("welcome")
        + '<div class="wel-shell"><div class="wel-bar">'
        '<button type="button" class="wel-navbtn" data-back hidden>Back</button>'
        + _dots()
        + '<a class="wel-skip" href="/#wire">Skip to The Wire</a></div>'
        + _network_art()
        + f'<main class="wel-stage" id="main">{hero}{interests}{brief}{inbox}{install}{follow}{tools}</main></div>'
        '<footer class="wel-foot"><p>Research-only data. Not official alerts.</p>'
        '<p><a href="/#wire">The Wire</a> · <a href="/newsletter">Newsletter</a> · '
        '<a href="/scoring">How we score</a> · <a href="/privacy">Privacy</a> · <a href="/tos">Terms</a></p>'
        "<p>BLACKOUT.NETWORK. Signal over noise.&trade;</p></footer>"
        '<script src="/welcome.js" defer></script>'
        "</body></html>"
    )


def handle_get(path, qs):
    p = path.rstrip("/")
    if p == "/welcome.js":
        return _asset("welcome.js", "application/javascript")
    if p == "/welcome.css":
        return _asset("welcome.css", "text/css")
    if p != "/welcome":
        return 404, {"error": "not found"}
    return 200, _render(), "text/html"
