"""Meshtastic on BLACKOUT.NETWORK: /mesh (live public-node map + drop-off watch), /mesh/chat (live mesh chat through the
reader's OWN radio), /mesh/guide (off-grid setup guide) and the "Push to Mesh" share helper.

Hard rules (Matt, Nov 12):
  * Our server never transmits onto the mesh or the MQTT broker. Every transmission is client-side, from the reader's own
    radio (Web Bluetooth / Web Serial, official @meshtastic/core JS), after an explicit tap on Send with a preview.
  * Node data: data/mesh_nodes.json, built on the box by tools/meshtastic/collect.py from MeshMap.net's public nodes.json and
    pushed as ONE signed file (tools/meshtastic/push.py). No database, no full render_sync. Without the file every page still
    renders and says "waiting for the first sync".
  * Drop-off signal: single source, unconfirmed, watchlist only, rank capped at 5 (never red, never 7+). Exposed at
    /api/mesh/signal; it does not feed scanner.py scoring.
  * Public read-only chat feed: OFF unless BN_MESH_PUBLIC_FEED=liamcottle (pending Matt's decision and the operator's OK).
    When on: broadcast text only, 30 s in-memory cache of the last 40 messages, e-mail / phone patterns masked, nothing written to disk.
Never touches scanner.py, scoring, push.py, jets.py, config.json, aviation_watch.py or blackout.db."""
import html, json, os, re, threading, time, urllib.request
try:
    import sitenav
except Exception:
    sitenav = None

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data", "mesh_nodes.json")
STATIC = os.path.join(BASE, "meshnet_static")
SITE = "https://blackout.network"; BRAND = "BLACKOUT.NETWORK"
E = lambda s: html.escape(str(s if s is not None else ""), quote=True)
FILES = {"app.js": "application/javascript; charset=utf-8", "app.css": "text/css; charset=utf-8", "device.js": "application/javascript; charset=utf-8",
         "lib.js": "application/javascript; charset=utf-8", "chat.js": "application/javascript; charset=utf-8", "share.js": "application/javascript; charset=utf-8",
         "grid-panel.js": "application/javascript; charset=utf-8", "LICENSES.txt": "text/plain; charset=utf-8",
         "build_lib.sh": "text/plain; charset=utf-8"}
IOS_APP = "https://apps.apple.com/us/app/meshtastic/id1586432531"
ANDROID_APP = "https://play.google.com/store/apps/details?id=com.geeksville.mesh"
WEB_CLIENT = "https://client.meshtastic.org/"
D = "https://meshtastic.org/docs"

_C = {"mt": None, "v": None}
def data():
    try: mt = os.path.getmtime(DATA)
    except OSError: return None
    if _C["mt"] != mt:
        try:
            with open(DATA, encoding="utf-8") as f: v = json.load(f)
            _C.update(mt=mt, v=v if isinstance(v, dict) else None)
        except Exception: _C.update(mt=mt, v=None)
    return _C["v"]

def summary():
    """Small JSON for panels: feed status, counts, regions (no node list)."""
    d = data()
    if not d: return {"ok": False, "waiting": True, "note": "Waiting for the first sync from the box collector.", "signals": [], "regions": []}
    return {"ok": True, "generated": d.get("generated"), "feed": d.get("feed"), "counts": d.get("counts"), "params": d.get("params"),
            "focus": d.get("focus"), "areas": d.get("areas"), "regions": d.get("regions") or [], "signals": d.get("signals") or []}

def signal():
    d = data() or {}
    feed = d.get("feed") or {}
    sig = d.get("signals") or [] if feed.get("ok") else []
    for s in sig: s["rank"] = min(int(s.get("rank") or 4), 5); s["list"] = "watchlist"; s["single_source"] = True; s["confirmed"] = False
    return {"source": "BLACKOUT.NETWORK off-grid network drop-off watch (MeshMap.net public node data)", "single_source": True,
            "max_rank": 5, "generated": d.get("generated"), "feed_ok": bool(feed.get("ok")), "baseline_ready": bool(feed.get("baseline_ready")),
            "signals": sig, "how": f"{SITE}/mesh#how"}

# ---------------------------------------------------------------- optional public chat feed (OFF by default)
_F = {"t": 0, "v": None}; _FL = threading.Lock()
FEED_URL = "https://meshtastic.liamcottle.net/api/v1/text-messages?count=60&order=desc&channel_id=LongFast"
_MASK = [(re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[email hidden]"), (re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{8,}\d)(?!\d)"), "[number hidden]")]
def _clean(t):
    t = re.sub(r"[\x00-\x1f\x7f]", " ", str(t or ""))[:240]
    for rx, rep in _MASK: t = rx.sub(rep, t)
    return t.strip()
def public_feed():
    mode = os.environ.get("BN_MESH_PUBLIC_FEED", "").strip().lower()
    if mode != "liamcottle":
        return {"enabled": False, "messages": [], "note": "The public read-only feed is switched off while we confirm permission to use it. Connect your own radio to read and send."}
    with _FL:
        if _F["v"] is not None and time.time() - _F["t"] < 30: return _F["v"]
        out = {"enabled": True, "messages": [], "source": "Public mesh map by Liam Cottle, default LongFast channel",
               "source_url": "https://meshtastic.liamcottle.net/", "note": "Public default-channel broadcasts uplinked to the public MQTT server. Read-only. Not stored."}
        try:
            r = urllib.request.urlopen(urllib.request.Request(FEED_URL, headers={"User-Agent": "BLACKOUT.NETWORK mesh chat (+https://blackout.network/mesh/chat)", "Accept": "application/json"}), timeout=12)
            rows = (json.loads(r.read(2_000_000)) or {}).get("text_messages") or []
            for m in rows:
                if str(m.get("to")) != "4294967295": continue          # broadcasts only, never direct messages
                txt = _clean(m.get("text"))
                if not txt: continue
                try: frm = "!" + format(int(m.get("from")), "08x")[-4:]
                except Exception: frm = "node"
                out["messages"].append({"t": m.get("created_at"), "ch": str(m.get("channel_id") or "")[:24], "from": frm, "text": txt})
                if len(out["messages"]) >= 40: break
        except Exception as ex:
            out["error"] = f"public feed unavailable ({type(ex).__name__})"
        _F.update(t=time.time(), v=out)
        return out

# ---------------------------------------------------------------- page shell
def _head(key, path):
    if sitenav is not None and key in getattr(sitenav, "PAGES", {}):
        try: return sitenav.head_html(key, path)
        except Exception: pass
    t, desc = TITLES[key]
    return f'<title>{E(t)}</title><meta name="description" content="{E(desc)}"><link rel="canonical" href="{SITE}{E(path)}"><link rel="stylesheet" href="/sitenav.css"><script src="/sitenav.js" defer></script>'
def _top():
    if sitenav is not None:
        try: return sitenav.header_html("@mesh")
        except Exception: pass
    return f'<header class="bn-hd"><a href="/" style="color:inherit;text-decoration:none;font-weight:800">BLACKOUT</a></header>'
TITLES = {
    "mesh": ("Off-grid network map: live public mesh radios | BLACKOUT.NETWORK", "A live map of public off-grid mesh radios worldwide, centered on Central Florida, with a drop-off watch that flags regions where radios go quiet."),
    "mesh-chat": ("Network chat from your own radio | BLACKOUT.NETWORK", "Read and send mesh channel messages from your own LoRa radio over Bluetooth or USB, right in the browser. Nothing is sent from our servers."),
    "mesh-guide": ("Off-grid setup guide: text messaging when the grid goes down | BLACKOUT.NETWORK", "How to set up a LoRa mesh radio for a grid-down emergency: hardware, the US 915 MHz band, the app, channels, solar power, etiquette and the rules for unlicensed and ham use."),
}
SUBNAV = [("mesh", "/mesh", "Network map"), ("mesh-chat", "/mesh/chat", "Network chat"), ("mesh-guide", "/mesh/guide", "Setup guide")]
def _subnav(cur):
    return '<nav class="mx-sub" aria-label="Off-grid network pages">' + "".join(
        f'<a class="mx-sl" href="{h}"' + (' aria-current="page"' if k == cur else "") + f'>{E(l)}</a>' for k, h, l in SUBNAV) + '</nav>'
I = {
 "mesh": '<path d="M5 19l7-14 7 14M8.5 12h7"/><circle cx="12" cy="5" r="1.6"/><circle cx="5" cy="19" r="1.6"/><circle cx="19" cy="19" r="1.6"/>',
 "radio": '<rect x="4" y="8" width="16" height="12" rx="2"/><path d="M8 8l8-5M8 14h3M15 13.5h.01M15 16.5h.01"/>',
 "bt": '<path d="M7 7l10 10-5 4V3l5 4L7 17"/>', "usb": '<path d="M12 3v14M8 7l4-4 4 4M7 11v2a5 5 0 0 0 10 0v-2"/><circle cx="12" cy="20" r="1.5"/>',
 "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/>', "send": '<path d="M4 12l16-8-6 16-2-7z"/>',
 "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M5 19l1.5-1.5M17.5 6.5L19 5"/>',
}
def icon(n, cls="mx-i"):
    return (f'<svg class="{cls}" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true" focusable="false">{I[n]}</svg>')
def page(key, path, body, scripts=()):
    head = _head(key, path) + '<meta name="robots" content="index,follow,max-image-preview:large"><link rel="stylesheet" href="/api/mesh/app.css?v=1">'
    js = "".join(f'<script src="{s}" defer></script>' for s in scripts)
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' + head +
            '<link rel="stylesheet" href="/theme.css"><link rel="icon" href="/favicon.ico?v=3" sizes="any">'
            '<style>body{margin:0;background:var(--bn-bg,#0B0D10);overflow-x:hidden}</style></head><body>'
            '<a class="skip bn-skip" href="#main" style="position:absolute;left:-999px">Skip to content</a>' + _top() +
            f'<main class="mx" id="main">{body}</main>'
            '<footer class="mx-foot">BLACKOUT.NETWORK · <a href="/">The Wire</a> · <a href="/#grid">Energy Grid</a> · <a href="/mesh">Off-grid network map</a> · '
            '<a href="/mesh/chat">Network chat</a> · <a href="/mesh/guide">Off-grid setup guide</a> · <a href="/privacy">Privacy</a> · <a href="/tos">Terms</a> · <a href="/tos#acknowledgments">Credits</a><br>'
            'Research only: not an official warning service.</footer>' + js + '</body></html>').encode("utf-8")

# ---------------------------------------------------------------- /mesh
def map_page():
    s = summary()
    feed = s.get("feed") or {}
    cnt = s.get("counts") or {}
    stat = ("Waiting for the first sync" if not s.get("ok") else
            f'{cnt.get("total", 0):,} nodes on the map · {cnt.get("active", 0):,} heard in the last hour')
    hero = (f'<section class="mx-hero"><div class="mx-kick">{icon("mesh")} OFF-GRID NETWORK · LIVE</div>'
            '<h1>Off-grid network map</h1>'
            '<p class="mx-dek">Small LoRa mesh radios send text with no license and keep working when the power grid and cell service are down. '
            'This map shows public radios heard through the open-source mesh project\'s public MQTT server, starting with Central Florida.</p>'
            f'<div class="mx-stats" id="mx_stats" aria-live="polite">{E(stat)}</div>{_subnav("mesh")}</section>')
    mapc = ('<section class="mx-card mx-mapcard"><div class="mx-maphead"><h2>Live node map</h2><div class="mx-seg" role="group" aria-label="Map view">'
            '<button type="button" data-view="cfl" aria-pressed="true">Central Florida</button><button type="button" data-view="us" aria-pressed="false">U.S.</button>'
            '<button type="button" data-view="world" aria-pressed="false">World</button></div></div>'
            '<div class="mx-map" id="mx_map" role="region" aria-label="Map of public mesh radios"><noscript><p class="mx-mu">The map needs JavaScript.</p></noscript></div>'
            '<div class="mx-legend"><span><i class="d d-r"></i>Router / repeater</span><span><i class="d d-c"></i>Client</span><span><i class="d d-o"></i>Not heard in 1 h+</span>'
            '<span><i class="ring"></i>Watch area</span></div>'
            '<p class="mx-mu mx-small" id="mx_fresh"></p></section>')
    focus = ('<section class="mx-grid2"><div class="mx-card" id="mx_focus"><h2>Central Florida right now</h2><p class="mx-mu">Sanford, Lake Mary, Orlando and the area within about 70 km (45 mi).</p>'
             '<div class="mx-kv" id="mx_focus_kv"><div><b>–</b><span>nodes listed</span></div><div><b>–</b><span>heard in the last hour</span></div><div><b>–</b><span>regular nodes gone quiet</span></div></div></div>'
             '<div class="mx-card" id="mx_watch"><h2>Drop-off watch</h2><p class="mx-mu">Regions where regular nodes have gone quiet compared with the prior 24 hours. '
             'Single source, unconfirmed.</p><div id="mx_watch_list" class="mx-wl"><p class="mx-mu">Loading…</p></div></div></section>')
    how = ('<section class="mx-card mx-how" id="how"><h2>How this works</h2><ul>'
           '<li><b>Data:</b> <a href="https://meshmap.net/" target="_blank" rel="noopener">MeshMap.net</a> publishes the nodes heard by the official '
           f'<a href="{D}/software/integrations/mqtt/" target="_blank" rel="noopener">public MQTT server</a> run by the open-source mesh project. We read that public snapshot once every 10 minutes. '
           'Only nodes whose owners turned on position sharing and MQTT (or that were heard by such a node) appear, so this is a sample of the mesh, not all of it.</li>'
           '<li><b>Privacy:</b> positions are rounded to about 1 km (the public server already blurs default-channel positions), and we show only a short name, role and hardware. '
           'No node IDs, long names, telemetry or messages are kept.</li>'
           '<li><b>Drop-off watch:</b> a node is "regular" in a region when it was heard in at least half of our 10-minute checks over the prior 24 hours. '
           'A region is flagged when at least 10 regular nodes are listed, 6 or more and at least half of them have not been heard for an hour, for two checks in a row. '
           'If nodes go quiet everywhere at once we treat it as a data-source problem and flag nothing.</li>'
           '<li><b>What a flag means:</b> gateway nodes need power and internet to reach MQTT, so a drop can point to a local power or internet outage. It can also be a gateway '
           'or MQTT problem. Flags are single-source watchlist items, never more than rank 5, and are not confirmed until other sources agree.</li>'
           '<li>Map tiles: <a href="https://openfreemap.org/" target="_blank" rel="noopener">OpenFreeMap</a> © <a href="https://www.openmaptiles.org/" target="_blank" rel="noopener">OpenMapTiles</a> '
           'data © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap contributors</a>.</li>'
           '<li>Software and data credits: <a href="/tos#acknowledgments">Credits</a>.</li></ul></section>')
    cta = ('<section class="mx-grid2"><a class="mx-card mx-link" href="/mesh/chat">' + icon("radio") + '<b>Network chat</b><span>Connect your own radio and read or send channel messages in the browser.</span></a>'
           '<a class="mx-card mx-link" href="/mesh/guide">' + icon("sun") + '<b>Off-grid setup guide</b><span>Hardware, the 915 MHz band, channels, solar power and etiquette.</span></a></section>')
    return page("mesh", "/mesh", hero + mapc + focus + cta + how, ["/api/mesh/app.js?v=1"])

# ---------------------------------------------------------------- /mesh/chat
def chat_page():
    hero = (f'<section class="mx-hero"><div class="mx-kick">{icon("radio")} NETWORK CHAT</div><h1>Network chat</h1>'
            '<p class="mx-dek">Connect your own LoRa mesh radio to read your channels and send messages over the mesh. '
            'Your browser talks to your radio directly. Messages stay on this page and are gone when you close it.</p>' + _subnav("mesh-chat") + '</section>')
    support = ('<section class="mx-card mx-note" id="mx_support"><h2>' + icon("info") + ' Works in Chrome and Edge</h2>'
               '<p>Bluetooth and USB connections work in Chrome or Edge on a computer and in Chrome on Android. They do not work in Safari or on iPhone and iPad (Apple does not allow it). '
               f'On iPhone, use the free official companion app (<a href="{IOS_APP}" target="_blank" rel="noopener">App Store</a>) to reply. Android: <a href="{ANDROID_APP}" target="_blank" rel="noopener">companion app on Google Play</a>. '
               f'Or use the official <a href="{WEB_CLIENT}" target="_blank" rel="noopener">web client</a>.</p><p class="mx-mu" id="mx_support_status"></p></section>')
    conn = ('<section class="mx-card" id="mx_conn"><h2>Your radio</h2><div class="mx-row">'
            f'<button type="button" class="mx-btn mx-pri" id="mx_bt" disabled>{icon("bt")} Connect by Bluetooth</button>'
            f'<button type="button" class="mx-btn" id="mx_usb" disabled>{icon("usb")} Connect by USB</button>'
            '<button type="button" class="mx-btn" id="mx_disc" hidden>Disconnect</button></div>'
            '<p class="mx-mu" id="mx_cstat" role="status" aria-live="polite">Not connected.</p>'
            '<label class="mx-lbl" for="mx_ch">Channel</label><select id="mx_ch" class="mx-sel" disabled><option value="0">Primary (channel 0)</option></select></section>')
    chat = ('<section class="mx-card mx-chat"><h2>Messages</h2><ol class="mx-msgs" id="mx_msgs" aria-live="polite"><li class="mx-mu mx-empty">Connect a radio to see messages on your channels.</li></ol>'
            '<form class="mx-compose" id="mx_form" autocomplete="off"><label class="mx-vh" for="mx_text">Message</label>'
            '<textarea id="mx_text" rows="2" maxlength="200" placeholder="Connect a radio to send" disabled></textarea>'
            f'<div class="mx-row mx-sendrow"><span class="mx-mu mx-small" id="mx_count">0 / 200 bytes</span><button type="submit" class="mx-btn mx-pri" id="mx_send" disabled>{icon("send")} Send to mesh</button></div>'
            '<p class="mx-mu mx-small" id="mx_rate">Sends only when you tap Send. One message every 30 seconds, at most 5 in 10 minutes, so the mesh stays usable for everyone.</p></form></section>')
    pub = ('<section class="mx-card" id="mx_pub"><h2>Public feed (read-only)</h2><p class="mx-mu" id="mx_pub_note">Loading…</p><ol class="mx-msgs" id="mx_pub_msgs"></ol></section>')
    how = ('<section class="mx-card mx-how"><h2>Privacy and etiquette</h2><ul>'
           '<li>Messages travel from this page to your radio and out over the air. BLACKOUT.NETWORK servers never see, store or send them.</li>'
           '<li>The default LongFast channel is public: anyone nearby with the default settings can read it. Do not share private details there.</li>'
           f'<li>Keep messages short and infrequent; every message uses shared airtime. See the <a href="{D}/configuration/tips/" target="_blank" rel="noopener">official configuration tips</a>.</li>'
           '<li>In an emergency call 911 if you can. The mesh is not monitored by emergency services.</li></ul></section>')
    return page("mesh-chat", "/mesh/chat", hero + support + conn + chat + pub + how, ["/api/mesh/device.js?v=1", "/api/mesh/chat.js?v=1"])

# ---------------------------------------------------------------- /mesh/guide
def _src(label, path):
    url = path if path.startswith("http") else D + path
    return f'<a href="{E(url)}" target="_blank" rel="noopener">{E(label)}</a>'
def guide_page():
    hero = (f'<section class="mx-hero"><div class="mx-kick">{icon("sun")} OFF-GRID GUIDE</div><h1>Off-grid setup guide</h1>'
            '<p class="mx-dek">A small LoRa radio paired with your phone can send text messages for miles with no cell towers, Wi-Fi or power grid. '
            'Here is how to set one up before you need it. Every step links to the official documentation of the open-source mesh project.</p>' + _subnav("mesh-guide") + '</section>')
    toc = [("what", "What it is"), ("hardware", "Hardware"), ("band", "US 915 MHz band"), ("app", "App setup"), ("channels", "Channels"),
           ("power", "Power and solar"), ("etiquette", "Etiquette"), ("legal", "Legal: unlicensed vs. ham"), ("drill", "Before the grid goes down")]
    nav = '<nav class="mx-card mx-toc" aria-label="On this page"><b>On this page</b><ol>' + "".join(f'<li><a href="#{i}">{E(t)}</a></li>' for i, t in toc) + '</ol></nav>'
    S = []
    S.append(('what', 'What it is', f'''<p>These radios run free, open-source mesh firmware (credited in our <a href="/tos#acknowledgments">Acknowledgments</a>). Each radio pairs with a phone or computer and relays messages for the others,
so a group of radios forms a <b>mesh</b>: a message hops from node to node (3 hops by default, up to 7) until it reaches everyone. It needs no cell service, internet or license
for normal use. It sends short text, positions and sensor readings, not voice. Sources: {_src("Introduction", "/introduction/")}, {_src("Mesh algorithm", "/overview/mesh-algo/")}, {_src("LoRa configuration", "/configuration/radio/lora/")}.</p>'''))
    S.append(('hardware', 'Hardware', f'''<p>Pick a supported board from the official {_src("supported devices list", "/hardware/devices/")}. The common types:</p><ul>
<li><b>Ready-made handhelds</b> with a case, battery and screen: easiest for families. Pair one with each phone.</li>
<li><b>Development boards</b> (for example Heltec, LILYGO, RAK WisBlock): cheaper, but you add a case, battery and antenna.</li>
<li><b>Solar nodes</b>: a weatherproof board, battery and panel for a roof or pole, to extend range for the whole neighborhood.</li></ul>
<p>Buy the <b>915 MHz (US)</b> version and a proper antenna for that band. Never power on a radio without its antenna attached. Height matters more than power: a node in an attic,
on a roof or on a hill reaches far more people. See {_src("Antennas", "/hardware/antennas/")} and {_src("Flashing firmware", "/getting-started/flashing-firmware/")} (the web {_src("flasher", "https://flasher.meshtastic.org/")} works in Chrome or Edge).</p>'''))
    S.append(('band', 'US 915 MHz band', f'''<p>In the United States, set the radio's region to <b>US</b>. That uses the 902–928 MHz band, with no duty-cycle limit and a 30 dBm (1 W) power cap in the firmware's region table.
A new radio with the region left <b>unset</b> will not transmit at all, so this is the first setting to change. Every radio in your group needs the same region and the same
<b>modem preset</b> (the default is LongFast). Sources: {_src("LoRa configuration: Region", "/configuration/radio/lora/")}, {_src("Radio settings and presets", "/overview/radio-settings/")}.</p>'''))
    S.append(('app', 'App setup', f'''<ol><li>Install the official app: {_src("iPhone / iPad / Mac", IOS_APP)}, {_src("Android", ANDROID_APP)}, or use the {_src("web client", WEB_CLIENT)} in Chrome or Edge.</li>
<li>Turn the radio on and pair it over Bluetooth from the app (the radio's screen or the app shows the PIN).</li>
<li>Set <b>Region: US</b> and leave the preset on LongFast unless your local group uses another one.</li>
<li>Set your long and short name, and keep the role on <b>CLIENT</b> (or CLIENT_MUTE for a second radio indoors).</li>
<li>Decide how precise your shared position should be before you go out (see Channels below).</li></ol>
<p>Sources: {_src("Getting started", "/getting-started/")}, {_src("Initial configuration", "/getting-started/initial-config/")}, {_src("Configuration tips: roles", "/configuration/tips/")}.</p>'''))
    S.append(('channels', 'Channels', f'''<p>Each radio has up to 8 channels. Channel 0, the <b>primary</b>, defaults to the public <b>LongFast</b> channel with a well-known key, so
anyone nearby with default settings can read it. That is good for meeting neighbors and for public calls for help, but not for private messages.</p><ul>
<li>Create a <b>secondary channel</b> with its own random key for your family or group, then share it by QR code or link from the app.</li>
<li>Only scan channel QR codes from people you trust: a QR code can also change your radio's LoRa settings.</li>
<li>Your position is shared on the primary channel. Lower the position precision, or turn position sharing off, if you do not want your home location on the public channel.</li></ul>
<p>Sources: {_src("Channel configuration", "/configuration/radio/channels/")}, {_src("FAQ: sharing a channel", "/faq/")}, {_src("Position configuration", "/configuration/radio/position/")}, {_src("Configuration tips", "/configuration/tips/")}.</p>'''))
    S.append(('power', 'Power and solar', f'''<p>Most boards run for a day or more on an 18650 or LiPo cell and charge from USB, so a USB power bank or a small folding solar panel keeps a handheld going.
For a fixed node, use a weatherproof box, a battery sized for several cloudy days and a panel sized for winter sun. The radio's power-saving setting turns off Bluetooth, USB serial, Wi-Fi and the screen
to stretch a small battery or solar supply, so use it only on a fixed relay node, not on the radio you pair with your phone. Sources: {_src("Power configuration", "/configuration/radio/power/")}, {_src("Supported devices", "/hardware/devices/")}.</p>'''))
    S.append(('etiquette', 'Etiquette', f'''<ul><li>Keep the role on CLIENT. Do not use ROUTER or REPEATER unless your local group agrees: extra routers cause collisions and shrink the mesh.</li>
<li>Keep messages short and do not repeat them. Every message uses airtime that everyone shares.</li>
<li>Leave the hop limit at 3 unless your area really needs more.</li>
<li>Do not set very short position or telemetry intervals; the defaults are chosen to keep the channel clear.</li>
<li>Do not send private details on the public LongFast channel.</li></ul><p>Source: {_src("Configuration tips", "/configuration/tips/")}, {_src("LoRa configuration: hop limit", "/configuration/radio/lora/")}.</p>'''))
    S.append(('legal', 'Legal: unlicensed vs. ham', f'''<p><b>Unlicensed (default):</b> in the US, the firmware runs in the 902–928 MHz ISM band with no license, within the firmware's region power limits and using
legal antennas for your device. Encryption is allowed in this mode.</p>
<p><b>Licensed amateur (ham) mode:</b> a licensed operator can turn on the licensed setting with their call sign as the long name. The official FAQ notes this allows more transmit power
in the US (up to 10 W, 47 CFR 97.313(j)) and higher-gain antennas, but <b>encryption is not allowed</b> (FCC Part 97.113(a)(4)), the call sign is sent at least every 10 minutes
(Part 97.119(a)), and licensed and unlicensed nodes cannot talk to each other. Sources: {_src("FAQ: Amateur radio (ham)", "/faq/")}, {_src("User configuration", "/configuration/radio/user/")}, {_src("Project legal notes", "/legal/")}.</p>
<p class="mx-mu">This is general information, not legal advice. Check the current FCC rules for your setup.</p>'''))
    S.append(('drill', 'Before the grid goes down', '''<ol><li>Set up every radio now, while you still have internet for firmware and app updates.</li>
<li>Agree on a private channel and a check-in time with your family or group, and practice once a month.</li>
<li>Charge everything, keep a power bank and a small solar panel with the radios, and label which radio is whose.</li>
<li>Find your local mesh group and see who is already on the air near you on our <a href="/mesh">mesh map</a>.</li>
<li>Write down the basics (region US, preset, channel name) on paper in case a radio needs a reset.</li></ol>'''))
    body = "".join(f'<section class="mx-card mx-art" id="{i}"><h2>{E(t)}</h2>{h}</section>' for i, t, h in S)
    note = ('<p class="mx-mu mx-small">This guide is independent and links to the official project documentation. '
            'We do not sell radios or use affiliate links. <a href="/tos#acknowledgments">Credits</a></p>')
    return page("mesh-guide", "/mesh/guide", hero + '<div class="mx-guide">' + nav + '<div>' + body + note + '</div></div>')

# ---------------------------------------------------------------- static + routes
def _file(name):
    p = os.path.join(STATIC, name)
    try:
        with open(p, "rb") as f: return 200, f.read(), FILES[name]
    except Exception: return 404, {"error": "not found"}

def handle_get(path, qs=None):
    p = path.rstrip("/") or "/"
    if p == "/mesh": return 200, map_page(), "text/html; charset=utf-8"
    if p == "/mesh/chat": return 200, chat_page(), "text/html; charset=utf-8"
    if p == "/mesh/guide": return 200, guide_page(), "text/html; charset=utf-8"
    if p == "/api/mesh/nodes":
        d = data()
        return (200, d) if d else (200, {"ok": False, "waiting": True, "nodes": [], "hw": [], "regions": [], "signals": []})
    if p == "/api/mesh/summary": return 200, summary()
    if p == "/api/mesh/signal": return 200, signal()
    if p == "/api/mesh/chat": return 200, public_feed()
    if p.startswith("/api/mesh/"):
        name = p.rsplit("/", 1)[-1]
        if name in FILES: return _file(name)
    return 404, {"error": "not found"}
