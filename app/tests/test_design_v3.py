"""Design v3 Wire bands (design_v3.py). Run: cd app && python3 -m unittest tests.test_design_v3 -v   (temp files only, no network)"""
import datetime, json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import design_v3 as V

NOW = datetime.datetime(2026, 11, 2, 15, 0, tzinfo=datetime.timezone.utc)
def card(**k):
    c = {"id": "c", "title": "T", "category": "war", "status": "S", "latest": "L", "why": "W", "as_of": "2026-11-02T13:00:00Z",
         "source": {"name": "Src", "url": "https://example.org/a"}}
    c.update(k); return c

class Bands(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.old = V.DATA; V.DATA = self.tmp.name
    def tearDown(self):
        V.DATA = self.old; self.tmp.cleanup()
    def put(self, name, obj):
        with open(os.path.join(self.tmp.name, name), "w") as f: f.write(obj if isinstance(obj, str) else json.dumps(obj))

    def test_missing_files_render_nothing(self):
        self.assertEqual(V.top_of_mind(NOW)["cards"], []); self.assertEqual(V.whats_coming()["items"], [])
        self.assertEqual(V.tom_html(V.top_of_mind(NOW)), ""); self.assertEqual(V.wc_html({"items": []}), "")
    def test_broken_json_renders_nothing(self):
        self.put("top_of_mind.json", "{not json"); self.put("whats_coming.json", "[]")
        self.assertEqual(V.top_of_mind(NOW)["cards"], []); self.assertEqual(V.whats_coming()["items"], [])
    def test_cards_need_every_field_and_a_real_source(self):
        self.put("top_of_mind.json", {"cards": [card(), card(id="x", why=""), card(id="y", source={"name": "n", "url": "javascript:alert(1)"}),
                                                card(id="z", source=None), card(id="s", as_of="2026-10-20T00:00:00Z"), card(id="f", as_of="2026-11-09T00:00:00Z")]})
        ids = [c["id"] for c in V.top_of_mind(NOW)["cards"]]
        self.assertEqual(ids, ["c"])   # missing why, bad URL, no source, stale (>96 h) and future-dated cards are dropped
    def test_max_four_cards_and_escaping(self):
        self.put("top_of_mind.json", {"cards": [card(id=str(i), title="<b>x</b>") for i in range(6)]})
        t = V.top_of_mind(NOW); self.assertEqual(len(t["cards"]), 4)
        h = V.tom_html(t); self.assertIn("&lt;b&gt;x&lt;/b&gt;", h); self.assertNotIn("<b>x</b>", h)
        self.assertNotIn("verified", h.lower())
    def test_internal_link_only(self):
        self.put("top_of_mind.json", {"cards": [card(link="https://evil.example/"), card(id="d", link="/midterms")]})
        c = V.top_of_mind(NOW)["cards"]; self.assertIsNone(c[0]["link"]); self.assertEqual(c[1]["link"], "/midterms")
    def test_whats_coming_window_and_order(self):
        today = datetime.datetime.now(V.ET).date(); d = lambda n: (today + datetime.timedelta(days=n)).isoformat()
        src = {"name": "BLS", "url": "https://www.bls.gov/"}
        self.put("whats_coming.json", {"items": [{"date": d(3), "title": "B", "source": src}, {"date": d(-1), "title": "past", "source": src},
                                                 {"date": d(15), "title": "far", "source": src}, {"date": d(0), "title": "A", "source": src},
                                                 {"date": d(2), "title": "nosrc"}, {"date": "bad", "title": "x", "source": src}]})
        w = V.whats_coming(); self.assertEqual([i["title"] for i in w["items"]], ["A", "B"])
        h = V.wc_html(w); self.assertIn("Today", h); self.assertIn("In 3 days", h); self.assertIn('href="https://www.bls.gov/"', h)
    def test_kill_switch(self):
        self.put("top_of_mind.json", {"cards": [card()]})
        os.environ["BN_DESIGN_V3"] = "0"
        try: self.assertEqual(V.wire_html(), "")
        finally: os.environ.pop("BN_DESIGN_V3")

if __name__ == "__main__": unittest.main()
