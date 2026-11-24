import os, sys, time, json, unittest
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, HERE)
os.environ.setdefault("BN_NETMAP_WARM", "0")
import gridfreq, netmap

class GridFreq(unittest.TestCase):
    def fake(self, ce, gb, no, age=60):
        now = time.time(); last = now - age
        def jget(url, **k):
            if "energy-charts" in url: return {"unix_seconds": [last - 10, last], "data": ce}
            if "elexon" in url: return {"data": [{"measurementTime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(last)), "frequency": gb}]}
            if "statnett" in url: return {"EndPointUTC": last * 1000, "Measurements": no}
            raise AssertionError(url)
        return jget

    def test_status_thresholds_and_outlines(self):
        r = gridfreq.build(self.fake([50.02, 49.95], 49.6, [50.0, 48.9]), netmap.STATIC)
        st = {a["id"]: a["status"] for a in r["areas"]}
        self.assertEqual(st, {"sa-ce": "ok", "sa-gb": "strain", "sa-nordic": "out"})
        for a in r["areas"]:
            self.assertEqual(a["g"]["type"], "MultiPolygon"); self.assertTrue(a["g"]["coordinates"], a["id"])
        self.assertNotIn("US", sum((a["countries"] for a in r["areas"]), []))

    def test_stale_or_failed_feed_is_grey_never_green(self):
        r = gridfreq.build(self.fake([50.0, 50.0], 50.0, [50.0], age=3600), netmap.STATIC)
        self.assertEqual({a["status"] for a in r["areas"]}, {"na"})
        def boom(url, **k): raise OSError("down")
        r = gridfreq.build(boom, netmap.STATIC)
        self.assertEqual({a["status"] for a in r["areas"]}, {"na"})

    def test_client_merges_areas_without_touching_the_paint_expression(self):
        js = open(os.path.join(netmap.STATIC, "net.js"), encoding="utf-8").read()
        self.assertIn('fetch("/api/netmap/gridfreq")', js)
        self.assertIn('FST[id] || "na"', js)
        self.assertIn("(grid frequency)", js)

if __name__ == "__main__": unittest.main()
