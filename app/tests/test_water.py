import os, sys, json, re, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import water as W

STATIC = os.path.join(os.path.dirname(W.__file__), "water_static")

def it(**k):
    d = dict(id="x1", kind="advisory", level="boil", label="Boil water notice", name="Test", place="Somewhere", lat=40.0, lon=-90.0, precision="point", since="2026-11-01T00:00:00Z",
             by="Agency", src="Agency data", url="https://example.gov/record/1")
    d.update(k); return d

class Water(unittest.TestCase):
    def setUp(self):
        W._C.clear()
        if getattr(W, '_PAY', None) is not None:
            W._PAY.update(t=0, items=None, map=None, list_meta=None)
    def test_title_case_only_for_all_caps(self):
        self.assertEqual(W._title("PORT PROTECTION"), "Port Protection")
        self.assertEqual(W._title("RURAL MUNICIPALITY OF MONTCALM ( MORRIS REGIONAL )"), "Rural Municipality of Montcalm (Morris Regional)")
        self.assertEqual(W._title("City of Jackson"), "City of Jackson")
    def test_point_validation(self):
        self.assertIsNone(W._pt(0, 0)); self.assertIsNone(W._pt("x", 1)); self.assertIsNone(W._pt(95, 10)); self.assertEqual(W._pt("56.32119", "-133.59911"), (56.3212, -133.5991))
    def test_county_centroids_cover_us(self):
        c = W.centroids(); self.assertGreater(len(c), 3100); self.assertEqual(c["12117"][3], "FL"); self.assertTrue(24 < c["12117"][0] < 31)
    def test_every_item_needs_an_https_source_link(self):
        W.FETCH.update({s[0]: (lambda: []) for s in W.SOURCES}); W.FETCH["ak"] = lambda: [it()]
        d = W.data(force=True)
        self.assertEqual(d["counts"], {"advisory": 1}); self.assertTrue(all(i["url"].startswith("https://") for i in d["items"]))
        self.assertNotIn("by", d["items"][0]); self.assertEqual(d["pubs"]["Agency data"], "Agency")
    def test_failed_source_keeps_last_good_and_says_unavailable(self):
        calls = {"n": 0}
        def flaky():
            calls["n"] += 1
            if calls["n"] > 1: raise OSError("down")
            return [it()]
        W.FETCH.update({s[0]: (lambda: []) for s in W.SOURCES}); W.FETCH["ak"] = flaky
        W.data(force=True); W._C["ak"]["t"] -= 120      # past the 60 s refresh floor
        d = W.data(force=True); s = [x for x in d["sources"] if x["id"] == "ak"][0]
        self.assertEqual(s["count"], 1); self.assertFalse(s["ok"]); self.assertEqual(s["error"], "OSError"); self.assertIsNotNone(s["updated"])
    def test_refresh_inside_60s_does_not_hit_upstream_again(self):
        n = {"c": 0}
        def one(): n["c"] += 1; return [it()]
        W.FETCH.update({s[0]: (lambda: []) for s in W.SOURCES}); W.FETCH["ak"] = one
        W.data(force=True); d = W.data(force=True)
        self.assertEqual(n["c"], 1); self.assertEqual(d["pulled"], [])
    def test_page_and_routes(self):
        import sitenav_ui
        r = W.handle_get("/water")
        self.assertEqual(r[0], 301); self.assertEqual(r[3]["Location"], "/grid/water")
        self.assertEqual(W.handle_get("/api/water/app.js")[0], 200); self.assertEqual(W.handle_get("/api/water/app.css")[0], 200)
        self.assertEqual(W.handle_get("/api/water/../server.py")[0], 404)
        self.assertEqual(sitenav_ui.refresh_mode("/grid"), "inpage")
        self.assertEqual(sitenav_ui.refresh_mode("/grid/water"), "inpage")
        import addons; self.assertEqual(addons.ROUTES["/water"], "water"); self.assertEqual(addons.ROUTES["/api/water"], "water")
    def test_theme_rules(self):
        css = open(os.path.join(STATIC, "app.css")).read(); js = open(os.path.join(STATIC, "app.js")).read(); src = open(W.__file__).read()
        for t in (css, js):
            for h in re.findall(r"#([0-9a-fA-F]{6})\b", t):
                r, g, b = int(h[:2], 16), int(h[2:4], 16), int(h[4:], 16)
                self.assertFalse(r > 200 and g > 170 and b < 120, "yellow-ish colour #" + h)      # no yellow
        allt = (css + js + src).lower()
        for bad in ("peer-to-peer", "meshtastic", "lora", "satellite", "<img"):
            self.assertNotIn(bad, allt.replace("sewage", "")) if bad != "satellite" else None
        self.assertNotIn("<img", W.page().lower())      # no map or satellite images on cards
        self.assertIn("openfreemap", js.lower()); self.assertNotIn("tile.openstreetmap.org", js.lower())
        self.assertIn("-96.5, 39.2", js)                # map opens centred on the U.S.

    def test_share_and_permalink(self):
        row = it(id="akabc123defg", name="Port Protection", place="Alaska", level="boil", label="Boil water notice",
                 note="Long term BWN issued by Alaska DEC.", kind="advisory")
        tags = W.item_tags(row)
        self.assertTrue(3 <= len(tags) <= 5, tags)
        joined = " ".join(tags)
        self.assertIn("#BoilWater", joined)
        self.assertIn("#Alaska", joined)
        self.assertNotIn("#DEC", tags)
        low = {t.lower() for t in tags}
        for ban in ("#news", "#blackoutnetwork", "#sdwis", "#npdes", "#icis", "#echo", "#dec", "#cwa", "#alerts", "#breaking"):
            self.assertNotIn(ban, low, tags)
        url = W.permalink(row, for_x=True)
        self.assertEqual(url, "https://blackout.network/water/akabc123defg?s=x")
        href = W.item_intent(row)
        self.assertTrue(href.startswith("https://x.com/intent/post?"))
        from urllib.parse import parse_qs, urlparse
        q = parse_qs(urlparse(href).query)
        self.assertEqual(q.get("url"), [url])
        hashes = (q.get("hashtags") or [""])[0].split(",")
        self.assertTrue(3 <= len(hashes) <= 5, hashes)
        self.assertNotIn("News", hashes)
        self.assertNotIn("BlackoutNetwork", hashes)
        packed = W.decorate(row)
        self.assertEqual(packed["permalink"], "https://blackout.network/water/akabc123defg")
        self.assertTrue(packed["xu"].startswith("https://x.com/intent/post?"))
        dnd = it(id="akabc123defg", name="Alaska Wildlife Center", place="Alaska", level="dnd",
                 label="Do not drink or use", note="Do not drink or use. Source: Alaska DEC.", kind="advisory")
        dt = W.item_tags(dnd)
        self.assertIn("#DoNotDrink", dt)
        self.assertIn("#Alaska", dt)
        self.assertNotIn("#DEC", dt)
        self.assertTrue(3 <= len(dt) <= 5, dt)
        ph = W.page_intent()
        self.assertIn("DoNotDrink", ph)
        self.assertIn("BoilWater", ph)
        self.assertNotIn("DEC", ph)

    def test_news_share_never_uses_news_hashtag(self):
        row = it(id="nwabc123defg", kind="news", level="news", label="News report", name="Boil-water order issued in Philadelphia",
                 place="Philadelphia", url="https://example.com/story")
        tags = W.item_tags(row)
        self.assertTrue(3 <= len(tags) <= 5, tags)
        self.assertNotIn("#News", tags)
        self.assertNotIn("#BlackoutNetwork", tags)

    def test_item_permalink_route_and_og(self):
        W.FETCH.update({s[0]: (lambda: []) for s in W.SOURCES})
        W.FETCH["ak"] = lambda: [it(id="akabc123defg", name="Port Protection", place="Alaska")]
        W.data(force=True)
        r = W.handle_get("/water/akabc123defg")
        self.assertEqual(r[0], 301)
        self.assertEqual(r[3]["Location"], "/grid/water/akabc123defg")
        self.assertEqual(W.handle_get("/water/not")[0], 404)          # too short
        self.assertEqual(W.handle_get("/water/bad id")[0], 404)
        # OG and share live on the Grid water view (the 301 target)
        import netmap
        code, body, ctype = netmap.handle_get("/grid/water/akabc123defg")
        self.assertEqual(code, 200)
        self.assertIn("text/html", ctype)
        self.assertIn("og:image", body)
        self.assertIn("/og/share/water/akabc123defg.png", body)
        self.assertIn("twitter:card", body)
        self.assertIn("summary_large_image", body)
        self.assertIn("BLACKOUT.NETWORK", body)
        self.assertIn("akabc123defg", body)
        self.assertIn("window.BN_WATER", body)
        self.assertIn("bnshare.js", body)
        self.assertIn('id="nx_card"', body)
        self.assertNotIn("nx_water_btn", body)
        self.assertNotIn('id="nx_water"', body)
        code, home, _ = netmap.handle_get("/grid/water")
        self.assertEqual(code, 200)
        self.assertIn("/og/share/water/page.png", home)
        self.assertIn('data-k="water"', home)
        self.assertIn("bnshare.js", home)
        self.assertNotIn("nx_water_btn", home)

    def test_share_card_is_typographic_not_a_map(self):
        import share_card
        W.FETCH.update({s[0]: (lambda: []) for s in W.SOURCES})
        W.FETCH["ak"] = lambda: [it(id="akabc123defg", name="Port Protection", place="Alaska", level="dnd", label="Do not drink or use")]
        W.data(force=True)
        spec = share_card.item_for_share("water", "akabc123defg")
        self.assertEqual(spec["art"], ("type",))
        self.assertEqual(spec["kind"], "water")
        self.assertEqual(spec["title"], "Port Protection")
        self.assertNotEqual((spec.get("art") or ("x",))[0], "map")
        page = share_card.item_for_share("water", "page")
        self.assertEqual(page["art"], ("type",))
        self.assertIn("BLACKOUT.NETWORK", page["kicker"])

    def test_js_reuses_growth_share_row(self):
        js = open(os.path.join(STATIC, "app.js")).read()
        self.assertIn("bng-share", js)
        self.assertIn("Post on X", js)
        self.assertIn("bng-copy", js)
        self.assertIn("bng-native", js)
        self.assertIn("Permalink", js)
        self.assertIn("Source", js)
        self.assertIn("x.com/intent/post", js)
        self.assertNotIn("peer-to-peer", js.lower())
        self.assertNotIn("meshtastic", js.lower())

    def test_sort_severity_then_us_then_recency(self):
        import water
        rows = [
            dict(id="nl1", kind="advisory", level="boil", name="Stephenville", cc="CA", pop=10000, since="2026-11-20T00:00:00Z"),
            dict(id="or1", kind="advisory", level="boil", name="Salem", cc="US", st="OR", pop=50, since="2026-11-10T00:00:00Z"),
            dict(id="or2", kind="advisory", level="boil", name="Bend", cc="US", st="OR", pop=50, since="2026-11-27T00:00:00Z"),
            dict(id="ak1", kind="advisory", level="dnd", name="Bethel", cc="US", st="AK", pop=10, since="2026-11-01T00:00:00Z"),
            dict(id="sd1", kind="violation", level="viol", name="A system", cc="US", st="TX", pop=80000, since="2026-11-28T00:00:00Z"),
        ]
        got = [r["id"] for r in water.sort_items(rows)]
        self.assertEqual(got, ["ak1", "or2", "or1", "nl1", "sd1"])
        self.assertEqual(water.us_advisory_counts(rows), {"AK": 1, "OR": 2})

    def test_new_us_advisory_sources_are_registered(self):
        import water
        self.assertIn("or", water.FETCH)
        self.assertIn("fl", water.FETCH)
        ids = [s[0] for s in water.SOURCES]
        self.assertEqual(ids[:3], ["ak", "or", "fl"])

    def test_data_and_map_never_wait_on_slow_sources(self):
        import time
        def slow():
            time.sleep(5)
            return [it()]
        W.FETCH.update({s[0]: (lambda: []) for s in W.SOURCES})
        W.FETCH["ak"] = slow
        W._C.clear(); W._PAY.update(t=0, items=None, map=None, list_meta=None)
        t0 = time.time()
        code, body, ct = W.handle_get("/api/water/map")[:3]
        self.assertEqual(code, 200)
        self.assertLess(time.time() - t0, 1.0, "map must not wait on upstream")
        self.assertEqual(body.get("r"), [])
        t0 = time.time()
        code, body, ct = W.handle_get("/api/water/data", {"limit": ["30"], "offset": ["0"]})[:3]
        self.assertEqual(code, 200)
        self.assertLess(time.time() - t0, 2.5, "list must return within the 2 s cold budget")
        # Warm path: a cached source is served at once.
        W._C["ak"] = {"t": time.time(), "ok_t": time.time(), "items": [it()], "err": None, "busy": False}
        W._rebuild()
        t0 = time.time()
        code, body, ct = W.handle_get("/api/water/data", {"limit": ["30"]})[:3]
        self.assertEqual(code, 200)
        self.assertEqual(len(body["items"]), 1)
        self.assertLess(time.time() - t0, 1.0)
        t0 = time.time()
        code, body, ct = W.handle_get("/api/water/map")[:3]
        self.assertEqual(code, 200)
        self.assertEqual(len(body["r"]), 1)
        self.assertLess(time.time() - t0, 1.0)

if __name__ == "__main__": unittest.main()
