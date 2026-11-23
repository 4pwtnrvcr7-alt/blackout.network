"""Network Status map (/network, Nov 23 2026, pt1755u): route, page skeleton, no yellow, no OSM tiles, bars math, old hub kept."""
import os, sys, re, unittest
from datetime import datetime, timezone, timedelta
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
os.environ["BN_NETMAP_WARM"] = "0"

class NetMap(unittest.TestCase):
    def test_routes(self):
        import addons, netmap, netpages
        self.assertEqual(addons.ROUTES["/api/netmap"], "netmap")
        self.assertEqual(addons.ROUTES["/network"], "netpages")
        code, body, ct = netpages.handle_get("/network", {})
        self.assertEqual((code, ct), (200, "text/html"))
        for s in ('id="nx_map"', 'id="nx_ld"', 'id="nx_ldcv"', 'id="nx_more"', 'id="nx_f"', "/api/netmap/net.js", "/api/signal/maplibre-gl.js"):
            self.assertIn(s, body)
        self.assertEqual(netmap.handle_get("/api/netmap/nope")[0], 404)
        self.assertEqual(netmap.handle_get("/api/netmap/net.js")[0], 200)

    def test_static_rules(self):
        for f in ("net.css", "net.js"):
            t = open(os.path.join(APP, "netmap_static", f), encoding="utf-8").read().lower()
            self.assertNotIn("yellow", re.sub(r"/\*.*?\*/", "", t, flags=re.S))
            self.assertNotIn("tile.openstreetmap.org", t)
            for c in ("#f5a524", "#ffd", "#ffcc00", "#ffeb3b", "#fde047", "#facc15", "#ff9900"): self.assertNotIn(c, t)
            self.assertIn("prefers-reduced-motion", t) if f == "net.js" else None
        self.assertIn("25000", open(os.path.join(APP, "netmap_static", "net.js")).read())

    def test_bars_union_and_bounds(self):
        import netmap
        n = datetime.now(timezone.utc)
        days, up = netmap._bars([(n - timedelta(hours=5), n - timedelta(hours=3), 2), (n - timedelta(hours=4), n - timedelta(hours=2), 3), (n - timedelta(days=90), None, 1)])
        self.assertEqual(len(days), netmap.DAYS)
        self.assertTrue(0 <= up <= 100)
        self.assertAlmostEqual(100 - up, 100 * 3 * 3600 / ((n - (n.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=netmap.DAYS - 1))).total_seconds()), places=1)
        self.assertEqual(max(days), 3)

    def test_asn_status(self):
        import netmap, time
        t = int(time.time())
        ev = [{"location": "asn/1", "datasource": "bgp", "start": t - 1800, "duration": 600, "location_name": "AS1"},
              {"location": "asn/1", "datasource": "merit-nt", "start": t - 600, "duration": 60, "location_name": "AS1"},
              {"location": "asn/2", "datasource": "bgp", "start": t - 86400 * 5, "duration": 86400 * 10, "location_name": "AS2"}]
        self.assertEqual(netmap.asn_one([1], ev)["level"], 2)
        self.assertEqual(netmap.asn_one([2], ev)["level"], 0)   # baseline shift longer than 3 days is ignored

    def test_every_network_has_links(self):
        import netmap
        ids = set()
        for n in netmap.NETS:
            self.assertNotIn(n[0], ids); ids.add(n[0])
            self.assertTrue(n[5].startswith("https://") and n[6].startswith("https://"), n[0])
            self.assertIn(n[2], {g for g, _ in netmap.GROUPS})

if __name__ == "__main__":
    unittest.main()
