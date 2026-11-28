"""Panel intro on "/" (intro_sx.py, Matt's spacex.com brief). Run: cd app && python3 -m unittest tests.test_intro_sx -v"""
import os, re, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import intro_sx, theme

def _read(n):
    with open(os.path.join(intro_sx.STATIC, n), encoding="utf-8") as f: return f.read()

class IntroSx(unittest.TestCase):
    def setUp(self): os.environ.pop("BN_INTRO_SX", None); os.environ.pop("BN_INTRO_PULSE", None)

    def test_one_panel_per_menu_item_linking_to_it(self):
        h = theme.home_page()
        items = intro_sx.menu_items(theme._home_page_raw())
        self.assertGreaterEqual(len(items), 5)
        secs = re.findall(r'<section class="sx[^"]*" id="s(\d+)" data-k="(\w+)"', h)
        self.assertEqual(len(secs), len(items))
        btns = re.findall(r'<a class="sx-btn" href="([^"]+)"', h)
        self.assertEqual(btns, [href for href, _ in items])
        self.assertEqual(h.count("<h1"), 1)
        self.assertIn('<h1 class="sx-h" id="sx_h1">Global threat monitoring</h1>', h)

    def test_keeps_header_menu_brief_follow_footer(self):
        h = theme.home_page()
        self.assertIn('<span class="bnt-wm">blackout.network</span>', h)
        self.assertIn('id="h_menu"', h); self.assertIn("data-h-menu", h)
        self.assertIn('id="brief"', h); self.assertIn('id="nl_app"', h)
        self.assertNotIn('href="#s6"', h)
        self.assertIn('id="bng_follow"', h)
        self.assertEqual(h.count("<footer"), 1)
        self.assertIn("/api/intro/intro.js", h); self.assertIn("/api/intro/intro.css", h)
        self.assertNotIn("home.js", h); self.assertNotIn("/api/pulse/", h)
        self.assertNotIn('class="h-pager"', h)

    def test_first_paint_one_image_rest_lazy_videos_deferred(self):
        h = theme.home_page()
        imgs = re.findall(r'<img src="/bnt/media/[^"]+" alt="" decoding="async" (fetchpriority="high"|loading="lazy")>', h)
        self.assertEqual(imgs[0], 'fetchpriority="high"'); self.assertTrue(all(x == 'loading="lazy"' for x in imgs[1:]))
        self.assertNotRegex(h, r'<video[^>]* src=')                    # footage attaches in JS, desktop only
        self.assertIn('preload="none"', h)
        self.assertEqual(len(re.findall(r'<link rel="preload" as="image"', h)), 2)

    def test_media_exist_and_names_are_servable(self):
        media = os.path.join(theme.BASE if hasattr(theme, "BASE") else os.path.dirname(theme.__file__), "theme_static", "media")
        names = set(os.listdir(media))
        for href, p in intro_sx.PANELS.items():
            for f in p[5]:
                if not f: continue
                self.assertRegex(f, r"^[a-z]+-[dm]\.(mp4|jpg|webm)$")
                self.assertTrue(f + ".b64" in names or any(n.startswith(f + ".b64.p") for n in names), f)

    def test_no_yellow_and_pills(self):
        css = re.sub(r"/\*.*?\*/", "", _read("intro.css"), flags=re.S).lower()
        for bad in ("bnt-y", "#ffd", "#fc0", "#ffcc", "#f5c", "gold", "yellow", "#e8b", "#fb0"):
            self.assertNotIn(bad, css)
        self.assertRegex(css, r"\.sx-btn\{[^}]*border-radius:999px")
        self.assertIn("#ff4d4f", css)                                   # red exists only as the rank 7+ dot
        self.assertEqual(len(re.findall(r"#ff4d4f", css)), 1)
        self.assertIn(".rk i.h", css)

    def test_no_pop_ups_or_peer_wording(self):
        h = theme.home_page().lower(); js = _read("intro.js").lower()
        self.assertNotIn("peer-to-peer", h)
        for bad in ("alert(", "window.open", "showmodal", "confirm("): self.assertNotIn(bad, js)

    def test_kill_switch_and_fallback(self):
        os.environ["BN_INTRO_SX"] = "0"
        try:
            h = theme.home_page(); self.assertNotIn('class="sx', h); self.assertIn('id="s2"', h)
            self.assertIs(theme._ledger(), theme.CREDITS_LEDGER)
        finally: os.environ.pop("BN_INTRO_SX", None)
        orig = intro_sx.transform
        try:
            intro_sx.transform = lambda h: (_ for _ in ()).throw(ValueError("drift"))
            h = theme.home_page(); self.assertIn('id="s2"', h); self.assertNotIn('class="sx', h)
        finally: intro_sx.transform = orig

    def test_credits_rows(self):
        rows = dict((k, r) for k, _, r in theme._ledger())["intro"]
        self.assertEqual(len(rows), len(intro_sx.PANELS))
        self.assertTrue(all(len(r) == 3 and r[2] for r in rows))
        self.assertNotIn("h-credit", theme.home_page())

    def test_route_files_and_live_shape(self):
        import addons
        self.assertEqual(addons.ROUTES.get("/api/intro"), "intro_sx")
        for n in ("intro.css", "intro.js"):
            r = intro_sx.handle_get("/api/intro/" + n, {}); self.assertEqual(r[0], 200); self.assertTrue(r[2].startswith(("text/css", "application/javascript")))
        self.assertEqual(intro_sx.handle_get("/api/intro/nope", {})[0], 404)
        orig = intro_sx.BUILDERS
        try:
            intro_sx.BUILDERS = (("feed", lambda: {"wire": {"n": 2, "top": []}, "map": None}), ("grid", lambda: (_ for _ in ()).throw(RuntimeError("x"))))
            intro_sx._C.update(t=0, v=None, good={})
            v = intro_sx._build()
            self.assertEqual(v["wire"]["n"], 2); self.assertIsNone(v["grid"]); self.assertEqual(v["errors"]["grid"], "RuntimeError")
            for k in intro_sx.KEYS: self.assertIn(k, v)
        finally: intro_sx.BUILDERS = orig; intro_sx._C.update(t=0, v=None, good={})

    def test_clean_titles(self):
        self.assertEqual(intro_sx._clean("8/ Ukrainian forces struck https://t.co/x"), "Ukrainian forces struck")

if __name__ == "__main__": unittest.main()
