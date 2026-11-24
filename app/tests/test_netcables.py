import os, sys, json, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import netcables as C, netmap
from datetime import datetime, timezone, timedelta

def at(h): return (datetime.now(timezone.utc) - timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ")

class Cables(unittest.TestCase):
    def test_geometry_is_licensed_and_light(self):
        p = os.path.join(os.path.dirname(C.__file__), "netmap_static", "cables.json")
        self.assertLess(os.path.getsize(p), 450_000)
        d = json.load(open(p)); self.assertIn("OpenStreetMap", d["credit"]); self.assertIn("NOAA", d["credit"])
        self.assertNotIn("telegeography", open(p).read().lower())   # CC BY-NC-SA: not used
        self.assertGreater(sum(1 for f in d["features"] if f["geometry"]["type"] == "LineString"), 200)   # pt1787u: landing-to-landing routes only
        self.assertEqual(netmap.handle_get("/api/netmap/cables.json")[0], 200)

    def test_quiet_news_is_inferred_never_official(self):
        r = C.status(dict(cable=[], conflict={z["id"]: [] for z in C.ZONES}, ok=True), dict(countries=[]))
        for z in r["zones"]:
            self.assertEqual(z["status"], "No damage reported (inferred)"); self.assertEqual(z["lv"], 0)
            self.assertEqual(z["score"], sum(p[1] for p in z["parts"])); self.assertLessEqual(z["score"], 100)
            for k in z["cuts"]: self.assertTrue(k["url"].startswith("https://"))
        self.assertIn("inferred", r["basis"].lower())

    def test_damage_news_and_ioda_raise_the_zone(self):
        nw = dict(cable=[dict(t="Red Sea subsea cable cut disrupts internet in Asia", src="X", url="https://e.com/a", at=at(3))], conflict={z["id"]: [] for z in C.ZONES})
        z = {x["id"]: x for x in C.status(nw, dict(countries=[]))["zones"]}
        self.assertEqual(z["redsea"]["status"], "Possible damage (inferred)"); self.assertEqual(z["baltic"]["lv"], 0)
        z = {x["id"]: x for x in C.status(nw, dict(countries=[dict(cc="YE", name="Yemen", cur=True, ioda="https://ioda.inetintel.cc.gatech.edu/country/YE")]))["zones"]}
        self.assertEqual(z["redsea"]["status"], "Likely damage (inferred)"); self.assertEqual(z["redsea"]["ioda"][0]["cc"], "YE")
        old = dict(nw, cable=[dict(nw["cable"][0], at=at(24 * 20))])
        self.assertEqual({x["id"]: x for x in C.status(old, None)["zones"]}["redsea"]["lv"], 0)
        power = dict(nw, cable=[dict(nw["cable"][0], t="Baltic power cable damaged near Gotland")])
        self.assertEqual({x["id"]: x for x in C.status(power, None)["zones"]}["baltic"]["lv"], 0)

if __name__ == "__main__": unittest.main()
