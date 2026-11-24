"""Nov 24 2026 (Matt): 21 pages deactivated (deactivated.py) + menu v5 (menu5.py); 7:50 AM: /mesh/chat off, newsletter-linked pages unlisted."""
import os, sys, re, unittest, threading, http.client
os.environ["NEWSLETTER_NO_WORKER"] = "1"   # never spawn newsletter_worker.py from a test
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import deactivated as D

ROUTES = ["/live", "/live/", "/dashboard", "/noise", "/solar", "/ai", "/crime", "/crime/zip/32771", "/grid/starlink", "/midterms", "/elections",
          "/politics", "/government", "/gunlaws", "/figures", "/elon", "/preppers", "/resources", "/maps", "/maps/x.pdf", "/medical",
          "/bushcraft", "/sources", "/scoring", "/about/scoring", "/spacex", "/cern", "/lhc", "/jets", "/games", "/mesh/chat", "/mesh/chat/x"]
UNLISTED = ["/sources", "/sources/", "/scoring", "/about/scoring", "/crime", "/crime/zip/32771", "/games", "/preppers", "/bushcraft", "/medical", "/first-aid"]   # + reworked pages (solo.py, pt1846u), unlisted until Matt approves   # hidden, but still served (newsletter links)
KEEP = ["/", "/wire", "/map", "/weather", "/grid", "/grid/aws", "/markets", "/newsletter", "/privacy", "/tos", "/ready", "/api/live/summary",
        "/api/sources/x", "/api/crime/x", "/livestream", "/sourcesx", "/mesh", "/mesh/guide", "/api/mesh/chat"]

class List(unittest.TestCase):
    def test_count_and_routes(self):
        self.assertEqual(len(D.DEACTIVATED_PAGES), 24)   # 21 names + "local resources / offline maps" split in two + mesh chat + old /grid (merged into /grid)
        for n, k, ps, st in D.DEACTIVATED_PAGES: self.assertIn(st, ("off", "unlisted"), n)
        for p in ROUTES: self.assertTrue(D.is_off(p), p)
        for p in KEEP: self.assertFalse(D.is_off(p), p); self.assertFalse(D.redirects(p), p)
        for p in UNLISTED: self.assertTrue(D.is_off(p), p); self.assertFalse(D.redirects(p), p)
        for p in ROUTES:
            if p not in UNLISTED: self.assertTrue(D.redirects(p), p)
    def test_mesh_pages_have_no_chat_links(self):
        import meshnet
        for p in ("/mesh", "/mesh/guide"):
            r = meshnet.handle_get(p); b = r[1].decode() if isinstance(r[1], bytes) else str(r[1])
            self.assertEqual(r[0], 200, p); self.assertNotIn('href="/mesh/chat', b, p); self.assertIn('href="/mesh/guide"', b, p)
    def test_href_off(self):
        for h in ["/#noise", "/live#jets", "https://blackout.network/sources", "https://www.blackout.network/scoring?x=1"]: self.assertTrue(D.href_off(h), h)
        for h in ["#s6", "/?intro=1", "https://x.com/live", "/wire", "/#wire", "mailto:a@b.c"]: self.assertFalse(D.href_off(h), h)
    def test_clean(self):
        h = '<p><a href="/wire">W</a> · <a href="/scoring">S</a> · <a href="/privacy">P</a></p>'
        self.assertEqual(D.clean(h), '<p><a href="/wire">W</a> · <a href="/privacy">P</a></p>')
    def test_unlisted_page_keeps_own_links(self):
        h = '<link rel="canonical" href="https://blackout.network/crime"><a href="/crime?place=X">x</a> · <a href="/sources">s</a> · <a href="/wire">w</a>'
        out = D.clean(h)
        self.assertIn('href="/crime?place=X"', out); self.assertNotIn('href="/sources"', out); self.assertIn('href="/wire"', out)
        self.assertNotIn('href="/crime', D.clean('<a href="/crime?place=X">x</a> · <a href="/wire">w</a>'))   # other pages: removed
        self.assertIn('"groups"', D.js_config())

class Menus(unittest.TestCase):
    def hrefs(self, h): return set(re.findall(r'<a\b[^>]*href="([^"]+)"', h))
    def check(self, h):
        for x in self.hrefs(h): self.assertFalse(D.href_off(x), x)
        for need in ("/wire", "/map", "/weather", "/grid", "/markets", "/newsletter", "https://x.com/BlkoutNtw", "https://www.youtube.com/@blkoutntw"):
            self.assertIn(need, self.hrefs(h))
        self.assertIn('data-m5-act="install"', h); self.assertIn('data-m5-act="notify"', h)
        self.assertIn("prefers-reduced-motion", h)
        self.assertNotRegex(h.lower(), r"#ffc21a|#c97b00")   # no yellow in the menu
    def test_sitenav_drawer(self):
        import sitenav; self.check(sitenav.header_html("threat"))
    def test_home_menu(self):
        import theme; h = theme._home_page_raw(); self.check(h)
        self.assertNotIn("location.replace('/live'", h)
    def test_wire_menu(self):
        import wire_v2; self.check(wire_v2.menu_html())
    def test_sitemap(self):
        import growth
        r = growth.handle_get("/sitemap.xml", {}); b = r[1].decode() if isinstance(r[1], bytes) else str(r[1])
        for loc in re.findall(r"<loc>https://blackout\.network(/[^<]*)</loc>", b): self.assertFalse(D.is_off(loc), loc)

class Server(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import server
        from http.server import ThreadingHTTPServer
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.H); cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
    @classmethod
    def tearDownClass(cls): cls.httpd.shutdown()
    def get(self, p):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        try: c.request("GET", p)
        except RuntimeError as e:   # another test module blocks sockets for the rest of the run; this file passes on its own
            raise unittest.SkipTest(str(e))
        r = c.getresponse(); b = r.read(); return r.status, r.getheader("Location"), b
    def test_302(self):
        for p in [x for x in ROUTES if x not in UNLISTED] + ["/LIVE?x=1", "/MESH/CHAT/"]:
            s, loc, _ = self.get(p); self.assertEqual((s, loc), (302, "/"), p)
    def test_unlisted_not_redirected(self):
        for p in ("/sources", "/crime"):
            s, loc, _ = self.get(p); self.assertNotEqual(loc, "/", p)
    def test_pages_have_no_dead_links(self):
        for p in ("/", "/privacy", "/tos"):
            s, _, b = self.get(p); self.assertLess(s, 500, p)
            if s == 200 and b"<html" in b[:4000].lower():
                self.assertIn(b"window.BN_OFF=", b)
                for x in re.findall(rb'<a\b[^>]*href="([^"]+)"', b): self.assertFalse(D.href_off(x.decode()), (p, x))

if __name__ == "__main__": unittest.main()
