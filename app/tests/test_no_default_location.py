"""No default visitor location (Sanford / Lake Mary / 32771 / Central Florida).

When the reader has not chosen a place, pages must show a neutral national
view or a set-your-location prompt. The legally required business mailing
address (PO Box 1228, Lake Mary, FL 32746) and the Seminole County court
venue on /privacy and /tos stay as they are.
Run: cd app && NEWSLETTER_NO_WORKER=1 python3 -m unittest tests.test_no_default_location -v
"""
import os, re, sys, unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BANNED_DEFAULTS = ("32771", "Sanford", "Lake Mary", "Central Florida")
MAILING = "PO Box 1228, Lake Mary, FL 32746"
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _html(mod, path, qs=None):
    import importlib
    m = importlib.import_module(mod)
    fn = getattr(m, "handle_get")
    code, body, ctype = fn(path, qs or {})
    if not (code == 200 and "html" in str(ctype)):
        raise AssertionError(f"{mod} {path} -> {code} {ctype}")
    return body if isinstance(body, str) else body.decode()


class WelcomeAndNewsletter(unittest.TestCase):
    def test_welcome_has_no_florida_default(self):
        import welcome
        code, body, ctype = welcome.handle_get("/welcome", {})
        h = body if isinstance(body, str) else body.decode()
        self.assertEqual(code, 200)
        for b in ("32771", "Sanford", "Central Florida"):
            self.assertNotIn(b, h, b)
        self.assertIn(MAILING, h)
        self.assertEqual(h.count("Lake Mary"), 1)
        self.assertIn('id="wel_loc"', h)
        self.assertIn("80202, Denver, CO or Germany", h)
        self.assertNotIn("data-loc=", h)
        self.assertIn("Nothing is filled in until you choose", h)

    def test_newsletter_forms_use_neutral_examples(self):
        import newsletter
        h = newsletter.page_html() if hasattr(newsletter, "page_html") else None
        # Fall back to the public subscribe page if the helper name differs.
        if not h:
            for name in ("subscribe_page", "signup_html", "landing_html", "page"):
                fn = getattr(newsletter, name, None)
                if callable(fn):
                    try:
                        out = fn()
                        h = out if isinstance(out, str) else None
                        if h:
                            break
                    except TypeError:
                        continue
        src = Path(APP, "newsletter.py").read_text(encoding="utf-8")
        self.assertIn('placeholder="e.g. 80202, Denver, CO or Germany"', src)
        self.assertNotIn("32771", src)
        self.assertNotIn("Sanford", src)
        self.assertIn(MAILING, src)
        self.assertIn("e.g. Denver, CO", src)


class LegalKeepsMailingAddress(unittest.TestCase):
    def test_privacy_example_is_neutral_and_mailing_address_stays(self):
        import legal
        privacy = legal.handle_get("/privacy", {})[1]
        if isinstance(privacy, bytes):
            privacy = privacy.decode()
        self.assertIn('for example "Denver, CO 80202"', privacy)
        self.assertNotIn("32771", privacy)
        self.assertNotIn("Sanford", privacy)
        self.assertIn(MAILING, privacy)
        self.assertIn("Seminole County, Florida", privacy)
        tos = legal.handle_get("/tos", {})[1]
        if isinstance(tos, bytes):
            tos = tos.decode()
        self.assertIn(MAILING, tos)
        self.assertIn("Seminole County, Florida", tos)


class MeshAndCern(unittest.TestCase):
    def test_mesh_opens_on_us_view(self):
        import meshnet
        h = meshnet.handle_get("/mesh", {})[1]
        if isinstance(h, bytes):
            h = h.decode()
        self.assertIn('data-view="us" aria-pressed="true"', h)
        self.assertIn('data-view="cfl" aria-pressed="false"', h)
        self.assertIn("United States right now", h)
        self.assertIn("opening on a U.S. view", h)
        self.assertNotIn("starting with Central Florida", h)
        self.assertNotIn("centered on Central Florida", h)
        self.assertNotIn("Sanford", h)
        self.assertNotIn("Lake Mary", h)
        js = Path(APP, "meshnet_static", "app.js").read_text(encoding="utf-8")
        self.assertIn('view:"us"', js)
        self.assertNotIn('view:"cfl"', js)
        # Central Florida remains an optional view the reader can pick.
        self.assertIn("area:cfl", js)
        self.assertIn('data-view="cfl"', h)

    def test_collector_focus_is_national(self):
        src = Path(APP).parent.joinpath("tools", "meshtastic", "collect.py").read_text(encoding="utf-8")
        self.assertIn('"focus": "country:United States of America"', src)
        self.assertNotIn('"focus": "area:cfl"', src)
        self.assertNotIn("Sanford / Lake Mary", src)

    def test_cern_map_opens_on_geneva(self):
        import cern
        with mock.patch.object(cern, "live_image", return_value=None):
            h = cern.handle_get("/cern", {})[1]
        if isinstance(h, bytes):
            h = h.decode()
        self.assertIn('value="geneva" selected', h)
        self.assertNotIn('value="sanford" selected', h)
        self.assertIn("The map opens on the real tunnel at Geneva", h)
        self.assertNotIn("dropped on Sanford", h)
        # Sanford may remain as an optional comparison city, but it is not selected.
        self.assertIn('value="sanford"', h)


class PlaceholdersAndExamples(unittest.TestCase):
    def test_network_and_crime_examples(self):
        net = Path(APP, "netpages.py").read_text(encoding="utf-8")
        sl = Path(APP, "netstarlink.py").read_text(encoding="utf-8")
        cr = Path(APP, "crime.py").read_text(encoding="utf-8")
        self.assertIn('placeholder="ZIP code or city, e.g. 80202 or Denver"', net)
        self.assertNotIn("32771", net)
        self.assertIn("80202, Denver or Mumbai", sl)
        self.assertNotIn("32771", sl)
        self.assertIn("Cook County, IL", cr)
        self.assertNotIn("Seminole County, FL", cr)

    def test_weather_has_no_default_place(self):
        js = Path(APP, "weather_static", "app.js").read_text(encoding="utf-8")
        self.assertIn("const DEF=null", js)
        self.assertIn("Pick a place", js)
        self.assertNotIn("32771", js)
        self.assertNotIn("Sanford", js)
        self.assertNotIn("default location (nothing saved yet)", js)

    def test_sitenav_mesh_blurb(self):
        import sitenav
        self.assertIn("opening on a U.S. view", (sitenav.PAGES.get("mesh") or ["","","",""])[2])
        src = Path(APP, "sitenav.py").read_text(encoding="utf-8")
        self.assertIn("opening on a U.S. view", src)
        self.assertNotIn("centered on Central Florida", src)


class SourceGuard(unittest.TestCase):
    """Catch new hardcoded hometown defaults in app code (not data files or legal copy)."""

    ALLOW_SUBSTRING = (
        # Business mailing address and court venue — required, not a visitor default.
        "PO Box 1228, Lake Mary, FL 32746",
        "Seminole County, Florida",
        '"addressLocality": "Lake Mary"',
        # Optional CERN comparison city (not selected by default).
        '("sanford", "Sanford, FL", 28.8003, -81.2731)',
        'value="sanford"',
        # Optional mesh region the reader can pick (not the opening view).
        "Central Florida</button>",
        'data-view="cfl"',
        "Central Florida right now",
        "area:cfl",
        "Central Florida (Orlando metro)",
        # Factual station / market labels, not a visitor default.
        "covers Seminole County",
        "Central Florida · covers",
        "East Central Florida · covers",
        "coastal Central Florida",
        '"Central Florida")',
        "no Central Florida priority",
    )

    SCAN_FILES = [
        "welcome.py", "newsletter.py", "legal.py", "netpages.py", "netstarlink.py",
        "crime.py", "cern.py", "meshnet.py", "sitenav.py", "growth.py",
        "weather.py", "weather_static/app.js", "meshnet_static/app.js",
        "geo_static/geo.js", "resources.py", "visitor_geo.py", "newsletter_v2.py",
    ]

    def test_app_code_has_no_unexpected_hometown_defaults(self):
        hits = []
        for rel in self.SCAN_FILES:
            path = os.path.join(APP, rel)
            if not os.path.isfile(path):
                continue
            text = Path(path).read_text(encoding="utf-8")
            # Strip allowed legal / optional-choice / factual strings before scanning.
            scrubbed = text
            for a in self.ALLOW_SUBSTRING:
                scrubbed = scrubbed.replace(a, "")
            for pat, label in (
                (r"32771", "32771"),
                (r"Sanford", "Sanford"),
                (r"Lake Mary", "Lake Mary"),
                (r"Central Florida", "Central Florida"),
                (r"Seminole County, FL", "Seminole County, FL"),
            ):
                if re.search(pat, scrubbed):
                    # show a short snippet
                    m = re.search(pat, scrubbed)
                    i = m.start()
                    snip = scrubbed[max(0, i - 60):i + 80].replace("\n", " ")
                    hits.append(f"{rel}: {label} :: {snip}")
        self.assertEqual(hits, [], "unexpected hometown defaults:\n" + "\n".join(hits))

LINKS = {
    "unsubscribe": "https://blackout.network/newsletter/unsubscribe?token=x",
    "manage": "https://blackout.network/newsletter",
    "categories": "https://blackout.network/newsletter",
    "sources": "https://blackout.network/sources",
    "scoring": "https://blackout.network/scoring",
    "site": "https://blackout.network/#wire",
    "_row": None,
}


def _quiet_issue():
    """A no-location subscriber's issue: no loc_label, no crime, no near-you block."""
    et = timezone(timedelta(hours=-5))
    end = datetime(2026, 11, 13, 19, 0, tzinfo=et)
    return {
        "near": [], "loc_label": None, "main": [], "notable": [], "watchlist": [],
        "updates": [], "follow": [], "politics": [], "developing": [], "quiet": True,
        "start": end - timedelta(hours=12), "end": end, "slot": "evening",
        "empty": False, "rule": {"rank": 5, "sources": 2}, "crime": None,
        "videos": [], "featured": [], "bluf": "Signal over noise.", "analysis": {},
    }


def _assert_no_hometown_crime(tc, html, text):
    for blob, name in ((html, "html"), (text, "text")):
        low = blob.lower()
        tc.assertNotIn("crime near you", low, name)
        tc.assertNotIn("sanford", low, name)
        tc.assertNotIn("32771", blob, name)
    tc.assertIn(MAILING, html)
    tc.assertIn(MAILING, text)


class NoLocationNewsletterIssue(unittest.TestCase):
    """A subscriber with no saved area must not get a Sanford crime block in v1 or v2."""

    def setUp(self):
        self._v2 = os.environ.get("BN_NL_V2")
        import newsletter as N
        self.N = N

    def tearDown(self):
        if self._v2 is None:
            os.environ.pop("BN_NL_V2", None)
        else:
            os.environ["BN_NL_V2"] = self._v2

    def _render_cfg(self):
        return {
            "base_url": "https://blackout.network",
            "mailing_address": MAILING,
            "from_email": "hello@blackout.network",
            "from_name": "BLACKOUT.NETWORK",
            "slots": {"morning": "07:00", "evening": "19:00"},
        }

    def test_v2_issue_html_and_text_have_no_crime_or_sanford(self):
        os.environ["BN_NL_V2"] = "1"
        _subj, html, text = self.N.render(_quiet_issue(), LINKS, self._render_cfg())
        _assert_no_hometown_crime(self, html, text)

    def test_v1_issue_html_and_text_have_no_crime_or_sanford(self):
        os.environ["BN_NL_V2"] = "0"
        _subj, html, text = self.N.render(_quiet_issue(), LINKS, self._render_cfg())
        _assert_no_hometown_crime(self, html, text)

    def test_crime_opt_in_without_an_area_does_not_invent_sanford(self):
        # Even if crime.brief_for would return Sanford, it must not be called.
        fake = {"label": "Sanford, FL 32771", "url": "https://blackout.network/crime?place=32771",
                "lines": ["placeholder"], "source": "test"}
        with mock.patch("crime.brief_for", return_value=fake) as bf:
            self.assertIsNone(self.N._subscriber_crime({"id": 1, "crime_brief": 1}))
            self.assertIsNone(self.N._subscriber_crime({"id": 1, "crime_brief": 1, "loc_label": ""}))
            self.assertIsNone(self.N._subscriber_crime({"id": 1, "crime_brief": 1, "loc_label": "   "}))
            self.assertIsNone(self.N._subscriber_crime({"id": 1, "crime_brief": 0, "loc_label": "Denver, CO"}))
            self.assertIsNone(self.N._subscriber_crime(None))
            bf.assert_not_called()
            out = self.N._subscriber_crime({"id": 1, "crime_brief": 1, "loc_label": "Denver, CO 80202"})
            bf.assert_called_once()
            self.assertEqual(out["label"], "Sanford, FL 32771")  # whatever brief_for returns when there IS a saved area

    def test_preview_and_test_send_do_not_hardcode_a_hometown(self):
        src = Path(APP, "newsletter.py").read_text(encoding="utf-8")
        # preview_issue uses a twice-daily sub with no location and no crime_brief
        prev = src[src.find("def preview_issue"):src.find("def admin_stats")]
        self.assertIn('{"id": None, "frequency": "twice"', prev)
        self.assertNotIn("Sanford", prev)
        self.assertNotIn("32771", prev)
        self.assertNotIn("loc_label", prev)
        self.assertIn("interests", src[src.find("def preview_issue"):src.find("def preview_issue")+800])
        # test_send only writes a location when the caller supplied one
        self.assertIn('if d.get("location"):', src)
        self.assertIn("_subscriber_crime(sub)", src)
        v2 = Path(APP, "newsletter_v2.py").read_text(encoding="utf-8")
        # v2 only draws the crime block from issue["crime"], never a hardcoded place
        self.assertIn('if issue.get("crime"):', v2)
        self.assertNotIn("32771", v2)
        self.assertNotIn("Sanford", v2)
