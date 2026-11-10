"""Supplemental unrest/UK feeds: matching, headline clean-up, outlet allowlist, event dedupe, widget assembly.
Run: cd app && python3 -m unittest tests.test_unrest_feeds -v"""
import os, sys, time, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import unrest_feeds as U

class Match(unittest.TestCase):
    def test_metaphors_and_minor_ordinances_out(self):
        for t in ["Coup or restoration? Poland's constitutional court standoff divides Europe",
                  "Whose Coup?: Restoring the Legality of Poland's Constitutional Tribunal",
                  "How the new Charlotte curfew for minors could impact parents", "Charlotte youth curfew now in effect",
                  "Tina Peters pushes for President Trump to deploy federal law enforcement, as her attorney seeks an order akin to martial law",
                  "Beef industry quietly squashes part of its own science curriculum after ranchers protest",
                  "Trying to find true owners, Paris' Musee D'Orsay exhibits art looted by Nazis",
                  "Lincoln University Clashes with UCI", "Early Route du Rhum setback for Dorange as protest looms after crash",
                  "Who are Europe's Black Bloc protesters?", "Sri Lanka unions protest bills expanding police powers"]:
            self.assertFalse(U.is_unrest(t), t)
    def test_real_unrest_in(self):
        for t in ["France protests draw 146,000 as clashes erupt for fourth straight weekend",
                  "Police use water cannon to disperse masked protesters in Tirana",
                  "Security forces clash with settlers during evacuation of illegal outpost in West Bank",
                  "Soldiers seize state TV in attempted coup in Guinea-Bissau", "Police arrest 40 after youth curfew clashes in Charlotte",
                  "Daniel Noboa Imposes Fourth Curfew Through Nov. 10 In Ecuador's Five Provinces"]:
            self.assertTrue(U.is_unrest(t), t)
    def test_us_split(self):
        self.assertTrue(U.is_us("Protesters gather at Boyle Heights hospital after ICE agents bring person to ER"))
        self.assertTrue(U.is_us("Protest outside Elon Musk's Austin home"))
        self.assertFalse(U.is_us("France protests draw 146,000 as clashes erupt"))
    def test_uk(self):
        self.assertTrue(U.is_uk("Police and firefighters around UK gear up for Bonfire Night disorder"))
        self.assertTrue(U.is_uk("UK also affected by cyber-attack which hit European fridges"))
        for t in ["Labour expected to cut EV targets for UK's car industry despite MPs' protests",
                  "Riot breaks out at influencer boxing event attended by Tommy Robinson in Ireland",
                  "UK spy agency MI5 will not face contempt case for misleading evidence, court rules",
                  "Brexiteer Arron Banks accused of using private investigators to spy on rivals",
                  "Domestic violence survivor living 'in terror' after attacker released without tag"]:
            self.assertFalse(U.is_uk(t), t)

class Clean(unittest.TestCase):
    def test_tails(self):
        c = U.clean_headline
        self.assertEqual(c("Security forces clash with settlers during evacuation of illegal outpost in West Bank - nice to see the Israeli gvt taking action against th"),
                         "Security forces clash with settlers during evacuation of illegal outpost in West Bank")
        self.assertEqual(c("Daniel Noboa Imposes Fourth Curfew Through Nov. 10 In Ecuador's Five Provinces: 12 outlets compared"),
                         "Daniel Noboa Imposes Fourth Curfew Through Nov. 10 In Ecuador's Five Provinces")
        self.assertEqual(c("France protests: clashes erupt in Paris - Reuters"), "France protests: clashes erupt in Paris")
        self.assertEqual(c("Video. France: Up to 55,000 march in Lyon amid clashes and tear gas"), "France: Up to 55,000 march in Lyon amid clashes and tear gas")
        self.assertEqual(c("Riot police fire tear gas in Lima. Thousands march again on Sunday as anger grows"), "Riot police fire tear gas in Lima")
        self.assertIn("St. Paul", c("Don Lemon seeks dismissal of St. Paul church protest case - FOX 9"))
    def test_outlets(self):
        self.assertEqual(U.outlet("www.bbc.co.uk")[1], "BBC"); self.assertEqual(U.outlet("news.sky.com")[1], "Sky News")
        self.assertIsNone(U.outlet("reddit.com")[0]); self.assertIsNone(U.outlet("someblog.substack.com")[0])

class Events(unittest.TestCase):
    def test_dedupe_outlets_and_rank_gate(self):
        now = time.time()
        raw = [{"kind": "u", "title": "Police clash with protesters in Paris as anti-government rallies sweep France - AP", "url": "https://apnews.com/a", "domain": "apnews.com", "t": now - 3600, "direct": True},
               {"kind": "u", "title": "Clashes in Paris as anti-government rallies sweep France", "url": "https://bbc.co.uk/b", "domain": "www.bbc.co.uk", "t": now - 3000, "direct": True},
               {"kind": "u", "title": "Riot police fire tear gas at protesters in Nairobi", "url": "https://x.example/c", "domain": "randomblog.net", "t": now - 2000, "direct": True},
               {"kind": "u", "title": "Riot police fire tear gas at protesters in Lima", "url": "https://reuters.com/d", "domain": "reuters.com", "t": now - 1000, "direct": True}]
        ev = U.build_events(raw, "u", now)
        self.assertEqual(len(ev), 2)                     # blog dropped, AP+BBC merged
        paris = [e for e in ev if "Paris" in e["title"]][0]; lima = [e for e in ev if "Lima" in e["title"]][0]
        self.assertEqual(paris["n_outlets"], 2); self.assertGreaterEqual(paris["rank"], 4)
        self.assertLessEqual(lima["rank"], 3)            # single outlet never ranks 4+
    def test_combine_counts_and_links(self):
        now = time.time(); day = lambda ts: time.strftime("%Y-%m-%d", time.gmtime(ts - 5 * 3600))
        days = [day(now - i * 86400) for i in range(6, -1, -1)]
        wire = [{"title": "Thousands protest in Belgrade as police fire tear gas", "url": "/wire/" + "a" * 16, "t": now - 7200, "ut": now - 7200, "rank": 6, "n": 3, "loc": "", "us": False}]
        ext = [{"title": "Police fire tear gas at Belgrade protest of thousands", "url": "https://reuters.com/x", "t": now - 5000, "t1": now - 5000, "n_outlets": 3, "outlets": ["Reuters", "AP", "BBC"], "rank": 5, "us": False},
               {"title": "Protesters clash with National Guard in Portland", "url": "https://apnews.com/y", "t": now - 4000, "t1": now - 4000, "n_outlets": 2, "outlets": ["AP", "CNN"], "rank": 5, "us": True}]
        o = U.combine(wire, ext, days, day, now, "Civil unrest", split_us=True)
        self.assertEqual(o["n24"], 2); self.assertEqual(o["us"]["n24"], 1); self.assertEqual(o["world"]["n24"], 1)
        st = o["stories"][day(now - 4000)]
        bel = [s for s in st if "Belgrade" in s["title"]][0]
        self.assertTrue(bel["url"].startswith("/wire/")); self.assertNotIn("ext", bel); self.assertIn("The Wire + 3 outlets", bel["src"])
        por = [s for s in st if "Portland" in s["title"]][0]
        self.assertEqual(por["ext"], 1); self.assertTrue(por["url"].startswith("https://"))
        self.assertEqual(o["src"], "The Wire + world news feeds")
    def test_dead_source_never_raises(self):
        U._C["v"] = None
        old = U._load; U._load = lambda: None
        try: self.assertEqual(U.events("u"), [])   # empty cache: no network on the request path, no exception
        finally: U._load = old


    def test_is_food_matches_supply_and_ignores_recall_verb(self):
        self.assertTrue(U.is_food("From California Milk to Nara Cans: The Supply Chain Behind the Second Infant Formula Botulism Scare"))
        self.assertTrue(U.is_food("Egypt holds fertilizer and grain shipments after Red Sea disruption"))
        self.assertTrue(U.is_food("Tanker reports explosion while leaving Strait of Hormuz"))
        self.assertFalse(U.is_food("Breaking News British couple in Krakow recall seeing 250 people running after shooting"))
        self.assertTrue(U.is_food("East Coast dockworkers go on strike after contract talks stall"))
        self.assertTrue(U.is_food("East Coast dock workers go on strike after contract talks stall"))
        self.assertFalse(U.is_food("Docker security advisory (AV26-1123)"))


class Gdelt(unittest.TestCase):
    def test_parse_and_429_backoff(self):
        import json as J
        old = U._get
        try:
            U._gd.update(next=0, last=0)
            U._get = lambda url, timeout=12: J.dumps({"articles": [{"title": "Riot police fire tear gas at protesters in Nairobi", "url": "https://www.reuters.com/x",
                                                                 "domain": "reuters.com", "seendate": "20261108T120000Z", "sourcecountry": "Kenya"}]})
            a = U._gdelt("protest", "24h"); self.assertEqual(a[0]["domain"], "reuters.com"); self.assertTrue(a[0]["t"] > 0)
            U._gd["last"] = 0
            U._get = lambda url, timeout=12: "Please limit requests to one every 5 seconds"
            with self.assertRaises(RuntimeError): U._gdelt("protest", "24h")
            self.assertGreater(U._gd["next"], time.time() + 3000)   # backs off ~1 h
        finally: U._get = old; U._gd.update(next=0, last=0)

if __name__ == "__main__": unittest.main()
