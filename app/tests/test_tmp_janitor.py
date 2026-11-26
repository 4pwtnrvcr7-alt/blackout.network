import os, sys, time, tempfile, unittest, importlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TmpJanitorTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(); self.state = os.path.join(self.root, "bn_state"); os.makedirs(os.path.join(self.state, "secrets"))
        os.environ.update(BN_TMP_ROOT=self.root, BN_STATE_DIR=self.state, BN_TMP_SOFT_MB="1", BN_TMP_TARGET_MB="0")
        import tmp_janitor; self.J = importlib.reload(tmp_janitor)

    def _f(self, rel, size, age=0):
        p = os.path.join(self.root, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f: f.write(b"x" * size)
        t = time.time() - age; os.utime(p, (t, t)); return p

    def test_trims_caches_and_stale_archives_keeps_dbs_and_secrets(self):
        old_tgz = self._f("bn_state/a.tgz", 10, age=3600); new_tgz = self._f("bn_state/b.tgz", 10)
        cache_old = self._f("bn-og-cache/x.png", 800_000, age=500); cache_new = self._f("bn_card_photo/y.jpg", 800_000)
        db = self._f("bn_small_places_1_2.db", 900_000); sec = self._f("bn_state/secrets/newsletter.env", 10, age=99999)
        man = self._f("bn_state/manifest.json", 10, age=99999); other = self._f("unrelated/z.bin", 10, age=99999)
        mb = self.J.sweep()
        self.assertFalse(os.path.exists(old_tgz)); self.assertTrue(os.path.exists(new_tgz))
        self.assertFalse(os.path.exists(cache_old)); self.assertFalse(os.path.exists(cache_new))
        for p in (db, sec, man, other): self.assertTrue(os.path.exists(p), p)
        self.assertLess(mb, 1.0)

    def test_under_soft_limit_keeps_caches(self):
        os.environ["BN_TMP_SOFT_MB"] = "100"; import tmp_janitor; J = importlib.reload(tmp_janitor)
        c = self._f("bn-og-cache/x.png", 1000, age=500); J.sweep(); self.assertTrue(os.path.exists(c))

    def test_thread_name_passes_render_guard(self):
        self.assertNotIn("loop", self.J._tmp_sweep.__name__.lower())

if __name__ == "__main__": unittest.main()
