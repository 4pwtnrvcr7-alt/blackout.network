import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class CrimeQ(unittest.TestCase):
    def test_growth_skips_site_search_on_crime(self):
        js = open(os.path.join(HERE, "growth_static", "app.js")).read()
        i = js.index("function q(){")
        self.assertIn("/crime", js[i:i + 120])
        self.assertLess(js.index("/crime", i), js.index("bnMenuOpen({search:true})", i))

    def test_crime_js_treats_q_as_place(self):
        js = open(os.path.join(HERE, "crime_static", "app.js")).read()
        self.assertIn('u.get("place")||u.get("q")', js)
        self.assertIn('history.replaceState(history.state,"","/crime?place="', js)

    def test_assets_use_build_version(self):
        # unversioned same-origin URLs get ?v=<build> from server.version_assets on every deploy (immutable cache busted per build)
        import server
        self.assertIsNotNone(server._ASSET_RE.search(b'<script src="/api/growth/app.js" defer>'))
        self.assertIn(b'src="/api/growth/app.js" ', server.GROWTH_HEAD)

    def test_server_renders_q_like_place(self):
        import crime
        a = crime.handle_get("/crime", {"q": ["32771"]})[1]
        b = crime.handle_get("/crime", {"place": ["32771"]})[1]
        a = a if isinstance(a, str) else a.decode(); b = b if isinstance(b, str) else b.decode()
        self.assertIn('value="32771"', a)
        self.assertEqual(a.count("cr-result"), b.count("cr-result"))

if __name__ == "__main__":
    unittest.main()
