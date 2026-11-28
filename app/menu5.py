"""Main menu v5 (Matt, voice, Nov 24 2026 12:25 AM ET): one menu body for every overlay on the site
(sitenav drawer #bn-menu, the "/" intro menu #h_menu, the Wire/story menu #w2_menu).

- Remaining pages only (deactivated.py removes the rest), as large bold uppercase links, right-aligned and stacked at the
  bottom of the screen (right-thumb zone on phones) so the city graphic stays clear in the middle. Type is Inter 700,
  sized so eight page links plus X/YouTube fit at 390 px without overflow. Desktop links also sit off the city, at the bottom.
- X and YouTube marks (monochrome SVG) sized to the link text, opening in a new tab, stay with the main list at the bottom.
- Items rise in (staggered) when the menu opens and fall out on close (the menus' existing open/closing classes drive it);
  a tap on an item zooms through to the page. prefers-reduced-motion: plain fades, no movement.
- Nov 27 2026 (Matt pt1984u): the old SVG radar is replaced by an original code-rendered canvas loop (static/pwa/bn-menu-city.js): a massive night city, the
  lights go out in waves, then a mesh comes online. Lazy-loaded on the first menu open; pointer-events:none, paused when the menu is
  closed or the tab is hidden, static frame under prefers-reduced-motion. Kill switch: BN_MENU_CITY=0 brings back the SVG radar.
- "Install App" and "Alerts" are regular menu items (same type as Intro / The Wire) and open /setup#install and
  /setup#notifications. The setup page has the per-OS steps and the working Install / Notifications buttons
  (static/pwa/install-guide.js: BN.installApp / BN.enableAlerts / BN.showNotifyGuide).
Kill switch: Render env BN_MENU_V5=0 brings back the previous menus unchanged."""
import os, html

E = lambda s: html.escape(str(s if s is not None else ""), quote=True)

def on():
    return os.environ.get("BN_MENU_V5", "1") != "0"

X_URL = "https://x.com/BlkoutNtw"
YT_URL = "https://www.youtube.com/@blkoutntw"

# Wanted order; anything deactivated is dropped. (key, label, href)
ORDER = [("intro", "Intro", "/?intro=1"), ("threat", "The Wire", "/wire"), ("heatmap", "Heat Map", "/map"), ("weather", "Weather", "/weather"),
         ("net", "The Grid", "/grid"),   # Nov 24 2026 (Matt pt1795u): Network Status merged with The Grid; /grid 302s to /grid
         ("finance", "Markets", "/markets"),
         ("comms", "Comms", "/comms"),  # Nov 27 2026 (Matt 11:24 PM ET): coming-soon /comms on the traffic menu
         ("newsletter", "Newsletter", "/newsletter"),
         ("setup-install", "Install App", "/setup#install"),
         ("setup-alerts", "Alerts", "/setup#notifications")]

def items(intro_href=None):
    try:
        import deactivated as D
        off = D.KEYS; path_off = D.is_off
    except Exception:
        off = frozenset(); path_off = lambda p: False
    out = []
    for k, label, href in ORDER:
        if k in off or path_off(href.split("?")[0]): continue
        if k == "intro" and intro_href: href = intro_href
        out.append((k, label, href))
    return out

I_X = ('<svg class="m5-ico m5-ico-x" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path fill="currentColor" '
       'd="M18.901 1.153h3.68l-8.04 9.19L24 22.846h-7.406l-5.8-7.584-6.638 7.584H.474l8.6-9.83L0 1.154h7.594l5.243 6.932ZM17.61 20.644h2.039L6.486 3.24H4.298Z"/></svg>')
# YouTube play-button mark, one colour (the play triangle is cut out), 28.57 x 20 proportions
I_YT = ('<svg class="m5-ico m5-ico-yt" viewBox="0 0 28.57 20" aria-hidden="true" focusable="false"><path fill="currentColor" fill-rule="evenodd" '
        'd="M27.97 3.12A3.58 3.58 0 0 0 25.45.6C23.22 0 14.29 0 14.29 0S5.35 0 3.12.6A3.58 3.58 0 0 0 .6 3.12C0 5.35 0 10 0 10s0 4.65.6 6.88a3.58 3.58 0 0 0 2.52 2.52C5.35 20 14.29 20 14.29 20s8.93 0 11.16-.6a3.58 3.58 0 0 0 2.52-2.52c.6-2.23.6-6.88.6-6.88s0-4.65-.6-6.88ZM11.43 14.29 18.85 10l-7.42-4.29Z"/></svg>')
I_PHONE = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><rect x="7" y="2.5" width="10" height="19" rx="2.2"/><path d="M11 18.5h2M12 6.5v7M9.2 10.8 12 13.6l2.8-2.8"/></svg>'
I_BELL = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M6 16.5V11a6 6 0 0 1 12 0v5.5l1.6 1.8H4.4z"/><path d="M10 20.6a2.2 2.2 0 0 0 4 0"/></svg>'

def _city_on():
    return os.environ.get("BN_MENU_CITY", "1") != "0"

def _city_ver():
    try:
        import hashlib
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "pwa", "bn-menu-city.js"), "rb") as f: return hashlib.sha1(f.read()).hexdigest()[:8]
    except Exception:
        return "0"

def _art():
    if _city_on(): return '<canvas class="m5-art m5-city" aria-hidden="true"></canvas>'
    return _art_svg()

def _art_svg():
    """Original abstract artwork: early-warning radar over a linked signal network. No words, no logos, no real imagery."""
    nodes = [(132, 214), (204, 132), (318, 98), (436, 150), (486, 262), (452, 392), (340, 470), (214, 446), (122, 344), (262, 262), (376, 300), (300, 372)]
    links = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (7, 8), (8, 0), (9, 1), (9, 2), (9, 8), (9, 10), (10, 3), (10, 4), (10, 11), (11, 6), (11, 7), (9, 11), (10, 5)]
    rings = "".join(f'<circle cx="300" cy="300" r="{r}" class="m5a-ring" style="opacity:{o}"/>' for r, o in ((58, .5), (116, .4), (174, .32), (232, .24), (290, .16)))
    ticks = "".join(f'<line x1="300" y1="6" x2="300" y2="{18 if i % 3 else 30}" class="m5a-tick" transform="rotate({i * 10} 300 300)"/>' for i in range(36))
    ln = "".join(f'<line x1="{nodes[a][0]}" y1="{nodes[a][1]}" x2="{nodes[b][0]}" y2="{nodes[b][1]}" class="m5a-link"/>' for a, b in links)
    nd = "".join(f'<circle cx="{x}" cy="{y}" r="{4.5 if i in (9, 10) else 3}" class="m5a-node"/>' for i, (x, y) in enumerate(nodes))
    return ('<svg class="m5-art" viewBox="0 0 600 600" aria-hidden="true" focusable="false">'
            '<defs><linearGradient id="m5sw" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#9FB4C8" stop-opacity="0"/>'
            '<stop offset="1" stop-color="#C9D6E2" stop-opacity=".30"/></linearGradient>'
            '<radialGradient id="m5gl" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#7D93A8" stop-opacity=".22"/><stop offset="1" stop-color="#7D93A8" stop-opacity="0"/></radialGradient></defs>'
            '<circle cx="300" cy="300" r="296" fill="url(#m5gl)"/>' + rings + ticks +
            '<path d="M300 300 300 10" class="m5a-axis"/><path d="M10 300H590" class="m5a-axis"/>'
            '<g class="m5a-sweep"><path d="M300 300 L300 10 A290 290 0 0 1 505.06 94.94 Z" fill="url(#m5sw)"/><line x1="300" y1="300" x2="505.06" y2="94.94" class="m5a-beam"/></g>'
            + ln + nd +
            '<circle cx="376" cy="300" r="10" class="m5a-pulse"/><circle cx="376" cy="300" r="10" class="m5a-pulse m5a-p2"/>'
            '<path d="M40 540 C110 540 130 500 170 500 S230 560 280 540 330 470 380 520 450 560 560 530" class="m5a-wave"/>'
            '</svg>')

CSS = ('<style id="bn_m5">'
 '.m5{position:relative;box-sizing:border-box;width:100%;flex:1 1 auto;display:flex;flex-direction:column;align-items:stretch;justify-content:space-between;'
 'min-height:0;padding:0;overflow:hidden;grid-column:1/-1;isolation:isolate}'
 '#h_menu.h-menu4:has(.m5){display:flex!important;flex-direction:column;grid-template-columns:none;align-content:stretch;overflow:hidden;'
 'padding:88px 0 0;box-sizing:border-box}'
 '#h_menu .m5{flex:1 1 auto;min-height:0;height:100%;padding:0}'
 '#h_menu.h-menu4:has(.m5)>.h-wm{display:none!important}'
 '#bn-menu.bn-m4:has(.m5) .bn-panel{overflow:hidden!important}'
 '#bn-menu:has(.m5) .m3-foot,#bn-menu:has(.m5) .m3-grid,#bn-menu:has(.m5) .m4-lead{display:none!important}'
 '#bn-menu:has(.m5) .m5{flex:1 1 0%!important;min-height:0;height:auto}'
 '#bn-menu:has(.m5) .bn-ph,#bn-menu:has(.m5) .m3-alerts,#bn-menu:has(.m5) .m3-tools,#bn-menu:has(.m5) .bn-dsearch{display:none!important}'
 '#bn-menu:has(.m5) .bn-mhead{border-bottom:0!important;padding-bottom:8px!important}'
 '#bn-menu:has(.m5) .bn-close span{display:none!important}'
 '#bn-menu:has(.m5) .bn-close{min-width:40px!important;min-height:40px!important;width:40px;height:40px;padding:0!important;gap:0!important;box-sizing:border-box;border:0!important;background:transparent!important;border-radius:0!important;box-shadow:none!important}'
 '#w2_menu:has(.m5) .w2-close{font-size:0!important;letter-spacing:0!important;gap:0!important;min-width:40px;min-height:40px;width:40px;height:40px;padding:0;justify-content:center;border:0!important;background:transparent!important;border-radius:0!important;box-shadow:none!important}'
 'body:has(#h_menu.open) .h-burger,body:has(#h_menu.open) #h_nav .h-x,body:has(#bn-menu.bn-open) .bn-burger,body:has(#w2_menu:not([hidden])) .w2-mbtn{min-width:40px!important;min-height:40px!important;width:40px;height:40px;padding:0!important;box-sizing:border-box;border:0!important;background:transparent!important;border-radius:0!important;box-shadow:none!important}'
 'body:has(#h_menu.open) .h-burger .bn-bl,body:has(#bn-menu.bn-open) .bn-burger .bn-bl,body:has(#w2_menu:not([hidden])) .w2-mbtn .bn-bl{display:none!important}'
 '#bn-menu:has(.m5) .m5{flex:1 1 auto;min-height:0}'
 '.w2-mnav.w2-m5{display:flex;flex-direction:column;flex:1 1 auto;min-height:0;height:100%;padding:0!important}'
 '.w2-m5 .m5{flex:1 1 auto;min-height:0;height:100%;padding:0}'
 '.m5 .m5-art{position:absolute;z-index:-1;pointer-events:none;left:max(-120px,-12vw);top:50%;width:min(92vw,620px);height:auto;transform:translateY(-50%);opacity:.38}'
 '@media (min-width:900px){.m5 .m5-art{left:4vw;width:min(46vw,640px);opacity:.9}}'
 '.m5a-ring{fill:none;stroke:#E8EEF4;stroke-width:1}.m5a-tick{stroke:#AEBBC8;stroke-width:1.2;opacity:.45}.m5a-axis{stroke:#AEBBC8;stroke-width:.8;opacity:.18;fill:none}'
 '.m5a-link{stroke:#9FB4C8;stroke-width:1;opacity:.38}.m5a-node{fill:#EEF3F8}.m5a-beam{stroke:#DCE6EF;stroke-width:1.2;opacity:.6}'
 '.m5a-wave{fill:none;stroke:#8FA3B7;stroke-width:1.4;opacity:.45;stroke-dasharray:6 7}'
 '.m5a-sweep{transform-origin:300px 300px;animation:m5sweep 7s linear infinite paused}'
 '.m5a-pulse{fill:none;stroke:#E8EEF4;stroke-width:1.4;transform-origin:376px 300px;animation:m5pulse 2.8s ease-out infinite paused}.m5a-p2{animation-delay:1.4s}'
 ':is(#bn-menu.bn-open,#h_menu.open,#w2_menu:not([hidden])) .m5 :is(.m5a-sweep,.m5a-pulse){animation-play-state:running}'
 '@keyframes m5sweep{to{transform:rotate(360deg)}}@keyframes m5pulse{0%{transform:scale(.6);opacity:.9}100%{transform:scale(4.2);opacity:0}}'
 '.m5-nav{display:flex;flex-direction:column;align-items:flex-end;text-align:right;gap:0;max-width:100%;margin-top:auto;position:relative;z-index:1;'
 'padding:0 max(20px,3vw) max(8px,env(safe-area-inset-bottom,0px));box-sizing:border-box}'
 '.m5-list{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;align-items:flex-end}'
 '.m5-list li{margin:0;padding:0;border:0;list-style:none}'
 '.m5 .m5-list a,.m5 .m5-soc{font:700 clamp(22px,5.6vw,32px)/1.08 Inter,system-ui,sans-serif!important;letter-spacing:.02em!important;text-transform:uppercase}'
 '.m5 .m5-list a{display:inline-flex;align-items:center;color:#fff!important;text-decoration:none!important;padding:3px 0!important;background:none!important;border:0!important;'
 'white-space:nowrap;max-width:100%;min-height:36px;box-sizing:border-box;transform-origin:right center;transition:color .15s}'
 '.m5 .m5-list a,.m5 .m5-soc a{text-shadow:0 1px 16px rgba(0,0,0,.85),0 0 3px rgba(0,0,0,.55)}'
 '.m5 .m5-list a:hover,.m5 .m5-list a:focus-visible{color:#C9CDD3!important}.m5 .m5-list a[aria-current]{color:#C9CDD3!important}'
 '.m5 .m5-list a:focus-visible,.m5 .m5-soc a:focus-visible,.m5 .m5-txt:focus-visible{outline:2px solid #fff;outline-offset:4px}'
 '.m5 .m5-soc{display:flex;gap:.55em;align-items:center;justify-content:flex-end;margin:.2em 0 0;line-height:1}'
 '.m5 .m5-soc a{display:inline-flex;align-items:center;color:#fff!important;text-decoration:none!important;height:1.1em;min-height:36px;transition:color .15s,transform .15s}'
 '.m5 .m5-soc a:hover{color:#C9CDD3!important}.m5 .m5-ico{display:block;height:.74em;width:auto}.m5 .m5-ico-yt{height:.74em}'
 '.m5 .m5-acts{display:flex;flex-wrap:wrap;gap:0 22px;justify-content:flex-end;align-items:center;margin:0;padding:4px max(20px,3vw) 0;position:relative;z-index:1;box-sizing:border-box;flex:0 0 auto}'
 '.m5 .m5-txt{display:inline-flex;align-items:center;min-height:36px;padding:6px 0;background:none!important;border:0!important;border-radius:0;color:rgba(230,232,235,.88)!important;'
 'font:500 11px/1.2 Inter,system-ui,sans-serif!important;letter-spacing:.08em!important;text-transform:uppercase;cursor:pointer;'
 'text-shadow:0 1px 10px rgba(0,0,0,.85);transition:color .15s}'
 '.m5 .m5-txt:hover,.m5 .m5-txt:focus-visible{color:#fff!important}'
 '@media (max-width:899px){.m5 .m5-acts{flex-direction:column;align-items:flex-end;gap:0;padding-top:2px}.m5 .m5-txt{min-height:32px;padding:4px 0}'
 '.m5 .m5-list a,.m5 .m5-soc{font-size:clamp(22px,7.2vw,28px)!important;line-height:1.05!important}'
 '.m5 .m5-list a{padding:2px 0!important;min-height:36px}.m5 .m5-soc{margin:.12em 0 0}.m5 .m5-soc a{min-height:36px}}'
 '@media (max-width:420px){.m5 .m5-list a,.m5 .m5-soc{font-size:26px!important;line-height:1.05!important}}'
 '@media (min-width:900px){.m5 .m5-list a,.m5 .m5-soc{font:700 clamp(24px,2.4vw,32px)/1.08 Inter,system-ui,sans-serif!important}'
 '.m5 .m5-list a{min-height:38px;padding:4px 0!important}.m5-nav{padding-bottom:max(8px,env(safe-area-inset-bottom,0px))}}'
 # entrance: rise in (staggered); exit: fall (existing menus' open / closing classes)
 ':is(#bn-menu.bn-open:not(.bn-closing),#h_menu.open:not(.h-closing),#w2_menu.open:not(.w2-closing)) .m5 .m5-r{animation:m5rise .55s cubic-bezier(.16,.84,.28,1) both;animation-delay:calc(var(--i,0)*45ms + 60ms)}'
 ':is(#bn-menu.bn-open:not(.bn-closing),#h_menu.open:not(.h-closing),#w2_menu.open:not(.w2-closing)) .m5 .m5-art{animation:m5art .9s ease both}'
 ':is(#bn-menu.bn-closing,#h_menu.h-closing,#w2_menu.w2-closing) .m5 .m5-r{animation:m5fall .46s cubic-bezier(.45,.02,.88,.28) both;animation-delay:calc(var(--i,0)*22ms)}'
 '@keyframes m5rise{from{opacity:0;transform:translateY(26px)}to{opacity:1;transform:none}}'
 '@keyframes m5fall{from{opacity:1;transform:none}to{opacity:0;transform:translateY(60vh)}}'
 '@keyframes m5art{from{opacity:0}}'
 # zoom-through on tap
 '@keyframes m5out{from{opacity:1;transform:none}to{opacity:0;transform:translateX(24px)}}@keyframes m5artout{from{opacity:1;transform:translateY(-50%)}to{opacity:0;transform:translateY(-50%) scale(1.5)}}'
 '.m5.m5-go .m5-r{animation:m5out .3s cubic-bezier(.5,0,.75,0) both!important}'
 '.m5.m5-go .m5-art{animation:m5artout .42s cubic-bezier(.5,0,.75,0) both!important}'
 '.m5.m5-go .m5-hit{animation:none!important;opacity:1!important;transform:none!important}'
 '.m5.m5-go .m5-hit a{transition:transform .42s cubic-bezier(.55,0,.8,.2),opacity .42s ease;transform:scale(2.6);opacity:0}'
 '@media (prefers-reduced-motion:reduce){.m5 .m5-r,.m5 .m5-art,.m5a-sweep,.m5a-pulse{animation:none!important}'
 ':is(#bn-menu.bn-open,#h_menu.open,#w2_menu.open) .m5{animation:m5art .2s ease both}'
 '.m5.m5-go .m5-r,.m5.m5-go .m5-art{animation:none!important}'
 '.m5.m5-go .m5-r,.m5.m5-go .m5-art,.m5.m5-go .m5-hit a{transition:opacity .15s ease!important;transform:none!important;opacity:0!important}'
 '.m5.m5-go .m5-art{transform:translateY(-50%)!important}}'
 # Nov 27 2026: city canvas fills the menu behind the links (never takes pointer events); the tap zoom-through only fades it
 '.m5 canvas.m5-city{position:absolute;z-index:-1;pointer-events:none;left:0;top:0;width:100%;height:100%;max-width:none;display:block;transform:none;opacity:1}'
 '@keyframes m5cityout{from{opacity:1}to{opacity:0}}'
 '.m5.m5-go canvas.m5-city{animation:m5cityout .42s ease both!important;transform:none!important}'
 # instruction panels sit above the full-screen menu
 '#bnig,#bnna{z-index:2147482000!important}'
 '#bnig.bnig-on,#bnna.bnig-on{visibility:visible!important}'   # tapped from the menu: show even while the open menu locks the page (html.bn-lock)
 '</style>')

JS = ('<script id="bn_m5js">(function(){if(window.__bnM5)return;window.__bnM5=1;'
 'var RM=false;try{RM=matchMedia("(prefers-reduced-motion: reduce)").matches}catch(e){}'
 # Matt 11:44 PM ET Nov 27 (#328): after a menu tap, an emptied black drawer (boxed Alerts, no links)
 # sometimes stayed on screen. Same-page taps close the menu; other taps navigate in the same turn.
 'document.addEventListener("click",function(e){var a=e.target.closest&&e.target.closest(".m5-list a[href]");if(!a)return;'
 'if(e.defaultPrevented||e.button||e.metaKey||e.ctrlKey||e.shiftKey||e.altKey||a.target==="_blank")return;'
 'var u;try{u=new URL(a.href,location.href)}catch(x){return}if(u.origin!==location.origin)return;'
 'var m=a.closest(".m5");if(!m||m.classList.contains("m5-go"))return;'
 'var same=u.pathname===location.pathname&&u.search===location.search;'
 'if(same&&u.hash)return;'
 'function m5clear(){m.classList.remove("m5-go");[].forEach.call(m.querySelectorAll(".m5-hit"),function(h){h.classList.remove("m5-hit")})}'
 'function m5shut(){m5clear();var sh=m.closest("#bn-menu,#h_menu,#w2_menu");'
 'if(sh&&sh.id==="bn-menu"&&window.bnMenuClose){window.bnMenuClose();return}'
 'var c=sh&&sh.querySelector(".bn-close,#w2_close,.m3-close,.h-x");if(c)c.click()}'
 'if(same){e.preventDefault();m5shut();return}'
 'e.preventDefault();e.stopPropagation();'
 'a.parentNode.classList.add("m5-hit");m.classList.add("m5-go");'
 'location.assign(u.pathname+u.search+u.hash);'
 'setTimeout(function(){if(!m.classList.contains("m5-go"))return;if(location.pathname===u.pathname&&location.search===u.search)return;location.assign(u.pathname+u.search+u.hash)},800)},true);'
 'addEventListener("pageshow",function(){[].forEach.call(document.querySelectorAll(".m5.m5-go"),function(m){m.classList.remove("m5-go");'
 '[].forEach.call(m.querySelectorAll(".m5-hit"),function(h){h.classList.remove("m5-hit")})})});'
 'function m5load(src,cb){var x=document.querySelector(\'script[data-m5-src="\'+src+\'"]\');if(x){x.addEventListener("load",cb);return}'
 'var t=document.createElement("script");t.src=src;t.setAttribute("data-m5-src",src);t.onload=cb;document.head.appendChild(t)}'
 # Nov 24 2026: pages that skip pwa_head (/mesh, /mesh/guide, /stats, /report-status) do not load the install guide or alerts; load them on tap
 'function m5act(k){var B=window.BN||{};'
 'if(k==="install"){if(B.installApp)B.installApp();else if(B.showInstallGuide)B.showInstallGuide();else return false}'
 'else{if(B.showNotifyGuide)B.showNotifyGuide();else if(B.enableAlerts)B.enableAlerts({});else return false}return true}'
 'document.addEventListener("click",function(e){var b=e.target.closest&&e.target.closest("[data-m5-act]");if(!b)return;e.preventDefault();var k=b.getAttribute("data-m5-act");'
 'if(m5act(k))return;if(!document.querySelector(\'link[href*="install-guide.css"]\')){var l=document.createElement("link");l.rel="stylesheet";l.href="/install-guide.css";document.head.appendChild(l)}m5load("/alerts.js",function(){m5load("/install-guide.js",function(){m5act(k)})})})'
 # Nov 27 2026: load the city animation script the first time a menu opens (nothing is fetched while menus stay closed)
 ';var cityLoaded=0;function cityLoad(){if(cityLoaded)return;cityLoaded=1;var s=document.createElement("script");s.src="/bn-menu-city.js?v=__CITYV__";s.async=true;document.head.appendChild(s)}'
 'function cityWatch(){var cs=document.querySelectorAll("canvas.m5-city"),seen={};[].forEach.call(cs,function(c){var m=c.closest("#bn-menu,#h_menu,#w2_menu");if(!m||seen[m.id])return;seen[m.id]=1;'
 'var Q="#bn-menu.bn-open,#h_menu.open,#w2_menu:not([hidden])";if(m.matches(Q)){cityLoad();return}'
 'if(window.MutationObserver){var o=new MutationObserver(function(){if(m.matches(Q)){cityLoad();o.disconnect()}});o.observe(m,{attributes:true,attributeFilter:["class","hidden"]})}})}'
 'if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",cityWatch);else cityWatch();'
 '})()</script>')

def html_block(active_href=None, intro_href=None):
    """The menu body. active_href marks the current page (aria-current)."""
    rows = items(intro_href)
    li = []
    for i, (k, label, href) in enumerate(rows):
        cur = ' aria-current="page"' if active_href and href.split("?")[0] == active_href and k != "intro" else ""
        li.append(f'<li class="m5-r" style="--i:{i}"><a href="{E(href)}"{cur}>{E(label)}</a></li>')
    n = len(rows)
    soc = (f'<div class="m5-soc m5-r" style="--i:{n}">'
           f'<a href="{X_URL}" target="_blank" rel="noopener me" aria-label="BLACKOUT.NETWORK on X, @BlkoutNtw (opens in a new tab)">{I_X}</a>'
           f'<a href="{YT_URL}" target="_blank" rel="noopener me" aria-label="BLACKOUT.NETWORK on YouTube (opens in a new tab)">{I_YT}</a></div>')
    return (CSS + '<div class="m5" data-m5>' + _art() + '<div class="m5-nav"><ul class="m5-list" aria-label="Pages">' + "".join(li) + '</ul>'
            + soc + '</div></div>' + JS.replace("__CITYV__", _city_ver()))
