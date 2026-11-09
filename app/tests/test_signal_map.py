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
        self.assertLess(page.index("bn_sig"), page.index("bna_dash"))

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
 ours:B.dest(item({})), ext:B.dest(item({cluster_id:"nope", title:"Talks", category:"political"})), bad:B.dest(item({cluster_id:"nope", title:"Note", category:"cyber", links:[{url:"javascript:alert(1)"}]})), trk:B.dest(item({cluster_id:"nope", title:"Quake south of Tokyo", category:"natural disaster", links:[{source:"USGS"}]})),
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
        self.assertEqual(got["ours"]["kind"], "wire")
        self.assertIn("BLACKOUT.NETWORK", got["ours"]["label"])
        self.assertEqual(got["ext"]["href"], "https://example.com/a")
        self.assertTrue(got["ext"]["ext"])
        self.assertEqual(got["ext"]["kind"], "source")
        self.assertTrue(got["ext"]["label"].startswith("Source:"))
        self.assertEqual(got["bad"]["href"], "/#wire")
        self.assertFalse(got["bad"]["ext"])
        self.assertEqual(got["bad"]["kind"], "fallback")
        self.assertEqual(got["trk"]["href"], "/#solar")
        self.assertEqual(got["trk"]["kind"], "tracker")
        self.assertFalse(got["trk"]["ext"])
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

    def test_named_place_beats_the_actor_country(self):
        import signal_place as P
        kyiv = P.infer("White House says Russia struck Kyiv")
        self.assertEqual(kyiv["place"], "Kyiv")
        self.assertEqual(kyiv["precision"], "city")
        self.assertFalse(kyiv["approximate"])
        self.assertGreater(kyiv["lon"], 20)
        gaza = P.infer("Israel strikes Gaza City")
        self.assertIn("Gaza", gaza["place"])
        self.assertEqual(gaza["cc"], "PS")
        rafah = P.infer("Explosion in Rafah after Israeli strike")
        self.assertEqual(rafah["place"], "Rafah")
        self.assertAlmostEqual(rafah["lat"], 31.30, delta=0.05)
        self.assertEqual(P.infer("Attack on Zaporizhzhia NPP")["precision"], "facility")
        self.assertEqual(P.infer("Fighting in Khan Younis")["place"], "Khan Younis")
        self.assertEqual(P.infer("Ships in the Strait of Hormuz")["precision"], "region")
        iran = P.infer("Israel strikes Iran")
        self.assertEqual(iran["precision"], "country")
        self.assertTrue(iran["approximate"])
        self.assertIsNone(P.infer("Russia and Ukraine say emergency alert apps were hit"))

    def test_live_wire_fixture_places_more_specifically(self):
        """Before, on this same live Wire pull: 432 unmapped, 473 country or region, 360 city or state."""
        import signal_place as P
        from collections import Counter
        fixture = json.load(open(os.path.join(APP, "tests", "fixtures", "signal_live_wire.json"), encoding="utf-8"))
        prec = Counter()
        for row in fixture["items"]:
            hit = P.infer(P.story_text(row.get("title") or "", row.get("location") or "", ""))
            prec[None if not hit else hit["precision"]] += 1
        specific = prec["city"] + prec["facility"] + prec["state"]
        broad = prec["country"] + prec["region"]
        self.assertGreater(len(fixture["items"]), 1200)
        # PIP country verification drops wrong-country cities; country-only pins are intentional.
        self.assertLess(prec[None], 360)
        self.assertGreater(specific, 380)
        self.assertLess(broad, 580)
        self.assertGreater(specific + broad, 800)

class Cluster(unittest.TestCase):
    def test_clusters_never_fan_into_a_ring(self):
        node = subprocess.run(["node", "-e", r'''
const fs=require("fs"), vm=require("vm");
const ctx={};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[1],"utf8"), ctx);
const B=ctx.BNSignal;
function pile(n, lat, lon, extra){var a=[];for(var i=0;i<n;i++)a.push(Object.assign({lat:lat,lon:lon,precision:"country",approximate:true}, extra||{}));return a}
const country=B.clusterPlan(pile(40, 39.54, -97.48), 2);
const cities=B.clusterPlan(pile(6, 50.45, 30.52, {precision:"city", approximate:false}), 3);
const many=B.clusterPlan(pile(30, 32.17, 54.93, {precision:"city", approximate:false}), 2);
function far(g){var m=0;(g.offsets||[]).forEach(function(o){m=Math.max(m, Math.hypot(o.dx,o.dy))});return m}
const out={
 groups: country.length, spider: country[0].spider, n: country[0].n,
 citySpider: cities[0].spider, cityR: far(cities[0]),
 manySpider: many.some(function(g){return g.spider}),
 manyR: Math.max.apply(null, many.map(far).concat([0])),
 fanMax: B.FAN_MAX,
 us: B.inUS({lat:39.5,lon:-98}), kyiv: B.inUS({lat:50.45,lon:30.52,cc:"UA"}),
 uscc: B.inUS({lat:10,lon:10,cc:"US"})
};
console.log(JSON.stringify(out));
''', JS], capture_output=True, text=True, check=True)
        got = json.loads(node.stdout)
        self.assertEqual(got["groups"], 1)
        self.assertFalse(got["spider"])
        self.assertEqual(got["n"], 40)
        self.assertFalse(got["citySpider"])
        self.assertEqual(got["cityR"], 0)
        self.assertFalse(got["manySpider"])
        self.assertEqual(got["manyR"], 0)
        self.assertEqual(got["fanMax"], 0)
        self.assertTrue(got["us"])
        self.assertFalse(got["kyiv"])
        self.assertTrue(got["uscc"])

class PinVerify(unittest.TestCase):
    def test_paraguay_lands_inside_paraguay(self):
        import signal_place as P
        for title in (
            "JUST IN - Paraguay's Senate impeaches President Santiago Peña, convicting him of corruption",
            "Paraguay Bank Failure",
            "Impeached Paraguay leader charged over shock collapse of bank",
            "Ousted Paraguayan president placed under house arrest after bank collapse",
            "Mass protests over Ueno Bank collapse topple Paraguay's president",
        ):
            hit = P.infer(title)
            self.assertIsNotNone(hit, title)
            self.assertEqual(hit["cc"], "PY", title)
            self.assertTrue(P.in_country(hit["lat"], hit["lon"], "PY"), (title, hit))
            self.assertNotEqual(hit.get("place"), "Santiago")
            self.assertNotEqual(hit.get("place"), "Bogota")

    def test_ten_country_only_stories_spread_not_ring(self):
        import signal_place as P, math
        pts = [P.place_in_country("PY", story_id=f"story-{i}", index=i, total=10) for i in range(10)]
        self.assertEqual(len(pts), 10)
        coords = [(p["lat"], p["lon"]) for p in pts]
        self.assertEqual(len(set(coords)), 10)
        for p in pts:
            self.assertTrue(P.in_country(p["lat"], p["lon"], "PY"), p)
        cx = sum(a for a, _ in coords) / len(coords)
        cy = sum(b for _, b in coords) / len(coords)
        radii = [math.hypot(a - cx, b - cy) for a, b in coords]
        self.assertGreater(max(radii) - min(radii), 0.3)
        one = P.place_in_country("PY", story_id="only", index=0, total=1)
        self.assertTrue(P.in_country(one["lat"], one["lon"], "PY"))
        self.assertAlmostEqual(one["lat"], -25.2865, delta=0.2)

    def test_kyiv_not_pulled_to_actor_country(self):
        import signal_place as P
        kyiv = P.infer("White House says Russia struck Kyiv")
        self.assertEqual(kyiv["place"], "Kyiv")
        self.assertEqual(kyiv["cc"], "UA")
        self.assertTrue(P.in_country(kyiv["lat"], kyiv["lon"], "UA"))

    def test_north_korean_missile_pins_in_north_korea(self):
        import signal_place as P
        # Reporter country must not steal the pin from a North Korean launch.
        title = "South Korea JCS says it tracked unannounced North Korean cluster-warhead ballistic missile launch"
        hit = P.infer(title)
        self.assertIsNotNone(hit)
        self.assertEqual(hit["cc"], "KP", hit)
        self.assertTrue(P.in_country(hit["lat"], hit["lon"], "KP"), hit)
        self.assertNotEqual(hit["cc"], "KR")
        self.assertNotEqual(hit.get("place"), "North")  # not Cameroon admin "North"
        # Demonym alone (no other place) → KP
        alone = P.infer("North Korean ballistic missile test over the sea")
        self.assertEqual(alone["cc"], "KP")
        # Impact place still wins over demonym actor
        israel = P.infer("Iranian missile strikes hit northern Israel")
        self.assertEqual(israel["cc"], "IL")

class SeedSpeed(unittest.TestCase):
    def test_seed_points_never_waits_on_full_build(self):
        """Homepage seed must come from cache/disk (or a capped verified build), never join the full PIP rebuild."""
        import time
        signal_map._SEED.update(t=0, v=None)
        signal_map._POINTS.update(t=0, v=None)
        # Wipe disk seed for this process so we exercise the cold path.
        try:
            os.remove(signal_map._seed_path())
        except FileNotFoundError:
            pass
        waits = []
        real_cached = signal_map._points_cached
        def wrap(wait=0.0):
            waits.append(wait)
            return real_cached(wait=0)  # force no wait even if caller regresses
        signal_map._points_cached = wrap
        try:
            t0 = time.time()
            pts = signal_map.seed_points()
            elapsed = time.time() - t0
        finally:
            signal_map._points_cached = real_cached
        self.assertTrue(all(w == 0 for w in waits), waits)
        self.assertLess(elapsed, 2.0)  # capped verified seed, not full 7-day PIP
        self.assertIsInstance(pts, list)
        if pts:
            self.assertLessEqual(len(pts), signal_map.SEED_US + signal_map.SEED_WORLD)
            html = signal_map.home_section()
            self.assertIn("bn-sig-pre", html)
            self.assertIn("bn_sig_seed", html)

if __name__ == "__main__":
    unittest.main()
