"""Scroll-to-top on new pages and dashboard tab hashes (Matt, Nov 12).

Run: cd app && python3 -m unittest tests.test_scrolltop -v
"""
import os, re, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import apple_v1
import sitenav
import site_page as S


def js():
    return sitenav.scroll_script()


class ScrollScript(unittest.TestCase):
    def test_script_is_inline_and_guarded(self):
        h = js()
        self.assertTrue(h.startswith("<script>"))
        self.assertTrue(h.endswith("</script>"))
        self.assertIn("window.bnScroll", h)
        self.assertIn("scrollRestoration", h)
        self.assertIn("bn_scroll:", h)
        self.assertIn("hashchange", h)
        self.assertIn("scrollTo(0,0)", h)
        src = os.path.join(os.path.dirname(sitenav.__file__), "static", "bn-scroll.js")
        with open(src, encoding="utf-8") as fh:
            self.assertIn("acknowledgments", fh.read())

    def test_tab_hashes_are_injected(self):
        h = js()
        self.assertNotIn("/*BN_TABS*/{}", h)
        for name in ("wire", "grid", "network", "solar", "home", "threat"):
            self.assertIn(f'"{name}":1', h, name)

    def test_head_html_includes_script(self):
        head = sitenav.head_html("privacy", "/privacy")
        self.assertIn("window.bnScroll", head)
        self.assertEqual(head.count("window.bnScroll=1"), 1)

    def test_site_page_includes_script(self):
        html = S.page("Test", "desc", "<p>x</p>", "/privacy", "privacy")
        if isinstance(html, bytes):
            html = html.decode()
        self.assertIn("window.bnScroll", html)

    def test_apple_switch_scrolls_when_leaving_home(self):
        tag = apple_v1.head_tag()
        if isinstance(tag, bytes):
            tag = tag.decode()
        self.assertIn("was&&!home", tag)
        self.assertIn("scrollTo(0,0)", tag)

    def test_welcome_and_tos_still_link_as_intended(self):
        # /wire (the bare path intent) and /#wire stay in the shared nav/welcome; acknowledgments id stays on Terms.
        head = sitenav.head_html("welcome")
        self.assertIn("/sitenav.js", head)
        import welcome, legal
        code, body, _ = welcome.handle_get("/welcome", {})
        self.assertEqual(code, 200)
        html = body if isinstance(body, str) else body.decode()
        self.assertIn('href="/#wire"', html)
        self.assertIn("window.bnScroll", html)
        code, body, _ = legal.handle_get("/tos", {})
        self.assertEqual(code, 200)
        tos = body if isinstance(body, str) else body.decode()
        self.assertIn('id="acknowledgments"', tos)
