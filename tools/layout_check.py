#!/usr/bin/env python3
"""Header/layout overlap check for BLACKOUT.NETWORK (t357).

Loads key pages in headless Chromium at phone..2560 px widths (and 90/125 % browser zoom) and FAILS if:
  - any two visible top-bar items (logo, primary nav links, follow links, icon buttons) intersect,
  - the logo/wordmark is clipped (its text is wider than its box) or any bar item spills outside the bar,
  - the top bar overlaps the page title / banners below it,
  - the page scrolls sideways (scrollWidth > clientWidth),
  - the content column's left and right gutters differ by more than 2 px,
  - the top bar changes height after the page settles (banners / late scripts must not shift it).

usage: python3 tools/layout_check.py [BASE_URL] [--shots DIR] [--pages /,/sources] [--widths 1280,1920]
exit 0 = all pass, 1 = failures.  Needs: pip install playwright && playwright install chromium
"""
import sys, argparse, json

PAGES = ["/", "/#figures", "/sources", "/scoring", "/newsletter", "/privacy", "/tos", "/social", "/report-status"]
WIDTHS = [320, 360, 390, 768, 1024, 1100, 1200, 1280, 1366, 1440, 1536, 1920, 2560]
ZOOMS = [(1280, 0.9), (1280, 1.25), (1920, 0.9), (1920, 1.25), (1366, 1.25), (1536, 1.25)]

JS = r"""() => {
 const vis = el => { if(!el) return false; const cs = getComputedStyle(el); const r = el.getBoundingClientRect();
   return cs.display!=='none' && cs.visibility!=='hidden' && +cs.opacity>0 && r.width>1 && r.height>1 };
 const box = el => { const r = el.getBoundingClientRect(); return {l:r.left,t:r.top,r:r.right,b:r.bottom,w:r.width,h:r.height} };
 const name = el => (el.className && String(el.className).split(' ')[0] || el.tagName.toLowerCase()) + ':' + (el.innerText||el.getAttribute('aria-label')||'').trim().replace(/\s+/g,' ').slice(0,24);
 const errs = [];
 const de = document.documentElement;
 if (de.scrollWidth > de.clientWidth) errs.push(`horizontal scroll: scrollWidth ${de.scrollWidth} > clientWidth ${de.clientWidth}`);
 const hdr = document.querySelector('header.bn-top'), bar = hdr && hdr.querySelector('.bn-tbar');
 if (!bar) { errs.push('no top bar'); return {errs}; }
 const hb = box(hdr), bb = box(bar);
 const items = [];
 const logo = bar.querySelector('.bn-logo');
 if (logo) items.push(logo);
 bar.querySelectorAll('.bn-primary a, .bn-acts a.bn-follow, .bn-acts .bn-ib, .bn-acts button, .bn-acts > a').forEach(e => { if(!items.includes(e)) items.push(e) });
 const V = items.filter(vis);
 if (!logo || !vis(logo)) errs.push('logo not visible');
 else {
   if (logo.scrollWidth > logo.clientWidth + 1) errs.push(`logo clipped: text ${logo.scrollWidth}px in ${logo.clientWidth}px box`);
   const w = logo.querySelector('.bn-word'); if (w && vis(w)) { const a = box(w), l = box(logo);
     if (a.r > l.r + 1 || a.l < l.l - 1) errs.push(`wordmark spills out of logo box (${Math.round(a.l)}-${Math.round(a.r)} vs ${Math.round(l.l)}-${Math.round(l.r)})`); }
 }
 for (let i=0;i<V.length;i++){ const a = box(V[i]);
   if (a.l < bb.l - 1 || a.r > bb.r + 1 || a.t < bb.t - 1 || a.b > bb.b + 1) errs.push(`${name(V[i])} outside bar`);
   for (let j=i+1;j<V.length;j++){ const b = box(V[j]);
     if (V[i].contains(V[j]) || V[j].contains(V[i])) continue;
     const ix = Math.min(a.r,b.r) - Math.max(a.l,b.l), iy = Math.min(a.b,b.b) - Math.max(a.t,b.t);
     if (ix > 0.5 && iy > 0.5) errs.push(`overlap ${name(V[i])} x ${name(V[j])} (${ix.toFixed(1)}px)`);
   } }
 // things below the bar must start below it (page at scrollY=0)
 document.querySelectorAll('.bn-pagehead, h1, #ns_gbanner, body > main, body > #main').forEach(e => { if(!vis(e) || hdr.contains(e)) return;
   const r = box(e); if (r.t < hb.b - 0.5 && r.b > hb.t) errs.push(`${name(e)} under the top bar (top ${Math.round(r.t)} < bar bottom ${Math.round(hb.b)})`) });
 // fixed / sticky elements in the header zone that are not the bar itself
 document.querySelectorAll('body *').forEach(e => { if (hdr.contains(e) || e.closest('#bn-menu') || !vis(e)) return; const cs = getComputedStyle(e);
   if (cs.position!=='fixed' && cs.position!=='sticky') return; const r = box(e);
   if (r.t < hb.b - 0.5 && r.b > hb.t + 0.5 && r.w < de.clientWidth*0.98 && +cs.zIndex >= 0 && r.h < 400) {
     const ix = Math.min(r.r,hb.r)-Math.max(r.l,hb.l); if (ix>0.5) errs.push(`fixed/sticky ${name(e)} covers the top bar`) } });
 // gutters: page title column and logo/content alignment
 const ph = document.querySelector('body > .bn-pagehead') || document.querySelector('body > main, body > #main');
 let gut = null;
 if (ph && vis(ph)) { const r = box(ph); const L = r.l, Rg = de.clientWidth - r.r; gut = [Math.round(L), Math.round(Rg)];
   if (Math.abs(L - Rg) > 2) errs.push(`unequal gutters: left ${L.toFixed(1)} right ${Rg.toFixed(1)}`);
   if (logo && vis(logo) && Math.abs(box(logo).l - L) > 2) errs.push(`logo not on the content column (${box(logo).l.toFixed(1)} vs ${L.toFixed(1)})`); }
 return {errs, barH: Math.round(hb.h), gut, n: V.length, logoW: logo ? Math.round(logo.getBoundingClientRect().width) : 0};
}"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base", nargs="?", default="https://blackout.network")
    ap.add_argument("--shots", default="")
    ap.add_argument("--pages", default="")
    ap.add_argument("--widths", default="")
    ap.add_argument("--no-zoom", action="store_true")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    pages = a.pages.split(",") if a.pages else PAGES
    combos = [(w, 1.0) for w in ([int(x) for x in a.widths.split(",")] if a.widths else WIDTHS)]
    if not a.no_zoom and not a.widths: combos += ZOOMS
    from playwright.sync_api import sync_playwright
    fails, rows = 0, []
    with sync_playwright() as p:
        br = p.chromium.launch()
        for w, z in combos:
            # browser zoom Z at a W px window == a W/Z css-px viewport rendered at devicePixelRatio Z
            ctx = br.new_context(viewport={"width": round(w / z), "height": round(900 / z)}, device_scale_factor=z)
            pg = ctx.new_page()
            for path in pages:
                url = a.base.rstrip("/") + path
                try:
                    pg.goto(url, wait_until="domcontentloaded", timeout=60000)
                    pg.wait_for_timeout(600)
                    h0 = pg.evaluate("()=>{const h=document.querySelector('header.bn-top');return h?Math.round(h.getBoundingClientRect().height):0}")
                    try: pg.wait_for_load_state("networkidle", timeout=15000)
                    except Exception: pass
                    pg.wait_for_timeout(1500)
                    r = pg.evaluate(JS)
                    if h0 and r.get("barH") and abs(r["barH"] - h0) > 1: r["errs"].append(f"top bar height shifted {h0} -> {r['barH']} after load")
                except Exception as e:
                    r = {"errs": [f"load error: {e}"[:200]]}
                tag = f"{w}px" + ("" if z == 1 else f" @{int(z*100)}%")
                ok = not r["errs"]; fails += (not ok)
                rows.append({"page": path, "width": w, "zoom": z, "ok": ok, **r})
                print(f"{'PASS' if ok else 'FAIL'}  {tag:<13} {path:<15} bar {r.get('barH','?')}px logo {r.get('logoW','?')}px gutters {r.get('gut')}" + ("" if ok else "\n      - " + "\n      - ".join(r["errs"][:8])))
                if a.shots and path == "/" and z == 1:
                    pg.screenshot(path=f"{a.shots.rstrip('/')}/{w}.png", clip={"x": 0, "y": 0, "width": round(w / z), "height": 260})
            ctx.close()
        br.close()
    print(f"\n{len(rows) - fails}/{len(rows)} checks pass")
    if a.json:
        json.dump(rows, open(a.json, "w"), indent=1)
    sys.exit(1 if fails else 0)

if __name__ == "__main__":
    main()
