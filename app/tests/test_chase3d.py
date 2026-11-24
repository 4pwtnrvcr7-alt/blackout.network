"""pt1842u: rocket chase camera (chase3d.js), lazy-loaded with three147.js from launches.js."""
import os, re, sys, unittest
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, APP)
STATIC = os.path.join(APP, "netmap_static")

def fns(name):
    return set(re.findall(r"function (\w+)\s*\(", open(os.path.join(STATIC, name), encoding="utf-8").read()))

class ChaseTest(unittest.TestCase):
    def test_served_and_lazy(self):
        import netmap, netpages
        code, body, ct = netmap.handle_get("/api/netmap/chase3d.js")
        self.assertEqual((code, ct), (200, "application/javascript"))
        html = netpages.handle_get("/grid", {})[1]
        self.assertIn("window.BN_CHASE3D=", html); self.assertNotIn('src="/api/netmap/chase3d.js', html)   # lazy, not on boot

    def test_no_duplicate_functions(self):
        mine = fns("chase3d.js")
        self.assertEqual(mine & fns("net.js"), set()); self.assertEqual(mine & fns("launches.js"), set())
        self.assertEqual(fns("launches.js") & fns("net.js"), set())

    def test_rules(self):
        js = open(os.path.join(STATIC, "chase3d.js"), encoding="utf-8").read()
        self.assertIn("Modeled trajectory, not telemetry", js); self.assertIn("The Space Devs Launch Library 2", js)
        low = re.sub(r"/\*.*?\*/", "", js.lower(), flags=re.S)
        self.assertNotIn("yellow", low); self.assertNotIn("<img", low)
        self.assertIn("OrbitControls", js); self.assertIn("ONE: T.TOUCH.ROTATE", js)
        lj = open(os.path.join(STATIC, "launches.js"), encoding="utf-8").read()
        self.assertIn("only the current event", lj); self.assertIn("lcChase(L", lj)

if __name__ == "__main__":
    unittest.main()
