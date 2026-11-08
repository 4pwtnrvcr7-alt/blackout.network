"""Global signal map. Run: cd app && python3 -m unittest tests.test_signal_map -v"""
import json, os, subprocess, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import addons, signal_map

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(APP, "signal_map_static", "app.js")

class Routes(unittest.TestCase):
    def test_routes_do_not_swallow_maps_tab(self):
        routes = addons.ROUTES
        self.assertEqual(routes["/map"], "signal_map")
        self.assertEqual(routes["/api/signal"], "signal_map")
        def hit(path):
            for pre, name in routes.items():
                if path == pre or path.startswith(pre + "/"): return name
            return None
        self.assertEqual(hit("/map"), "signal_map")
        self.assertEqual(hit("/map/"), "signal_map")
        self.assertNotEqual(hit("/maps"), "signal_map")
        self.assertEqual(hit("/api/signal/world.geojson"), "signal_map")
        self.assertNotEqual(hit("/api/signals"), "signal_map")

    def test_page_and_files(self):
        code, body, ctype = signal_map.handle_get("/map", {"rank": ["7"], "window": ["24"], "topic": ["cyber"]})
        self.assertEqual(code, 200)
        self.assertEqual(ctype, "text/html")
        html = body if isinstance(body, str) else body
        self.assertIn("Global signal map", html)
        self.assertIn('id="bn_sig_topic"', html)
        self.assertIn('id="bn_sig_rank"', html)
        self.assertIn('id="bn_sig_win"', html)
        self.assertIn('value="7" selected', html)
        self.assertIn('value="24" selected', html)
        self.assertIn(">cyber</option>", html)
        self.assertNotIn("openfreemap", html.lower())
        self.assertNotIn("maplibre", html.lower())
        self.assertNotIn("openstreetmap", html.lower())
        for name, ctype in (("app.js", "application/javascript"), ("app.css", "text/css"),
                            ("leaflet.js", "application/javascript"), ("leaflet.css", "text/css"),
                            ("world.geojson", "application/json")):
            c, b, ct = signal_map.handle_get("/api/signal/" + name, {})
            self.assertEqual(c, 200, name)
            self.assertEqual(ct, ctype, name)
            self.assertTrue(len(b) > 100, name)
        self.assertEqual(signal_map.handle_get("/api/signal/../scanner.py", {})[0], 404)
        geo = json.loads(signal_map.handle_get("/api/signal/world.geojson", {})[1])
        self.assertEqual(geo["type"], "FeatureCollection")
        self.assertGreater(len(geo["features"]), 10)

    def test_home_section_is_lazy_and_keyless(self):
        html = signal_map.home_section()
        self.assertIn('id="bn_sig"', html)
        self.assertIn('href="/map"', html)
        self.assertIn("IntersectionObserver", html)
        self.assertIn("requestIdleCallback", html)
        self.assertNotIn("openfreemap", html.lower())
        self.assertNotIn("maplibre", html.lower())
        self.assertNotIn("<script src=", html)  # nothing loads until the card is near the viewport
        import apple_v1
        class SN:
            YT_URL = "https://www.youtube.com/@BlkoutNtw"
            X_URL = "https://x.com/BlkoutNtw"
        page = apple_v1.home_html(SN)
        self.assertIn('id="bn_sig"', page)
        # Nov 7 homepage rebuild puts Active Threat Monitoring first. The map stays on the page after The latest.
        self.assertLess(page.index("bna_dash"), page.index("bna_h_latest"))
        self.assertLess(page.index("bna_h_latest"), page.index("bn_sig"))

    def test_marker_rules(self):
        node = subprocess.run(["node", "-e", r'''
const fs=require("fs"), vm=require("vm");
const ctx={};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[1],"utf8"), ctx);
const B=ctx.BNSignal;
const now=Date.parse("2026-11-08T00:00:00Z");
function item(o){return Object.assign({cluster_id:"0123456789abcdef",title:"Quake",category:"cyber",rank:6,lat:10,lon:20,watchlist:0,event_time:"2026-11-07T18:00:00Z",links:[{url:"https://example.com/a"}]}, o||{});}
const out={
 r0:B.band(0).color, r3:B.band(3).color, r4:B.band(4).color, r6:B.band(6).color, r7:B.band(7).color, r10:B.band(10).color,
 zero:B.real(item({lat:0,lon:0})), eq:B.real(item({lat:0,lon:10})), nan:B.real(item({lat:null,lon:1})),
 wl2:B.real(item({watchlist:2})), wl1:B.real(item({watchlist:1})),
 ours:B.dest(item({})), ext:B.dest(item({cluster_id:"nope"})), bad:B.dest(item({cluster_id:"nope", links:[{url:"javascript:alert(1)"}]})),
 hi:B.pass(item({rank:8}),{rank:"7",topic:"",hours:168},now),
 mid:B.pass(item({rank:5}),{rank:"7",topic:"",hours:168},now),
 band:B.pass(item({rank:5}),{rank:"4",topic:"",hours:168},now),
 low:B.pass(item({rank:2}),{rank:"0",topic:"",hours:168},now),
 topic:B.pass(item({category:"cyber"}),{rank:"",topic:"disease",hours:168},now),
 old:B.pass(item({event_time:"2026-10-01T00:00:00Z"}),{rank:"",topic:"",hours:24},now),
 recent:B.pass(item({event_time:"2026-11-07T20:00:00Z"}),{rank:"",topic:"",hours:24},now),
 hidden:B.pass(item({watchlist:2,rank:9}),{rank:"",topic:"",hours:168},now)
};
if(!B) throw new Error("no BNSignal");
console.log(JSON.stringify(out));
''', JS], capture_output=True, text=True, check=True)
        got = json.loads(node.stdout)
        red = "#FF4D4F"
        self.assertNotEqual(got["r0"], red)
        self.assertNotEqual(got["r3"], red)
        self.assertNotEqual(got["r4"], red)
        self.assertNotEqual(got["r6"], red)
        self.assertEqual(got["r7"], red)
        self.assertEqual(got["r10"], red)
        self.assertEqual(got["r4"], "#F5A524")
        self.assertEqual(got["r0"], "#55b7ff")
        self.assertFalse(got["zero"])
        self.assertTrue(got["eq"])
        self.assertFalse(got["nan"])
        self.assertFalse(got["wl2"])
        self.assertTrue(got["wl1"])
        self.assertEqual(got["ours"]["href"], "/wire/0123456789abcdef")
        self.assertFalse(got["ours"]["ext"])
        self.assertEqual(got["ext"]["href"], "https://example.com/a")
        self.assertTrue(got["ext"]["ext"])
        self.assertIsNone(got["bad"])
        self.assertTrue(got["hi"])
        self.assertFalse(got["mid"])
        self.assertTrue(got["band"])
        self.assertTrue(got["low"])
        self.assertFalse(got["topic"])
        self.assertFalse(got["old"])
        self.assertTrue(got["recent"])
        self.assertFalse(got["hidden"])

class Place(unittest.TestCase):
    def test_inference_skips_ambiguous_and_food(self):
        import signal_place as P
        self.assertEqual(P.infer("Thanksgiving turkey dinner leftovers"), None)
        self.assertEqual(P.infer("Roast turkey sandwich"), None)
        self.assertEqual(P.infer("Georgia"), None)
        self.assertEqual(P.infer("Jordan said the plan would wait"), None)
        self.assertEqual(P.infer("Russia and Ukraine say emergency alert apps were hit"), None)
        japan = P.infer("Earthquake in Japan")
        self.assertEqual(japan["precision"], "country")
        self.assertEqual(japan["place"], "Japan")
        coast = P.infer("A quake struck off the coast of Vanuatu")
        self.assertEqual(coast["place"], "Vanuatu")
        turkey = P.infer("Talks in Turkey on the grain deal")
        self.assertEqual(turkey["place"], "Turkey")
        nws = P.infer("Tornado Watch issued November 2 by NWS Norman OK")
        self.assertEqual(nws["precision"], "city")
        self.assertIn("Oklahoma", nws["place"])
        utah = P.infer("Flooding in Southern Utah")
        self.assertEqual(utah["precision"], "state")
        self.assertIn("Utah", utah["place"])
        hobbs = P.infer("Gov. Katie Hobbs declares a state of emergency as storms batter Arizona")
        self.assertEqual(hobbs["precision"], "state")
        self.assertIn("Arizona", hobbs["place"])

    def test_points_add_inferred_and_hide_watchlist_two(self):
        os.environ["BN_APPLE"] = "1"
        body = signal_map.points_payload()
        self.assertIn("points", body)
        titles = " ".join(p["title"] for p in body["points"])
        self.assertNotIn("HIDDEN should not plot", titles)
        self.assertGreater(body["shown"], body["stored"])
        self.assertGreater(body["inferred"], 0)
        inferred = [p for p in body["points"] if p["exact"] is False]
        self.assertTrue(all(p["watchlist"] in (0, 1) for p in body["points"]))
        self.assertTrue(all(p["lat"] and p["lon"] for p in inferred))

if __name__ == "__main__":
    unittest.main()
