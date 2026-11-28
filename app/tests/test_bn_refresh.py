"""Shared #293 Refresh fill button on every live data page (Matt Nov 27–28 2026)."""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _read(*parts):
    with open(os.path.join(APP, *parts), encoding="utf-8") as fh:
        return fh.read()

FILL = "linear-gradient(90deg,#FFE566"
MARKUP_BITS = ("bn-ref", "tl-ref-fill", "tl-ref-sheen", "tl-ref-lab-a", ">Refresh</span>")


class TestSharedRefreshAssets(unittest.TestCase):
    def test_css_is_the_293_fill(self):
        css = _read("static", "bn-refresh.css")
        self.assertIn(FILL, css)
        self.assertIn("#FF9A1A", css)
        self.assertIn("#FF5A3C", css)
        self.assertIn("#0B0D10", css)
        self.assertIn("--tl-ref-p", css)
        self.assertIn("@keyframes tlsheen", css)
        self.assertIn("prefers-reduced-motion", css)
        self.assertIn(".bn-has-ref .bn-tbar .bn-refresh", css)

    def test_js_tracks_real_stages_and_skips_99(self):
        js = _read("static", "bn-refresh.js")
        self.assertIn("W.BNRefresh", js)
        self.assertIn("tgt >= 100 && p >= 99", js)
        self.assertIn("Refresh ", js)
        self.assertIn("bind:", js)
        self.assertIn("prefers-reduced-motion", js)
        self.assertIn("shown >= 99", js)

    def test_routes_and_cache_bust(self):
        addons = _read("addons.py")
        files = _read("static_files.py")
        server = _read("server.py")
        self.assertIn('"/bn-refresh.css": "static_files"', addons)
        self.assertIn('"/bn-refresh.js": "static_files"', addons)
        self.assertIn("/bn-refresh.css", files)
        self.assertIn("bn-refresh|", server)


class TestPagesUseSharedButton(unittest.TestCase):
    def test_wire_uses_shared_assets_and_delegates(self):
        html_src = _read("wire_timeline.py")
        js = _read("wire_timeline_static", "app.js")
        self.assertIn("/bn-refresh.css", html_src)
        self.assertIn("/bn-refresh.js", html_src)
        self.assertIn('id="tl_ref"', html_src)
        self.assertIn("bn-has-ref", html_src)
        for bit in MARKUP_BITS:
            self.assertIn(bit, html_src)
        self.assertIn("BNRefresh.apply", js)
        self.assertIn("BNRefresh.stage", js)
        self.assertIn("function refresh", js)
        self.assertIn("fresh=1", js)

    def test_map_button_and_fresh_fetch(self):
        html_src = _read("signal_map.py")
        js = _read("signal_map_static", "map2.js")
        self.assertIn("/bn-refresh.css", html_src)
        self.assertIn("/bn-refresh.js", html_src)
        self.assertIn("bnm_ref", html_src)
        self.assertIn("bn-has-ref", html_src)
        self.assertIn("heat_payload(force=force)", html_src)
        self.assertIn('get("fresh"', html_src)
        self.assertIn("?fresh=1", js)
        self.assertIn("BNRefresh.bind", js)
        self.assertIn("window.bnRefreshPage", js)
        self.assertIn("refreshNow", js)

    def test_grid_button_and_fresh_fetch(self):
        html_src = _read("netmap.py")
        js = _read("netmap_static", "net.js")
        self.assertIn("/bn-refresh.css", html_src)
        self.assertIn("/bn-refresh.js", html_src)
        self.assertIn("nx_ref", html_src)
        self.assertIn("bn-has-ref", html_src)
        self.assertIn("force=force", html_src)
        self.assertIn('get("fresh"', html_src)
        self.assertIn("/api/netmap/data?fresh=1", js)
        self.assertIn("window.bnRefreshPage", js)
        self.assertIn("BNRefresh.bind", js)

    def test_weather_button_reloads_layers(self):
        html_src = _read("wxmap.py")
        js = _read("wxmap_static", "wx.js")
        self.assertIn("/bn-refresh.css", html_src)
        self.assertIn("/bn-refresh.js", html_src)
        self.assertIn("wx_ref", html_src)
        self.assertIn("bn-has-ref", html_src)
        self.assertIn("window.bnRefreshPage", js)
        self.assertIn("loadFrames(false)", js)
        self.assertIn("loadAlerts()", js)
        self.assertIn("loadStorms()", js)
        self.assertIn("BNRefresh.bind", js)

    def test_markets_replaces_old_button(self):
        html_src = _read("markets.py")
        js = _read("markets_static", "app.js")
        css = _read("markets_static", "app.css")
        self.assertIn("/bn-refresh.css", html_src)
        self.assertIn("/bn-refresh.js", html_src)
        self.assertIn('id="mk_ref"', html_src)
        self.assertIn("bn-ref", html_src)
        self.assertIn("tl-ref-fill", html_src)
        self.assertNotIn('class="mk-ref" id="mk_ref"', html_src)
        self.assertIn("window.bnRefreshPage", js)
        self.assertIn("BNRefresh.bind", js)
        self.assertIn("/api/markets/data", js)
        self.assertNotIn(".mk-ref span{display:none}", css)

    def test_live_pages_render_the_button(self):
        import signal_map, netmap, wxmap, markets, wire_timeline as W
        _, map_html, _ = signal_map.handle_get("/map", {})
        _, grid_html, _ = netmap.handle_get("/grid", {})
        _, wx_html, _ = wxmap.handle_get("/weather", {})
        code, wire_html, _ = W.handle_get("/wire", {})
        self.assertEqual(code, 200)
        self.assertIn('id="bnm_ref"', map_html)
        self.assertIn("tl-ref-fill", map_html)
        self.assertIn(">Refresh</span>", map_html)
        self.assertIn('id="nx_ref"', grid_html)
        self.assertIn("tl-ref-fill", grid_html)
        self.assertIn('id="wx_ref"', wx_html)
        self.assertIn("tl-ref-fill", wx_html)
        self.assertIn('id="tl_ref"', wire_html)
        self.assertIn("tl-ref-fill", wire_html)
        mk = markets.page_html() if hasattr(markets, "page_html") else None
        if mk is None and hasattr(markets, "page"):
            out = markets.page()
            mk = out[1] if isinstance(out, tuple) else out
        if mk:
            self.assertIn('id="mk_ref"', mk)
            self.assertIn("tl-ref-fill", mk)


class TestFreshBypassesCaches(unittest.TestCase):
    def test_heat_force_signature(self):
        import inspect, signal_map
        self.assertIn("force", inspect.signature(signal_map.heat_payload).parameters)

    def test_netmap_data_force_signature(self):
        import inspect, netmap
        self.assertIn("force", inspect.signature(netmap.data).parameters)
        self.assertIn("force", inspect.signature(netmap.swr).parameters)



class TestRefreshModes(unittest.TestCase):
    def setUp(self):
        import sitenav_ui as UI
        self.UI = UI
        UI.set_page_path("")

    def tearDown(self):
        self.UI.set_page_path("")

    def test_mode_table(self):
        UI = self.UI
        cases = {
            "/wire": "inpage", "/map": "inpage", "/grid": "inpage", "/weather": "inpage", "/markets": "inpage",
            "/people": "header", "/people/ada-lovelace": "header", "/mesh": "header", "/mesh/chat": "header",
            "/stats": "header", "/sources": "header", "/wire-classic": "header", "/grid/aws": "header",
            "/privacy": "off", "/tos": "off", "/terms": "off", "/cookies": "off", "/privacy-choices": "off",
            "/do-not-sell": "off", "/credits": "off", "/scoring": "off", "/about/scoring": "off",
            "/welcome": "off", "/ready": "off", "/report-status": "off", "/newsletter": "off",
            "/newsletter/sample": "off", "/social": "off", "/story/x": "off", "/mesh/guide": "off",
            "/sources/admin": "off", "/wire/deadbeefdeadbeef": "off", "/": "off", "/figures": "off",
        }
        for path, mode in cases.items():
            self.assertEqual(UI.refresh_mode(path), mode, path)

    def test_compact_markup(self):
        UI = self.UI
        html = UI.refresh_fill_btn("bn_hdr_ref", compact=True)
        self.assertIn("bn-ref-sm", html)
        self.assertIn('id="bn_hdr_ref"', html)
        self.assertIn("tl-ref-fill", html)
        self.assertIn(">Refresh</span>", html)
        self.assertIn("linear-gradient" if False else "tl-ref-sheen", html)
        css = _read("static", "bn-refresh.css")
        self.assertIn(".bn-ref.bn-ref-sm", css)
        js = _read("static", "bn-refresh.js")
        self.assertIn("headerRun", js)
        self.assertIn("bindHeader", js)

    def test_legal_pages_have_no_old_or_new_refresh_control(self):
        import sitenav
        UI = self.UI
        for path in ("/privacy", "/tos", "/cookies", "/credits", "/scoring", "/welcome"):
            UI.set_page_path(path)
            html = sitenav.header_html()
            self.assertNotIn("data-bn-refresh", html, path)
            self.assertNotIn('id="bn_hdr_ref"', html, path)
            self.assertNotIn("bn-rf-row", html, path)

    def test_header_pages_emit_compact_button(self):
        import sitenav
        UI = self.UI
        for path in ("/people", "/stats", "/sources", "/mesh"):
            UI.set_page_path(path)
            html = sitenav.header_html()
            self.assertIn('id="bn_hdr_ref"', html, path)
            self.assertIn("bn-ref-sm", html, path)
            self.assertIn("tl-ref-fill", html, path)
            self.assertNotIn("data-bn-refresh", html, path)

    def test_inpage_pages_do_not_also_get_header_button(self):
        import sitenav
        UI = self.UI
        for path in ("/wire", "/map", "/grid", "/weather", "/markets"):
            UI.set_page_path(path)
            html = sitenav.header_html()
            self.assertNotIn('id="bn_hdr_ref"', html, path)
            self.assertEqual(UI.refresh_btn(), "")

    def test_markets_nav_wraps_at_390(self):
        css = _read("markets_static", "app.css")
        self.assertIn(".mk-nav{flex-wrap:wrap", css)
        self.assertIn(".mk-navi{flex:1 1 100%", css)

    def test_people_and_netpages_force_signatures(self):
        import inspect, people, netpages, stats, meshnet
        self.assertIn("force", inspect.signature(people.index_payload).parameters)
        self.assertIn("force", inspect.signature(netpages.brief).parameters)
        self.assertIn("force", inspect.signature(netpages.data).parameters)
        self.assertIn("force", inspect.signature(stats.load).parameters)
        self.assertIn("force", inspect.signature(stats.public_json).parameters)
        self.assertIn("force", inspect.signature(meshnet.data).parameters)
        self.assertIn("force", inspect.signature(meshnet.public_feed).parameters)

    def test_sources_and_mesh_and_classic_hooks(self):
        self.assertIn("window.bnRefreshPage", _read("sources_static", "app.js"))
        self.assertIn("fresh=1", _read("sources_static", "app.js"))
        self.assertIn("id=\"sc_up\"", _read("sources.py"))
        self.assertIn("window.bnRefreshPage", _read("meshnet_static", "app.js"))
        self.assertIn("/api/mesh/nodes?fresh=1", _read("meshnet_static", "app.js"))
        self.assertIn("window.bnRefreshPage", _read("meshnet_static", "chat.js"))
        self.assertIn("/api/mesh/chat?fresh=1", _read("meshnet_static", "chat.js"))
        w2 = _read("wire_v2.py")
        self.assertIn("bn_hdr_ref", w2)
        self.assertIn("fresh=1", w2)
        self.assertIn("wc_up", w2)
        st = _read("stats.py")
        self.assertIn("st_up", st)
        self.assertIn("/api/stats?fresh=1", st)
        self.assertIn("id=\"st_yt_up\"", st)
        np = _read("netpages.py")
        self.assertIn("np_fetched", np)
        self.assertIn("brief?fresh=1", np)
        pe = _read("people.py")
        self.assertIn("/api/people/index?fresh=1", pe)
        self.assertIn("id=\"pf_up\"", pe)



if __name__ == "__main__":
    unittest.main()
