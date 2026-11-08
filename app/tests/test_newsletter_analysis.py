"""Analyst brief: history labels, syndication, trajectory, guides, render. No network, no email sent.
Run: cd app && python3 -m unittest tests.test_newsletter_analysis -v
"""
import json, os, socket, sqlite3, sys, tempfile, unittest
from datetime import datetime, timedelta, timezone
TMP = tempfile.mkdtemp(prefix="nlanal_")
for k, v in {"NEWSLETTER_DB": "nl.db", "NEWSLETTER_SRC_DB": "src.db", "NEWSLETTER_CONFIG": "nl_config.json",
             "NEWSLETTER_OUTBOX": "outbox", "NEWSLETTER_ENV": "creds/newsletter.env", "NEWSLETTER_PASSFILE": "PASS.txt",
             "NEWSLETTER_LOG": "nl.log", "NEWSLETTER_BO_CONFIG": "bo.json"}.items():
    os.environ[k] = os.path.join(TMP, v)
os.environ["NEWSLETTER_NO_WORKER"] = "1"
os.makedirs(os.path.join(TMP, "creds"), exist_ok=True)
open(os.path.join(TMP, "PASS.txt"), "w").write("x\n")
open(os.path.join(TMP, "bo.json"), "w").write("{}")
open(os.path.join(TMP, "nl_config.json"), "w").write(json.dumps({"live_sending_approved": False, "base_url": "https://blackout.network"}))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def _blocked(*a, **k): raise RuntimeError("network access attempted during tests")
socket.socket.connect = _blocked
socket.create_connection = _blocked
import newsletter_analysis as NA
import newsletter as NL

UTC = timezone.utc
AT = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)  # 7:00 AM ET
BANNED = ("not proof", "could ", "might ", "perhaps", "likely to", "horrific", "evil")


def _item(**kw):
    base = {"cluster_id": "abc123abc123abcd", "title": "Event", "what": "Event.", "where": "Somewhere", "rank": 7,
            "score": 50, "category": "other", "section": "main", "links": [], "families": [], "eff": 1, "n_items": 1,
            "first_seen": AT - timedelta(hours=5), "tier": "Major"}
    base.update(kw)
    return base


def _alert(title, family, source, hours, official=0, url="https://example.com/r"):
    return {"title": title, "family": family, "source": source, "t": AT - timedelta(hours=hours),
            "official": official, "url": url, "location": "", "extra": {}}


class Rules(unittest.TestCase):
    def test_syndication_is_one_source(self):
        alerts = [
            _alert("Ship hit near Hormuz, 4 dead", "reuters.com", "Reuters", 10, url="https://example.com/r1"),
            _alert("Ship hit near Hormuz, 4 dead", "yahoo.com", "Yahoo", 9, url="https://example.com/y"),
            _alert("Ship hit near Hormuz, 4 dead", "aol.com", "AOL", 8, url="https://example.com/a"),
            _alert("UKMTO logs a separate strike near Hormuz", "bbc.com", "BBC", 7),
            _alert("UKMTO logs a separate strike near Hormuz", "bbc.co.uk", "BBC UK", 6),
        ]
        leaders, copies, _ = NA.collapse_sources(alerts)
        real = [a for a in leaders if not a.get("echo")]
        self.assertEqual(len(real), 2)  # Reuters + BBC; Yahoo/AOL and bbc.co.uk do not add a source
        self.assertGreaterEqual(copies, 2)
        level, real2, _e = NA.confidence_of(leaders, True)
        self.assertEqual(level, "Medium")
        self.assertEqual(len(real2), 2)

    def test_syndicator_only_is_not_confirmation(self):
        alerts = [_alert("Same wire headline about the talks", "yahoo.com", "Yahoo", h) for h in (5, 4, 3, 2)]
        leaders, _c, _u = NA.collapse_sources(alerts)
        self.assertTrue(all(a.get("echo") for a in leaders))
        level, real, echoes = NA.confidence_of(leaders, True)
        self.assertEqual(level, "Low")
        self.assertEqual(real, [])
        self.assertEqual(len(echoes), 1)

    def test_social_never_confirms(self):
        alerts = [_alert("Unique report one", "social", "social", 3), _alert("Totally different report two", "Reuters", "Reuters", 2)]
        leaders, _c, _u = NA.collapse_sources(alerts)
        self.assertEqual(len([a for a in leaders if not a.get("echo")]), 1)

    def test_missing_window_is_not_zero(self):
        alerts = [_alert("Flood warning for Utah", "NWS", "NWS", 2, official=1)]
        it = _item(title="Flood warning for Utah", category="natural disaster")
        out = NA.analyze_item(it, alerts, AT, AT - timedelta(days=1), True, None, None, "https://blackout.network")
        self.assertEqual(out["history"]["24h"], 1)
        self.assertEqual(out["history"]["7d"], "not enough history")
        self.assertEqual(out["history"]["30d"], "not enough history")
        blob = out["analysis"]
        self.assertIn("7d: not enough history", blob)
        self.assertIn("30d: not enough history", blob)
        self.assertNotIn("7d: 0", blob)
        self.assertNotIn("30d: 0", blob)
        self.assertEqual(out["spark"]["label"], "24h")
        self.assertIsNotNone(out["spark"]["png"])

    def test_empty_alert_table_is_not_zero(self):
        it = _item(title="Gov. Cox declares flooding emergency in Utah", category="political", n_items=21, eff=17,
                   families=["yahoo.com", "ksl.com"])
        out = NA.analyze_item(it, [], AT, AT - timedelta(days=8), False, None, None, "https://blackout.network")
        self.assertEqual(out["history"]["24h"], "not enough history")
        self.assertNotIn("24h: 0", out["analysis"])
        self.assertEqual(out["confidence"], "Low")
        self.assertIn("not enough history", out["confidence_line"])
        self.assertEqual(out["trajectory"], "Steady")

    def test_real_zero_when_scanner_was_watching(self):
        # Alerts exist, but none in the last 24h. 24h is a real zero. 7d is not.
        alerts = [_alert("Older quake note M6.2 near Chile", "USGS", "USGS", 24 * 3, official=1)]
        it = _item(title="Older quake note M6.2 near Chile", category="natural disaster")
        out = NA.analyze_item(it, alerts, AT, AT - timedelta(days=8), True, None, None, "https://blackout.network")
        self.assertEqual(out["history"]["24h"], 0)
        self.assertGreater(out["history"]["7d"], 0)
        self.assertEqual(out["history"]["30d"], "not enough history")

    def test_volume_does_not_set_trajectory(self):
        title = "Trump says the Hormuz strikes will not change the Iran talks"
        alerts = [_alert(title, "reuters.com", "Reuters", 20)]
        alerts += [_alert(title, "yahoo.com", "Yahoo", h) for h in (5, 4, 3, 2, 1)]
        it = _item(title=title, category="political", where="Iran")
        out = NA.analyze_item(it, alerts, AT, AT - timedelta(days=8), True, 7, None, "https://blackout.network")
        self.assertEqual(out["trajectory"], "Steady")
        self.assertIn("Volume alone does not set the danger reading", out["analysis"])
        self.assertIn("rose", out["analysis"])
        self.assertEqual(out["confidence"], "Low")
        self.assertIn("1 independent", out["confidence_line"])

    def test_deaths_set_rising_and_are_not_from_zero(self):
        alerts = [
            _alert("Yakima County reports 1 avian flu case", "cidrap.umn.edu", "CIDRAP", 24 * 5, url="https://example.com/c1"),
            _alert("Yakima health district confirms 1 death and 2 new cases", "yakimaherald.com", "Yakima Herald", 4, url="https://example.com/y1"),
        ]
        it = _item(title="Yakima County reports 2 more avian flu cases, 1 death", category="disease")
        out = NA.analyze_item(it, alerts, AT, AT - timedelta(days=8), True, None, None, "https://blackout.network")
        self.assertEqual(out["trajectory"], "Rising")
        self.assertNotIn("from 0", out["analysis"])
        self.assertNotIn("from 0", out["outlook"])
        self.assertTrue(any(a["name"] == "Prepare › First aid" for a in out["actions"]))

    def test_pager_downgrade_is_easing(self):
        alerts = [
            _alert("M7.1 earthquake near Antofagasta, Chile, PAGER orange", "USGS", "USGS", 36, official=1, url="https://example.com/u1"),
            _alert("M7.1 earthquake near Antofagasta, Chile, PAGER yellow", "USGS", "USGS", 3, official=1, url="https://example.com/u2"),
        ]
        it = _item(title="M7.1 earthquake near Antofagasta, Chile, PAGER yellow", category="natural disaster", where="Antofagasta, Chile")
        out = NA.analyze_item(it, alerts, AT, AT - timedelta(days=8), True, None, None, "https://blackout.network")
        self.assertEqual(out["trajectory"], "Easing")
        self.assertIn("PAGER moved from orange to yellow", out["outlook"])

    def test_water_guide_named(self):
        alerts = [
            _alert("Flood warning for Washington County, Utah", "NWS", "NWS", 30, official=1, url="https://example.com/n1"),
            _alert("Flood warning extended to Iron County and Kane County, Utah", "NWS", "NWS", 8, official=1, url="https://example.com/n2"),
        ]
        it = _item(title="Gov. Cox declares state of emergency after repeat flooding in Southern Utah", category="political", where="Southern Utah")
        out = NA.analyze_item(it, alerts, AT, AT - timedelta(days=8), True, None, None, "https://blackout.network")
        self.assertEqual(out["trajectory"], "Rising")
        self.assertIn("Iron County", out["outlook"])
        names = [a["name"] for a in out["actions"]]
        self.assertIn("Prepare › Water", names)
        self.assertTrue(any(a["url"].endswith("/ready#water") for a in out["actions"]))
        self.assertIn("one gallon", out["actions"][0]["action"])

    def test_generated_lines_stay_plain(self):
        alerts = [_alert("Iran missile strike on a ship near the Strait of Hormuz kills 4", "reuters.com", "Reuters", 20, url="https://example.com/r"),
                  _alert("Iran missile strike on a ship near the Strait of Hormuz kills 18", "reuters.com", "Reuters", 6, url="https://example.com/r2")]
        it = _item(title="Iran missile strike near Hormuz kills 18", category="war/conflict", where="Strait of Hormuz", rank=8)
        out = NA.analyze_item(it, alerts, AT, AT - timedelta(days=8), True, 6, None, "https://blackout.network")
        blob = " ".join([out["what"], out["analysis"], out["outlook"], out["confidence_line"]] + [a["action"] for a in out["actions"]])
        for bad in BANNED:
            self.assertNotIn(bad, blob.lower())
        self.assertTrue(out["analysis"].startswith("Analysis:"))
        self.assertIn("https://example.com/r2", [s["url"] for s in out["sources"]])
        self.assertEqual(out["trajectory"], "Rising")
        self.assertIn("from 6", out["analysis"])  # prior rank in our ledger, a real stored number


class Render(unittest.TestCase):
    def setUp(self):
        NA.write_demo_db(NL.P["src"], AT)
        k = NL.db()
        k.execute("DELETE FROM sent_items")
        k.execute("""INSERT INTO sent_items(send_id,subscriber_id,cluster_id,title_norm,section,sent_at,rank,kind)
                     VALUES(0,0,'a11ce00000000001','iran hormuz','main',?,6,'new')""",
                  ((AT - timedelta(hours=26)).strftime("%Y-%m-%dT%H:%M:%SZ"),))
        k.commit(); k.close()

    def _issue(self):
        return NL.build_issue({"id": None, "frequency": "twice", "interests": '["all"]'}, at=AT, since=AT - timedelta(hours=24), slot="morning")

    def test_morning_brief_has_analysis_and_keeps_story_links(self):
        issue = self._issue()
        an = issue["analysis"]
        self.assertIsNotNone(an)
        self.assertEqual(len(an["items"]), 5)
        by = {it["cluster_id"]: it for it in an["items"]}
        self.assertEqual(by["a11ce00000000001"]["trajectory"], "Rising")
        self.assertEqual(by["a11ce00000000001"]["confidence"], "High")
        self.assertIn("3 independent", by["a11ce00000000001"]["confidence_line"])
        self.assertEqual(by["a11ce00000000002"]["trajectory"], "Steady")
        self.assertEqual(by["a11ce00000000002"]["confidence"], "Low")
        self.assertEqual(by["a11ce00000000003"]["trajectory"], "Rising")
        self.assertTrue(any(a["name"] == "Prepare › Water" for a in by["a11ce00000000003"]["actions"]))
        self.assertEqual(by["a11ce00000000005"]["trajectory"], "Easing")
        self.assertIn("M6.8", by["a11ce00000000005"]["analysis"])
        for it in an["items"]:
            self.assertEqual(it["history"]["30d"], "not enough history")
            self.assertNotEqual(it["history"]["7d"], "not enough history")
            self.assertIsNotNone(it["spark"]["png"])
            self.assertNotIn("from 0", it["analysis"])
        names = [p["name"] for p in an["patterns"]]
        self.assertIn("Iran", names)
        self.assertIn("Donald Trump", names)
        self.assertEqual(an["cost"]["usd"], 0.0)
        self.assertEqual(an["cost"]["llm_calls"], 0)
        links = {"unsubscribe": "https://blackout.network/newsletter", "manage": "https://blackout.network/newsletter",
                 "categories": "https://blackout.network/newsletter", "sources": "https://blackout.network/sources",
                 "scoring": "https://blackout.network/scoring", "site": "https://blackout.network/#wire", "_row": None}
        _subj, html, text = NL.render(issue, links)
        self.assertIn("Analyst brief", html)
        self.assertIn("Prepare › Water", html)
        self.assertIn("#water", html)
        self.assertIn("WHAT HAPPENED", html)
        self.assertIn("TRAJECTORY", html)
        self.assertGreaterEqual(html.count("Full story"), 5)
        self.assertIn("data:image/png;base64,", html)
        self.assertIn("Patterns", html)
        self.assertIn("not enough history", html)
        self.assertNotIn("30d: 0", html)
        self.assertNotIn("Confirmed by 8 independent", html)
        self.assertIn("after collapsing repeated headlines", html)
        self.assertNotIn("not proof", html.lower())
        self.assertIn("ANALYST BRIEF", text)
        self.assertIn("Prepare › Water", text)
        self.assertIn("https://blackout.network/wire/a11ce00000000003", text)
        # sender mode untouched: preview, and render did not write an outbox message
        self.assertEqual((NL.env().get("NEWSLETTER_SENDER") or "preview"), "preview")
        self.assertFalse(NL.cfg().get("live_sending_approved"))

    def test_quiet_brief_invents_nothing(self):
        c = sqlite3.connect(NL.P["src"])
        c.execute("DELETE FROM clusters"); c.execute("DELETE FROM alerts"); c.commit(); c.close()
        issue = self._issue()
        self.assertTrue(issue["quiet"])
        self.assertEqual(issue["analysis"]["items"], [])
        links = {"unsubscribe": "https://blackout.network/newsletter", "manage": "https://blackout.network/newsletter",
                 "scoring": "https://blackout.network/scoring", "site": "https://blackout.network/#wire", "_row": None}
        _s, html, text = NL.render(issue, links)
        self.assertIn("No confirmed high-severity events", html)
        self.assertNotIn("WHAT HAPPENED", html)
        self.assertNotIn("Analyst brief", html)
        self.assertNotIn("WHAT HAPPENED", text)

    def test_mime_uses_cid_and_does_not_send(self):
        issue = self._issue()
        links = {"unsubscribe": "https://blackout.network/newsletter", "manage": "https://blackout.network/newsletter",
                 "scoring": "https://blackout.network/scoring", "site": "https://blackout.network/#wire", "_row": None}
        subj, html, text = NL.render(issue, links)
        msg = NL.build_mime("preview@outbox.invalid", subj, html, text, None, "issue")
        raw = msg.as_string()
        self.assertIn("cid:bn-spark-1@blackout.network", raw)
        self.assertNotIn("data:image/png;base64,", raw)
        self.assertIn("Content-ID: <bn-spark-1@blackout.network>", raw)
        self.assertNotIn("RESEND_API_KEY", raw)
        self.assertNotIn("@mail.test", raw)


if __name__ == "__main__":
    unittest.main()
