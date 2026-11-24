import os, sys, json, unittest
from datetime import datetime, timedelta
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, HERE)
os.environ.setdefault("BN_NETMAP_WARM", "0")
import reservoirs, netmap

def fake(mead, powell, age=1):
    def jget(url, **k):
        v = mead if "sdi=1930" in url else powell
        days = [datetime.utcnow() - timedelta(days=age + i) for i in range(9)]
        return {"Series": [{"Data": [{"t": d.strftime("%m/%d/%Y 12:00:00 AM"), "v": str(v)} for d in reversed(days)]}]}
    return jget

class Reservoirs(unittest.TestCase):
    def test_thresholds(self):
        L = reservoirs.build(fake(1041.3, 3600))["levels"]
        self.assertEqual(L["USA-HOOVER"]["status"], "low"); self.assertEqual(L["USA0000153"]["status"], "ok")
        L = reservoirs.build(fake(970, 3520))["levels"]
        self.assertEqual({v["status"] for v in L.values()}, {"out"})
        self.assertEqual(L["USA-HOOVER"]["min_pool"], 950); self.assertEqual(L["USA0000153"]["min_pool"], 3490)

    def test_stale_or_failed_is_grey(self):
        self.assertEqual({v["status"] for v in reservoirs.build(fake(1100, 3600, age=10))["levels"].values()}, {"na"})
        def boom(url, **k): raise OSError("down")
        self.assertEqual({v["status"] for v in reservoirs.build(boom)["levels"].values()}, {"na"})

    def test_hydro_layer(self):
        d = json.load(open(os.path.join(netmap.STATIC, "hydro.json")))
        self.assertIn("CC BY 4.0", d["credit"]); self.assertGreater(len(d["p"]), 3000)
        ids = {r[7] for r in d["p"]}
        for r in reservoirs.RES: self.assertIn(r["id"], ids)   # every rated reservoir has its dam on the map
        self.assertEqual(netmap.handle_get("/api/netmap/hydro.json")[0], 200)
        self.assertIn('data-k="hydro"', netmap.page({}))
        js = open(os.path.join(netmap.STATIC, "net.js"), encoding="utf-8").read()
        self.assertIn('"rgba(124,129,144,.35)"', js)   # no level data = grey, never green by default

if __name__ == "__main__": unittest.main()
