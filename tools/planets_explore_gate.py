#!/usr/bin/env python3
"""Pre-merge / live check: Moon close-zoom and Apollo 11 pin info in the solar explorer.

Routes local solar3d.js, planets3d.js and /api/netmap/planets/* over the live /grid page
so the check can run before merge. After merge, --live uses the deployed files.

  python3 tools/planets_explore_gate.py https://blackout.network
  python3 tools/planets_explore_gate.py https://blackout.network --live
"""
from __future__ import annotations
import argparse, json, mimetypes, sys, time
from pathlib import Path

CHROME = "/usr/bin/google-chrome"
ARGS = ["--no-sandbox", "--disable-dev-shm-usage", "--use-gl=angle", "--use-angle=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"]
VIEWS = [("iphone-390", 390, 844), ("desktop-1440", 1440, 900)]
STATIC = Path(__file__).resolve().parents[1] / "app" / "netmap_static"

JS_EVAL = """() => {
  const s = window.BNSolar && window.BNSolar._state && window.BNSolar._state();
  const p = window.BNPlanets && window.BNPlanets._state && window.BNPlanets._state();
  const info = document.getElementById("s3_info");
  const el = document.getElementById("bn_s3");
  const cam = window.BNSolar && window.BNSolar._cam;
  return {
    solar: s || null,
    planets: p || null,
    open: !!(el && !el.hidden),
    info: info ? info.innerText : "",
    infoHtml: info ? info.innerHTML : ""
  };
}"""


def route_local(page):
    mapping = {
        "/api/netmap/solar3d.js": STATIC / "solar3d.js",
        "/api/netmap/planets3d.js": STATIC / "planets3d.js",
    }

    def fulfill_file(route, path: Path):
        b64 = Path(str(path) + ".b64")
        if not path.is_file() and b64.is_file():
            import base64
            suffix = path.suffix.lower()
            ctype = {".js": "application/javascript; charset=utf-8", ".json": "application/json",
                     ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                     ".webp": "image/webp", ".txt": "text/plain; charset=utf-8"}.get(suffix, "application/octet-stream")
            return route.fulfill(status=200, content_type=ctype, headers={"cache-control": "no-store"}, body=base64.b64decode(b64.read_text()))
        if not path.is_file():
            return route.fallback()
        suffix = path.suffix.lower()
        ctype = {".js": "application/javascript; charset=utf-8", ".json": "application/json",
                 ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                 ".webp": "image/webp", ".txt": "text/plain; charset=utf-8"}.get(suffix, "application/octet-stream")
        route.fulfill(status=200, content_type=ctype, headers={"cache-control": "no-store"}, body=path.read_bytes())

    def on_js(route):
        url = route.request.url
        for key, path in mapping.items():
            if key in url:
                return fulfill_file(route, path)
        route.fallback()

    def on_planet(route):
        url = route.request.url
        # /api/netmap/planets/<file>
        name = url.split("/api/netmap/planets/", 1)[-1].split("?", 1)[0]
        path = (STATIC / "planets" / name).resolve()
        root = (STATIC / "planets").resolve()
        if not str(path).startswith(str(root) + "/") and path != root:
            return route.fulfill(status=404, body=b"not found")
        return fulfill_file(route, path)

    page.route("**/api/netmap/solar3d.js**", on_js)
    page.route("**/api/netmap/planets3d.js**", on_js)
    page.route("**/api/netmap/planets/**", on_planet)


def run_view(browser, name, w, h, base, live, shots):
    errors = []
    page = browser.new_page(viewport={"width": w, "height": h})
    page.on("pageerror", lambda e: errors.append(str(e)))
    if not live:
        route_local(page)
    url = base.rstrip("/") + "/grid#sky"
    page.goto(url, wait_until="load", timeout=45000)
    page.wait_for_timeout(4000)
    # open Sky if the hash did not already
    if not page.evaluate("() => document.body.classList.contains('nx-sky')"):
        btn = page.locator("button:has-text('Sky'), [data-mode='sky'], #nx_mode_sky")
        if btn.count():
            btn.first.click()
            page.wait_for_timeout(2000)
    # Solar system chip
    chip = page.locator('#nx_sf button[data-g="ss"]')
    chip.wait_for(timeout=20000)
    chip.click()
    page.wait_for_timeout(1000)
    # Wait for explorer + Horizons payload
    ok = False
    for _ in range(40):
        st = page.evaluate("""() => ({
            solar: !!(window.BNSolar),
            open: !!(document.getElementById('bn_s3') && !document.getElementById('bn_s3').hidden),
            data: !!(window.BNSolar && window.BNSolar._state && window.BNSolar._state().data),
            objs: (window.BNSolar && window.BNSolar._state && window.BNSolar._state().objects) || []
        })""")
        if st.get("solar") and st.get("data") and "moon" in st.get("objs", []):
            ok = True
            break
        page.wait_for_timeout(1000)
    if not ok:
        page.wait_for_timeout(2000)
    # Focus the Moon, then the Apollo 11 pin
    page.evaluate("""() => {
        if (window.BNSolar) window.BNSolar.focus('moon');
    }""")
    page.wait_for_timeout(2500)
    # textures / module may still be attaching
    for _ in range(20):
        pst = page.evaluate("() => window.BNPlanets && window.BNPlanets._state && window.BNPlanets._state()")
        if pst and pst.get("attached") and "apollo11" in (pst.get("pins") or []):
            break
        page.wait_for_timeout(500)
    page.evaluate("""() => {
        if (window.BNPlanets && window.BNPlanets.openSite) window.BNPlanets.openSite('moon', 'apollo11');
    }""")
    page.wait_for_timeout(1500)
    st = page.evaluate(JS_EVAL)
    if shots:
        Path(shots).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(shots) / f"{name}-moon-apollo11.png"), full_page=False)
    # Mars focus + overview for visual QA (pt1841u)
    page.evaluate("() => { if (window.BNSolar) window.BNSolar.focus('mars'); }")
    page.wait_for_timeout(1600)
    if shots:
        page.screenshot(path=str(Path(shots) / f"{name}-mars.png"), full_page=False)
    page.evaluate("() => { if (window.BNSolar) window.BNSolar.focus('earth'); }")
    page.wait_for_timeout(1600)
    if shots:
        page.screenshot(path=str(Path(shots) / f"{name}-earth-aurora.png"), full_page=False)
    page.evaluate("() => { if (window.BNSolar) window.BNSolar.focus('jupiter'); }")
    page.wait_for_timeout(1600)
    if shots:
        page.screenshot(path=str(Path(shots) / f"{name}-jupiter-aurora.png"), full_page=False)
    page.evaluate("() => { var b = document.getElementById('s3_all'); if (b) b.click(); }")
    page.wait_for_timeout(1400)
    if shots:
        page.screenshot(path=str(Path(shots) / f"{name}-overview.png"), full_page=False)
    info = (st.get("info") or "")
    problems = []
    if errors:
        problems.append("pageerrors: " + " | ".join(errors[:8]))
    if not st.get("open"):
        problems.append("explorer not open")
    if "Armstrong" not in info and "Tranquility" not in info:
        problems.append("Apollo 11 info missing: " + info[:240])
    if st.get("planets") and not st["planets"].get("attached"):
        problems.append("BNPlanets not attached")
    au = (st.get("planets") or {}).get("auroras") or []
    for need in ("earth", "jupiter", "saturn"):
        if need not in au:
            problems.append("aurora missing: " + need)
    # camera should be close to the Moon (focusDist ~ size*2.2, moon size 0.18)
    print(name, "FAIL" if problems else "OK", json.dumps({"errors": errors, "info": info[:400], "state": {k: st[k] for k in st if k != "infoHtml"}, "problems": problems}))
    page.close()
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base", nargs="?", default="https://blackout.network")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--shots", default="")
    args = ap.parse_args()
    from playwright.sync_api import sync_playwright
    bad = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=CHROME, args=ARGS)
        for name, w, h in VIEWS:
            bad.extend(run_view(browser, name, w, h, args.base, args.live, args.shots))
        browser.close()
    if bad:
        print("PLANETS_GATE_FAIL")
        sys.exit(1)
    print("PLANETS_GATE_OK")
    sys.exit(0)

if __name__ == "__main__":
    main()
