""" /cern CERN & LHC explainer (Nov 13). Run: cd app && python3 -m unittest tests.test_cern -v """
import json, os, re, sys, unittest

def rd(p):
    with open(p, encoding="utf-8") as fh: return fh.read()

from datetime import date
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cern
import sitenav
import sitenav_ui as UI
import addons

BANNED = ("before the news", "before cable", "verified", "matt johnston", "meshtastic", "lora ", "lorawan")
STATIC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cern_static")


def page():
    with mock.patch.object(cern, "live_image", return_value=None):
        code, body, ctype = cern.handle_get("/cern", {})
    assert code == 200 and ctype == "text/html"
    return body if isinstance(body, str) else body.decode()


def visible_text(h):
    h = re.sub(r"<script.*?</script>|<style.*?</style>", " ", h, flags=re.S)
    return re.sub(r"<[^>]+>", " ", h)


class Page(unittest.TestCase):
    def test_sections_and_key_facts(self):
        h = page()
        for s in ('id="what"', 'id="how"', 'id="collide"', 'id="built"', 'id="scale"', 'id="money"', 'id="people"', 'id="found"',
                  'id="myths"', 'id="live"', 'id="dots"', 'id="sources"', "CERN and the Large Hadron Collider", "Mark Thomson",
                  "Stéphane Willocq", "Anadi Canepa", "Kai Schweda", "Tim Gershon", "$531 million", "4 332", "Long Shutdown 3",
                  "BLACKOUT.NETWORK analysis", "Illustration · not to scale", "Illustration · not real collision data",
                  "Not affiliated with or endorsed by CERN", "Signal over noise."):
            self.assertIn(s, h, s)

    def test_interactive_hooks_present(self):
        h = page()
        for i in ("cx-tracks", "cx-chain-panel", "cx-cv", "cx-go", "cx-tl-r", "cx-tl-track", "cx-city", "cx-geo", "cx-map",
                  "cx-quiz", "cx-st-lhc", "cx-st-p1", "cx-od", "cx-beamchip", "cx-data"):
            self.assertIn(f'id="{i}"', h, i)
        self.assertEqual(h.count('class="cx-stage"'), 6)
        self.assertGreaterEqual(h.count('class="cx-flip"'), 5)
        self.assertEqual(h.count('class="cx-bar"') + h.count('class="cx-bar cx-bar-a"'), 36)
        d = json.loads(re.search(r'id="cx-data">(.*?)</script>', h, re.S).group(1).replace("<\\/", "</"))
        self.assertEqual(len(d["fund"]), 25); self.assertEqual(len(d["assoc"]), 11)
        self.assertEqual({s["id"] for s in d["stages"]}, {"linac4", "psb", "ps", "sps", "lhc"})

    def test_banned_words_and_tiles(self):
        h = page().lower()
        t = visible_text(h)
        for b in BANNED: self.assertNotIn(b, t, b)
        self.assertNotIn("tile.openstreetmap.org", h)
        js = rd(os.path.join(STATIC, "app.js"))
        self.assertNotIn("tile.openstreetmap.org", js)
        self.assertIn("tiles.openfreemap.org/styles/dark", js)
        self.assertIn("sha384-5+cfbwT0iiub6VsQAdn6yz16nr6sDiQoHx6tm4O8OVYXHYOxcffFmCJBL0dgdvGp", js)
        for f in ("app.js", "app.css"):
            body = rd(os.path.join(STATIC, f)).lower()
            self.assertNotIn("meshtastic", body); self.assertIn("prefers-reduced-motion", body)

    def test_no_emoji_in_page_body(self):
        main = page().split('<main class="cx" id="main">', 1)[1].split("</main>", 1)[0]
        main = re.sub(r'<script type="application/json".*?</script>', "", main, flags=re.S)
        self.assertIsNone(re.search("[\U0001F300-\U0001FAFF\u2600-\u27BF]", main))

    def test_external_links_open_safely(self):
        for a in re.findall(r'<a [^>]*href="https?://[^"]+"[^>]*>', page()):
            self.assertRegex(a, r'rel="[^"]*noopener', a)


class Data(unittest.TestCase):
    def test_every_image_credited_and_present(self):
        for f, meta in cern.IMG.items():
            self.assertTrue(os.path.exists(os.path.join(STATIC, "img", f)), f)
            self.assertTrue(cern.credit(f).strip(), f)
        h = page()
        for f in cern.IMG:
            self.assertIn(f, h)

    def test_sources_referenced_exist(self):
        src = rd(cern.__file__)
        keys = set(re.findall(r'\bs\("([a-z0-9_]+)"', src))
        for k in keys: self.assertIn(k, cern.SRC, k)
        for grp in re.findall(r'srcs\(([^)]*)\)', src):
            for k in re.findall(r'"([a-z0-9_]+)"', grp): self.assertIn(k, cern.SRC, k)
        for k, (t, u) in cern.SRC.items():
            self.assertTrue(u.startswith("https://"), k)
        for coll in (cern.STAGES, cern.EXPTS):
            for x in coll:
                for k in x["src"]: self.assertIn(k, cern.SRC, k)
        for m in cern.MYTHS:
            for k in m["src"]: self.assertIn(k, cern.SRC, k)

    def test_funding_totals(self):
        self.assertEqual(len(cern.FUND), 25)
        self.assertAlmostEqual(sum(p for _, p, _, _ in cern.FUND), 100, delta=0.05)
        self.assertEqual(sum(v for _, _, v, _ in cern.FUND), cern.MEMBER_TOTAL)
        self.assertEqual(sum(v for _, v, _ in cern.ASSOC), cern.ASSOC_TOTAL)

    def test_machine_state_schedule(self):
        self.assertEqual(cern.machine_state(date(2026, 5, 1))["lhc"], "RUN 3")
        s = cern.machine_state(date(2026, 7, 15)); self.assertEqual(s["lhc"], "LS3 · NO BEAM"); self.assertEqual(s["inj"], "RUNNING")
        s = cern.machine_state(date(2026, 11, 13)); self.assertEqual(s["inj"], "LS3")
        self.assertEqual(cern.machine_state(date(2031, 1, 1))["lhc"], "HILUMI ERA")


class Routes(unittest.TestCase):
    def test_aliases(self):
        for p in ("/cern", "/lhc", "/cern/lhc", "/cern/"):
            with mock.patch.object(cern, "live_image", return_value=None):
                self.assertEqual(cern.handle_get(p, {})[0], 200, p)

    def test_static_and_images(self):
        for n, ct in (("app.js", "application/javascript"), ("app.css", "text/css"), ("ring.json", "application/json")):
            code, body, ctype = cern.handle_get("/api/cern/" + n, {})
            self.assertEqual((code, ctype), (200, ct))
        ring = json.loads(cern.handle_get("/api/cern/ring.json", {})[1])
        self.assertGreater(len(ring), 100)
        f = next(iter(cern.IMG))
        code, body, ctype = cern.handle_get("/api/cern/img/" + f, {})
        self.assertEqual((code, ctype), (200, "image/jpeg")); self.assertTrue(body.startswith(b"\xff\xd8"))
        self.assertNotIn(b"Exif", body[:4096])
        for bad in ("/api/cern/img/../cern.py", "/api/cern/img/x.jpg", "/api/cern/../../etc/passwd", "/api/cern/cern.py", "/api/cern/nope"):
            self.assertEqual(cern.handle_get(bad, {})[0], 404, bad)

    def test_live_allowlist(self):
        with mock.patch.object(cern, "_get") as g:
            self.assertIsNone(cern.live_image("atlas"))
            self.assertEqual(cern.handle_get("/api/cern/live/../../x.png", {})[0], 404)
            g.assert_not_called()

    def test_live_fallback_keeps_stale(self):
        cern._live.clear()
        with mock.patch.object(cern, "_get", return_value=(b"\x89PNGxx", "Fri, 13 Nov 2026 12:00:00 GMT")):
            self.assertTrue(cern.live_image("lhc1")["ok"])
        cern._live["lhc1"]["t"] = 0
        with mock.patch.object(cern, "_get", side_effect=OSError("down")):
            c = cern.live_image("lhc1")
        self.assertFalse(c["ok"]); self.assertEqual(c["body"], b"\x89PNGxx")
        with mock.patch.object(cern, "_get", side_effect=OSError("down")):
            st = cern.status()
        self.assertEqual(st["displays"][0]["updated"], "2026-11-13T12:00:00Z")
        cern._live.clear()

    def test_status_shape_offline(self):
        cern._live.clear()
        with mock.patch.object(cern, "_get", side_effect=OSError("down")):
            code, st = cern.handle_get("/api/cern/status", {})
        self.assertEqual(code, 200); self.assertIn("state", st); self.assertEqual(len(st["displays"]), len(cern.LIVE))
        self.assertTrue(all(not d["ok"] for d in st["displays"]))

    def test_registered_routes(self):
        for p in ("/cern", "/lhc", "/api/cern"):
            self.assertEqual(addons.ROUTES.get(p), "cern", p)


class Nav(unittest.TestCase):
    def test_nav_and_menus(self):
        keys = [t[0] for _, tabs in sitenav.NAV for t in tabs]
        self.assertIn("@cern", keys)
        self.assertEqual(keys[keys.index("spacex") + 1], "@cern")
        self.assertIn("cern", sitenav.PAGES)
        self.assertTrue(any("@cern" in ks for _, ks in UI.MENU))
        self.assertTrue(any(k == "@cern" for sec in UI.MENU3 for k, _ in sec[3]))
        self.assertIn('href="/cern"', sitenav.header_html("@cern"))


if __name__ == "__main__":
    unittest.main()
