""" /comms — coming-soon lander for the Comms product (pt2031u).

Full-screen, dark, SpaceX-style page. The email field posts to the existing
newsletter subscribe endpoint (POST /api/newsletter/subscribe) with source=comms,
stored as subscribers.signup_source. No new list and no new accounts.
Does not mention radio protocols or hardware vendors. Not in the main menu
(adding a large menu5 link would reflow the just-shipped menu animation).
"""
import html
import sitenav
import newsletter as NL

E = lambda s: html.escape(str(s if s is not None else ""), quote=True)

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
.comms-in h1{margin:0 0 18px;font:700 clamp(52px,16vw,112px)/.92 var(--bn-font-ui,Inter,system-ui,sans-serif);
  letter-spacing:-.04em;text-transform:uppercase;color:#fff}
.comms-lede{margin:0 0 32px;max-width:22em;font:400 17px/1.45 var(--bn-font-body,Inter,system-ui,sans-serif);color:#c9ced5}
body.comms-page .nlx-form{margin:0;max-width:36rem;background:none;border:0;padding:0}
body.comms-page .nlx-form .nl-row{max-width:520px}
body.comms-page .nlx-form .nl-row{display:flex;gap:10px;align-items:stretch}
body.comms-page .nlx-form .nl-row input[type=email]{flex:1 1 auto;min-width:0;min-height:48px;height:48px;
  padding:0 14px;border:1px solid rgba(255,255,255,.35);border-radius:0;background:rgba(0,0,0,.35);
  color:#fff;font:400 16px/1.2 Inter,system-ui,sans-serif}
body.comms-page .nlx-form .nl-row input[type=email]::placeholder{color:#8b95a3}
body.comms-page .nlx-form .nl-row input[type=email]:focus,body.comms-page .nlx-form .nl-row input[type=email]:focus-visible{
  outline:2px solid #fff;outline-offset:2px;border-color:#fff}
body.comms-page .nlx-form .nl-row input[aria-invalid=true]{border-color:#ff8a80}
body.comms-page .nlx-form button.pri{flex:none;min-height:48px;height:48px;padding:0 22px;border-radius:0;
  background:#fff;color:#000;border:1px solid #fff;font:700 15px/1 Inter,system-ui,sans-serif;
  letter-spacing:.02em;cursor:pointer}
body.comms-page .nlx-form button.pri:hover,body.comms-page .nlx-form button.pri:focus-visible{
  background:transparent;color:#fff}
body.comms-page .nlx-form button.pri:focus-visible{outline:2px solid #fff;outline-offset:2px}
body.comms-page .nlx-form button.pri[disabled]{opacity:.6;cursor:wait}
body.comms-page .nlx-form .nl-msg{margin:12px 0 0;min-height:1.3em;font:400 14px/1.45 Inter,system-ui,sans-serif}
body.comms-page .nlx-form .nl-msg:empty{display:none}
body.comms-page .nlx-form .nl-msg.ok{color:#e6e9ee}
body.comms-page .nlx-form .nl-msg.err{color:#ff8a80}
body.comms-page .nlx-form .nl-priv{margin:14px 0 0;font:400 11px/1.55 Inter,system-ui,sans-serif;color:#6f7782}
body.comms-page .nlx-form .nl-priv a{color:#9aa3ad;text-decoration:underline;text-underline-offset:2px}
body.comms-page .nlx-form .nl-priv a:hover,body.comms-page .nlx-form .nl-priv a:focus-visible{color:#fff}
body.comms-page .nlx-form .nl-trk{margin:12px 0 0}
body.comms-page .nlx-form .nl-trk .nl-chk{display:flex;gap:8px;align-items:flex-start;font:400 12.5px/1.45 Inter,system-ui,sans-serif;color:#9aa3ad}
body.comms-page .nlx-form .nl-trk input{flex:none;width:16px;height:16px;margin:2px 0 0;accent-color:#fff}
.comms-foot{position:relative;z-index:1;margin-top:48px;font:400 12px/1.5 Inter,system-ui,sans-serif;color:#6f7782}
.comms-foot a{color:#9aa3ad;text-decoration:none}
.comms-foot a:hover,.comms-foot a:focus-visible{color:#fff;text-decoration:underline;text-underline-offset:2px}
@media(max-width:639px){
  body.comms-page .nlx-form .nl-row{flex-wrap:wrap}
  body.comms-page .nlx-form .nl-row input[type=email],body.comms-page .nlx-form button.pri{flex-basis:100%;width:100%}
}
@media(min-width:800px){
  .comms-in{margin-left:clamp(32px,12vw,180px);margin-right:auto}
  .comms-lede{font-size:20px;margin-bottom:40px}
  .comms-k{font-size:12px}
}
@media(prefers-reduced-motion:reduce){
  .comms-bg::after{animation:none}
  body.comms-page .nlx-form button.pri{transition:none}
}
"""


def _page():
    form = NL.form_html("comms")
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="index,follow">'
        + sitenav.head_html("comms")
        + '<link rel="stylesheet" href="/theme.css"><link rel="icon" href="/favicon.ico?v=5" sizes="any">'
        '<link rel="stylesheet" href="/api/newsletter/app.css">'
        f'<style>{CSS}</style></head>'
        '<body class="comms-page"><a class="skip" href="#main">Skip to content</a>'
        + sitenav.header_html("")
        + '<main class="comms-main" id="main"><div class="comms-bg" aria-hidden="true"></div>'
        '<div class="comms-in"><p class="comms-k">Coming soon</p>'
        '<h1>Comms</h1>'
        '<p class="comms-lede">Communications that work when the grid does not.</p>'
        f'{form}'
        '<p class="comms-foot"><a href="/newsletter">Newsletter</a> · '
        '<a href="/privacy">Privacy</a> · <a href="/tos">Terms</a></p>'
        '</div></main>'
        '<script src="/api/newsletter/app.js" defer></script>'
        '<script src="/api/search/app.js" defer></script>'
        '</body></html>'
    )


def handle_get(path, qs):
    p = (path or "").rstrip("/") or "/"
    if p == "/comms":
        return 200, _page(), "text/html"
    return 404, "Not found", "text/plain"
