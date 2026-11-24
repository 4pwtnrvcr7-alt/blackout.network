import os, sys, json, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import netcables as C, netmap
from datetime import datetime, timezone, timedelta

def at(h): return (datetime.now(timezone.utc) - timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ")
def nw(cable, ok=True): return dict(cable=cable, conflict={z["id"]: [] for z in C.ZONES}, ok=ok)

class Cables(unittest.TestCase):
    def test_geometry_is_licensed_and_light(self):
        p = os.path.join(os.path.dirname(C.__file__), "netmap_static", "cables.json")
        self.assertLess(os.path.getsize(p), 450_000)
        d = json.load(open(p)); self.assertIn("OpenStreetMap", d["credit"]); self.assertIn("NOAA", d["credit"]); self.assertIn("Wikidata", d["credit"])
        self.assertNotIn("telegeography", open(p).read().lower())   # CC BY-NC-SA: not used
        self.assertGreater(sum(1 for f in d["features"] if f["geometry"]["type"] == "LineString"), 200)   # landing-to-landing routes only
        self.assertEqual(netmap.handle_get("/api/netmap/cables.json")[0], 200)

    def test_quiet_news_all_working_and_no_zone_payload(self):
        r = C.status(nw([]), dict(countries=[]))
        self.assertEqual(r["cables"], {})
        self.assertNotIn("zones", r)
        self.assertNotIn("model", r)
        self.assertIn("no fault reports", r["basis"].lower())
        self.assertGreater(r["counts"]["working"], 200)
        self.assertEqual(r["counts"]["out"], 0)
        self.assertEqual(r["counts"]["degraded"], 0)
        self.assertEqual(r["counts"]["working"] + r["counts"]["out"] + r["counts"]["degraded"], r["counts"]["unique"])

    def test_named_cut_is_red_and_alias_matches(self):
        r = C.status(nw([dict(t="SEA-ME-WE 3 subsea cable cut disrupts internet in Asia", src="X", url="https://e.com/a", at=at(3))]))
        c = r["cables"]["SEA-ME-WE 3"]
        self.assertEqual(c["lv"], 2); self.assertEqual(c["status"], "Out of service")
        self.assertEqual(c["src"], "X"); self.assertTrue(c["url"].startswith("https://"))
        # SMW3 alias, and a fault (not a cut) is yellow
        r = C.status(nw([dict(t="SMW3 submarine cable fault under investigation, repair underway", src="Y", url="https://e.com/b", at=at(2))]))
        c = r["cables"]["SEA-ME-WE 3"]
        self.assertEqual(c["lv"], 1); self.assertEqual(c["status"], "Service interruption")

    def test_zone_damage_without_a_name_is_jeopardy_only_in_that_zone(self):
        r = C.status(nw([dict(t="Red Sea subsea cable cut disrupts internet in Asia", src="X", url="https://e.com/a", at=at(3))]))
        self.assertEqual(r["cables"].get("Saudi Arabia-Sudan-1 (SAS-1)", {}).get("lv"), 1)
        self.assertEqual(r["cables"]["Saudi Arabia-Sudan-1 (SAS-1)"]["status"], "In jeopardy")
        # Other routes that cross the Red Sea are also in jeopardy; Baltic cables stay working
        for nm in ("SEA-ME-WE 5", "AAE-1", "PEACE Cable", "2Africa"):
            self.assertEqual(r["cables"].get(nm, {}).get("lv"), 1, nm)
        self.assertNotIn("C-Lion 1", r["cables"])
        self.assertGreaterEqual(r["counts"]["degraded"], 5)
        self.assertEqual(r["counts"]["out"], 0)
        # stale news does not colour
        old = C.status(nw([dict(t="Red Sea subsea cable cut disrupts internet in Asia", src="X", url="https://e.com/a", at=at(24 * 20))]))
        self.assertEqual(old["cables"], {})
        # power cables are ignored
        power = C.status(nw([dict(t="Baltic power cable damaged near Gotland", src="X", url="https://e.com/a", at=at(3))]))
        self.assertEqual(power["cables"], {})

    def test_funding_story_is_not_jeopardy(self):
        r = C.status(nw([dict(t="EU Funds Baltic Subsea Cable Repair Capacity", src="SubTel Forum", url="https://subtelforum.com/eu-funds-baltic-subsea-cable-repair-capacity/", at=at(3))]))
        self.assertEqual(r["cables"], {})
        self.assertEqual(r["counts"]["degraded"], 0)

    def test_page_has_no_chokepoint_notes(self):
        html = netmap.page()
        self.assertNotIn("Chokepoint risk", html)
        self.assertNotIn("chokepoints", html.lower())
        js = open(os.path.join(os.path.dirname(C.__file__), "netmap_static", "net.js")).read()
        self.assertNotIn("seaz-fill", js)
        self.assertNotIn("Chokepoint risk", js)


    def test_major_cables_include_smw5_aae1_peace_2africa(self):
        p = os.path.join(os.path.dirname(C.__file__), "netmap_static", "cables.json")
        d = json.load(open(p))
        lines = [f for f in d["features"] if f["geometry"]["type"] == "LineString"]
        by = {}
        for f in lines:
            by.setdefault(f["properties"]["n"], []).append(f)
        for nm in ("SEA-ME-WE 5", "AAE-1", "PEACE Cable", "2Africa"):
            self.assertTrue(any(f["properties"].get("s") == "approx" for f in by[nm]), nm)
        # AAE-1 also keeps the OSM Hong Kong approach
        self.assertTrue(any(f["properties"].get("s") == "osm" for f in by["AAE-1"]))

    def test_smw5_fault_is_yellow_and_cut_is_red(self):
        r = C.status(nw([dict(t="SMW5 Cable Fault Threatened Pakistan's Internet Connectivity", src="Digital Pakistan", url="https://e.com/smw5", at=at(3))]))
        c = r["cables"]["SEA-ME-WE 5"]
        self.assertEqual(c["lv"], 1)
        self.assertEqual(c["status"], "Service interruption")
        r = C.status(nw([dict(t="SEA-ME-WE 5 subsea cable cut off Karachi, service out", src="X", url="https://e.com/cut", at=at(3))]))
        self.assertEqual(r["cables"]["SEA-ME-WE 5"]["lv"], 2)
        self.assertEqual(r["cables"]["SEA-ME-WE 5"]["status"], "Out of service")
        # Unrelated Karachi-landing systems are not painted by an SMW5-only headline
        self.assertNotIn("AAE-1", r["cables"])
        self.assertNotIn("PEACE Cable", r["cables"])

    def test_peace_cable_not_triggered_by_generic_peace(self):
        r = C.status(nw([dict(t="Peace talks continue after a power outage, no submarine cable involved", src="X", url="https://e.com/p", at=at(3))]))
        self.assertNotIn("PEACE Cable", r["cables"])

    def test_approx_route_is_labelled_in_popup(self):
        js = open(os.path.join(os.path.dirname(C.__file__), "netmap_static", "net.js")).read()
        self.assertIn("Approximate route", js)
        self.assertIn("sea-line-approx", js)

if __name__ == "__main__": unittest.main()
