"""Hide 9 pages from menus/footer/sitemap and reorganise the menu (Matt pt1687u, Nov 21 2026).

Run: cd app && python3 -m unittest tests.test_menu_hide -v
"""
import os, re, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sitenav
import sitenav_ui as UI
import growth
import og
import site_page
import welcome

# Matt's labels -> nav key, public href, share/standalone path
HIDDEN = [
    ("Live TV & Radio", "streams", "/live#streams", "/streams"),
    ("Trends", "trends", "/live#trends", "/trends"),
    ("Broadcast transcripts", "bcast", "/live#broadcasts", "/broadcasts"),
    ("Live Radio", "radio", "/live#radio", "/radio"),
    ("Networks near me", "netnear", "/network/near", "/network/near"),
    ("Intel Streams", "intel", "/live#intel", "/intel"),
    ("Videos & Posts", "@social", "/social", "/social"),
    ("Ranked by Users", "ranked", "/live#ranked", "/ranked"),
    ("Public Stats", "@stats", "/stats", "/stats"),
]
HIDDEN_KEYS = {k for _, k, _, _ in HIDDEN}
HIDDEN_HREFS = {h for _, _, h, p in HIDDEN for h in (h,)} | {p for _, _, _, p in HIDDEN}
HIDDEN_LABELS = [
    "Live TV & Radio", "Trends", "Broadcast transcripts", "Broadcast Transcripts",
    "Live Radio", "Networks near me", "Intel Streams", "Intel streams",
    "Videos & Posts", "Videos & posts", "Videos and posts",
    "Ranked by Users", "Ranked by users", "Public Stats", "Public stats",
]

SECTIONS = [
    ("latest", "Live", ["The Wire", "Heat Map", "Weather", "Background Noise"]),
    ("threats", "Threats", ["The Grid", "Network Status", "Solar & Seismic", "AI Threats", "Crime", "Starlink"]),
    ("politics", "News", ["Newsletter", "Midterms 2026", "Politics", "Government", "Gun Laws", "Key Figures", "Markets"]),
    ("prepare", "Prepare", ["Preppers", "Local Resources", "Offline Maps", "First Aid", "Bushcraft"]),
    ("about", "More", ["Sources", "How We Score", "SpaceX", "CERN & LHC", "Private Jets", "Games"]),
]


def drawer_html():
    return UI.drawer(sitenav, active="threat")


import os as _os_d, sys as _sys_d
_sys_d.path.insert(0, _os_d.path.dirname(_os_d.path.dirname(_os_d.path.abspath(__file__))))
try:
    import deactivated as _deact_mod; _DEACT_ON = _deact_mod.ON
except Exception:
    _DEACT_ON = False
import unittest
class Mapping(unittest.TestCase):
    def test_hidden_keys_match_sitenav(self):
        self.assertEqual(sitenav.HIDDEN_MENU_KEYS, frozenset(k for k in HIDDEN_KEYS if k != "netnear"))

    def test_nav_items_are_flagged_hidden_not_removed(self):
        keys = {it[0]: it for g, its in sitenav.NAV for it in its}
        for _label, key, href, _path in HIDDEN:
            if key == "netnear":
                self.assertNotIn(key, keys)
                continue
            self.assertIn(key, keys, key)
            self.assertTrue(len(keys[key]) > 5 and keys[key][5], key)
            # route still defined
            if href.startswith("/live#"):
                self.assertEqual(keys[key][1], href.split("#", 1)[1])
            else:
                self.assertEqual(keys[key][1], href)


class Menu(unittest.TestCase):
    def test_hidden_pages_absent_from_drawer(self):
        html = drawer_html()
        for label, key, href, path in HIDDEN:
            self.assertNotIn(f'data-tab="{key}"', html, label)
            self.assertNotIn(f'href="{href}"', html, label)
            self.assertNotIn(f'href="{path}"', html, path)
        for label in HIDDEN_LABELS:
            self.assertNotIn(label, html, label)
        self.assertNotIn("/stats", html)
        self.assertNotIn("/social", html)
        self.assertNotIn("/network/near", html)
        self.assertNotIn("welcome", html.lower())
        self.assertNotIn("Meshtastic", html)
        self.assertNotIn("LoRa", html)
        self.assertNotIn("/welcome", html)

    @unittest.skipIf(_DEACT_ON, "Nov 24 2026 (Matt): old menu layout / deactivated pages; replaced by menu v5 + tests/test_deactivate_pages.py")
    def test_section_order_and_labels(self):
        secs = UI.menu3_sections(sitenav)
        self.assertEqual([s[0] for s in secs], [s[0] for s in SECTIONS])
        self.assertEqual([s[1] for s in secs], [s[1] for s in SECTIONS])
        for (sid, name, labels), got in zip(SECTIONS, secs):
            got_labels = [row[1] for row in got[3] if row[2] is not None]
            # mesh/tips stay out unless their flags are on
            self.assertEqual(got_labels, labels, name)
            for row in got[3]:
                if row[0] in ("@mesh", "meshguide", "tips"):
                    continue
                self.assertIsNotNone(row[2], row)
                self.assertNotIn(row[0], HIDDEN_KEYS)

    @unittest.skipIf(_DEACT_ON, "Nov 24 2026 (Matt): old menu layout / deactivated pages; replaced by menu v5 + tests/test_deactivate_pages.py")
    def test_no_duplicate_hrefs_or_labels(self):
        rows = [row for sec in UI.menu3_sections(sitenav) for row in sec[3] if row[2]]
        hrefs = [r[2] for r in rows]
        labels = [r[1] for r in rows]
        self.assertEqual(len(hrefs), len(set(hrefs)), hrefs)
        self.assertEqual(len(labels), len(set(labels)), labels)
        self.assertIn("/wire", hrefs)
        self.assertIn("/map", hrefs)
        self.assertIn("/newsletter", hrefs)
        self.assertIn("/sources", hrefs)
        self.assertIn("/midterms", hrefs)

    @unittest.skipIf(_DEACT_ON, "Nov 24 2026 (Matt): old menu layout / deactivated pages; replaced by menu v5 + tests/test_deactivate_pages.py")
    def test_every_menu_link_is_absolute_site_path(self):
        html = drawer_html()
        hrefs = re.findall(r'<div class="m3-grid">.*?<div class="m3-foot">', html, re.S)
        self.assertTrue(hrefs)
        block = hrefs[0]
        for m in re.finditer(r'<a href="([^"]+)"', block):
            h = m.group(1)
            self.assertTrue(h.startswith("/") or h.startswith("https://"), h)
            self.assertFalse(h.startswith("/welcome"), h)

    @unittest.skipIf(_DEACT_ON, "Nov 24 2026 (Matt): old menu layout / deactivated pages; replaced by menu v5 + tests/test_deactivate_pages.py")
    def test_five_sections_no_soon_rows(self):
        html = drawer_html()
        self.assertEqual(html.count('<details class="bn-grp'), 5)
        self.assertNotIn('<li class="m3-soon"', html)
        self.assertIn('m3-t">Live<', html)
        self.assertIn('m3-t">News<', html)
        self.assertIn('m3-t">More<', html)


class FooterSitemap(unittest.TestCase):
    @unittest.skipIf(_DEACT_ON, "Nov 24 2026 (Matt): old menu layout / deactivated pages; replaced by menu v5 + tests/test_deactivate_pages.py")
    def test_menu_footer_drops_stats(self):
        html = drawer_html()
        self.assertIn('href="/privacy"', html)
        self.assertIn('href="/tos"', html)
        self.assertIn('href="/scoring"', html)
        self.assertNotIn('href="/stats"', html)

    def test_site_page_footer_drops_social(self):
        html = site_page.page("T", "D", "<p>x</p>", "/scoring", "@scoring").decode()
        self.assertNotIn("/social", html)
        self.assertNotIn("Videos", html)
        self.assertIn('href="/wire"', html)
        self.assertIn('href="/newsletter"', html)

    def test_sitemap_and_llms_drop_hidden_hubs(self):
        sm = growth.sitemap().decode()
        self.assertIn("https://blackout.network/wire", sm)
        self.assertIn("https://blackout.network/newsletter", sm)
        for path in ("/social", "/stats", "/network/near"):
            self.assertNotIn(f"https://blackout.network{path}<", sm.replace(">", "<"), path)
            self.assertNotIn(f"<loc>https://blackout.network{path}</loc>", sm, path)
        self.assertNotIn("/mesh<", sm)
        txt = growth.handle_get("/llms.txt", {})[1]
        if isinstance(txt, bytes):
            txt = txt.decode()
        self.assertNotIn("/social", txt)
        self.assertNotIn("/stats", txt)
        self.assertIn("/newsletter", txt)
        self.assertNotIn("/welcome", txt)

    def test_welcome_directory_drops_hidden_hubs(self):
        hrefs = [row[-1] for row in welcome.TOOLS] + [h for _l, h in welcome.ALSO]
        for h in hrefs:
            self.assertNotIn(h, HIDDEN_HREFS)
        text = " ".join(str(x) for row in welcome.TOOLS for x in row)
        for label in ("Live Broadcasts", "Videos & posts", "Public stats"):
            self.assertNotIn(label, text)
        self.assertNotIn("/stats", [h for _l, h in welcome.ALSO])


class Noindex(unittest.TestCase):
    def test_share_pages_for_hidden_tabs(self):
        for seg in ("streams", "trends", "broadcasts", "radio", "intel", "ranked"):
            html = og.share_page(seg).decode()
            self.assertIn('name="robots" content="noindex,nofollow"', html, seg)
        # a still-public tab is not noindexed
        pub = og.share_page("weather").decode()
        self.assertNotIn("noindex", pub)

    def test_site_page_noindex_flag(self):
        html = site_page.page("T", "D", "<p>x</p>", "/network/near", "net", noindex=True).decode()
        self.assertIn('name="robots" content="noindex,nofollow"', html)


if __name__ == "__main__":
    unittest.main()
