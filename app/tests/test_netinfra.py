import os, sys, json, tempfile, unittest
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import netmap, netinfra
import build_infra as B
ST = os.path.join(HERE, "netmap_static")

class Infra(unittest.TestCase):
    def test_static_layers_are_licensed_and_served(self):
        lim = {"towers.json": 6_000_000, "grid.json": 9_000_000}
        for n, cr in (("towers.json", "FCC"), ("grid.json", "OpenStreetMap")):
            p = os.path.join(ST, n); self.assertLess(os.path.getsize(p), lim[n], n)
            d = json.load(open(p)); self.assertIn(cr, d["credit"])
            self.assertEqual(netmap.handle_get("/api/netmap/" + n)[0], 200)
        self.assertNotIn("opencellid", open(os.path.join(ST, "towers.json")).read().lower())   # needs an API key; not used

    def test_grid_vector_tiles(self):
        self.assertEqual(netinfra.tile(ST, 0, 0, 0)[0], 200)
        self.assertGreater(len(netinfra.tile(ST, 0, 0, 0)[1]), 10)
        self.assertEqual(netinfra.tile(ST, 12, 0, 0)[0], 404)
        self.assertEqual(netinfra.tile(ST, 1, 2, 0)[0], 404)
        self.assertEqual(netmap.handle_get("/api/netmap/gridtiles/0/0/0.pbf")[0], 200)
        self.assertEqual(netinfra.tile(ST, 9, 0, 0)[1], b"")
        js = open(os.path.join(ST, "net.js")).read()
        self.assertIn('type: "vector", tiles:', js)
        self.assertIn("© OpenStreetMap contributors", js)

    def test_heavy_layers_off_by_default(self):
        js = open(os.path.join(ST, "net.js")).read()
        self.assertIn("sea: false, towers: false, grid: false }", js)
        html = netmap.page({})
        for k in ("towers", "grid"): self.assertIn(f'data-k="{k}" aria-pressed="false"', html)

    def test_voltage_and_fiber_filters(self):
        self.assertEqual(B.kv({"voltage": "345000;138000"}), 345); self.assertEqual(B.kv({"voltage": "n/a"}), 0)
        with tempfile.NamedTemporaryFile("w", suffix=".geojsonseq", delete=False) as f:
            L = lambda c, **t: f.write(json.dumps({"type": "Feature", "geometry": {"type": "LineString", "coordinates": c}, "properties": t}) + "\n")
            L([[-100, 40], [-100, 40.5]], power="line", voltage="500000", name="A")       # ~55 km, kept
            L([[-100, 40], [-100, 40.1]], power="line", voltage="115000")                 # below 230 kV, dropped
            L([[-90, 35], [-90, 35.3]], telecom="line", operator="Zayo")                   # ~33 km, kept
            L([[-91, 35], [-91, 35.01]], telecom="line", operator="Local")                 # ~1 km, dropped
            L([[-92, 35], [-92, 36]], telecom="line", location="underwater")               # submarine, dropped
        g = B.grid(f.name); fb = B.fiber(f.name); os.unlink(f.name)
        self.assertEqual([x["properties"]["v"] for x in g["features"]], [500])
        self.assertEqual([x["properties"]["op"] for x in fb["features"]], ["Zayo"]); self.assertGreater(fb["km"], 30)

if __name__ == "__main__": unittest.main()
