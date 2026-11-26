"""Nov 25 2026 (pt1917u): category filters scan the whole history and never report `end` early."""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import wire_timeline as W

def _rows(n, special_at):
    out = []
    for i in range(n):
        cat, title = ("space weather", "Geomagnetic Storm Watch") if i == special_at else ("natural disaster", "Flood warning")
        out.append({"id": f"{i:016x}", "t": f"2026-{1 + (n - i) * 11 // n:02d}-01T00:00:{i % 60:02d}Z".replace("-00-", "-01-"),
                    "title": title, "location": "", "category": cat, "lat": None, "lon": None})
    out.sort(key=lambda r: (r["t"], r["id"]), reverse=True)
    return out

class CategoryScanTest(unittest.TestCase):
    def setUp(self):
        self.sv = (W._fetch_window, W._item, W._public_row, W._SCAN_BUDGET_S)
        self.rows = _rows(9000, 8990)
        def fw(ct, cid, n, newer, *a):
            older = [r for r in self.rows if (r["t"], r["id"]) < (ct, cid)]
            return [(r, True) for r in older[:n]]
        W._fetch_window = fw
        W._item = lambda r, a, **k: {"id": r["id"], "t": r["t"]}
        W._public_row = lambda r, a: True

    def tearDown(self):
        W._fetch_window, W._item, W._public_row, W._SCAN_BUDGET_S = self.sv

    def test_sparse_category_past_old_cap_is_found(self):
        d = W._page_build(limit=100, cats="space")
        self.assertEqual(len(d["items"]), 1)
        self.assertTrue(d["end"])

    def test_budget_cut_returns_cursor_not_end(self):
        W._SCAN_BUDGET_S = 0.0
        d = W._page_build(limit=100, cats="space")
        self.assertFalse(d["end"]); self.assertTrue(d["next"])
        got, cur = list(d["items"]), d["next"]
        for _ in range(50):
            if not cur: break
            d = W._page_build(before=cur, limit=100, cats="space"); got += d["items"]; cur = d["next"]
        self.assertEqual(len(got), 1)

    def test_stored_space_weather_beats_storm_word(self):
        self.assertEqual(W.cat_key("space weather", "Geomagnetic Storm Watch issued", False), "space")
        self.assertEqual(W.cat_key("war/conflict", "M 6.1 earthquake near Tonga", False), "quake")

if __name__ == "__main__": unittest.main()
