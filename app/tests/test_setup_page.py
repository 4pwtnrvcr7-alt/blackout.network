"""Matt 7:39 AM ET Nov 28: /setup install + alerts page. Run: cd app && python3 -m unittest tests.test_setup_page -v"""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import addons, growth, menu5, setup_page, sitenav_ui as UI

class SetupPage(unittest.TestCase):
    def test_route_and_content(self):
        self.assertEqual(addons.ROUTES.get("/setup"), "setup_page")
        code, body, ct = setup_page.handle_get("/setup", {})
        self.assertEqual((code, ct), (200, "text/html"))
        if isinstance(body, bytes):
            body = body.decode("utf-8")
        self.assertIn('id="install"', body)
        self.assertIn('id="notifications"', body)
        self.assertIn("Add to Home Screen", body)
        self.assertIn("iOS 16.4", body)
        self.assertIn("Android", body)
        self.assertIn("Chrome", body)
        self.assertIn("Edge", body)
        self.assertIn("Safari", body)
        self.assertIn("Firefox", body)
        self.assertIn('data-su="install"', body)
        self.assertIn('data-su="notify"', body)
        self.assertIn("Install app", body)
        self.assertIn("Turn on notifications", body)
        self.assertIn("installApp", body)
        self.assertIn("showNotifyGuide", body)
        self.assertIn("enableAlerts", body)
        self.assertNotIn("peer-to-peer", body.lower())
        self.assertNotIn("peer to peer", body.lower())
        self.assertEqual(UI.refresh_mode("/setup"), "off")
        self.assertIn("/sitenav.css", body)
        self.assertIn('id="bn-menu"', body)

    def test_sitemap_and_menu(self):
        self.assertIn("/setup", [p[0] for p in growth.STATIC_PAGES])
        hrefs = [h for _, _, h in menu5.ORDER]
        self.assertIn("/setup#install", hrefs)
        self.assertIn("/setup#notifications", hrefs)
