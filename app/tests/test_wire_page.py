"""The Wire listing page (/wire). Run: cd app && python3 -m unittest tests.test_wire_page -v"""
import os, re, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import addons, story, wire_page, sitenav, growth

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class Routes(unittest.TestCase):
    def test_addons_route(self):
        self.assertEqual(addons.ROUTES["/wire"], "story")
        self.assertEqual(addons.ROUTES["/api/wire_page"], "wire_page")

    def test_prefix_does_not_steal_story_ids(self):
        def hit(path):
            for pre, name in addons.ROUTES.items():
                if path == pre or path.startswith(pre + "/"):
                    return name
            return None
        self.assertEqual(hit("/api/wire_page/app.js"), "wire_page")
        self.assertEqual(hit("/api/wire_history"), "wire_history")
        self.assertEqual(hit("/wire/0123456789abcdef"), "story")
        self.assertEqual(hit("/wire"), "story")

class Page(unittest.TestCase):
    def test_listing_html(self):
        code, body, ctype = wire_page.page()
        self.assertEqual(code, 200)
        self.assertEqual(ctype, "text/html")
        html = body.decode() if isinstance(body, (bytes, bytearray)) else body
        self.assertIn("<title>The Wire: live threat feed | BLACKOUT.NETWORK</title>", html)
        self.assertIn('name="description"', html)
        self.assertIn("https://blackout.network/wire", html)
        self.assertIn('id="w-bulletin"', html)
        self.assertIn("Last 24 hours", html)
        self.assertIn('data-mode="confirmed"', html)
        self.assertIn('data-mode="single"', html)
        self.assertIn("What matters now", html)
        self.assertIn("/api/wire_page/app.js", html)
        self.assertIn("/api/wire_page/app.css", html)
        self.assertIn("window.BN_WIRE_NOTICE=", html)
        self.assertIn('class="bn-logo"', html)
        self.assertNotIn("fonts.googleapis.com", html)
        self.assertNotIn("MOCKUP", html)

    def test_story_dispatch_and_passthrough(self):
        code, body, ctype = story.handle_get("/wire", {})
        self.assertEqual(code, 200)
        self.assertEqual(ctype, "text/html")
        html = body.decode() if isinstance(body, (bytes, bytearray)) else body
        self.assertIn("What matters now", html)
        code2, body2 = story.handle_get("/wire/not-an-id", {})[:2]
        self.assertEqual(code2, 404)
        # A well-formed id still goes to story.py (not found without a live row is OK).
        r = story.handle_get("/wire/0123456789abcdef", {})
        self.assertIn(r[0], (404, 503))  # 503 = warming up when blackout.db is absent

    def test_assets(self):
        code, body, ctype = wire_page.handle_get("/api/wire_page/app.js", {})
        self.assertEqual(code, 200)
        self.assertEqual(ctype, "application/javascript")
        js = body.decode()
        self.assertIn("/api/state", js)
        self.assertIn("/api/state_items", js)
        self.assertIn("/api/social", js)
        self.assertIn("What we know", js)
        self.assertIn("youtube-nocookie.com", js)
        self.assertNotIn("/api/apple/home", js)
        code, body, ctype = wire_page.handle_get("/api/wire_page/app.css", {})
        self.assertEqual(code, 200)
        self.assertIn("text/css", ctype)
        self.assertIn("grid-template-rows", body.decode())
        self.assertEqual(wire_page.handle_get("/api/wire_page/secret", {})[0], 404)

    def test_shell_cache_is_one_slot(self):
        wire_page.page()
        self.assertEqual(len(wire_page._SHELL), 2)  # keys: key, html
        wire_page._file("app.js")
        self.assertLessEqual(len(wire_page._FILE), 2)

    def test_sitenav_and_sitemap(self):
        self.assertEqual(sitenav.PAGES["wire"][0], "threat")
        self.assertTrue(sitenav.PAGES["wire"][1].startswith("The Wire: live threat feed"))
        paths = [p[0] for p in growth.STATIC_PAGES]
        self.assertIn("/wire", paths)
        self.assertLess(paths.index("/wire"), paths.index("/newsletter"))

    def test_page_does_not_read_blackout_db(self,):
        """The listing shell is built without opening the scanner database."""
        import sqlite3
        opened = []
        orig = sqlite3.connect
        def wrapped(*a, **k):
            s = a[0] if a else ""
            if "blackout.db" in str(s):
                opened.append(s)
            return orig(*a, **k)
        sqlite3.connect = wrapped
        try:
            wire_page._SHELL["key"] = None
            wire_page._SHELL["html"] = None
            wire_page.page()
        finally:
            sqlite3.connect = orig
        self.assertEqual(opened, [])
