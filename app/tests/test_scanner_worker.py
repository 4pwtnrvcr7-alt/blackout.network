"""Offline tests for the Render scanner worker (Nov 23 2026).

No network, no real scanner run, no secrets printed.
"""
import gzip, hashlib, hmac, io, json, os, sqlite3, sys, tarfile, tempfile, time, unittest

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
import scanner_worker as W


def _tar(files, meta=None):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        raw = json.dumps(meta or {"part": "bulk", "secrets": {"newsletter_secret": "SHOULD_NOT_BE_APPLIED"}}).encode()
        ti = tarfile.TarInfo("__meta__.json"); ti.size = len(raw); tf.addfile(ti, io.BytesIO(raw))
        for name, data in files.items():
            ti = tarfile.TarInfo(name); ti.size = len(data); tf.addfile(ti, io.BytesIO(data))
    return buf.getvalue()


def _db_bytes():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        c = sqlite3.connect(path)
        c.execute("CREATE TABLE t(id INTEGER)"); c.execute("INSERT INTO t VALUES (1)"); c.commit(); c.close()
        with open(path, "rb") as fh: return fh.read()
    finally:
        os.unlink(path)


class Sign(unittest.TestCase):
    def test_sign_matches_site_formula(self):
        cl = W.Client("https://blackout.network", "s" * 32)
        body = b"hello"
        h = cl.sign("POST", "/internal/rt/push", body)
        self.assertIn("X-BN-Ts", h)
        self.assertIn("X-BN-Sig", h)
        want = hmac.new(
            ("s" * 32).encode(),
            f"{h['X-BN-Ts']}\nPOST\n/internal/rt/push\n{hashlib.sha256(body).hexdigest()}".encode(),
            hashlib.sha256,
        ).hexdigest()
        self.assertEqual(h["X-BN-Sig"], want)

    def test_get_export_path_includes_query(self):
        cl = W.Client("https://blackout.network", "s" * 32)
        path = "/internal/sync/export?part=bulk"
        h = cl.sign("GET", path, b"")
        want = hmac.new(
            ("s" * 32).encode(),
            f"{h['X-BN-Ts']}\nGET\n{path}\n{hashlib.sha256(b'').hexdigest()}".encode(),
            hashlib.sha256,
        ).hexdigest()
        self.assertEqual(h["X-BN-Sig"], want)

    def test_rejects_non_https(self):
        with self.assertRaises(ValueError):
            W.Client("http://evil.example", "s" * 32)


class Seed(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bnw-")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_extracts_only_allowed_dbs_and_ignores_secrets(self):
        blob = _tar({
            "blackout.db": _db_bytes(),
            "geo.db": _db_bytes(),
            "votes.db": _db_bytes(),
            "../escape.db": _db_bytes(),
            "/tmp/abs.db": _db_bytes(),
        })
        written = W.extract_seed_tar(blob, self.tmp)
        self.assertEqual(set(written), {"blackout.db", "geo.db"})
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "blackout.db")))
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "geo.db")))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "votes.db")))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "escape.db")))
        # secrets in meta must not be written anywhere in dest
        for root, dirs, files in os.walk(self.tmp):
            for n in files:
                self.assertNotIn("secret", n.lower())
                with open(os.path.join(root, n), "rb") as fh:
                    data = fh.read()
                self.assertNotIn(b"SHOULD_NOT_BE_APPLIED", data)

    def test_rejects_corrupt_db(self):
        blob = _tar({"blackout.db": b"not a sqlite file"})
        with self.assertRaises(ValueError):
            W.extract_seed_tar(blob, self.tmp)

    def test_safe_member(self):
        self.assertEqual(W._safe_member("blackout.db"), "blackout.db")
        self.assertIsNone(W._safe_member("../blackout.db"))
        self.assertIsNone(W._safe_member("foo/blackout.db"))
        self.assertIsNone(W._safe_member("votes.db"))


class StatusAndEnv(unittest.TestCase):
    def test_env_report_never_includes_secret_value(self):
        old = os.environ.get("BN_SYNC_SECRET")
        os.environ["BN_SYNC_SECRET"] = "super-secret-value-32chars-minxx"
        try:
            r = W.env_report()
            blob = json.dumps(r)
            self.assertNotIn("super-secret-value-32chars-minxx", blob)
            self.assertEqual(r["BN_SYNC_SECRET"], "set")
            self.assertTrue(W.secret_ok())
        finally:
            if old is None:
                os.environ.pop("BN_SYNC_SECRET", None)
            else:
                os.environ["BN_SYNC_SECRET"] = old

    def test_secret_missing(self):
        old = os.environ.pop("BN_SYNC_SECRET", None)
        try:
            self.assertFalse(W.secret_ok())
            self.assertEqual(W.env_report()["BN_SYNC_SECRET"], "missing")
        finally:
            if old is not None:
                os.environ["BN_SYNC_SECRET"] = old

    def test_write_status_has_last_scan_field_and_no_secret(self):
        tmp = tempfile.mkdtemp(prefix="bnws-")
        old_data, old_status = W.DATA, W.STATUS_PATH
        W.DATA = tmp
        W.STATUS_PATH = os.path.join(tmp, "worker_status.json")
        os.environ["BN_SYNC_SECRET"] = os.environ.get("BN_SYNC_SECRET") or ""
        try:
            info = W.write_status(note="ok")
            self.assertIn("last_scan", info)
            self.assertEqual(info["node"], "render-scanner-worker")
            with open(W.STATUS_PATH) as fh:
                raw = fh.read()
            self.assertNotIn("BN_SYNC_SECRET", raw)
            self.assertIn("last_scan", raw)
        finally:
            W.DATA, W.STATUS_PATH = old_data, old_status
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_default_interval_is_nine_minutes(self):
        self.assertEqual(W.INTERVAL_MIN, 9)


class DedupeContract(unittest.TestCase):
    def test_site_upsert_is_by_primary_key(self):
        # The public node (app/realtime.py RULES) upserts alerts by id and
        # clusters by cluster_id, updating only when the incoming row is newer.
        # Re-import the live module if present so a typo in this comment stays honest.
        import realtime
        self.assertEqual(realtime.RULES["alerts"][0], "id")
        self.assertEqual(realtime.RULES["clusters"][0], "cluster_id")
        self.assertIn("last_seen", realtime.RULES["alerts"][2])
        self.assertIs(realtime.RULES["scans"][2], None)


if __name__ == "__main__":
    unittest.main()
