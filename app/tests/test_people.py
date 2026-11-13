""" People layer + same-origin media cache (Nov 13). Run: cd app && NEWSLETTER_NO_WORKER=1 python3 -m unittest tests.test_people -v """
import json, os, re, sys, unittest
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import people as PP
import story_report as SR
import addons

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "people_sr.json")
with open(FIX, encoding="utf-8") as fh: DATA = json.load(fh)
BANNED = ("before the news", "verified", "meshtastic", "lora ", "lorawan")
EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF]")


def visible(h):
    h = re.sub(r"<script.*?</script>|<style.*?</style>", " ", h, flags=re.S)
    return re.sub(r"<[^>]+>", " ", h)


class Base(unittest.TestCase):
    def setUp(self):
        self.p = mock.patch.object(PP, "_reports", return_value=(DATA, 12345.0))
        self.p.start()
        self.a = mock.patch.object(PP, "archive_stories", return_value=[])
        self.a.start()
        PP._D["mt"] = None
        self.env = mock.patch.dict(os.environ, {"BN_PEOPLE": "1", "BN_MEDIA_PROXY": "1", "BN_STORY_LEAD_FALLBACK": "1"})
        self.env.start()

    def tearDown(self):
        self.p.stop(); self.a.stop(); self.env.stop(); PP._D["mt"] = None

    def clean(self, h):
        t = visible(h).lower()
        for b in BANNED: self.assertNotIn(b, t, b)
        self.assertIsNone(EMOJI.search(h))


class Strip(Base):
    def test_strip_has_photo_drawer_and_profile_button(self):
        cid = next(iter(DATA["people"]["story_people"]))
        h = PP.strip_html(cid, "Pete Hegseth and Donald Trump said")
        self.assertTrue(h)
        self.assertIn("People in this story", h)
        self.assertIn('aria-expanded="false"', h)
        self.assertRegex(h, r'href="/people/[a-z0-9-]+"')
        self.assertIn("Wikimedia Commons", h)
        self.assertIn("/api/people/people.js", h)
        self.clean(h)

    def test_request_time_match_without_box_list(self):
        names = [p["slug"] for p in PP.people_for("ffffffffffffffff", "Tucker Carlson spoke")]
        self.assertIn("tucker-carlson", names)

    def test_kill_switch(self):
        with mock.patch.dict(os.environ, {"BN_PEOPLE": "0"}):
            self.assertFalse(PP.strip_html(next(iter(DATA["people"]["story_people"])), "Donald Trump"))
            self.assertEqual(PP.handle_get("/people/donald-trump")[0], 404)


class Profile(Base):
    def test_profile_sections_and_sources(self):
        code, h, ct = PP.handle_get("/people/pete-hegseth")
        self.assertEqual((code, ct), (200, "text/html"))
        h = h if isinstance(h, str) else h.decode()
        for s in ('id="photos"', 'id="career"', 'id="timeline"', 'id="stories"', 'id="sources"', "Wikidata", "Wikipedia", "ProfilePage"):
            self.assertIn(s, h, s)
        self.assertIn("Pete Hegseth", h)
        self.clean(h)

    def test_unknown_profile_404_and_index(self):
        self.assertEqual(PP.handle_get("/people/nobody-here")[0], 404)
        code, h, _ = PP.handle_get("/people")
        self.assertEqual(code, 200)
        self.assertIn("/people/donald-trump", h if isinstance(h, str) else h.decode())

    def test_routes_registered(self):
        with open(addons.__file__, encoding="utf-8") as fh: src = fh.read()
        for r in ('"/people"', '"/api/people"', '"/api/media"'): self.assertIn(r, src)


class Media(Base):
    def test_allowlist(self):
        PP.block()
        po = DATA["people"]["profiles"]["pete-hegseth"]["portrait"]
        self.assertIn(PP.mid(po["src"]), PP._D["allow"])
        self.assertTrue(PP.media_url(po["src"]).startswith("/api/media/"))
        self.assertIsNone(PP.media_bytes("ffffffffffffffffffff.jpg"))
        self.assertIsNone(PP.media_bytes("../../etc/passwd"))
        self.assertEqual(PP.handle_get("/api/media/ffffffffffffffffffff.jpg")[0], 404)

    def test_http_never_allowed(self):
        self.assertNotIn(PP.mid("http://example.com/a.jpg"), PP._D["allow"] if PP.block() is not None else {})

    def test_private_hosts_rejected(self):
        with mock.patch.dict(os.environ, {"BN_MEDIA_TEST_ALLOW_PRIVATE": "0"}):
            self.assertFalse(PP._public_host("127.0.0.1"))
            self.assertFalse(PP._public_host("10.0.0.5"))

    def test_proxy_kill_switch_keeps_original(self):
        u = DATA["people"]["profiles"]["pete-hegseth"]["portrait"]["src"]
        with mock.patch.dict(os.environ, {"BN_MEDIA_PROXY": "0"}):
            self.assertEqual(PP.media_url(u), u)


class Lead(Base):
    def test_lead_prefers_person_first_in_headline(self):
        v = PP.lead_for("ffffffffffffffff", "Tucker Carlson claims Donald Trump could act", "", "")
        self.assertEqual((v or {}).get("person"), "tucker-carlson")
        self.assertIn("File photo", v["caption"])
        self.assertTrue(v["credit"])

    def test_lead_kill_switch(self):
        with mock.patch.dict(os.environ, {"BN_STORY_LEAD_FALLBACK": "0"}):
            self.assertIsNone(PP.lead_for("ffffffffffffffff", "Donald Trump said"))

    def test_country_fallback(self):
        k = next(iter(DATA["people"]["country_alias"]))
        v = PP.lead_for("ffffffffffffffff", f"Protests in {k.title()} grow", "", "")
        self.assertTrue(v and v.get("src", "").startswith("https://"))


class Glance(unittest.TestCase):
    def test_glance_is_labelled_graphic(self):
        import inspect
        src = inspect.getsource(SR.glance)
        self.assertIn("Graphic: BLACKOUT.NETWORK", inspect.getsource(SR))
        self.assertIn("<svg", src)


if __name__ == "__main__":
    unittest.main()
