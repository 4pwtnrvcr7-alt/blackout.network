"""Analyst brief: history labels, syndication, trajectory, guides, render. No network, no email sent.
Run: cd app && python3 -m unittest tests.test_newsletter_analysis -v
"""
import json, os, re, socket, sqlite3, sys, tempfile, unittest
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


class Bugs(unittest.TestCase):
    def test_quake_is_not_war(self):
        title = "M6.1 earthquake strikes off the coast of Japan"
        self.assertEqual(NL.display_category(title, "", "war/conflict"), "natural disaster")
        row = {"title": title, "brief": "WHAT: " + title + ". WHERE: location not reported.", "rank": 6, "category": "war/conflict",
               "mentions_3h": 0, "rising": 0}
        why = NL.why_it_matters(row, category="natural disaster")
        self.assertNotIn("shipping", why.lower())
        self.assertIn("power and water", why)

    def test_why_lines_are_not_identical(self):
        row = {"brief": "", "rank": 6, "category": "war/conflict", "mentions_3h": 0, "rising": 0}
        a = NL.why_it_matters({**row, "title": "Iran's IRGC claims a 2,000 km ballistic missile range limit has been lifted", "location": "Iran"}, category="war/conflict")
        b = NL.why_it_matters({**row, "title": "Strikes hit Kyiv's Northern Bridge with ballistic missiles", "location": "Kyiv"}, category="war/conflict")
        self.assertNotEqual(a, b)
        self.assertIn("IRGC", a)
        self.assertIn("Kyiv", b)
        self.assertNotIn("Armed conflict can escalate fast", a)
        self.assertNotIn("Armed conflict can escalate fast", b)

    def test_summary_does_not_repeat_the_title(self):
        title = "M6.1 earthquake strikes off the coast of Japan"
        self.assertEqual(NL.summary_text(title, title), "")
        self.assertEqual(NL.summary_text(title, title + ". " + title), "")
        self.assertIn("depth", NL.summary_text(title, title + ". The USGS page lists a depth of 40 km."))
        glued = "Magnitude 6.1 Earthquake Strikes Off Japan's Eastern Coast Near Tokyo A magnitude 6.1 earthquake struck off Japan's eastern coast on November 6, 2026, according to the Japan Meteorological Agency"
        self.assertEqual(NL.tighten_title(glued), "Magnitude 6.1 Earthquake Strikes Off Japan's Eastern Coast Near Tokyo")
        self.assertNotIn("November 6", NL.summary_text(NL.tighten_title(glued), glued))

    def test_headline_place_is_approximate(self):
        hit = NL._place_from_headline("M6.1 earthquake strikes off the coast of Japan", "")
        self.assertIsNotNone(hit)
        self.assertIn("Japan", hit["place"])
        row = {"cluster_id": "ab" * 8, "title": "Explosion reported in Riyadh overnight", "brief": "WHAT: Explosion reported in Riyadh overnight. WHERE: location not reported.",
               "rank": 7, "score": 50, "category": "war/conflict", "eff_families": 2, "families": "[]", "links": "[]",
               "n_items": 2, "lat": None, "lon": None, "location": "", "event_time": None, "first_seen": "2026-11-08T10:00:00Z",
               "mentions_3h": 0, "rising": 0, "watchlist": 0}
        it = NL.item_of(row, "main", 0)
        self.assertTrue(it["approx"])
        self.assertIn("Riyadh", it["where"])
        self.assertIn("approximate", NL._where(it).lower())
        self.assertIsNotNone(it["lat"])

    def test_old_story_does_not_lead(self):
        NA.write_demo_db(NL.P["src"], AT)
        c = sqlite3.connect(NL.P["src"])
        iso = "2026-11-05T12:00:00Z"
        c.execute("""INSERT INTO clusters(cluster_id,title,category,location,lat,lon,event_time,first_seen,updated,score,confidence,
                     n_items,n_families,families,links,watchlist,brief,high_at,rising,mentions_3h,eff_families,rank)
                     VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  ("a11ce00000000009", "Paraguay: President under investigation for bank failure", "financial", "Paraguay",
                   None, None, iso, iso, "2026-11-08T11:00:00Z", 50, "Medium", 4, 4, "[]", "[]", 0,
                   "WHAT: Paraguay: President under investigation for bank failure. WHERE: Paraguay.", "2026-11-08T11:00:00Z", 0, 1, 4, 7))
        c.commit(); c.close()
        issue = NL.build_issue({"id": None, "frequency": "twice", "interests": '["all"]'}, at=AT, since=AT - timedelta(hours=24), slot="morning")
        lead = [it["cluster_id"] for sec in ("main", "politics", "notable") for it in issue.get(sec) or []]
        self.assertNotIn("a11ce00000000009", lead)
        self.assertIn("a11ce00000000009", [it["cluster_id"] for it in issue.get("developing") or []])


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
        self.assertGreaterEqual(html.count("WHAT HAPPENED"), len(an["items"]))
        self.assertGreaterEqual(html.count("WHAT TO DO"), len(an["items"]))
        self.assertIn("Prepare › Water", html)
        self.assertIn("#water", html)
        self.assertIn("WHAT HAPPENED", html)
        self.assertIn("TRAJECTORY", html)
        self.assertGreaterEqual(html.count("Full story"), 5)
        self.assertIn("data:image/png;base64,", html)
        self.assertIn("Patterns", html)
        self.assertNotIn("not enough history", html)
        self.assertNotIn("30d: 0", html)
        self.assertNotIn("Confirmed by 8 independent", html)
        self.assertTrue(any("after collapsing repeated headlines" in (it.get("card_confidence") or "") for it in an["items"]))
        self.assertNotIn("not proof", html.lower())
        self.assertIn("ANALYST BRIEF", text)
        self.assertGreaterEqual(text.count("WHAT HAPPENED"), len(an["items"]))
        visible = re.sub(r'<div style="display:none.*?</div>', " ", html, count=1)
        low = re.sub(r"<[^>]+>", " ", visible).lower()
        for bad in ("is named.", "for this missile", "the headline states", "the report says", "the place named is"):
            self.assertNotIn(bad, low)
        blocks = re.split(r"WHAT HAPPENED", visible)[1:]
        shared_actions = {a[0].rstrip(".") for a in NA._FALLBACK_DO.values()}
        seen = {}
        dups = []
        for i, block in enumerate(blocks):
            plain = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", block))
            for sent in re.findall(r"[A-Za-z][^.!?]{40,}[.!?]", plain):
                s = sent.strip()
                if any(act in s for act in shared_actions):
                    continue
                if s in seen and seen[s] != i and s not in dups:
                    dups.append(s)
                seen.setdefault(s, i)
        self.assertEqual(dups, [], dups[:3])
        self.assertIn("Prepare › Water", text)
        self.assertIn("https://blackout.network/wire/a11ce00000000003", text)
        # sender mode untouched: preview, and render did not write an outbox message
        self.assertLess(len(html.encode()), 1_500_000)
        self.assertIn("Story map", html)
        self.assertIn("Section Top threats", html)
        self.assertIn("Signal over noise", html)
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
        subj, html, text = NL.render(issue, links)
        self.assertIn("Here's what matters right now", subj)
        self.assertIn("Here's what matters right now", html)
        self.assertIn("Here's what matters right now", text)
        self.assertNotIn("WHAT HAPPENED", html)
        self.assertNotIn("Analyst brief", html)
        self.assertNotIn("WHAT HAPPENED", text)
        _assert_no_empty_framing(self, subj, html, text)
        self.assertNotIn("Live cluster snapshot", html)
        self.assertIn('content="dark"', html)
        self.assertNotIn('content="dark light"', html)
        self.assertIn('bgcolor="#0B0C0F"', html)
        self.assertNotIn("background:#FFFFFF", html)
        self.assertNotIn("background:#F5F5F7", html)

    def test_preview_without_alert_history_labels_loading(self):
        c = sqlite3.connect(NL.P["src"])
        c.execute("DELETE FROM alerts"); c.commit(); c.close()
        issue = self._issue()
        links = {"unsubscribe": "https://blackout.network/newsletter", "manage": "https://blackout.network/newsletter",
                 "scoring": "https://blackout.network/scoring", "site": "https://blackout.network/#wire", "_row": None}
        _s, html, text = NL.render(issue, links)
        self.assertIn("trend data loading", html)
        self.assertNotIn("Live cluster snapshot", html)
        self.assertIn("trend data loading", text)

    def test_mime_uses_cid_and_does_not_send(self):
        issue = self._issue()
        links = {"unsubscribe": "https://blackout.network/newsletter", "manage": "https://blackout.network/newsletter",
                 "scoring": "https://blackout.network/scoring", "site": "https://blackout.network/#wire", "_row": None}
        subj, html, text = NL.render(issue, links)
        msg = NL.build_mime("preview@outbox.invalid", subj, html, text, None, "issue")
        raw = msg.as_string()
        unfolded = raw.replace("=\n", "")
        self.assertIn("cid:bn-img-1@blackout.network", unfolded)
        self.assertNotIn("data:image/png;base64,", raw)
        self.assertIn("Content-ID: <bn-img-1@blackout.network>", raw)
        self.assertNotIn("RESEND_API_KEY", raw)
        self.assertNotIn("@mail.test", raw)


_EMPTY = ("no new rank-", "nothing new to report", "no confirmed high-severity", "nothing to report", "all quiet", "no rank-")

def _assert_no_empty_framing(case, *blobs):
    for blob in blobs:
        low = (blob or "").lower()
        for phrase in _EMPTY:
            case.assertNotIn(phrase, low)


class Notes(unittest.TestCase):
    def setUp(self):
        NA.write_demo_db(NL.P["src"], AT)
        self.notes = os.path.join(TMP, "newsletter_analysis.json")
        os.environ["NEWSLETTER_ANALYSIS_JSON"] = self.notes

    def tearDown(self):
        os.environ.pop("NEWSLETTER_ANALYSIS_JSON", None)
        if os.path.exists(self.notes): os.remove(self.notes)

    def _write(self, generated, items, lead="", patterns=None):
        with open(self.notes, "w") as f:
            json.dump({"generated_at": generated, "items": items, "lead": lead, "patterns": patterns or []}, f)

    def _issue(self):
        return NL.build_issue({"id": None, "frequency": "twice", "interests": '["all"]'}, at=AT, since=AT - timedelta(hours=24), slot="morning")

    def test_note_overlays_exact_text_and_badge(self):
        self._write(AT.strftime("%Y-%m-%dT%H:%M:%SZ"), {
            "a11ce00000000001": {
                "what_happened": "Eighteen people were killed near Hormuz.",
                "analysis": "The death toll in the later reports is higher than the first count.",
                "trajectory": "UPTREND",
                "outlook": "The danger stays elevated for the next day.",
                "confidence": "High",
                "confidence_why": "Three outlets reported it independently.",
                "what_to_do": "Agree on one out-of-area contact tonight.",
                "guide": "Prepare > Family plan",
                "why_it_matters": "A higher death toll at Hormuz is the change that matters.",
            }
        }, lead="Hormuz is the story to read first.", patterns=["Hormuz appears in more than one report."])
        issue = self._issue()
        self.assertEqual(issue["notes_lead"], "Hormuz is the story to read first.")
        self.assertIn("Hormuz is the story to read first.", issue["bluf"])
        hit = next(it for it in issue["main"] if it["cluster_id"] == "a11ce00000000001")
        self.assertTrue(hit["analyst"]["from_note"])
        self.assertEqual(hit["analyst"]["what"], "Eighteen people were killed near Hormuz.")
        self.assertEqual(hit["trajectory"], "Rising")
        links = {"unsubscribe": "https://blackout.network/newsletter", "manage": "https://blackout.network/newsletter",
                 "scoring": "https://blackout.network/scoring", "site": "https://blackout.network/#wire", "_row": None}
        _s, html, _t = NL.render(issue, links)
        self.assertIn("Eighteen people were killed near Hormuz.", html)
        self.assertIn("Agree on one out-of-area contact tonight.", html)
        self.assertIn("Hormuz appears in more than one report.", html)
        self.assertIn("UPTREND", html)
        self.assertNotIn("is named.", html.lower())

    def test_stale_notes_are_ignored(self):
        self._write((AT - timedelta(hours=19)).strftime("%Y-%m-%dT%H:%M:%SZ"), {
            "a11ce00000000001": {"what_happened": "STALE NOTE SHOULD NOT APPEAR", "analysis": "old",
                                 "trajectory": "STEADY", "outlook": "old", "confidence": "Low",
                                 "confidence_why": "old", "what_to_do": "old", "guide": "Prepare > Water",
                                 "why_it_matters": "old"}
        })
        issue = self._issue()
        self.assertNotIn("notes_lead", issue)
        html_bits = " ".join((it.get("analyst") or {}).get("what") or "" for sec in ("main", "politics", "notable") for it in issue.get(sec) or [])
        self.assertNotIn("STALE NOTE", html_bits)

    def test_headline_match_when_ids_differ(self):
        self._write(AT.strftime("%Y-%m-%dT%H:%M:%SZ"), {
            "different-id": {
                "headline": "Iran missile strike near the Strait of Hormuz kills 18, Trump says he is watching",
                "what_happened": "Matched by headline, not by id.",
                "analysis": "Same event, new cluster id.",
                "trajectory": "STEADY", "outlook": "Holds.", "confidence": "Medium",
                "confidence_why": "Two outlets.", "what_to_do": "Pick a meeting place.",
                "guide": "Prepare > Family plan", "why_it_matters": "The toll is the fact.",
            }
        })
        issue = self._issue()
        hit = next(it for it in issue["main"] if it["cluster_id"] == "a11ce00000000001")
        self.assertEqual(hit["analyst"]["what"], "Matched by headline, not by id.")

    def test_fallback_is_short(self):
        os.environ.pop("NEWSLETTER_ANALYSIS_JSON", None)
        if os.path.exists(self.notes): os.remove(self.notes)
        issue = self._issue()
        links = {"unsubscribe": "https://blackout.network/newsletter", "manage": "https://blackout.network/newsletter",
                 "scoring": "https://blackout.network/scoring", "site": "https://blackout.network/#wire", "_row": None}
        _s, html, _t = NL.render(issue, links)
        blocks = re.split(r"WHAT HAPPENED", html)[1:]
        self.assertGreaterEqual(len(blocks), 1)
        for block in blocks:
            self.assertLessEqual(block.lower().count("not enough history"), 1)
            self.assertNotIn("for the report", block.lower())
            self.assertNotIn("is named", block.lower())
        self.assertIn("Prepare ›", html)
        import render_rules
        self.assertIn("newsletter_analysis.json", render_rules.SYNC_JSON)

    def test_noted_cluster_is_included_and_sources_link_to_ready(self):
        c = sqlite3.connect(NL.P["src"])
        iso = (AT - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
        c.execute("""INSERT INTO clusters(cluster_id,title,category,location,lat,lon,event_time,first_seen,updated,score,confidence,
                     n_items,n_families,families,links,watchlist,brief,high_at,rising,mentions_3h,eff_families,rank)
                     VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  ("a6272da62f181f19", "Local bakery opens on Main Street", "other", "Town", None, None, iso, iso, iso,
                   40, "Low", 2, 2, "[]", "[]", 0, "WHAT: Local bakery opens on Main Street.", iso, 0, 0, 2, 6))
        c.commit(); c.close()
        self._write(AT.strftime("%Y-%m-%dT%H:%M:%SZ"), {
            "a6272da62f181f19": {
                "headline": "House GOP leaders brace for enough defections to impeach Defense Secretary Hegseth",
                "what_happened": "House leaders expect enough votes to impeach the defense secretary.",
                "analysis": "The vote would test Congress against the cabinet.",
                "trajectory": "UPTREND", "outlook": "A floor vote is likely within days.",
                "confidence": "Medium", "confidence_why": "Axios reporting, not a published whip count.",
                "what_to_do": "Read the resolution text before the vote.",
                "guide": "Prepare › Home kit",
                "why_it_matters": "The vote tests whether Congress can rein in a cabinet officer.",
                "sources": ["https://www.axios.com/2026/11/08/pete-hegseth-impeachment-house-republicans-massie"],
            }
        })
        issue = self._issue()
        ids = [it["cluster_id"] for sec in ("main", "politics", "notable") for it in issue.get(sec) or []]
        self.assertIn("a6272da62f181f19", ids)
        hit = next(it for sec in ("main", "politics", "notable") for it in issue.get(sec) or [] if it["cluster_id"] == "a6272da62f181f19")
        self.assertEqual(hit["analyst"]["what"], "House leaders expect enough votes to impeach the defense secretary.")
        self.assertTrue(hit["analyst"]["guide_url"].endswith("/ready#home-kit"))
        self.assertNotIn("/prepare", hit["analyst"]["guide_url"])
        links = {"unsubscribe": "https://blackout.network/newsletter", "manage": "https://blackout.network/newsletter",
                 "scoring": "https://blackout.network/scoring", "site": "https://blackout.network/#wire", "_row": None}
        _s, html, _t = NL.render(issue, links)
        self.assertIn("https://www.axios.com/2026/11/08/pete-hegseth-impeachment-house-republicans-massie", html)
        self.assertIn("Prepare › Home kit", html)
        self.assertIn("#home-kit", html)
        self.assertNotIn("/prepare", html)

    def test_older_noted_cluster_is_a_full_card(self):
        c = sqlite3.connect(NL.P["src"])
        old = (AT - timedelta(hours=40)).strftime("%Y-%m-%dT%H:%M:%SZ")
        seen = (AT - timedelta(hours=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        c.execute("""INSERT INTO clusters(cluster_id,title,category,location,lat,lon,event_time,first_seen,updated,score,confidence,
                     n_items,n_families,families,links,watchlist,brief,high_at,rising,mentions_3h,eff_families,rank)
                     VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  ("98fdd3f9a50d90a8", "Russian missiles hit Kyiv bridge", "war/conflict", "Kyiv", None, None, old, seen, seen,
                   80, "High", 6, 4, "[]", "[]", 0, "WHAT: Russian missiles hit Kyiv bridge.", seen, 0, 0, 4, 7))
        c.commit(); c.close()
        self._write(AT.strftime("%Y-%m-%dT%H:%M:%SZ"), {
            "98fdd3f9a50d90a8": {
                "headline": "Russian ballistic missiles damage Kyiv's Northern Bridge",
                "what_happened": "Overnight, Russia fired 36 ballistic missiles at Kyiv and hit the Northern Bridge.",
                "analysis": "The campaign is aimed at the lines that feed the capital.",
                "trajectory": "UPTREND", "outlook": "More strikes on power and transport are likely within 72 hours.",
                "confidence": "High", "confidence_why": "Kyiv city government and the Ukrainian Air Force.",
                "what_to_do": "Charge a power bank and keep a battery radio within reach.",
                "guide": "Prepare › Power outage",
                "why_it_matters": "A capital's power and bridges are the systems people rely on.",
            }
        })
        issue = self._issue()
        self.assertTrue(any(it["cluster_id"] == "98fdd3f9a50d90a8" for it in issue["main"]))
        self.assertFalse(any(it["cluster_id"] == "98fdd3f9a50d90a8" for it in issue.get("developing") or []))
        links = {"unsubscribe": "https://blackout.network/newsletter", "manage": "https://blackout.network/newsletter",
                 "scoring": "https://blackout.network/scoring", "site": "https://blackout.network/#wire", "_row": None}
        _s, html, _t = NL.render(issue, links)
        self.assertIn("Overnight, Russia fired 36 ballistic missiles at Kyiv and hit the Northern Bridge.", html)
        self.assertIn("#power", html)


class Topics(unittest.TestCase):
    def setUp(self):
        NA.write_demo_db(NL.P["src"], AT)

    def _add(self, cid, title, cat, rank, eff, hours=4, loc=""):
        c = sqlite3.connect(NL.P["src"])
        iso = (AT - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
        c.execute("""INSERT INTO clusters(cluster_id,title,category,location,lat,lon,event_time,first_seen,updated,score,confidence,
                     n_items,n_families,families,links,watchlist,brief,high_at,rising,mentions_3h,eff_families,rank)
                     VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (cid, title, cat, loc, None, None, iso, iso, iso, 40, "Medium", eff, eff, "[]", "[]", 0,
                   f"WHAT: {title}. WHERE: {loc}.", iso, 0, 1, eff, rank))
        c.commit(); c.close()

    def _issue(self):
        return NL.build_issue({"id": None, "frequency": "twice", "interests": '["all"]'}, at=AT, since=AT - timedelta(hours=24), slot="morning")

    def test_topic_gate(self):
        self.assertFalse(NL.topic_on_brief("M6.1 earthquake strikes off the coast of Japan", "", "natural disaster", "Japan", 6))
        self.assertFalse(NL.topic_on_brief(
            "Magnitude 6.1 Earthquake Strikes Off Japan's Eastern Coast Near Tokyo. No tsunami expected, the U.S. Geological Survey said.",
            "", "war/conflict", "", 6))
        self.assertTrue(NL.topic_on_brief("M7.1 earthquake near Antofagasta, Chile", "", "natural disaster", "Chile", 7))
        self.assertTrue(NL.topic_on_brief("M5.6 earthquake near Los Angeles", "", "natural disaster", "Los Angeles, California", 6))
        self.assertFalse(NL.topic_on_brief("M5.4 earthquake near Los Angeles", "", "natural disaster", "Los Angeles", 6))
        self.assertFalse(NL.topic_on_brief("M5.6 earthquake off the coast of California", "", "natural disaster", "California", 6))
        self.assertTrue(NL.topic_on_brief("M6.2 earthquake in Chile triggers a tsunami warning", "", "natural disaster", "Chile", 6))
        self.assertFalse(NL.topic_on_brief("Winter storm warning for Denver", "", "natural disaster", "Denver", 6))
        self.assertTrue(NL.topic_on_brief("Governor declares a state of emergency after flooding", "", "natural disaster", "Utah", 7))
        self.assertFalse(NL.topic_on_brief("S&P 500 rises 0.4 percent", "", "financial", "", 6))
        self.assertTrue(NL.topic_on_brief("Bank failure freezes withdrawals nationwide", "", "financial", "", 6))
        self.assertTrue(NL.topic_on_brief("Supreme Court ruling on a speech mandate", "", "political", "", 6))
        self.assertTrue(NL.topic_on_brief("Surveillance law expands warrantless collection", "", "political", "", 6))
        self.assertTrue(NL.topic_on_brief("Mass protests over emergency powers", "", "political", "", 6))
        self.assertTrue(NL.topic_on_brief("Border security surge at the southern border", "", "political", "", 6))
        self.assertTrue(NL.topic_on_brief("AI hiring systems replace warehouse jobs", "", "other", "", 6))
        self.assertFalse(NL.topic_on_brief("Local bakery opens on Main Street", "", "other", "", 6))
        self.assertFalse(NL.topic_on_brief("Bomb cyclone warning for the coast", "", "natural disaster", "", 6))
        self.assertLess(NL.topic_tier("Iran missile strike", "", "war/conflict"), NL.topic_tier("Supreme Court ruling on a speech mandate", "", "political"))
        self.assertLess(NL.topic_tier("Supreme Court ruling on a speech mandate", "", "political"), NL.topic_tier("M7.1 earthquake near Chile", "", "natural disaster"))

    def test_selection_order_and_exclusions(self):
        self._add("bb11ce0000000001", "M6.1 earthquake strikes off the coast of Japan near Tokyo", "war/conflict", 6, 2, loc="Japan")
        self._add("bb11ce0000000002", "Winter storm warning for Denver", "natural disaster", 6, 2, loc="Denver")
        self._add("bb11ce0000000003", "M5.6 earthquake near Los Angeles", "natural disaster", 6, 2, loc="Los Angeles, California")
        self._add("bb11ce0000000004", "Supreme Court ruling on a digital ID mandate", "other", 7, 2)
        issue = self._issue()
        slots = ("main", "politics", "notable", "developing", "near", "updates", "follow", "watchlist")
        ids = [it["cluster_id"] for sec in slots for it in issue.get(sec) or []]
        self.assertNotIn("bb11ce0000000001", ids)
        self.assertNotIn("bb11ce0000000002", ids)
        self.assertIn("bb11ce0000000003", [it["cluster_id"] for it in issue["notable"]])
        main_ids = [it["cluster_id"] for it in issue["main"]]
        self.assertLess(main_ids.index("a11ce00000000001"), main_ids.index("bb11ce0000000004"))
        self.assertLess(main_ids.index("bb11ce0000000004"), main_ids.index("a11ce00000000005"))
        blob = " ".join([issue["bluf"], issue["subject"] if "subject" in issue else ""])
        self.assertNotIn("Japan", issue["bluf"])
        self.assertNotIn("Winter storm", issue["bluf"])
        self.assertIn("Here's what matters right now", issue["bluf"])
        links = {"unsubscribe": "https://blackout.network/newsletter", "manage": "https://blackout.network/newsletter",
                 "scoring": "https://blackout.network/scoring", "site": "https://blackout.network/#wire", "_row": None}
        subj, html, text = NL.render(issue, links)
        self.assertTrue(subj.startswith("Morning Brief, Nov 8: "))
        self.assertIn("Iran missile", subj)
        self.assertIn("+ ", subj)
        self.assertIn("Here's what matters right now", html)
        self.assertIn(NL.share_text(issue).split("\n", 1)[0], text)
        _assert_no_empty_framing(self, subj, html, text, NL.share_text(issue))
        self.assertIn('width="72"', html)
        self.assertLessEqual(len(NL.card_headline({"title": "The aftermath of yesterday's strikes on Kyiv's Northern Bridge using RM-48U ballistic missiles. As with the attack on the Southern Bridge, the missile penetrated the roadway completely. However, it remains unclear whether the damage is severe enough"})), 90)
        self.assertEqual(NL.card_headline({"title": "raw scanner text that goes on and on", "display_title": "Russian ballistic missiles damage Kyiv's Northern Bridge"}), "Russian ballistic missiles damage Kyiv's Northern Bridge")
        self.assertIn("Section Top threats", html)
        self.assertNotIn('height="315"', html)
        self.assertIn("UPTREND", html)
        self.assertGreaterEqual(html.count("WHAT HAPPENED"), 5)
        low = html.lower()
        for bad in ("is named.", "for this missile", "the headline states", "the report says", "the place named is"):
            self.assertNotIn(bad, low)
        import newsletter_art as ART
        self.assertEqual(ART.event_kind("Supreme Court ruling on a speech mandate", "political"), "rights")
        self.assertEqual(ART.event_kind("Surveillance law expands warrantless collection", "political"), "surveillance")
        self.assertEqual(ART.event_kind("Mass protests over emergency powers", "political"), "protest")
        self.assertEqual(ART.event_kind("Border security surge at the southern border", "political"), "border")
        root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "newsletter", "engraved")
        for name in ("banner-politics", "banner-threats", "scene-storm", "scene-rights", "scene-surveillance", "scene-protest", "scene-missile"):
            path = os.path.join(root, name + ".png")
            self.assertTrue(os.path.exists(path), path)
            self.assertLess(os.path.getsize(path), 70_000)
        self.assertLess(len(html.encode()), 1_500_000)
        self.assertNotIn("tyranny", html.lower())
        self.assertNotIn("attack on freedom", html.lower())


if __name__ == "__main__":
    unittest.main()
