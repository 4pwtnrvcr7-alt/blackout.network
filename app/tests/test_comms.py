import unittest
import comms

class CommsLander(unittest.TestCase):
    def test_hero_is_full_viewport_black_no_inner_box(self):
        css = comms.CSS.replace(" ", "")
        self.assertIn("100svh", comms.CSS)
        self.assertIn("max-width:none!important", css)
        self.assertIn("background:#000!important", css)
        # Beat the apple column and the grey --a-bg page.
        self.assertIn("html.bna-pgbody.comms-page>main#main.comms-main", css)
        self.assertIn("htmlbody.comms-page>main#main.comms-main", css)
        self.assertIn("margin-left:0!important", css)
        html = comms._page()
        self.assertIn("Coming soon", html)
        self.assertIn("<h1>Comms</h1>", html)
        self.assertNotIn("<form", html.lower())
        self.assertNotIn("Get the free brief", html)
        self.assertNotIn("bng_follow", html)
        # No custom lander footer; server injects the standard legal footer below the fold.
        self.assertNotIn("<footer", html.lower())
        self.assertNotIn("Research-only data", html)
        self.assertNotIn("Dashboard", html)
        self.assertNotIn("comms-bg", html)
        self.assertIn('class="comms-main"', html)
        self.assertIn("viewport-fit=cover", html)

    def test_handle_get(self):
        code, body, typ = comms.handle_get("/comms", {})
        self.assertEqual(code, 200)
        self.assertIn("text/html", typ)
        self.assertIn("Coming soon", body)
        code, _, _ = comms.handle_get("/comms/", {})
        self.assertEqual(code, 200)
        code, _, _ = comms.handle_get("/other", {})
        self.assertEqual(code, 404)
