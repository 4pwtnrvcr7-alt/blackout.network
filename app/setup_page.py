"""GET /setup — install the app and turn on alerts, with per-OS steps.

Matt 7:39 AM ET Nov 28: the open-menu Install / Notifications pills become regular
menu items (Install App, Alerts) that open this page (#install, #notifications).
Working buttons reuse BN.installApp / BN.enableAlerts / BN.showNotifyGuide from
static/pwa/install-guide.js and alerts.js. Static page: no Refresh control.
Never touches scanner core. Never says peer-to-peer.
"""
import html
import sitenav

E = lambda s: html.escape(str(s if s is not None else ""), quote=True)

CSS = """
.su{max-width:720px;margin:0 auto;padding:20px 20px 64px;color:#E6E8EB;font:15px/1.55 Inter,system-ui,sans-serif}
.su h1{margin:8px 0 10px;font:700 28px/1.15 Inter,system-ui,sans-serif;letter-spacing:.04em;text-transform:uppercase;color:#fff}
.su .lead{margin:0 0 28px;color:#C9CDD3;font-size:16px;line-height:1.5}
.su section{margin:0 0 28px;padding:20px 20px 22px;background:#0a0a0a;border:1px solid rgba(255,255,255,.12);border-radius:14px;scroll-margin-top:88px}
.su h2{margin:0 0 8px;font:700 13px/1.2 Inter,system-ui,sans-serif;letter-spacing:.14em;text-transform:uppercase;color:#fff}
.su h3{margin:18px 0 6px;font:700 12px/1.3 Inter,system-ui,sans-serif;letter-spacing:.1em;text-transform:uppercase;color:#C9CDD3}
.su p,.su li{margin:0 0 8px;color:#E6E8EB}
.su ol,.su ul{margin:0 0 10px;padding-left:22px}
.su .note{margin:12px 0 0;color:#8A8F98;font-size:13px}
.su .acts{display:flex;flex-wrap:wrap;gap:10px;margin:16px 0 0}
.su .su-btn{appearance:none;cursor:pointer;font:600 11px/1 Inter,system-ui,sans-serif;letter-spacing:.14em;text-transform:uppercase}
.su a{color:#fff}
.su a:hover{color:#C9CDD3}
@media(max-width:430px){.su{padding:16px 14px 48px}.su h1{font-size:24px}.su section{padding:16px}}
"""

JS = r"""
<script>
(function(){
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
})();
</script>
"""

BODY = """
<div class="su">
<h1>Set up BLACKOUT.NETWORK</h1>
<p class="lead">Put the app on your Home Screen, then turn on alerts. Steps differ by phone, tablet and computer. The buttons below use this browser’s install prompt and notification permission when they are available.</p>

<section id="install">
<h2>Install app</h2>
<p>Adding BLACKOUT.NETWORK to your Home Screen (or as a desktop app) gives you a full-screen icon and, on iPhone and iPad, is required before alerts will work.</p>

<h3>iPhone and iPad (Safari)</h3>
<ol>
<li>Open <b>blackout.network</b> in <b>Safari</b> (not inside another app’s browser).</li>
<li>Tap the <b>Share</b> button.</li>
<li>Scroll and tap <b>Add to Home Screen</b>, then <b>Add</b>. If you don’t see it, scroll further or tap <b>View More</b>.</li>
<li>Open the new <b>BLACKOUT.NETWORK</b> icon from your Home Screen.</li>
</ol>
<p class="note">Chrome, Edge or Firefox on iPhone or iPad: use that browser’s Share sheet, then Add to Home Screen. If it isn’t listed, open the page in Safari instead.</p>

<h3>Android (Chrome)</h3>
<ol>
<li>Open <b>blackout.network</b> in <b>Chrome</b>.</li>
<li>Tap the menu (⋮), then <b>Add to Home screen</b> or <b>Install app</b>.</li>
<li>Confirm, then open the app from your Home Screen.</li>
</ol>

<h3>Desktop — Chrome and Edge</h3>
<ol>
<li>Open <b>blackout.network</b> in Chrome or Edge.</li>
<li>Click the install icon in the address bar, or open the browser menu and choose <b>Install BLACKOUT.NETWORK</b>.</li>
<li>Confirm. The app opens in its own window.</li>
</ol>

<h3>Desktop — Safari (Mac)</h3>
<ol>
<li>Open <b>blackout.network</b> in Safari.</li>
<li>Choose <b>File → Add to Dock</b>, or use Share → Add to Dock, then confirm.</li>
</ol>

<h3>Desktop — Firefox</h3>
<p>Firefox does not always offer a full install. You can pin the tab or bookmark the site. For a standalone app window, use Chrome or Edge. You can still turn on alerts in Firefox (see below).</p>

<div class="acts"><button type="button" class="su-btn" data-su="install">Install app</button></div>
</section>

<section id="notifications">
<h2>Alerts</h2>
<p>Alerts use this browser’s notification permission. You can change or turn them off later in your device or browser settings.</p>

<h3>iPhone and iPad</h3>
<ol>
<li>Install the app to your Home Screen first (see <a href="#install">Install app</a>). Alerts do not work from a regular Safari tab.</li>
<li>You need <b>iOS 16.4</b> or later.</li>
<li>Open BLACKOUT.NETWORK from the Home Screen icon, tap <b>Turn on notifications</b> below, then tap <b>Allow</b>.</li>
</ol>

<h3>Android</h3>
<ol>
<li>Open the site or the installed app in Chrome.</li>
<li>Tap <b>Turn on notifications</b> below, then allow notifications when the system asks.</li>
</ol>

<h3>Desktop (Chrome, Edge, Safari, Firefox)</h3>
<ol>
<li>Open <b>blackout.network</b> in that browser (Safari on Mac needs a recent version with web notifications).</li>
<li>Click <b>Turn on notifications</b> below, then allow the permission prompt.</li>
</ol>
<p class="note">If nothing happens, the browser may already have notifications blocked. Check the site settings for blackout.network and allow notifications, then try again.</p>

<div class="acts"><button type="button" class="su-btn" data-su="notify">Turn on notifications</button></div>
</section>
</div>
"""


def page():
    body = (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        + sitenav.head_html("setup", "/setup")
        + "<link rel=\"stylesheet\" href=\"/theme.css\"><link rel=\"icon\" href=\"/favicon.ico?v=5\" sizes=\"any\">"
        f"<style>{CSS}</style></head>"
        "<body><a class=\"skip\" href=\"#main\">Skip to content</a>"
        + sitenav.site_top("setup")
        + "<main id=\"main\">" + BODY + "</main>"
        + JS
        + "</body></html>"
    )
    if "peer-to-peer" in body.lower() or "peer to peer" in body.lower():
        raise RuntimeError("setup page copy must not say peer-to-peer")
    return body


def handle_get(path, qs):
    p = (path or "").rstrip("/") or "/setup"
    if p != "/setup":
        return 404, {"error": "not found"}
    return 200, page().encode("utf-8"), "text/html"
