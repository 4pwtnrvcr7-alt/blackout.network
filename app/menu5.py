"""Main menu v5 (Matt, voice, Nov 24 2026 12:25 AM ET): one menu body for every overlay on the site
(sitenav drawer #bn-menu, the "/" intro menu #h_menu, the Wire/story menu #w2_menu).

- Remaining pages only (deactivated.py removes the rest), as large bold uppercase links, right-aligned and vertically centred,
  in the same type as the old lead links (Intro / The Wire / Live / Newsletter: Inter 700, clamp(30px,4.2vw,52px)/1.1, .02em).
- X and YouTube marks (monochrome SVG) sized to the link text, opening in a new tab.
- Items rise in (staggered) when the menu opens and fall out on close (the menus' existing open/closing classes drive it);
  a tap on an item zooms through to the page. prefers-reduced-motion: plain fades, no movement.
- Original text-free artwork (inline SVG: radar rings, sweep, linked nodes, one pulse) in white/grey/cool tones only.
- "Install on home screen" and "Turn on notifications" buttons open the existing device-aware animated panels
  (static/pwa/install-guide.js: BN.installApp / BN.showNotifyGuide) on tap only. Nothing opens by itself.
Kill switch: Render env BN_MENU_V5=0 brings back the previous menus unchanged."""
import os, html

E = lambda s: html.escape(str(s if s is not None else ""), quote=True)

def on():
    return os.environ.get("BN_MENU_V5", "1") != "0"

X_URL = "https://x.com/BlkoutNtw"
YT_URL = "https://www.youtube.com/@blkoutntw"

# Wanted order; anything deactivated is dropped. (key, label, href)
ORDER = [("intro", "Intro", "/?intro=1"), ("threat", "The Wire", "/wire"), ("heatmap", "Heat Map", "/map"), ("weather", "Weather", "/weather"),
         ("net", "The Grid", "/network"),   # Nov 24 2026 (Matt pt1795u): Network Status merged with The Grid; /grid 302s to /network
         ("finance", "Markets", "/markets"),
         ("newsletter", "Newsletter", "/newsletter")]

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

def _art():
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
 '.m5{position:relative;box-sizing:border-box;width:100%;flex:1 0 auto;display:flex;align-items:center;justify-content:flex-end;'
 'min-height:0;padding:20px max(20px,3vw) 20px;overflow:hidden;grid-column:1/-1;isolation:isolate}'
 '#h_menu .m5{min-height:calc(100vh - 124px);min-height:calc(100dvh - 124px);padding-left:0;padding-right:0}#h_menu.h-menu4:has(.m5)>.h-wm{display:none!important}'
 '.w2-mnav.w2-m5{display:flex;flex-direction:column;padding:0!important}.w2-m5 .m5{padding-left:0;padding-right:0}'
 '.m5 .m5-art{position:absolute;z-index:-1;pointer-events:none;left:max(-120px,-12vw);top:50%;width:min(92vw,620px);height:auto;transform:translateY(-50%);opacity:.38}'
 '@media (min-width:900px){.m5 .m5-art{left:4vw;width:min(46vw,640px);opacity:.9}}'
 '.m5a-ring{fill:none;stroke:#E8EEF4;stroke-width:1}.m5a-tick{stroke:#AEBBC8;stroke-width:1.2;opacity:.45}.m5a-axis{stroke:#AEBBC8;stroke-width:.8;opacity:.18;fill:none}'
 '.m5a-link{stroke:#9FB4C8;stroke-width:1;opacity:.38}.m5a-node{fill:#EEF3F8}.m5a-beam{stroke:#DCE6EF;stroke-width:1.2;opacity:.6}'
 '.m5a-wave{fill:none;stroke:#8FA3B7;stroke-width:1.4;opacity:.45;stroke-dasharray:6 7}'
 '.m5a-sweep{transform-origin:300px 300px;animation:m5sweep 7s linear infinite paused}'
 '.m5a-pulse{fill:none;stroke:#E8EEF4;stroke-width:1.4;transform-origin:376px 300px;animation:m5pulse 2.8s ease-out infinite paused}.m5a-p2{animation-delay:1.4s}'
 ':is(#bn-menu.bn-open,#h_menu.open,#w2_menu:not([hidden])) .m5 :is(.m5a-sweep,.m5a-pulse){animation-play-state:running}'
 '@keyframes m5sweep{to{transform:rotate(360deg)}}@keyframes m5pulse{0%{transform:scale(.6);opacity:.9}100%{transform:scale(4.2);opacity:0}}'
 '.m5-nav{display:flex;flex-direction:column;align-items:flex-end;text-align:right;gap:0;max-width:100%}'
 '.m5-list{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;align-items:flex-end}'
 '.m5-list li{margin:0;padding:0;border:0;list-style:none}'
 '.m5 .m5-list a,.m5 .m5-soc{font:700 clamp(30px,4.2vw,52px)/1.1 Inter,system-ui,sans-serif!important;letter-spacing:.02em!important;text-transform:uppercase}'
 '.m5 .m5-list a{display:inline-block;color:#fff!important;text-decoration:none!important;padding:2px 0!important;background:none!important;border:0!important;'
 'white-space:nowrap;max-width:100%;transform-origin:right center;transition:color .15s}'
 '.m5 .m5-list a:hover,.m5 .m5-list a:focus-visible{color:#C9CDD3!important}.m5 .m5-list a[aria-current]{color:#C9CDD3!important}'
 '.m5 .m5-list a:focus-visible,.m5 .m5-soc a:focus-visible,.m5 .m5-btn:focus-visible{outline:2px solid #fff;outline-offset:4px}'
 '.m5 .m5-soc{display:flex;gap:.55em;align-items:center;justify-content:flex-end;margin:.34em 0 0;line-height:1}'
 '.m5 .m5-soc a{display:inline-flex;align-items:center;color:#fff!important;text-decoration:none!important;height:1.1em;transition:color .15s,transform .15s}'
 '.m5 .m5-soc a:hover{color:#C9CDD3!important}.m5 .m5-ico{display:block;height:.74em;width:auto}.m5 .m5-ico-yt{height:.74em}'
 '.m5 .m5-acts{display:flex;flex-wrap:wrap;gap:10px;justify-content:flex-end;margin-top:22px}'
 '.m5 .m5-btn{display:inline-flex;align-items:center;gap:8px;min-height:44px;padding:0 16px;background:none;border:1px solid rgba(255,255,255,.45);border-radius:0;color:#fff;'
 'font:600 11px/1 Inter,system-ui,sans-serif;letter-spacing:.14em;text-transform:uppercase;cursor:pointer;transition:background .15s,border-color .15s}'
 '.m5 .m5-btn:hover{background:rgba(255,255,255,.08);border-color:#fff}.m5 .m5-btn svg{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}'
 '@media (max-width:420px){.m5 .m5-list a,.m5 .m5-soc{font-size:30px!important}.m5 .m5-btn{padding:0 12px;min-height:40px;letter-spacing:.1em}.m5 .m5-acts{gap:8px;margin-top:16px}}'
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
 # instruction panels sit above the full-screen menu
 '#bnig,#bnna{z-index:2147482000!important}'
 '</style>')

JS = ('<script id="bn_m5js">(function(){if(window.__bnM5)return;window.__bnM5=1;'
 'var RM=false;try{RM=matchMedia("(prefers-reduced-motion: reduce)").matches}catch(e){}'
 'document.addEventListener("click",function(e){var a=e.target.closest&&e.target.closest(".m5-list a[href]");if(!a)return;'
 'if(e.defaultPrevented||e.button||e.metaKey||e.ctrlKey||e.shiftKey||e.altKey||a.target==="_blank")return;'
 'var u;try{u=new URL(a.href,location.href)}catch(x){return}if(u.origin!==location.origin)return;'
 'if(u.pathname===location.pathname&&u.search===location.search&&u.hash)return;'
 'var m=a.closest(".m5");if(!m||m.classList.contains("m5-go"))return;e.preventDefault();e.stopPropagation();'
 'a.parentNode.classList.add("m5-hit");m.classList.add("m5-go");setTimeout(function(){location.href=a.href},RM?140:400)},true);'
 'addEventListener("pageshow",function(){[].forEach.call(document.querySelectorAll(".m5.m5-go"),function(m){m.classList.remove("m5-go");'
 '[].forEach.call(m.querySelectorAll(".m5-hit"),function(h){h.classList.remove("m5-hit")})})});'
 'document.addEventListener("click",function(e){var b=e.target.closest&&e.target.closest("[data-m5-act]");if(!b)return;e.preventDefault();var B=window.BN||{},k=b.getAttribute("data-m5-act");'
 'if(k==="install"){if(B.installApp)B.installApp();else if(B.showInstallGuide)B.showInstallGuide()}'
 'else if(k==="notify"){if(B.showNotifyGuide)B.showNotifyGuide();else if(B.enableAlerts)B.enableAlerts({})}})'
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
    acts = (f'<div class="m5-acts m5-r" style="--i:{n + 1}">'
            f'<button type="button" class="m5-btn" data-m5-act="install">{I_PHONE}<span>Install on home screen</span></button>'
            f'<button type="button" class="m5-btn" data-m5-act="notify">{I_BELL}<span>Turn on notifications</span></button></div>')
    return (CSS + '<div class="m5" data-m5>' + _art() + '<div class="m5-nav"><ul class="m5-list" aria-label="Pages">' + "".join(li) + '</ul>'
            + soc + acts + '</div></div>' + JS)
