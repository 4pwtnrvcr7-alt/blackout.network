""" /comms — coming-soon lander for the Comms product (pt2031u, pt2040u).

Full-viewport black hero (100svh minus the header, edge to edge, no inner box).
Copy is only "Coming soon" and "Comms", plus the standard site header and
(below the fold) the standard legal footer. No Follow band, tagline, form,
or other on-page text. Does not mention radio protocols or hardware vendors.
"""
import sitenav

CSS = """
/* Beat html.bna-pg body{background:var(--a-bg)} (#0B0D10) and the apple
   column (max-width: calc(var(--a-max) + 2*var(--a-gut))) so the lander
   is one full-bleed black hero, not a boxed panel on a grey page. */
html,html.bna-pg{background:#000!important}
html.bna-pg body.comms-page,body.comms-page{
  background:#000!important;color:#fff;margin:0;display:block;min-height:0;
  color-scheme:dark}
body.comms-page a.skip{position:absolute;left:-999px}
body.comms-page a.skip:focus{left:12px;top:8px;z-index:99;background:#111;color:#fff;padding:8px 12px}
html.bna-pg body.comms-page>main,
html.bna-pg body.comms-page>main#main,
html.bna-pg body.comms-page>main.comms-main,
html.bna-pg body.comms-page>main#main.comms-main,
body.comms-page>main.comms-main{
  max-width:none!important;width:100%!important;
  margin:0!important;padding:0!important;
  padding-left:env(safe-area-inset-left)!important;
  padding-right:env(safe-area-inset-right)!important;
  box-sizing:border-box;background:#000!important;
  min-height:calc(100svh - var(--bn-tbar-h,60px));
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  position:relative}
.comms-in,html.bna-pg body.comms-page .comms-in{
  width:100%;max-width:none!important;margin:0;padding:0 20px;
  background:none!important;border:0!important;border-radius:0!important;
  box-shadow:none!important;text-align:center;box-sizing:border-box}
.comms-k,html.bna-pg body.comms-page .comms-k{
  margin:0 0 clamp(16px,2vw,28px);
  font:600 clamp(11px,1.05vw,13px)/1 var(--bn-font-ui,Montserrat,Inter,system-ui,sans-serif)!important;
  letter-spacing:.42em;text-transform:uppercase;
  color:rgba(242,242,244,.55)!important}
.comms-in h1,html.bna-pg body.comms-page .comms-in h1,html.bna-pg body.comms-page main h1{
  margin:0;
  font:700 clamp(64px,14vw,200px)/.86 var(--bn-font-ui,Montserrat,Inter,system-ui,sans-serif)!important;
  letter-spacing:-.045em;text-transform:uppercase;color:#fff!important;
  text-align:center}
/* Beat sitenav html body>#main {margin-left:var(--bn-col-m);width:auto} — edge to edge. */
html body.comms-page>main#main.comms-main{
  margin:0!important;margin-left:0!important;margin-right:0!important;
  width:100%!important;max-width:none!important;padding:0!important;
  padding-left:env(safe-area-inset-left)!important;
  padding-right:env(safe-area-inset-right)!important}
"""


def _page():
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        '<meta name="robots" content="index,follow">'
        + sitenav.head_html("comms")
        + '<link rel="stylesheet" href="/theme.css"><link rel="icon" href="/favicon.ico?v=5" sizes="any">'
        f'<style>{CSS}</style></head>'
        '<body class="comms-page"><a class="skip" href="#main">Skip to content</a>'
        + sitenav.header_html("")
        + '<main class="comms-main" id="main">'
        '<div class="comms-in"><p class="comms-k">Coming soon</p>'
        '<h1>Comms</h1></div></main>'
        '<script src="/api/search/app.js" defer></script>'
        '</body></html>'
    )


def handle_get(path, qs):
    p = (path or "").rstrip("/") or "/"
    if p == "/comms":
        return 200, _page(), "text/html"
    return 404, "Not found", "text/plain"
