#!/usr/bin/env python3
"""Standalone-PWA menu check (iPhone 14/15 390x844 + 1440).

Serves the real header/menu (sitenav + v3 + apple CSS/JS) and fails unless, with
display-mode: standalone and a 47px top safe-area inset:
  - the open menu's wordmark and Close stay below the inset and are hittable
  - Close is at least 44px, and also closes via Escape, the backdrop, and Back
  - Home is the first menu item and goes to /
  - the header hamburger and theme toggle sit below the inset
  - the page scrolls again after the menu closes

Screenshots (menu open): /opt/cursor/artifacts/menu-open-390-dark.png,
menu-open-390-light.png, menu-open-1440.png.
"""
import os, sys, threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "app")
sys.path.insert(0, APP)
os.chdir(APP)
import sitenav

SAFE = 47
SHOTS = os.environ.get("BN_MENU_SHOTS", "/opt/cursor/artifacts")
FILES = {
    "/sitenav.css": ("static/sitenav.css", "text/css"),
    "/sitenav.js": ("static/sitenav.js", "application/javascript"),
    "/bn-v3.css": ("static/bn-v3.css", "text/css"),
    "/bn-v3.js": ("static/bn-v3.js", "application/javascript"),
    "/bn-apple.css": ("static/bn-apple.css", "text/css"),
    "/bn-apple.js": ("static/bn-apple.js", "application/javascript"),
    "/install-guide.css": ("static/pwa/install-guide.css", "text/css"),
}

def page(theme):
    top = sitenav.header_html("threat")
    # The live search widget is a separate script. A quiet field keeps the menu header in its real shape.
    top = top.replace(
        '<div class="bn-dsearch bn-js-only" id="bn_dsearch"></div>',
        '<div class="bn-dsearch bn-js-only" id="bn_dsearch"><div id="bns"><form role="search">'
        '<input id="bns_q" type="search" placeholder="Search threats, places, sources…" aria-label="Search all sources"></form></div></div>',
        1)
    return f"""<!doctype html><html lang="en" class="bna-pg" data-theme="{theme}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<link rel="stylesheet" href="/sitenav.css"><link rel="stylesheet" href="/install-guide.css">
<link rel="stylesheet" href="/bn-v3.css"><link rel="stylesheet" href="/bn-apple.css">
<script src="/sitenav.js" defer></script><script src="/bn-v3.js" defer></script><script src="/bn-apple.js" defer></script>
</head><body>
{top}
<main id="main"><div id="scroll-spacer" style="height:2400px;padding-top:24px">Page body for scroll.</div></main>
</body></html>"""

class H(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path.startswith("/fonts/"):
            fp = os.path.join(APP, "static", "fonts", os.path.basename(path))
            if os.path.isfile(fp):
                self._send(open(fp, "rb").read(), "font/woff2"); return
        if path in FILES:
            rel, ctype = FILES[path]
            self._send(open(os.path.join(APP, rel), "rb").read(), ctype); return
        theme = "light" if "theme=light" in self.path else "dark"
        self._send(page(theme).encode(), "text/html; charset=utf-8")
    def _send(self, body, ctype):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

def serve():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd

HIT = """(sel) => {
  const el = document.querySelector(sel); if (!el) return {missing:true};
  const r = el.getBoundingClientRect();
  const x = Math.min(window.innerWidth - 2, Math.max(2, r.left + r.width / 2));
  const y = Math.min(window.innerHeight - 2, Math.max(2, r.top + Math.min(r.height / 2, 30)));
  const hit = document.elementFromPoint(x, y);
  const cs = getComputedStyle(el);
  return {top:r.top, left:r.left, w:r.width, h:r.height, x, y,
    pad: cs.paddingTop, pos: cs.position,
    hit: hit ? (hit.closest(sel) === el || el.contains(hit)) : false,
    hitTag: hit ? (hit.className && String(hit.className).slice(0, 40) || hit.tagName) : ""};
}"""

def fail(msg):
    print("FAIL", msg); raise SystemExit(1)

def main():
    os.makedirs(SHOTS, exist_ok=True)
    httpd = serve()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    from playwright.sync_api import sync_playwright
    errs = []
    def check(cond, msg):
        print(("ok " if cond else "FAIL ") + msg)
        if not cond: errs.append(msg)

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            check_phone(browser, base, check)
            check_desktop(browser, base, check)
        finally:
            browser.close()
    httpd.shutdown()
    if errs:
        print(f"\n{len(errs)} failed"); raise SystemExit(1)
    print("\nall checks passed")
    print("shots:", SHOTS)

def standalone(page):
    # Chrome's media emulation does not implement display-mode. Ask for it anyway, then confirm the
    # shipped stylesheet. The inset is simulated by overriding --bn-safe-top (production value is
    # env(safe-area-inset-top)), which is 0 in a desktop tab.
    try:
        page.context.new_cdp_session(page).send("Emulation.setEmulatedMedia", {
            "media": "screen", "features": [{"name": "display-mode", "value": "standalone"}]})
    except Exception as e:
        print("display-mode emulation unavailable:", e)
    page.add_init_script(
        "document.addEventListener('DOMContentLoaded',function(){"
        f"document.documentElement.style.setProperty('--bn-safe-top','{SAFE}px')}})")

def open_menu(page):
    page.locator("header.bn-top .bn-burger").click()
    page.wait_for_function("() => document.getElementById('bn-menu').classList.contains('bn-open')")

def check_phone(browser, base, check):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    page = ctx.new_page()
    standalone(page)
    page.goto(base + "/inside", wait_until="domcontentloaded")
    page.wait_for_function("() => window.bnMenuOpen")
    media = page.evaluate("() => matchMedia('(display-mode: standalone)').matches")
    print("display-mode standalone match:", media)
    rule = page.evaluate(r"""() => {
      let found = false;
      for (const sheet of document.styleSheets) {
        let rules; try { rules = sheet.cssRules } catch (e) { continue }
        for (const r of rules) {
          if (r.type === CSSRule.MEDIA_RULE && /display-mode:\s*standalone/.test(r.conditionText) && /bn-top/.test(r.cssText) && /padding-top:\s*0/.test(r.cssText)) found = true;
        }
      }
      return found;
    }""")
    check(rule, "standalone stylesheet drops body padding so it does not stack on the header")
    safe = page.evaluate("() => getComputedStyle(document.documentElement).getPropertyValue('--bn-safe-top').trim()")
    check(safe == f"{SAFE}px", f"safe-area top override is {SAFE}px (got {safe})")

    # header: hamburger and the sun/moon toggle (shown in the bar on current main)
    burger = page.evaluate(HIT, "header.bn-top .bn-burger")
    header_pad = page.evaluate("() => getComputedStyle(document.querySelector('header.bn-top')).paddingTop")
    check(header_pad == f"{SAFE}px", f"header padding-top is the safe inset (got {header_pad})")
    check(burger["top"] >= SAFE - 0.5 and burger["hit"], f"hamburger below the status bar and hittable {burger}")
    check(burger["top"] < SAFE + 40, f"hamburger is not double-padded {burger}")
    theme_shown = page.evaluate("""() => {
      const b = document.querySelector('header.bn-top .bn-theme-bar');
      const cs = getComputedStyle(b);
      return cs.display !== 'none' && cs.visibility !== 'hidden';
    }""")
    check(theme_shown, "header sun/moon toggle is shown")
    theme = page.evaluate(HIT, "header.bn-top .bn-theme-bar")
    check(theme["top"] >= SAFE - 0.5 and theme["h"] >= 44 and theme["hit"], f"header sun/moon toggle below the status bar {theme}")

    open_menu(page)
    bar = page.evaluate(HIT, "#bn-menu .bn-mbar")
    word = page.evaluate(HIT, "#bn-menu .bn-mbar .bn-logo")
    close = page.evaluate(HIT, "#bn-menu .bn-mbar .bn-close")
    check(bar["pos"] == "sticky", f"menu top row is sticky (got {bar['pos']})")
    check(word["top"] >= SAFE - 0.5 and word["hit"] and word["h"] >= 44, f"wordmark below the inset and tappable {word}")
    check(close["top"] >= SAFE - 0.5 and close["w"] >= 44 and close["h"] >= 44 and close["hit"], f"Close is >=44px and hittable {close}")
    home = page.evaluate("""() => {
      const a = document.querySelector('#bn-menu .m3-latest ul li a');
      return a && {text:a.textContent.trim(), href:a.getAttribute('href')};
    }""")
    check(home and home["text"] == "Home" and home["href"] == "/", f"Home is the first menu item {home}")
    items = page.evaluate("""() => [...document.querySelectorAll('#bn-menu .m3-p li')].map(li => {
      const a = li.querySelector('a');
      return {text: li.textContent.replace(/\\s+/g,' ').trim(), href: a ? a.getAttribute('href') : '', soon: li.classList.contains('m3-soon')};
    })""")
    by = {it["text"].split(" SOON")[0].strip(): it for it in items}
    check(not any(it["text"].startswith("The Thread") for it in items), f"The Thread is not in the menu {items}")
    check(by.get("Starlink", {}).get("href") == "/network/starlink" and not by.get("Starlink", {}).get("soon"), f"Starlink is a live link {by.get('Starlink')}")
    check(by.get("Networks near me", {}).get("href") == "/network/near" and not by.get("Networks near me", {}).get("soon"), f"Networks near me is a live link {by.get('Networks near me')}")
    menu_theme = page.evaluate(HIT, "#bn-menu .bn-theme-row")
    check(menu_theme["top"] >= SAFE - 0.5 and menu_theme["h"] >= 44, f"menu theme toggle below the inset {menu_theme}")

    # sticky row survives scrolling the menu
    page.evaluate("() => { document.querySelector('#bn-menu .bn-panel').scrollTop = 2000 }")
    page.wait_for_timeout(100)
    close2 = page.evaluate(HIT, "#bn-menu .bn-mbar .bn-close")
    word2 = page.evaluate(HIT, "#bn-menu .bn-mbar .bn-logo")
    check(close2["top"] >= SAFE - 0.5 and close2["top"] < 160 and close2["hit"], f"Close stays on screen after menu scroll {close2}")
    check(word2["hit"] and word2["top"] >= SAFE - 0.5, f"wordmark stays on screen after menu scroll {word2}")
    page.evaluate("() => { document.querySelector('#bn-menu .bn-panel').scrollTop = 0 }")
    page.mouse.move(20, 700)
    page.evaluate("() => { const a = document.activeElement; if (a && a.blur) a.blur() }")

    page.screenshot(path=os.path.join(SHOTS, "menu-open-390-dark.png"))
    page.locator("#bn-menu [data-bn-theme]").click()
    page.wait_for_function("() => document.documentElement.getAttribute('data-theme')==='light'")
    check(page.evaluate("() => document.getElementById('bn-menu').classList.contains('bn-open')"), "theme toggle does not close the menu")
    page.mouse.move(20, 700)
    page.evaluate("() => { const a = document.activeElement; if (a && a.blur) a.blur() }")
    page.screenshot(path=os.path.join(SHOTS, "menu-open-390-light.png"))
    page.locator("#bn-menu [data-bn-theme]").click()
    page.wait_for_function("() => document.documentElement.getAttribute('data-theme')==='dark'")

    # Escape
    page.keyboard.press("Escape")
    page.wait_for_function("() => !document.getElementById('bn-menu').classList.contains('bn-open') && !(history.state && history.state.bnMenu)")
    check(not page.evaluate("() => document.documentElement.classList.contains('bn-lock')"), "scroll lock cleared after Escape")
    page.evaluate("() => window.scrollTo(0, 700)")
    sy = page.evaluate("() => window.scrollY")
    check(sy > 200, f"page scrolls after close (scrollY {sy})")
    page.evaluate("() => window.scrollTo(0, 0)")

    # Close button + history does not pile up
    n0 = page.evaluate("() => history.length")
    open_menu(page)
    page.locator("#bn-menu .bn-mbar .bn-close").click()
    page.wait_for_function("() => !document.getElementById('bn-menu').classList.contains('bn-open') && !(history.state && history.state.bnMenu)")
    n1 = page.evaluate("() => history.length")
    check(n1 == n0, f"Close pops the menu history entry ({n0} -> {n1})")

    # backdrop: the full-page menu covers the scrim, so dispatch the click on the scrim itself
    open_menu(page)
    here = page.url
    page.evaluate("""() => document.querySelector('#bn-menu .bn-scrim').click()""")
    page.wait_for_function("() => !document.getElementById('bn-menu').classList.contains('bn-open') && !(history.state && history.state.bnMenu)")
    check(page.url.split("#")[0] == here.split("#")[0], f"backdrop click closes the menu without navigating ({page.url})")

    # Android/browser Back, on a fresh load so earlier closes cannot drain the stack
    page.goto(base + "/section", wait_until="domcontentloaded")
    page.wait_for_function("() => window.bnMenuOpen")
    open_menu(page)
    page.wait_for_function("() => history.state && history.state.bnMenu")
    page.go_back()
    page.wait_for_function("() => !document.getElementById('bn-menu').classList.contains('bn-open')")
    check("/section" in page.url, f"Back closes the menu and stays on the page ({page.url})")

    # Home, then the wordmark, both leave for /
    open_menu(page)
    page.locator("#bn-menu a[data-nav=home]").click()
    page.wait_for_url("**/")
    check(page.url.split("?")[0].rstrip("/") == base.rstrip("/"), f"Home navigates to / ({page.url})")
    check(not page.evaluate("() => document.getElementById('bn-menu').classList.contains('bn-open')"), "menu is closed on the home page")
    page.goto(base + "/inside", wait_until="domcontentloaded")
    page.wait_for_function("() => window.bnMenuOpen")
    open_menu(page)
    page.locator("#bn-menu .bn-mbar .bn-logo").click()
    page.wait_for_url("**/")
    check(page.url.rstrip("/") == base.rstrip("/"), f"wordmark navigates home ({page.url})")
    check(not page.evaluate("() => document.getElementById('bn-menu').classList.contains('bn-open')"), "menu is closed after the wordmark")
    page.evaluate("() => window.scrollTo(0, 400)")
    check(page.evaluate("() => window.scrollY") > 100, "home page scrolls")
    ctx.close()

def check_desktop(browser, base, check):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
    page = ctx.new_page()
    page.goto(base + "/", wait_until="domcontentloaded")
    page.wait_for_function("() => window.bnMenuOpen")
    open_menu(page)
    page.wait_for_timeout(250)
    close = page.evaluate(HIT, "#bn-menu .bn-close")
    word = page.evaluate(HIT, "#bn-menu .bn-mbar .bn-logo, #bn-menu .bn-mhead .bn-logo")
    home = page.evaluate("""() => {
      const a = document.querySelector('#bn-menu a[data-nav=home]');
      const r = a.getBoundingClientRect();
      return {text:a.textContent.trim(), top:r.top, h:r.height, w:r.width};
    }""")
    check(close["w"] >= 44 and close["h"] >= 44 and close["hit"], f"1440 Close is hittable {close}")
    check(word["hit"], f"1440 wordmark is tappable {word}")
    check(home["text"] == "Home" and home["h"] > 0, f"1440 Home is visible {home}")
    # desktop header has no standalone inset
    pad = page.evaluate("() => getComputedStyle(document.querySelector('header.bn-top')).paddingTop")
    check(pad in ("0px", "auto"), f"1440 header has no extra top inset (got {pad})")
    page.mouse.move(20, 700)
    page.evaluate("() => { const a = document.activeElement; if (a && a.blur) a.blur() }")
    page.screenshot(path=os.path.join(SHOTS, "menu-open-1440.png"))
    page.locator("#bn-menu .bn-close").focus()
    page.keyboard.press("Escape")
    page.wait_for_function("() => !document.getElementById('bn-menu').classList.contains('bn-open')")
    page.evaluate("() => window.scrollTo(0, 500)")
    check(page.evaluate("() => window.scrollY") > 100, "1440 page scrolls after close")
    ctx.close()

if __name__ == "__main__":
    main()
