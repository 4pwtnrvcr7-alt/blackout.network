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

    def test_views_spread_and_links(self):
        node = subprocess.run(["node", "-e", r'''
const fs=require("fs"), vm=require("vm");
const ctx={};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[1],"utf8"), ctx);
const B=ctx.BNSignal;
const now=Date.parse("2026-11-08T00:00:00Z");
function item(o){return Object.assign({cluster_id:"0123456789abcdef",title:"Quake",category:"cyber",rank:6,lat:10,lon:20,watchlist:0,event_time:"2026-11-07T18:00:00Z",links:[{url:"https://example.com/a"}]}, o||{});}
const fan=B.spread([{lat:32.17,lon:54.93},{lat:32.17,lon:54.93},{lat:32.166,lon:54.931},{lat:40,lon:-100}]);
const keys=fan.slice(0,3).map(p=>p.dx.toFixed(2)+","+p.dy.toFixed(2));
const tally=B.counts([item({category:"war/conflict",rank:8}), item({category:"war/conflict",rank:5}), item({category:"cyber",rank:8}), item({category:"political",rank:2,event_time:"2026-10-01T00:00:00Z"})], {rank:"",topic:"",hours:168}, now);
const out={
 us:B.viewSpec("us"), world:B.viewSpec("world"), conf:B.viewSpec("conflicts"), def:B.viewSpec(""),
 refresh:B.refreshMs,
 war:B.pass(item({category:"war/conflict",rank:8}),{rank:"",topic:"",hours:168,conflict:true},now),
 peace:B.pass(item({category:"cyber",rank:8}),{rank:"",topic:"",hours:168,conflict:true},now),
 track:B.dest(item({cluster_id:"nope", title:"Quake south of Tokyo", category:"natural disaster", links:[{source:"USGS"}]})),
 wire:B.dest(item({links:[{url:"/track/iran"},{url:"https://example.com/a"}]})),
 ext:B.dest(item({cluster_id:"nope", title:"Talks", category:"political"})),
 fan:fan, keys:keys, lone:B.spread([{lat:10,lon:20}])[0], tally:tally
};
console.log(JSON.stringify(out));
''', JS], capture_output=True, text=True, check=True)
        got = json.loads(node.stdout)
        self.assertEqual(got["us"]["lat"], 39)
        self.assertEqual(got["us"]["lon"], -98)
        self.assertFalse(got["us"]["conflict"])
        self.assertEqual(got["def"]["name"], "us")
        self.assertFalse(got["world"]["conflict"])
        self.assertEqual(got["world"]["lat"], 20)
        self.assertTrue(got["conf"]["conflict"])
        self.assertLess(got["conf"]["bounds"]["south"], 32)
        self.assertGreater(got["conf"]["bounds"]["north"], 52)
        self.assertGreater(got["conf"]["bounds"]["east"], 50)
        self.assertLess(got["conf"]["bounds"]["west"], 10)
        self.assertEqual(got["refresh"], 300000)
        self.assertTrue(got["war"])
        self.assertFalse(got["peace"])
        self.assertEqual(got["track"]["href"], "/#solar")
        self.assertEqual(got["track"]["kind"], "tracker")
        self.assertFalse(got["track"]["ext"])
        self.assertEqual(got["wire"]["href"], "/wire/0123456789abcdef")
        self.assertEqual(got["wire"]["kind"], "wire")
        self.assertEqual(got["ext"]["href"], "https://example.com/a")
        self.assertEqual(got["ext"]["kind"], "source")
        self.assertEqual(got["lone"]["dx"], 0)
        self.assertEqual(got["lone"]["dy"], 0)
        self.assertEqual(len(set(got["keys"])), 3)
        self.assertTrue(all(p["dx"] or p["dy"] for p in got["fan"][:3]))
        self.assertEqual(got["fan"][3]["dx"], 0)
        self.assertEqual(got["tally"]["war"], 2)
        self.assertEqual(got["tally"]["total"], 3)
        css = open(os.path.join(APP, "signal_map_static", "app.css"), encoding="utf-8").read()
        self.assertNotIn("bn-sig-radar", css)
        self.assertNotIn("box-shadow:0 0 12px", css)
        growth = open(os.path.join(APP, "growth_static", "app.js"), encoding="utf-8").read()
        self.assertIn("bng_mapchip", growth)
        self.assertIn("mapOnScreen", growth)
        gcss = open(os.path.join(APP, "growth_static", "app.css"), encoding="utf-8").read()
        self.assertIn("bn-map-root #bng_prompt", gcss)
        self.assertIn("bn-sig-visible", gcss)

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
        self.assertTrue(japan["approximate"])
        self.assertFalse(nws["approximate"])

    def test_conflict_cities_beat_the_actor_country(self):
        import signal_place as P
        russia = (58.2494, 44.6865)
        us = (39.5385, -97.4826)
        washington = (38.8977, -77.0365)
        cases = {
            "Russian strike on Kyiv kills civilians": ("Kyiv", 50.45, 30.52),
            "White House says Russia struck Kyiv": ("Kyiv", 50.45, 30.52),
            "US officials say Russia targeted Kyiv": ("Kyiv", 50.45, 30.52),
            "Moscow condemns strike on Kyiv": ("Kyiv", 50.45, 30.52),
            "Drone strike on Odesa": ("Odesa", 46.49, 30.74),
            "Kharkiv hit overnight by Russia": ("Kharkiv", 49.98, 36.25),
            "Israel strikes Gaza City": ("Gaza", 31.50, 34.47),
            "Israeli airstrikes on Gaza kill dozens": ("Gaza", 31.50, 34.47),
            "Explosion in Rafah after Israeli strike": ("Rafah", 31.30, 34.24),
            "Missile hits Tel Aviv": ("Tel Aviv", 32.08, 34.78),
            "Israel strikes Beirut": ("Beirut", 33.89, 35.50),
            "Explosion in Tehran": ("Tehran", 35.69, 51.42),
            "Israel strikes targets in Tehran": ("Tehran", 35.69, 51.42),
        }
        for title, (name, lat, lon) in cases.items():
            hit = P.infer(title)
            self.assertIsNotNone(hit, title)
            self.assertEqual(hit["precision"], "city", title)
            self.assertIn(name, hit["place"], title)
            self.assertFalse(hit["approximate"], title)
            self.assertAlmostEqual(hit["lat"], lat, delta=0.05, msg=title)
            self.assertAlmostEqual(hit["lon"], lon, delta=0.05, msg=title)
            self.assertNotAlmostEqual(hit["lat"], russia[0], delta=0.2, msg=title)
            self.assertFalse(abs(hit["lon"] - us[1]) < 1 and abs(hit["lat"] - us[0]) < 1, title)
            self.assertFalse(abs(hit["lat"] - washington[0]) < 0.2 and abs(hit["lon"] - washington[1]) < 0.2, title)
        iran = P.infer("Israel strikes Iran")
        self.assertEqual(iran["place"], "Iran")
        self.assertEqual(iran["precision"], "country")
        self.assertTrue(iran["approximate"])
        self.assertAlmostEqual(iran["lat"], 32.17, delta=0.2)
        ukraine = P.infer("Fighting in Ukraine")
        self.assertEqual(ukraine["place"], "Ukraine")
        self.assertTrue(ukraine["approximate"])
        self.assertIsNone(P.infer("Russia and Ukraine say emergency alert apps were hit"))

    def test_points_add_inferred_and_hide_watchlist_two(self):
        os.environ["BN_APPLE"] = "1"
        _ensure_points_db()
        signal_map._POINTS.update(t=0.0, v=None)
        body = signal_map.points_payload()
        self.assertIn("generated", body)
        self.assertRegex(body["generated"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        self.assertIsInstance(body["unmapped"], int)
        self.assertGreaterEqual(body["unmapped"], 0)
        self.assertIn("points", body)
        titles = " ".join(p["title"] for p in body["points"])
        self.assertNotIn("HIDDEN should not plot", titles)
        self.assertGreater(body["shown"], body["stored"])
        self.assertGreater(body["inferred"], 0)
        inferred = [p for p in body["points"] if p["exact"] is False]
        self.assertTrue(all(p["watchlist"] in (0, 1) for p in body["points"]))
        self.assertTrue(all(p["lat"] and p["lon"] for p in inferred))

def _ensure_points_db():
    """The points test reads app/blackout.db. A checkout without the synced database still has rows to place."""
    path = os.path.join(APP, "blackout.db")
    if os.path.isfile(path) and os.path.getsize(path) > 1000: return
    import sqlite3
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    c = sqlite3.connect(path)
    c.execute("""CREATE TABLE IF NOT EXISTS clusters(
        cluster_id TEXT PRIMARY KEY, title TEXT, category TEXT, location TEXT, lat REAL, lon REAL,
        event_time TEXT, first_seen TEXT, updated TEXT, rank INTEGER, links TEXT, watchlist INTEGER, brief TEXT)""")
    link = json.dumps([{"url": "https://example.com/a", "source": "Reuters"}])
    rows = [
        ("aaaaaaaaaaaaaaa1", "HIDDEN should not plot", "war/conflict", "", 32.0, 53.0, now, now, now, 9, link, 2, ""),
        ("aaaaaaaaaaaaaaa2", "Storms over Kansas", "natural disaster", "Kansas", 39.0, -98.0, now, now, now, 5, link, 0, ""),
        ("aaaaaaaaaaaaaaa3", "Quake near Los Angeles", "natural disaster", "", 34.05, -118.24, now, now, now, 6, link, 0, ""),
        ("bbbbbbbbbbbbbbb0", "Thanksgiving turkey dinner leftovers", "other", "", None, None, now, now, now, 1, link, 0, ""),
        ("bbbbbbbbbbbbbbb1", "Russian strike on Kyiv kills civilians", "war/conflict", "", None, None, now, now, now, 8, link, 0, ""),
        ("bbbbbbbbbbbbbbb2", "White House says Russia struck Kyiv", "war/conflict", "", None, None, now, now, now, 7, link, 0, ""),
        ("bbbbbbbbbbbbbbb3", "Israel strikes Gaza City", "war/conflict", "", None, None, now, now, now, 8, link, 0, ""),
        ("bbbbbbbbbbbbbbb4", "Explosion in Rafah after Israeli strike", "war/conflict", "", None, None, now, now, now, 6, link, 0, ""),
        ("bbbbbbbbbbbbbbb5", "Explosion in Tehran", "war/conflict", "", None, None, now, now, now, 7, link, 0, ""),
        ("bbbbbbbbbbbbbbb6", "Israel strikes Iran", "war/conflict", "", None, None, now, now, now, 8, link, 0, ""),
        ("bbbbbbbbbbbbbbb7", "Fighting in Ukraine", "war/conflict", "", None, None, now, now, now, 5, link, 0, ""),
        ("bbbbbbbbbbbbbbb8", "Drone strike on Odesa", "war/conflict", "", None, None, now, now, now, 5, link, 0, ""),
        ("bbbbbbbbbbbbbbb9", "Missile hits Tel Aviv", "war/conflict", "", None, None, now, now, now, 6, link, 0, ""),
    ]
    # Eight stories stored on one Iran centroid, so the map has to separate them.
    for i in range(8):
        rows.append((f"ccccccccccccccc{i}", f"Strike report {i} in Iran", "war/conflict", "Iran", 32.1662, 54.9315, now, now, now, 5, link, 0, ""))
    c.executemany("INSERT OR REPLACE INTO clusters(cluster_id,title,category,location,lat,lon,event_time,first_seen,updated,rank,links,watchlist,brief) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    c.commit(); c.close()

if __name__ == "__main__":
    unittest.main()
