"""Nov 24 2026: U.S. operator sections are rebuilt on the public node when the synced gridstatus.db lacks them (gridlive.py)."""
import os, sys, json, sqlite3, tempfile, unittest
from datetime import timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gridstatus as G, gridlive


def fake_eia():
    t0 = G.now().replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    out = {}
    for r in G.EIA_RESP:
        ser = {G.iso(t0 - timedelta(hours=h)): 10000.0 + h for h in range(30)}
        out[r] = {"D": ser, "DF": dict(ser), "NG": dict(ser)}
    return out


class GridLive(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(); self.old = G.GDB; G.GDB = os.path.join(self.tmp, "gridstatus.db")
        c = G.gdb(); G.sput(c, "odin", []); G.sput(c, "nws", []); G.sput(c, "swpc", {"g": 0}); c.close()   # synced rows, but no 'sections'/'eia'
        self.fe, self.gm = G.fetch_eia, G.grid_matches
        G.fetch_eia = fake_eia; G.grid_matches = lambda: []
        gridlive._C.update(t=0.0, v=None, eia_ts=None, err=None)

    def tearDown(self):
        G.GDB = self.old; G.fetch_eia, G.grid_matches = self.fe, self.gm
        gridlive._C.update(t=0.0, v=None, eia_ts=None, err=None)

    def test_summary_rebuilds_us_sections(self):
        code, s = G.summary({})
        self.assertEqual(code, 200)
        secs = s["sections"]
        for k in ("CAISO", "ERCOT", "PJM", "MISO", "SPP", "NYISO", "ISO-NE"):
            self.assertTrue(secs[k]["demand_mw"] > 0, k)
            self.assertEqual(secs[k]["status"], "online", k)
        self.assertIsNotNone(s["freshness"]["eia"]["ts"])

    def test_synced_sections_win(self):
        c = G.gdb(); G.sput(c, "sections", {"X": {"id": "X"}}); c.close()
        G.fetch_eia = lambda: (_ for _ in ()).throw(AssertionError("must not fetch"))
        self.assertEqual(G.summary({})[1]["sections"], {"X": {"id": "X"}})

    def test_eia_failure_is_quiet_and_cached(self):
        n = []
        def bad(): n.append(1); raise OSError("down")
        G.fetch_eia = bad
        self.assertIsNone(G.summary({})[1]["sections"])
        self.assertIsNone(G.summary({})[1]["sections"])
        self.assertEqual(len(n), 1)

    def test_gridpage_regions(self):
        import gridpage
        gridpage._C.update(t=0.0, v=None)
        d = gridpage.data()
        ids = {r["id"] for r in d["regions"] if r.get("demand_mw")}
        self.assertTrue({"ERCOT", "CAISO", "PJM", "MISO", "SPP", "NYISO", "ISO-NE"} <= ids)
        self.assertTrue(d["ok"])
        gridpage._C.update(t=0.0, v=None)


class WorldPulled(unittest.TestCase):
    def test_operators_without_live_data_are_pulled(self):
        import gridpage as GP
        old = (GP.INTL, GP._wire_grid, dict(GP._W))
        ok = lambda: {"demand_mw": 1000, "data_time": GP._iso(GP._dt.now(GP._tz.utc))}
        stale = lambda: {"demand_mw": 1000, "data_time": "2026-01-01T00:00:00Z"}
        GP.INTL = [("A", "Live op", "europe", 0, 0, (0, 0, 1, 1), "https://a", ok, None, "s"),
                   ("B", "Stale op", "europe", 0, 0, (0, 0, 1, 1), "https://b", stale, None, "s"),
                   ("C", "Keyed op", "europe", 0, 0, (0, 0, 1, 1), "https://c", None, "needs a key", None)]
        GP._wire_grid = lambda: []; GP._W.update(t=0.0, v=None)
        try:
            w = GP.world()
            self.assertEqual([o["id"] for o in w["operators"]], ["A"])
            self.assertEqual(sorted(x["id"] for x in w["pulled"]), ["B", "C"])
        finally:
            GP.INTL, GP._wire_grid = old[0], old[1]; GP._W.clear(); GP._W.update(old[2])


class Diamonds(unittest.TestCase):
    def test_diamonds_win_over_network_points(self):
        d = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "netmap_static")
        gl = open(os.path.join(d, "gridlayer.js")).read(); nj = open(os.path.join(d, "net.js")).read()
        self.assertIn("window.__gxWxHit", gl)
        self.assertIn("w || !nxHit", gl)
        self.assertEqual(nj.count("window.__gxWxHit(e.point)"), 2)


if __name__ == "__main__":
    unittest.main()
