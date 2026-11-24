"""Provider analysis pages use the same severity palette as Status cards (pt1846u follow-up)."""
import os, sys, unittest
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
os.environ["BN_NETMAP_WARM"] = "0"

class ProviderPalette(unittest.TestCase):
    def test_netpages_lvc_and_legend(self):
        import netpages
        self.assertEqual(netpages.LVC[1], "#FFA040")
        self.assertEqual(netpages.LVC[2], "#FF3B3B")
        self.assertEqual(netpages.LVC[3], "#FF3B3B")
        self.assertNotIn("#FF7A1A", netpages.LEG)
        self.assertNotIn("#F5A524", netpages.LEG)
        self.assertNotIn("#FF4D4F", netpages.LEG)
        self.assertIn("#FFA040", netpages.LEG)
        self.assertEqual(netpages.LEG.count("#FF3B3B"), 2)  # Degraded + Major
        src = open(os.path.join(APP, "netpages.py"), encoding="utf-8").read()
        self.assertIn('C={0:"#2BB673",1:"#FFA040",2:"#FF3B3B",3:"#FF3B3B","-1":"#5b6573"}', src)
        # severity palette only: leftover #F5A524 / #FF4D4F may remain as incident-type tags
        self.assertNotIn("#FF7A1A", src)

    def test_starlink_and_near_me_palette(self):
        src = open(os.path.join(APP, "netstarlink.py"), encoding="utf-8").read()
        self.assertIn('C={0:"#2BB673",1:"#FFA040",2:"#FF3B3B",3:"#FF3B3B","-1":"#5b6573"}', src)
        self.assertIn('style="--c:#FF3B3B"', src)  # official outage list
        self.assertNotIn("#FF7A1A", src)
        # CelesTrak satellite-status key and IODA series colors are not this palette

    def test_provider_page_renders_new_legend(self):
        import netpages
        code, body, ct = netpages.handle_get("/grid/cloudflare", {})
        self.assertEqual(code, 200)
        html = body.decode() if isinstance(body, bytes) else body
        self.assertIn("#FFA040", html)
        self.assertIn("#FF3B3B", html)
        self.assertNotIn("#FF7A1A", html)
        # old minor/major swatches must not appear in the severity key
        self.assertNotIn("background:#F5A524", html)
        self.assertNotIn("background:#FF4D4F", html)

if __name__ == "__main__":
    unittest.main()
