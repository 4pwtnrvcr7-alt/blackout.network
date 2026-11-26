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
        def fw(ct, cid, n, newer, *a, meta=None, live_n=None):
            older = [r for r in self.rows if (r["t"], r["id"]) < (ct, cid)]
            got = older[:n]
            if meta is not None:
                meta["done"] = len(got) < n
                meta["edge"] = (got[-1]["t"], got[-1]["id"]) if got else None
            return [(r, True) for r in got]
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



class StormVerbTest(unittest.TestCase):
    def test_raid_is_conflict_not_weather(self):
        import storm_verb as S, card_photo as C
        t = "Israeli occupation forces storm a Palestinian residential building in the Khallet al-Iman neighborhood in Nablus"
        self.assertEqual(W.cat_key("natural disaster", t, False), "conflict")
        self.assertIsNone(C.hazard_for(t))
        self.assertEqual(S.fix_category("natural disaster", t), "war/conflict")
        for w in ("Winter Storm Warning issued November 25", "Tropical Storm Sara nears Honduras", "storm surge expected"):
            self.assertEqual(W.cat_key("natural disaster", w, False), "weather", w)
            self.assertFalse(S.is_raid(w))

    def test_raid_tags(self):
        os.environ.setdefault("BN_XTAGS_DB", "/tmp/bn_test_xtags_cat.db")
        import x_share as X
        t = "Israeli occupation forces storm a Palestinian residential building in the Khallet al-Iman neighborhood in the city of Nablus, West Bank"
        tags = X.finalize_tags(["#Storm", "#israel", "#WestBank", "#Palestinian", "#Khallet"],
                               item={"title": t, "category": "natural disaster", "location": "Nablus, West Bank"})
        self.assertNotIn("#Storm", tags); self.assertNotIn("#Khallet", tags); self.assertIn("#Israel", tags)
        self.assertNotIn("#edge", X.finalize_tags(["#edge", "#HKCERT"], item={"title": "Microsoft Edge Multiple Vulnerabilities", "category": "cyber"}))
if __name__ == "__main__": unittest.main()
