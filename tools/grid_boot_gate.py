#!/usr/bin/env python3
"""Mandatory /grid boot gate (Nov 24 2026, after #139).

Load /grid in headless Chromium at 390x844 and 1440x900, wait_until="load", then 15 s.
Fail if any pageerror is thrown or map layers do not render.

Usage:
  python3 tools/grid_boot_gate.py https://blackout.network
  python3 tools/grid_boot_gate.py https://blackout.network --js app/netmap_static/net.js
  python3 tools/grid_boot_gate.py https://blackout.network --js app/netmap_static/net.js --sky

--js serves a local net.js in place of the live file (pre-merge check of built JS).
--sky also opens /grid#sky after the boot gate and checks zoom/chip; does not fail the boot gate if Sky-only checks fail unless --require-sky.
"""
from __future__ import annotations

import argparse, json, sys, time
from pathlib import Path

CHROME = "/usr/bin/google-chrome"
ARGS = ["--no-sandbox", "--disable-dev-shm-usage", "--use-gl=angle", "--use-angle=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"]
VIEWS = [("iphone-390", 390, 844), ("desktop-1440", 1440, 900)]

JS_STATE = """() => {
  const map = window.__nxMap;
  const errs = [];
  const canvas = document.querySelector('#nx_map canvas') || document.querySelector('.nx-map canvas') || document.querySelector('canvas.maplibregl-canvas');
  let nLayers = 0, zoom = null, styleLoaded = false, layerIds = [];
  try {
    zoom = map && map.getZoom && map.getZoom();
    styleLoaded = !!(map && map.isStyleLoaded && map.isStyleLoaded());
    const st = map && map.getStyle && map.getStyle();
    layerIds = (st && st.layers || []).map(l => l.id);
    nLayers = layerIds.length;
  } catch (e) { errs.push(String(e)); }
  const chip = document.getElementById('nx_sum') ? document.getElementById('nx_sum').textContent : '';
  return {
    ready: document.body.classList.contains('nx-ready'),
    sky: document.body.classList.contains('nx-sky'),
    hasMap: !!map,
    hasCanvas: !!(canvas && canvas.width > 0 && canvas.height > 0),
    canvasCss: canvas ? [canvas.clientWidth, canvas.clientHeight] : null,
    nLayers, zoom, styleLoaded, layerIds: layerIds.slice(0, 12),
    sum: chip, href: location.href, body: document.body.className
  };
}"""


def run_view(browser, name, w, h, base, js_path, want_sky, require_sky, shots):
    from playwright.sync_api import sync_playwright  # noqa: F401
    errors = []
    page = browser.new_page(viewport={"width": w, "height": h})
    page.on("pageerror", lambda e: errors.append(str(e)))
    if js_path:
        local = Path(js_path).read_bytes()
        def fulfill(route):
            route.fulfill(status=200, content_type="application/javascript; charset=utf-8",
                          headers={"cache-control": "no-store"}, body=local)
        page.route("**/api/netmap/net.js**", fulfill)
    url = base.rstrip("/") + "/grid"
    page.goto(url, wait_until="load", timeout=45000)
    page.wait_for_timeout(15000)
    st = page.evaluate(JS_STATE)
    if shots:
        Path(shots).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(shots) / f"{name}-grid.png"))
    problems = []
    if errors:
        problems.append("pageerrors: " + " | ".join(errors[:8]))
    if not st.get("hasMap"):
        problems.append("window.__nxMap missing")
    if not st.get("hasCanvas"):
        problems.append("map canvas missing or zero size")
    if not st.get("nLayers"):
        problems.append("no map layers rendered")
    if "VERTEX_SHADER" in " ".join(errors):
        problems.append("VERTEX_SHADER pageerror (likely a function-name collision in net.js)")
    print(f"{name} /grid", "FAIL" if problems else "OK", json.dumps({"errors": errors, "state": st, "problems": problems}))
    sky_notes = []
    if want_sky:
        # A second goto to #sky does not re-run the first-load hook; click the Sky control instead.
        page.click('#nx_mode button[data-m="sky"]')
        page.wait_for_timeout(15000)
        sk = page.evaluate(JS_STATE)
        sk2 = page.evaluate("""() => {
          const map = window.__nxMap;
          let hasLayer = false, vis2d = null, minz = null;
          try {
            hasLayer = !!(map && map.getLayer && map.getLayer('sats3d'));
            vis2d = map && map.getLayer('sat') ? map.getLayoutProperty('sat', 'visibility') : null;
            minz = map && map.getMinZoom && map.getMinZoom();
          } catch (e) {}
          const chip = document.getElementById('nx_chip');
          const iel = chip && chip.querySelector('i');
          return {
            sky: document.body.classList.contains('nx-sky'),
            sum: (document.getElementById('nx_sum') || {}).textContent,
            zoom: map && map.getZoom && map.getZoom(),
            minz, hasLayer, vis2d,
            chipClass: chip && chip.className,
            chipDot: iel ? getComputedStyle(iel).display : null
          };
        }""")
        if shots:
            page.screenshot(path=str(Path(shots) / f"{name}-sky.png"))
        print(f"{name} /grid#sky", json.dumps({"boot": sk, "sky": sk2}))
        if require_sky:
            if not sk2.get("sky"):
                sky_notes.append("body.nx-sky not set")
            if not sk2.get("hasLayer"):
                sky_notes.append("sats3d layer missing")
            if sk2.get("hasLayer") and sk2.get("vis2d") not in (None, "none"):
                sky_notes.append("2D sat layer still visible while 3D is on")
            if errors:
                sky_notes.append("pageerrors during sky: " + " | ".join(errors[:8]))
            if sky_notes:
                problems.extend(sky_notes)
    page.close()
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base", nargs="?", default="https://blackout.network")
    ap.add_argument("--js", default="", help="local net.js to inject in place of /api/netmap/net.js")
    ap.add_argument("--sky", action="store_true")
    ap.add_argument("--require-sky", action="store_true")
    ap.add_argument("--shots", default="")
    a = ap.parse_args()
    js_path = a.js or None
    if js_path and not Path(js_path).is_file():
        print("missing --js file", js_path, file=sys.stderr)
        return 2
    from playwright.sync_api import sync_playwright
    failed = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME, args=ARGS)
        try:
            for name, w, h in VIEWS:
                problems = run_view(browser, name, w, h, a.base, js_path, a.sky, a.require_sky, a.shots)
                if problems:
                    failed.append((name, problems))
        finally:
            browser.close()
    if failed:
        print("GATE_FAIL", json.dumps(failed))
        return 1
    print("GATE_OK")
    return 0

if __name__ == "__main__":
    sys.exit(main())
