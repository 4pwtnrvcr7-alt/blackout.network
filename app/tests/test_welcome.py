""" /welcome onboarding (t1305u). Run: cd app && python3 -m unittest tests.test_welcome -v """
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import welcome
import sitenav
import sitenav_ui as UI

BANNED = ("before the news", "before cable", "verified", "matt johnston")


def html():
    code, body, ctype = welcome.handle_get("/welcome", {})
    assert code == 200 and ctype == "text/html"
    return body if isinstance(body, str) else body.decode()


class WelcomePage(unittest.TestCase):
    def test_page_and_assets(self):
        h = html()
        self.assertIn("Welcome in.", h)
        self.assertIn("Created by humans. Powered by Superintelligence.", h)
        self.assertIn("Signal over noise.", h)
        self.assertIn("Get the Free brief.", h)
        self.assertIn("hello@blackout.network", h)
        self.assertIn("Confirm your BLACKOUT.NETWORK newsletter subscription", h)
        self.assertIn("Confirm subscription", h)
        self.assertIn("Add to Home Screen", h)
        self.assertIn("iOS 16.4", h)
        self.assertIn("youtube.com/@blkoutntw?sub_confirmation=1", h)
        self.assertIn("x.com/BlkoutNtw", h)
        self.assertIn('source" value="welcome', h)
        self.assertIn("/#wire", h)
        c, b, t = welcome.handle_get("/welcome.js", {})
        self.assertEqual((c, t), (200, "application/javascript")); self.assertGreater(len(b), 100)
        c, b, t = welcome.handle_get("/welcome.css", {})
        self.assertEqual((c, t), (200, "text/css"))
        self.assertEqual(welcome.handle_get("/welcome/nope", {})[0], 404)

    def test_only_real_newsletter_options(self):
        h = html()
        self.assertIn('value="morning"', h)
        self.assertIn('value="evening"', h)
        self.assertIn('value="twice"', h)
        for cat, _lab, *_ in welcome.CHIP_CATS + [(a, b) for a, b in welcome.MORE_CATS]:
            self.assertIn(f'value="{cat}"', h)
        self.assertIn("Denver, CO", h)
        self.assertIn("80202, Denver, CO or Germany", h)
        self.assertNotIn("Sanford", h)
        self.assertNotIn("32771", h)
        self.assertNotIn("Central Florida", h)
        self.assertIn("The brief does not have a separate category", h)

    def test_copy_rules(self):
        h = html().lower()
        for w in BANNED:
            self.assertNotIn(w, h)
        self.assertNotIn("matt johnston", h)
        # red class only for rank 7+
        self.assertIn("wel-r7", h)
        self.assertIn("rank 7+", h)
        self.assertIn('wel-video" hidden', h)

    def test_prompt_default_off(self):
        os.environ.pop("BN_WELCOME_FIRST", None)
        self.assertEqual(welcome.prompt_html(), "")
        os.environ["BN_WELCOME_FIRST"] = "banner"
        self.assertIn("bn_welbar", welcome.prompt_html())
        os.environ["BN_WELCOME_FIRST"] = "redirect"
        self.assertIn("location.replace", welcome.prompt_html())
        os.environ["BN_WELCOME_FIRST"] = "off"
        self.assertEqual(welcome.prompt_html(), "")


class WelcomeNav(unittest.TestCase):
    def test_pages_entry(self):
        self.assertIn("welcome", sitenav.PAGES)
        self.assertTrue(sitenav.PAGES["welcome"][1].startswith("Start here"))

    def test_no_inbound_links(self):
        # welcome ships unlinked: no nav/menu/footer entry, no first-visit hook in the header
        self.assertNotIn("welcome", UI.M3_HREF)
        self.assertNotIn("/welcome", UI.topbar(sitenav))
        self.assertNotIn("/welcome", UI.drawer(sitenav))


if __name__ == "__main__":
    unittest.main()
