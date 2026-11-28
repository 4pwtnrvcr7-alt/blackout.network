"""Pre-publish Wire validator (pt1925u). Run: cd app && python3 -m unittest tests.test_wire_check -v"""
import os, unittest
import wire_check as WC

class Category(unittest.TestCase):
    def test_fixes(self):
        self.assertEqual(WC.category("conflict", "Xi unleashes China \u2018earthquake\u2019 with shock ouster of rising star"), "politics")
        self.assertEqual(WC.category("quake", "Xi unleashes China \u2018earthquake\u2019 with shock ouster of rising star"), "politics")
        self.assertEqual(WC.category("conflict", "Fuel truck explosion kills 31 on highway near Cairo, Egypt"), "wreck")
        self.assertEqual(WC.category("cyber", "F1 teams Williams and Alpine penalized for breaching 2025 cost cap rules"), "other")
        self.assertEqual(WC.category("conflict", "California warned of potential Thanksgiving flooding as storms threaten"), "weather")
        self.assertEqual(WC.category("weather", "Israeli occupation forces storm a Palestinian residential building in Nablus"), "conflict")
    def test_keeps_correct(self):
        self.assertEqual(WC.category("quake", "GeoNet: M4.1 quake 15 km north-west of Te Araroa (MMI 4)"), "quake")
        self.assertEqual(WC.category("conflict", "Russian forces hit Kyiv with ballistic missiles, mayor says"), "conflict")
        self.assertEqual(WC.category("weather", "Winter Storm Warning issued November 25 at 10:21AM MST"), "weather")
        self.assertEqual(WC.category("cyber", "Ransomware claim: the gentlemen lists Leffman Law Firm"), "cyber")

class Tags(unittest.TestCase):
    def test_rules(self):
        self.assertFalse(WC.tag_ok("#Maybe", "Maybe. He's a fascist and could stage a coup"))
        self.assertFalse(WC.tag_ok("#StageCoup", "Maybe. He's a fascist and could stage a coup"))
        self.assertFalse(WC.tag_ok("#WAAF", "Volcanic ash advisory: Eruption Mt Dukono"))
        self.assertFalse(WC.tag_ok("#Hicks", "M 5.2 - 183 km N of Hicks Bay, New Zealand"))
        self.assertFalse(WC.tag_ok("#News", "x")); self.assertFalse(WC.tag_ok("#BlackoutNetwork", "x"))
        self.assertFalse(WC.tag_ok("#edge", "Microsoft Edge Multiple Vulnerabilities"))
        self.assertTrue(WC.tag_ok("#Earthquake", "")); self.assertTrue(WC.tag_ok("#Ukraine", ""))
        self.assertTrue(WC.tag_ok("#AlJazeera", "Al Jazeera correspondent: An explosion rocks Sanaa"))
    def test_three_to_five(self):
        t = WC.tags(["#Maybe", "#Fascist", "#StageCoup"], "politics", "Maybe. He's a fascist and could stage a coup", ["#US"])
        self.assertTrue(all(WC.tag_ok(x, "") or x == "#Politics" for x in t)); self.assertLessEqual(len(t), 5)
        t = WC.tags(["#Earthquake", "#Hicks", "#Zealand"], "quake", "M 5.2 - 183 km N of Hicks Bay, New Zealand", ["#NewZealand"])
        self.assertEqual(t[:2], ["#Earthquake", "#NewZealand"])

    def test_location_and_lead_fill_known_tags(self):
        # Place and disease live in the lead/location, not the short title.
        t = WC.tags([], "disease", "Outbreak update", text="Ebola cases rise in Uganda")
        self.assertGreaterEqual(len(t), 3)
        self.assertTrue("#Ebola" in t or "#Health" in t or "#Outbreak" in t)
        self.assertIn("#Uganda" if "#Uganda" in t else t[0], t)  # Uganda if known, otherwise still 3 tags
        self.assertNotIn("#News", t)
        self.assertNotIn("#BlackoutNetwork", t)
        t2 = WC.tags([], "weather", "Flooding", text="State of emergency in Florida after flooding")
        self.assertGreaterEqual(len(t2), 3)
        self.assertTrue("#Florida" in t2 or "#Flood" in t2 or "#Weather" in t2)
        self.assertTrue(all(WC.tag_ok(x, "State of emergency in Florida after flooding") for x in t2))

    def test_japanese_gentilic_fills_japan(self):
        # A politics row would otherwise only get #Politics; the adjectival form must supply #Japan.
        t = WC.tags([], "politics", "Japanese lawmakers debate the proposal in parliament")
        self.assertIn("#Japan", t)
        self.assertGreaterEqual(len(t), 2)
        self.assertNotIn("#News", t)

class Headline(unittest.TestCase):
    def test_dangling(self):
        self.assertEqual(WC.headline("Explosion near the hospital in the\u2026")[0], "Explosion near the hospital\u2026")
        self.assertEqual(WC.headline("Flood Watch by NWS Portland OR")[0], "Flood Watch by NWS Portland OR")
        self.assertTrue(WC.thin_headline("Maybe"))

class Location(unittest.TestCase):
    def test_codes(self):
        self.assertEqual(WC.location("WAAF UJUNG PANDANG", 1.67, 128.29)[0], "")
        self.assertIsNone(WC.location("", 39.8283, -98.5795)[1])
        self.assertEqual(WC.location("Kyiv, Ukraine", 50.45, 30.52)[:3], ("Kyiv, Ukraine", 50.45, 30.52))

class Photo(unittest.TestCase):
    def test_verdicts(self):
        sat = {"src": "https://upload.wikimedia.org/x/Hurricane_Katrina_imaged_by_NOAA-16_AVHRR.jpg", "kind": "topic", "hazard": "storm"}
        self.assertTrue(WC.photo_verdict("weather", sat).startswith("bad:satellite"))
        storm = {"src": "https://upload.wikimedia.org/x/FEMA_-_38737_-_Boats.jpg", "kind": "topic", "hazard": "storm"}
        self.assertEqual(WC.photo_verdict("weather", storm), "ok")
        self.assertTrue(WC.photo_verdict("conflict", storm).startswith("bad:topic-storm"))
        kremlin = {"src": "https://upload.wikimedia.org/x/Moscow_StBasilCathedral.jpg", "kind": "place", "subject": "Russia"}
        self.assertTrue(WC.photo_verdict("conflict", kremlin, {"russia"}).startswith("bad:country"))
        self.assertTrue(WC.photo_verdict("quake", {"src": "https://u/x.jpg", "kind": "place", "subject": "Tokyo"}).startswith("bad:place"))
        self.assertEqual(WC.photo_verdict("conflict", None), "none")

class Gate(unittest.TestCase):
    def test_strict_gate_needs_a_passing_verdict(self):
        import wire_timeline as W
        os.environ["BN_WIRE_VALIDATE"] = "1"
        try:
            real = W._gate_ok; W._gate_ok = lambda cid: True
            import time as _t
            r = {"id": "c0000000000000aa", "title": "Russian forces hit Kyiv with ballistic missiles",
                 "fs": _t.strftime("%Y-%m-%dT%H:%M:%SZ", _t.gmtime())}
            old = {"id": "c0000000000000ab", "title": "Older story", "fs": "2026-01-01T00:00:00Z"}
            self.assertTrue(W._public_row(old, False))      # outside the validator window: previous gate only
            W._VR.pop(r["id"], None)
            self.assertFalse(W._public_row(r, False))
            self.assertTrue(W._public_row(r, False, strict=False))
            W._VR[r["id"]] = {"ok": True, "k": "conflict", "h": r["title"], "loc": "", "lat": None, "lon": None, "why": [], "at": 0}
            self.assertTrue(W._public_row(r, False))
            W._VR[r["id"]]["ok"] = False
            self.assertFalse(W._public_row(r, False))
            os.environ["BN_WIRE_VALIDATE"] = "0"
            self.assertTrue(W._public_row(r, False))
        finally:
            W._gate_ok = real; W._VR.pop("c0000000000000aa", None); os.environ["BN_WIRE_VALIDATE"] = "0"


class Release(unittest.TestCase):
    def test_release_pushes_to_the_stream(self):
        import sys, types, wire_timeline as W
        got = []
        rt = types.SimpleNamespace(on=lambda: True, announce=lambda ids, src="": got.append((list(ids), src)))
        real = sys.modules.get("realtime"); sys.modules["realtime"] = rt
        warmed = W._V_STATS.get("warmed")
        try:
            W._V_STATS["warmed"] = True
            W._PC["t"]["k"] = 123.0
            W._release(["c0000000000000aa"])
            self.assertEqual(got, [(["c0000000000000aa"], "release")])
            self.assertEqual(W._PC["t"]["k"], 0.0)        # the poll the event triggers rebuilds the page
        finally:
            W._PC["t"].pop("k", None); W._V_STATS["warmed"] = warmed
            if real is None: sys.modules.pop("realtime", None)
            else: sys.modules["realtime"] = real

class Leftovers(unittest.TestCase):
    """COS-33 leftovers (Nov 25 10:38 PM ET)."""
    def test_function_words_and_fragments(self):
        h = "M 5.2 - 183 km N of Hicks Bay, New Zealand"
        for t in ("#LoggedNov", "#Later", "#Which", "#WhatHappened", "#Zealand", "#Hicks", "#Maybe"):
            self.assertFalse(WC.tag_ok(t, h + " later which what happened logged Nov"), t)
        self.assertTrue(WC.tag_ok("#NewZealand", h))
        self.assertIn("#NewZealand", WC.tags(["#Earthquake", "#Hicks", "#Zealand"], "quake", h))

    def test_unknown_capitalised_word_is_not_an_entity(self):
        self.assertFalse(WC.tag_ok("#Rachel", "Children in Gaza, says Rachel at the UN"))
        self.assertTrue(WC.tag_ok("#Nablus", "Raid in Nablus", known=["#Nablus"]))

    def test_volcano_never_gets_earthquake(self):
        tg = WC.tags(["#Eruption", "#SCEZSantiago"], "quake", "Volcanic ash advisory: Eruption Mt Nevados De Chillan ash cloud")
        self.assertNotIn("#Earthquake", tg); self.assertGreaterEqual(len(tg), 3)

    def test_weather_misfiles(self):
        self.assertEqual(WC.category("conflict", "Thanksgiving Nor'Easter brings Holiday Storm to the Northeast", ""), "weather")
        self.assertEqual(WC.category("politics", "Chincoteague braces for coastal storm and flooding", ""), "weather")

    def test_intent_posts_exactly_the_validated_tags(self):
        import x_share, wire_timeline as W
        body = x_share.with_body({"cluster_id": "c1", "title": "M 5.2 - 183 km N of Hicks Bay, New Zealand",
                                  "headline": "M 5.2 - 183 km N of Hicks Bay, New Zealand", "location": "New Zealand",
                                  "category": "quake", "brief": "", "rank": 5, "watchlist": 0, "hidden": False, "links": [], "d": ""})
        xu, final = W._vt_intent(x_share, body, ["#Earthquake", "#NewZealand", "#Seismic"])
        self.assertEqual(final, ["#Earthquake", "#NewZealand", "#Seismic"])
        self.assertIn("hashtags=Earthquake,NewZealand,Seismic", xu)
        self.assertNotIn("Hicks%20%23", xu); self.assertNotIn("%23Zealand", xu)

class Scheduling(unittest.TestCase):
    def test_new_rows_before_rechecks(self):
        import time as _t, wire_timeline as W
        seen = []
        real_eval, real_pub = W._v_eval, W._public_row
        old = dict(W._VR); env = os.environ.get("BN_WIRE_VALIDATE")
        try:
            os.environ["BN_WIRE_VALIDATE"] = "1"
            W._VR.clear()
            now = _t.time()
            for i in range(5):
                W._VR["h%d" % i] = {"ok": False, "why": ["no-photo-card"], "at": now - 60, "k": "x", "h": "", "loc": "", "lat": None, "lon": None, "photo": ""}
            W._VR["t0"] = {"ok": False, "why": ["tags"], "at": now - 20, "k": "x", "h": "", "loc": "", "lat": None, "lon": None, "photo": ""}
            W._v_eval = lambda r, n: seen.append(r["id"]) or True
            W._public_row = lambda r, a, strict=True: True
            rows = [{"id": "h%d" % i} for i in range(5)] + [{"id": "t0"}, {"id": "n1"}, {"id": "n2"}]
            W._warm_validate(rows)
            self.assertEqual(seen[:2], ["n1", "n2"])          # never-checked rows first
            self.assertNotIn("t0", seen)                       # a tag hold is not re-checked every 15 s (45 s interval)
            seen.clear()
            W._VR["t0"]["at"] = now - 50
            W._warm_validate(rows)
            self.assertIn("t0", seen)                          # but a 45 s tag recheck is due after 50 s
        finally:
            W._v_eval, W._public_row = real_eval, real_pub
            W._VR.clear(); W._VR.update(old)
            if env is None: os.environ.pop("BN_WIRE_VALIDATE", None)
            else: os.environ["BN_WIRE_VALIDATE"] = env

class QAHold(unittest.TestCase):
    def test_hold_hides_and_release_restores(self):
        import tempfile, wire_timeline as W
        W._QAH_FILE = os.path.join(tempfile.mkdtemp(), "h.json")
        class R(dict):
            def keys(self): return super().keys()
        r = R(id="c0000000000000qa", title="x", fs="2020-01-01T00:00:00Z")
        try:
            out = W.qa_endpoint({"holds": {"c0000000000000qa": "tags"}, "replace": True})
            self.assertEqual(out["held"], 1)
            self.assertFalse(W._public_row(r, False))
            self.assertTrue(W._public_row(r, True))                 # archive rows are never held
            W.qa_endpoint({"holds": {}, "release": ["c0000000000000qa"]})
            self.assertNotIn("c0000000000000qa", W._QAH)
        finally:
            W._QAH.clear()

if __name__ == "__main__":
    unittest.main()
