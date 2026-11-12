"""Meshtastic pages (meshnet.py) and the box-side collector's drop-off logic (tools/meshtastic/collect.py)."""
import json, os, subprocess, sys, tempfile, time, unittest
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
COLLECT = os.path.join(os.path.dirname(APP), "tools", "meshtastic", "collect.py")
import meshnet

def run_collect(nodes, now, state, out):
    src = os.path.join(os.path.dirname(state), "nodes.json")
    with open(src, "w") as f: json.dump(nodes, f)
    r = subprocess.run([sys.executable, COLLECT, "--src-file", src, "--now", str(now), "--state", state, "--out", out], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    with open(out) as f: return json.load(f)

def fleet(now, n, lat, lon, quiet=0, prefix=0, minutes_ago=5, silent_ago=180):
    out = {}
    for i in range(n):
        ago = silent_ago if i < quiet else minutes_ago
        out[str(prefix + i)] = {"longName": f"Long {i}", "shortName": f"N{i}", "hwModel": "RAK4631", "role": "CLIENT",
                                "latitude": int((lat + (i % 7) * 0.01) * 1e7), "longitude": int((lon + (i // 7) * 0.01) * 1e7), "seenBy": {"msh/US/FL": int(now - ago * 60)}}
    return out

class Pages(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); meshnet.DATA = os.path.join(self.d, "mesh_nodes.json"); meshnet._C.update(mt=None, v=None)
    def test_pages_render_without_data(self):
        for p in ("/mesh", "/mesh/chat", "/mesh/guide"):
            code, body, ct = meshnet.handle_get(p, {})
            self.assertEqual(code, 200); self.assertTrue(ct.startswith("text/html"))
            h = body.decode()
            self.assertIn('id="bn-menu"', h)                     # shared header + main menu
            self.assertNotIn("tile.openstreetmap.org", h)
            for bad in ("verified", "BREAKING", "before the news"): self.assertNotIn(bad, h)
        self.assertIn("Waiting for the first sync", meshnet.handle_get("/mesh", {})[1].decode())
    def test_guide_cites_official_docs(self):
        h = meshnet.handle_get("/mesh/guide", {})[1].decode()
        for u in ("meshtastic.org/docs/configuration/radio/lora/", "meshtastic.org/docs/faq/", "meshtastic.org/docs/configuration/radio/channels/",
                  "meshtastic.org/docs/configuration/radio/power/", "902–928 MHz", "97.313(j)", "/tos#acknowledgments"):
            self.assertIn(u, h)
    def test_white_label_no_visible_brand(self):
        import re as _re
        for path in ("/mesh", "/mesh/chat", "/mesh/guide"):
            h = meshnet.handle_get(path, {})[1].decode()
            vis = _re.sub(r"<script.*?</script>|<style.*?</style>", " ", h, flags=_re.S)
            vis = _re.sub(r"<[^>]+>", " ", vis)
            self.assertNotIn("meshtastic", vis.lower(), path)
            self.assertNotRegex(vis.lower(), r"\blora\b", path)
            self.assertIn('href="/tos#acknowledgments"', h, path)
    def test_tos_acknowledgments(self):
        import legal
        h = legal.handle_get("/tos", {})[1].decode()
        self.assertIn('id="acknowledgments"', h)
        for t in ("Meshtastic® is a registered trademark of Meshtastic LLC. Meshtastic software components are released under various licenses",
                  "not affiliated with or endorsed by the Meshtastic project", "gpl-3.0", "/api/mesh/build_lib.sh", "/api/mesh/LICENSES.txt", "MeshMap.net", "OpenStreetMap contributors"):
            self.assertIn(t, h)
        self.assertEqual(meshnet.handle_get("/api/mesh/build_lib.sh", {})[0], 200)
    def test_chat_page_support_notice(self):
        h = meshnet.handle_get("/mesh/chat", {})[1].decode()
        self.assertIn("Chrome or Edge", h); self.assertIn("apps.apple.com/us/app/meshtastic/id1586432531", h); self.assertIn('maxlength="200"', h)
    def test_signal_is_capped_single_source(self):
        with open(meshnet.DATA, "w") as f: json.dump({"feed": {"ok": True, "baseline_ready": True}, "signals": [{"region": "area:cfl", "name": "x", "rank": 9}]}, f)
        s = meshnet.handle_get("/api/mesh/signal", {})[1]
        self.assertTrue(s["single_source"]); self.assertEqual(s["signals"][0]["rank"], 5); self.assertEqual(s["signals"][0]["list"], "watchlist")
        self.assertFalse(s["signals"][0]["confirmed"])
    def test_signal_empty_when_feed_stale(self):
        with open(meshnet.DATA, "w") as f: json.dump({"feed": {"ok": False}, "signals": [{"region": "a", "rank": 4}]}, f)
        self.assertEqual(meshnet.handle_get("/api/mesh/signal", {})[1]["signals"], [])
    def test_public_feed_off_by_default(self):
        os.environ.pop("BN_MESH_PUBLIC_FEED", None)
        d = meshnet.handle_get("/api/mesh/chat", {})[1]
        self.assertFalse(d["enabled"]); self.assertEqual(d["messages"], [])
    def test_masking(self):
        self.assertEqual(meshnet._clean("mail me a@b.com or 407-555-0123"), "mail me [email hidden] or [number hidden]")
    def test_static_files(self):
        for f in ("app.js", "app.css", "device.js", "chat.js", "share.js", "grid-panel.js", "lib.js", "LICENSES.txt"):
            self.assertEqual(meshnet.handle_get("/api/mesh/" + f, {})[0], 200, f)
        self.assertEqual(meshnet.handle_get("/api/mesh/../server.py", {})[0], 404)
    def test_share_row_has_push_to_mesh(self):
        import growth
        h = growth.share_html("https://blackout.network/wire/abc", "Headline (rank 7/10) via BLACKOUT.NETWORK")
        self.assertIn("bng-mesh", h); self.assertIn("Push to Mesh", h); self.assertIn(" hidden ", h.split("bng-mesh")[1][:20] + " ")
    def test_menu_has_mesh(self):
        import sitenav
        h = sitenav.header_html("@mesh")
        self.assertIn('href="/mesh"', h); self.assertIn('href="/mesh/guide"', h)

class Collector(unittest.TestCase):
    def test_dropoff_flags_after_baseline_and_persist(self):
        d = tempfile.mkdtemp(); st = os.path.join(d, "state.json"); out = os.path.join(d, "out.json")
        now = 1_800_000_000
        cfl = (28.70, -81.33); other = (40.73, -73.95)
        for k in range(40):   # 40 healthy samples (> 6 h baseline)
            o = run_collect({**fleet(now, 30, *cfl), **fleet(now, 150, *other, prefix=1000)}, now, st, out); now += 600
        self.assertTrue(o["feed"]["baseline_ready"]); self.assertEqual(o["signals"], [])
        r = {x["id"]: x for x in o["regions"]}; self.assertEqual(r["area:cfl"]["regular"], 30)
        # 20 of 30 Central Florida nodes go quiet; New York stays up
        o = run_collect({**fleet(now, 30, *cfl, quiet=20), **fleet(now, 150, *other, prefix=1000)}, now, st, out); now += 600
        self.assertEqual(o["signals"], [])                                   # first sample: forming, not yet flagged
        self.assertEqual({x["id"]: x for x in o["regions"]}["area:cfl"]["status"], "forming")
        o = run_collect({**fleet(now, 30, *cfl, quiet=20), **fleet(now, 150, *other, prefix=1000)}, now, st, out)
        ids = [s["region"] for s in o["signals"]]
        self.assertIn("area:cfl", ids); self.assertNotIn("area:nyc", ids)
        for s in o["signals"]:
            self.assertLessEqual(s["rank"], 5); self.assertTrue(s["single_source"]); self.assertEqual(s["list"], "watchlist")
        self.assertNotIn("Long", json.dumps(o["nodes"]))                       # no long names in the public file
    def test_feed_guard_suppresses_global_drop(self):
        d = tempfile.mkdtemp(); st = os.path.join(d, "state.json"); out = os.path.join(d, "out.json"); now = 1_800_000_000
        for k in range(40): run_collect({**fleet(now, 30, 28.7, -81.33), **fleet(now, 150, 40.73, -73.95, prefix=1000)}, now, st, out); now += 600
        for k in range(3):
            o = run_collect({**fleet(now, 30, 28.7, -81.33, quiet=25), **fleet(now, 150, 40.73, -73.95, quiet=125, prefix=1000)}, now, st, out); now += 600
        self.assertFalse(o["feed"]["ok"]); self.assertEqual(o["signals"], [])

if __name__ == "__main__":
    unittest.main()
