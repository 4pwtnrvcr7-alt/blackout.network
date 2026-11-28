""" /comms — coming-soon lander for the Comms product (pt2031u, pt2040u).

Full-screen, dark, SpaceX-style page. Copy is only "Comms" and "Coming soon",
plus the standard site header and footer. No tagline, email form, or signup.
Does not mention radio protocols or hardware vendors. Not in the main menu
(adding a large menu5 link would reflow the just-shipped menu animation).
"""
import sitenav

CSS = """
html,body{background:#000;color:#fff}
body.comms-page{margin:0;min-height:100dvh;display:flex;flex-direction:column}
body.comms-page a.skip{position:absolute;left:-999px}
body.comms-page a.skip:focus{left:12px;top:8px;background:#111;color:#fff;padding:8px 12px;z-index:99}
.comms-main{position:relative;isolation:isolate;flex:1 0 auto;display:flex;flex-direction:column;
  justify-content:center;min-height:0;
  padding:28px 22px 40px;
  padding-left:max(22px,env(safe-area-inset-left));
  padding-right:max(22px,env(safe-area-inset-right));
  padding-bottom:max(40px,env(safe-area-inset-bottom))}
.comms-bg{position:absolute;inset:0;z-index:0;pointer-events:none;overflow:hidden;
  background:
    radial-gradient(1100px 560px at 50% 0%,rgba(196,210,224,.09),transparent 58%),
    radial-gradient(700px 700px at 88% 100%,rgba(70,90,120,.10),transparent 52%),
    #000}
.comms-bg::after{content:"";position:absolute;inset:0;opacity:.16;
  background-image:
    linear-gradient(rgba(255,255,255,.07) 1px,transparent 1px),
    linear-gradient(90deg,rgba(255,255,255,.07) 1px,transparent 1px);
  background-size:72px 72px;
  -webkit-mask-image:radial-gradient(ellipse at 50% 38%,#000 28%,transparent 74%);
  mask-image:radial-gradient(ellipse at 50% 38%,#000 28%,transparent 74%)}
@media (prefers-reduced-motion:no-preference){
  .comms-bg::after{animation:comms-drift 60s linear infinite}
}
@keyframes comms-drift{to{background-position:72px 72px}}
.comms-in{position:relative;z-index:1;width:100%;max-width:720px;margin:0 auto}
.comms-k{margin:0 0 14px;font:600 11px/1.2 var(--bn-font-ui,Montserrat,Inter,system-ui,sans-serif);
  letter-spacing:.22em;text-transform:uppercase;color:#9aa3ad}
.comms-in h1{margin:0;font:700 clamp(52px,16vw,112px)/.92 var(--bn-font-ui,Inter,system-ui,sans-serif);
  letter-spacing:-.04em;text-transform:uppercase;color:#fff}
body.comms-page footer{position:relative;z-index:1;margin-top:auto;
  padding:16px 22px 24px;
  padding-left:max(22px,env(safe-area-inset-left));
  padding-right:max(22px,env(safe-area-inset-right));
  padding-bottom:max(24px,env(safe-area-inset-bottom));
  font:400 12px/1.5 Inter,system-ui,sans-serif;color:#6f7782;text-align:center}
body.comms-page footer a{color:#9aa3ad;text-decoration:none}
body.comms-page footer a:hover,body.comms-page footer a:focus-visible{color:#fff;text-decoration:underline;text-underline-offset:2px}
@media(min-width:800px){
  .comms-in{margin-left:clamp(32px,12vw,180px);margin-right:auto}
  .comms-k{font-size:12px}
}
@media(prefers-reduced-motion:reduce){
  .comms-bg::after{animation:none}
}
"""


def _page():
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="index,follow">'
        + sitenav.head_html("comms")
        + '<link rel="stylesheet" href="/theme.css"><link rel="icon" href="/favicon.ico?v=5" sizes="any">'
        f'<style>{CSS}</style></head>'
        '<body class="comms-page"><a class="skip" href="#main">Skip to content</a>'
        + sitenav.header_html("")
        + '<main class="comms-main" id="main"><div class="comms-bg" aria-hidden="true"></div>'
        '<div class="comms-in"><p class="comms-k">Coming soon</p>'
        '<h1>Comms</h1></div></main>'
        '<footer>Research-only data · blackout.network · <a href="/#wire">Dashboard</a> · '
        '<a href="/newsletter">Newsletter</a> · <a href="/privacy">Privacy</a> · <a href="/tos">Terms</a>'
        '<br>BLACKOUT.NETWORK · PO Box 1228, Lake Mary, FL 32746</footer>'
        '<script src="/api/search/app.js" defer></script>'
        '</body></html>'
    )


def handle_get(path, qs):
    p = (path or "").rstrip("/") or "/"
    if p == "/comms":
        return 200, _page(), "text/html"
    return 404, "Not found", "text/plain"
