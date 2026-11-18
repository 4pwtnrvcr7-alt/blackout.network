"""Wire timeline (/wire; /wire-next 301s here). Run: cd app && python3 -m unittest tests.test_wire_timeline -v"""
import os, sqlite3, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import addons, wire_timeline as W

def hit(path):
    for pre, name in addons.ROUTES.items():
        if path == pre or path.startswith(pre + "/"): return name
    return None

class Routes(unittest.TestCase):
    def test_routes(self):
        self.assertEqual(hit("/wire-next"), "wire_timeline")
        self.assertEqual(hit("/api/wire_tl"), "wire_timeline")
        self.assertEqual(hit("/api/wire_tl/meta"), "wire_timeline")
        self.assertEqual(hit("/wire"), "story")
        self.assertEqual(hit("/wire/0123456789abcdef"), "story")
        self.assertEqual(hit("/wire-classic"), "story")
        self.assertEqual(hit("/wire-classic/x"), "story")

    def test_not_linked_or_indexed(self):
        app = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # Menus, sitemap and the shared theme must not link the preview URL or the hidden classic listing.
        for needle in ("/wire-next", "/wire-classic"):
            for f in ("sitenav.py", "sitenav_ui.py", "growth.py", "theme.py"):
                self.assertNotIn(needle, open(os.path.join(app, f), encoding="utf-8").read(), f"{f} {needle}")
        # The v2 menu (used on story pages and the classic listing) still points at /wire, not the hidden path or old preview.
        w2 = open(os.path.join(app, "wire_v2.py"), encoding="utf-8").read()
        self.assertNotIn("/wire-next", w2)
        self.assertNotIn('href="/wire-classic"', w2)

class Display(unittest.TestCase):
    def test_categories(self):
        self.assertEqual(W.cat_key("natural disaster", "M 4.7 - South Sandwich Islands region", True), "quake")
        self.assertEqual(W.cat_key("natural disaster", "Green alert: Forest fires in Brazil", True), "weather")
        self.assertEqual(W.cat_key("war/conflict", "Nepal: Flash Floods - Aug 2026", True), "weather")
        self.assertEqual(W.cat_key("war/conflict", "Strikes on Kyiv", False), "conflict")
        self.assertEqual(W.cat_key("financial", "x", False), "markets")
        keys = [k for k, _, _ in W.CATS]
        for c in ("#E5484D",): self.assertNotIn(c, [x[2] for x in W.CATS])   # red is reserved for rank 7+

    def test_regions(self):
        self.assertEqual(W.region_key("Brazil", ""), "la")
        self.assertEqual(W.region_key("146 km E of Kokopo, Papua New Guinea", ""), "oc")
        self.assertEqual(W.region_key(None, "Floods hit Sudan"), "af")
        self.assertEqual(W.region_key("southern Mid-Atlantic Ridge", ""), "sea")

class Paging(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = tempfile.mkdtemp()
        db = os.path.join(cls.d, "blackout.db"); c = sqlite3.connect(db)
        c.execute("""CREATE TABLE clusters (cluster_id TEXT, title TEXT, category TEXT, location TEXT, lat REAL, lon REAL, event_time TEXT, first_seen TEXT,
                     updated TEXT, score INT, confidence TEXT, n_items INT, n_families INT, families TEXT, links TEXT, watchlist INT, brief TEXT, rank INT)""")
        for i in range(30):
            c.execute("INSERT INTO clusters VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (f"{i:016x}", f"Quake number {i} in Japan", "natural disaster", "Japan", None, None,
                      None, f"2026-11-{1 + i % 28:02d}T{i % 24:02d}:00:00Z", None, 10, "High", 1, 1, '["official"]', '[{"source":"USGS","url":"https://usgs.gov/x"}]', 0, "WHAT: A quake.", i % 11))
        c.commit(); c.close()
        cls.old = (W.DB, W.HDB); W.DB = db; W.HDB = os.path.join(cls.d, "none.db")
    @classmethod
    def tearDownClass(cls): W.DB, W.HDB = cls.old

    def test_both_directions_no_gaps(self):
        a = W.page(limit=7); seen = [x["id"] for x in a["items"]]
        cur = a["next"]
        while cur:
            p = W.page(before=cur, limit=7); seen += [x["id"] for x in p["items"]]; cur = p["next"]
        self.assertEqual(len(seen), 30); self.assertEqual(len(set(seen)), 30)
        mid = W.page(before=a["next"], limit=7)
        up = W.page(after=f'{mid["items"][0]["t"]}|{mid["items"][0]["id"]}', limit=50)
        self.assertEqual([x["id"] for x in up["items"]], [x["id"] for x in a["items"]])   # newer page, newest first

    def test_search_and_api(self):
        self.assertEqual(W.count("number 1")["count"], 12)   # every word must match: 1, 10-19, 21
        code, body = W.handle_get("/api/wire_tl", {"q": ["number 12"], "limit": ["5"]})
        self.assertEqual(code, 200); self.assertEqual(len(body["items"]), 1)
        self.assertEqual(W.handle_get("/api/wire_tl", {"before": ["nope"]})[0], 400)
        code, body, ct, hdr = W.handle_get("/wire-next", {})
        self.assertEqual(code, 301); self.assertEqual(hdr["Location"], "/wire")
        code, html, ct = W.handle_get("/wire", {})
        self.assertEqual(code, 200); self.assertEqual(ct, "text/html")
        self.assertNotIn('content="noindex', html)
        self.assertIn("data-bn-tl", html[:300])
        self.assertIn("<title>The Wire: live threat feed | BLACKOUT.NETWORK</title>", html)
        self.assertIn('rel="canonical" href="https://blackout.network/wire"', html)
        self.assertIn('id="tl_ref"', html)
        self.assertIn('id="tl_new"', html)
        self.assertIn('id="tl_upd"', html)
        self.assertIn(">Refresh</span>", html)
        css=open(os.path.join(os.path.dirname(W.__file__), "wire_timeline_static", "app.css"), encoding="utf-8").read()
        self.assertIn(".tl-newp", css)
        self.assertNotIn("#FFC", css)
        js=open(os.path.join(os.path.dirname(W.__file__), "wire_timeline_static", "app.js"), encoding="utf-8").read()
        self.assertIn("pollNewer", js)
        self.assertIn("d.hidden", js)

    def test_flag_off(self):
        os.environ["BN_WIRE_TIMELINE"] = "0"
        try:
            r = W.handle_get("/wire-next", {})
            self.assertEqual(r[0], 301); self.assertEqual(r[3]["Location"], "/wire")
            self.assertEqual(W.handle_get("/wire", {})[0], 404)
            self.assertEqual(W.handle_get("/api/wire_tl", {})[0], 404)
        finally: del os.environ["BN_WIRE_TIMELINE"]

if __name__ == "__main__": unittest.main()
