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

if __name__ == "__main__":
    unittest.main()
