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
        self.assertLess(prec[None], 360)
        self.assertGreater(specific, 480)
        self.assertLess(broad, 460)
        self.assertGreater(specific, broad)

class Cluster(unittest.TestCase):
    def test_country_pile_is_one_dot_and_rings_stay_small(self):
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
 manySpider: many.some(function(g){return g.spider && g.n>8}),
 manyR: Math.max.apply(null, many.map(far).concat([0])),
 us: B.inUS({lat:39.5,lon:-98}), kyiv: B.inUS({lat:50.45,lon:30.52,cc:"UA"}),
 uscc: B.inUS({lat:10,lon:10,cc:"US"})
};
console.log(JSON.stringify(out));
''', JS], capture_output=True, text=True, check=True)
        got = json.loads(node.stdout)
        self.assertEqual(got["groups"], 1)
        self.assertFalse(got["spider"])
        self.assertEqual(got["n"], 40)
        self.assertTrue(got["citySpider"])
        self.assertLessEqual(got["cityR"], 40)
        self.assertGreaterEqual(got["cityR"], 20)
        self.assertFalse(got["manySpider"])
        self.assertLessEqual(got["manyR"], 40)
        self.assertTrue(got["us"])
        self.assertFalse(got["kyiv"])
        self.assertTrue(got["uscc"])

class Category(unittest.TestCase):
    def _js(self, body):
        node = subprocess.run(["node", "-e", body, JS], capture_output=True, text=True, check=True)
        return json.loads(node.stdout)

    def test_category_palette_and_mapping(self):
        got = self._js(r'''
const fs=require("fs"), vm=require("vm");
const ctx={};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[1],"utf8"), ctx);
const B=ctx.BNSignal;
function item(o){return Object.assign({cluster_id:"0123456789abcdef",title:"",category:"other",rank:1,lat:10,lon:20,watchlist:0,event_time:"2026-11-07T18:00:00Z",links:[]}, o||{});}
const ids=B.CAT_IDS;
const colors=ids.map(id=>B.colorFor(id,false));
const lights=ids.map(id=>B.colorFor(id,true));
const now=Date.parse("2026-11-08T00:00:00Z");
const health=item({category:"disease",title:"Kerala measles outbreak hits vaccinated children",place:"Kerala"});
const storm=item({category:"natural disaster",title:"Tornado in Oklahoma"});
const quake=item({category:"natural disaster",title:"Earthquake in Japan"});
const war=item({category:"war/conflict",title:"Russia struck Kyiv",place:"Kyiv"});
const nuke=item({category:"war/conflict",title:"Nuclear strike order on Iran"});
const solar=item({category:"space weather",title:"Geomagnetic storm reaches G3"});
const cyber=item({category:"cyber",title:"Ransomware hits a hospital network"});
const grid=item({category:"cyber",title:"Amhara, Ethiopia: internet outage",links:[{source:"IODA",url:"https://ioda.inetintel.cc/"}]});
const pol=item({category:"political",title:"Parliament dissolved after the vote"});
const money=item({category:"financial",title:"Bank failure shakes the market"});
const ufo=item({category:"ufo/uap",title:"UAP sighting reported"});
const misc=item({category:"political",title:"Measles cases rise in the county"});
const out={
 ids:ids, colors:colors, lights:lights,
 health:B.catOf(health).id, storm:B.catOf(storm).id, quake:B.catOf(quake).id, war:B.catOf(war).id,
 nuke:B.catOf(nuke).id, solar:B.catOf(solar).id, cyber:B.catOf(cyber).id, grid:B.catOf(grid).id,
 pol:B.catOf(pol).id, money:B.catOf(money).id, ufo:B.catOf(ufo).id, misc:B.catOf(misc).id,
 other:B.catOf(item({title:"A quiet note"})).id,
 measles:B.matches(health,"measles"), ukraine:B.matches(item({title:"Russian invasion of Ukraine",category:"war/conflict",place:"Kyiv"}),"Ukraine"),
 place:B.matches(item({title:"Talks",place:"Odesa, Ukraine"}),"ukraine"),
 source:B.matches(grid,"ioda"), catLabel:B.matches(health,"health"),
 miss:B.matches(health,"ukraine"),
 top:B.topMatches([health,item({title:"Measles clinic opens",category:"disease",rank:9,lat:11,lon:21}),war],"measles",8).map(x=>x.rank),
 passHealth:B.pass(health,{rank:"",topic:"",hours:168,cats:["health"]},now),
 passWar:B.pass(war,{rank:"",topic:"",hours:168,cats:["health"]},now),
 passNone:B.pass(health,{rank:"",topic:"",hours:168,cats:[]},now),
 passOld:B.pass(item({category:"cyber",rank:6}),{rank:"",topic:"",hours:168},now),
 counts:B.viewCounts([
   item({category:"disease",title:"Measles",lat:40,lon:-100}),
   item({category:"disease",title:"Flu",lat:41,lon:-90}),
   item({category:"war/conflict",title:"Shelling in Ukraine",lat:50.4,lon:30.5})
 ],{rank:"",topic:"",hours:168,cats:["health"]},now),
 countsAll:B.viewCounts([
   item({category:"disease",title:"Measles",lat:40,lon:-100}),
   item({category:"war/conflict",title:"Shelling in Ukraine",lat:50.4,lon:30.5})
 ],{rank:"",topic:"",hours:168,cats:B.CAT_IDS},now),
 dom:B.dominantColor([war,war,health],false),
 tie:B.dominantColor([war,health],false),
 neutral:B.neutralColor(false),
 dot:B.dotClass(item({exact:false,approximate:true,precision:"country"}),false),
 dotDim:B.dotClass(item({exact:true}),true),
 dotHit:B.dotClass(item({exact:true}),false,true),
 mc:B.matchCount([item({title:"Measles in Texas",category:"disease"}),item({title:"Storm in Ohio",category:"natural disaster"}),item({title:"Measles clinic",category:"disease"})],"measles"),
 mc0:B.matchCount([item({title:"Storm in Ohio",category:"natural disaster"})],"measles"),
 mcAll:B.matchCount([item({title:"A"}),item({title:"B"})],""),
 ms:B.SEARCH_MS, key:B.CAT_KEY,
 saved:B.enabledFrom(JSON.stringify(["cyber","health"])),
 none:B.enabledFrom(JSON.stringify(B.CAT_IDS)),
 all:B.enabledFrom(null),
 round:B.disabledFrom(B.enabledFrom(JSON.stringify(["grid"])))
};
console.log(JSON.stringify(out));
''')
        self.assertEqual(got["ids"], ["health", "weather", "conflict", "quake", "solar", "grid", "cyber", "nuclear", "politics", "other"])
        self.assertEqual(len(set(got["colors"])), 10)
        self.assertEqual(len(set(got["lights"])), 10)
        self.assertEqual(got["health"], "health")
        self.assertEqual(got["storm"], "weather")
        self.assertEqual(got["quake"], "quake")
        self.assertEqual(got["war"], "conflict")
        self.assertEqual(got["nuke"], "nuclear")
        self.assertEqual(got["solar"], "solar")
        self.assertEqual(got["cyber"], "cyber")
        self.assertEqual(got["grid"], "grid")
        self.assertEqual(got["pol"], "politics")
        self.assertEqual(got["money"], "politics")
        self.assertEqual(got["ufo"], "other")
        self.assertEqual(got["misc"], "health")
        self.assertEqual(got["other"], "other")
        self.assertTrue(got["measles"])
        self.assertTrue(got["ukraine"])
        self.assertTrue(got["place"])
        self.assertTrue(got["source"])
        self.assertTrue(got["catLabel"])
        self.assertFalse(got["miss"])
        self.assertEqual(got["top"][0], 9)
        self.assertTrue(got["passHealth"])
        self.assertFalse(got["passWar"])
        self.assertFalse(got["passNone"])
        self.assertTrue(got["passOld"])
        self.assertEqual(got["counts"], {"us": 2, "world": 2, "conflicts": 0})
        self.assertEqual(got["countsAll"], {"us": 1, "world": 2, "conflicts": 1})
        self.assertEqual(got["dom"], "#F2554A")
        self.assertEqual(got["tie"], got["neutral"])
        self.assertEqual(got["neutral"], "#8B95A3")
        self.assertEqual(got["dot"], "signal approx")
        self.assertEqual(got["dotDim"], "signal dim")
        self.assertEqual(got["dotHit"], "signal hit")
        self.assertEqual(got["mc"], 2)
        self.assertEqual(got["mc0"], 0)
        self.assertEqual(got["mcAll"], 2)
        self.assertEqual(got["ms"], 200)
        self.assertEqual(got["key"], "bn-sig-cats")
        self.assertNotIn("cyber", got["saved"])
        self.assertNotIn("health", got["saved"])
        self.assertIn("conflict", got["saved"])
        self.assertEqual(got["none"], [])
        self.assertEqual(got["all"], got["ids"])
        self.assertEqual(got["round"], ["grid"])
        css = open(os.path.join(APP, "signal_map_static", "app.css"), encoding="utf-8").read()
        js = open(JS, encoding="utf-8").read()
        for hexcolor in got["colors"] + got["lights"]:
            self.assertIn(hexcolor, css)
            self.assertIn(hexcolor, js)
        self.assertIn("opacity:.72", css)
        self.assertIn("opacity:.15", css)
        self.assertIn(".bn-sig-search:focus-within", css)
        self.assertIn(".signal.hit", css)
        results_css = css[css.find(".bn-sig-results{"):css.find(".bn-sig-results{") + 420]
        self.assertIn("background:#152033", results_css)
        self.assertNotIn("sig-tip", results_css)
        self.assertIn('html[data-theme="light"] .bn-sig-results{background:#ffffff', css)
        self.assertIn("Math.random() * 15", js)
        self.assertIn("LOWER48", js)
        self.assertNotIn("0 0 8px", css)
        self.assertNotIn("bounce", css.lower())

    def test_filter_and_search_markup(self):
        home = signal_map.home_section()
        _code, body, _ctype = signal_map.handle_get("/map", {})
        js = open(JS, encoding="utf-8").read()
        for html in (home, body):
            self.assertIn('class="bn-sig-search"', html)
            self.assertIn('id="bn_sig_q"', html)
            self.assertIn('class="bn-sig-clear"', html)
            self.assertIn('class="bn-sig-cats"', html)
            self.assertIn('aria-label="Categories"', html)
            for cid in ("all", "none", "health", "weather", "conflict", "quake", "solar", "grid", "cyber", "nuclear", "politics", "other"):
                self.assertIn('data-cat="%s"' % cid, html)
        self.assertIn("localStorage", js)
        self.assertIn("bn-sig-cats", js)
        self.assertIn("setTimeout(function () { setQuery(input.value); }, SEARCH_MS)", js)


if __name__ == "__main__":
    unittest.main()
