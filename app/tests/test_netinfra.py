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

    def test_opens_on_map_with_every_layer_on(self):   # pt1787u
        js = open(os.path.join(ST, "net.js")).read()
        self.assertIn("sea: true, towers: true, grid: true }", js)
        self.assertNotIn("false, ", js[js.index("var ON = {"):js.index("};", js.index("var ON = {"))])
        self.assertNotIn('localStorage.getItem("bn_net_layers")', js)
        html = netmap.page({})
        self.assertNotIn('aria-pressed="false"><i></i>', html)
        for k in ("sea", "towers", "grid", "dc"): self.assertIn(f'data-k="{k}" aria-pressed="true"', html)
        self.assertIn('<body class="nx">', html); self.assertIn('data-m="map" aria-pressed="true"', html)

    def test_cables_drawn_landing_to_landing(self):   # pt1787u: dead ends at sea are not drawn; news matching keeps every name
        import json, netcables
        gj = json.load(open(os.path.join(ST, "cables.json")))
        drawn = {f["properties"]["n"] for f in gj["features"] if f["geometry"]["type"] == "LineString" and f["properties"].get("n")}
        self.assertIn("note", gj); self.assertTrue(drawn <= set(gj["names"])); self.assertGreater(len(gj["names"]), len(drawn))
        self.assertGreater(len(netcables.cable_names()), 200)

    def test_board_shows_live_signal_only_problems_first(self):   # pt1787u
        js = open(os.path.join(ST, "net.js")).read(); bj = open(os.path.join(ST, "board.js")).read()
        self.assertIn("return !n.link_only && n.level >= 0;", js); self.assertIn("s.networks = ns.length", js)
        self.assertIn("D = liveOnly(j)", js); self.assertIn(".then(liveOnly)", js)
        self.assertIn("return !n.link_only && n.level >= 0; }) : [];", bj); self.assertIn("ns.sort(order)", bj)
        self.assertIn("(eff(b) - eff(a)) || (changed(b) - changed(a))", bj); self.assertNotIn("no live signal\" : \"\")", bj)

    def test_layer_panel_removed_credit_kept(self):   # pt1787u
        html = netmap.page({}); js = open(os.path.join(ST, "net.js")).read()
        self.assertNotIn('id="nx_inf"', html); self.assertIn('id="nx_sea"', html)
        self.assertRegex(js, r'Power grid: <a href="https://www.openstreetmap.org/copyright"[^>]*>© OpenStreetMap contributors</a> \(ODbL\)')   # map credit line
        self.assertIn("© OpenStreetMap contributors (ODbL). Shows lines and substations", js)

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
