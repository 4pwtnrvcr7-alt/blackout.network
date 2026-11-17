"""crime_news: real local crime reports layer (Nov 17 2026). Offline: network calls are stubbed."""
import os, sys, unittest, tempfile
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import crime_news as CN

def rss(items):
    x = "".join(f"<item><title>{t}</title><link>{u}</link><pubDate>{format_datetime(d)}</pubDate><source url=\"{su}\">{sn}</source></item>" for t, u, d, su, sn in items)
    return f"<?xml version='1.0'?><rss><channel>{x}</channel></rss>"

NOW = datetime.now(timezone.utc)
GN = rss([("Sanford man arrested after shooting on 13th Street - WESH", "https://news.google.com/a1", NOW - timedelta(days=1), "https://www.wesh.com", "WESH"),
          ("Sanford man arrested after shooting on 13th Street - WFTV", "https://news.google.com/a2", NOW - timedelta(days=1), "https://www.wftv.com", "WFTV"),   # dupe
          ("Sanford Police Charge Two Men After Jewelry Store Robbery - Hoodline", "https://news.google.com/a3", NOW - timedelta(days=2), "https://hoodline.com", "Hoodline"),   # not a local outlet
          ("Sanford honors veterans with ceremony - WKMG", "https://news.google.com/a4", NOW - timedelta(days=2), "https://www.clickorlando.com", "WKMG"),   # not crime
          ("Mugshots: Seminole County arrests this week - WFTV", "https://news.google.com/a5", NOW - timedelta(days=2), "https://www.wftv.com", "WFTV"),   # no mugshots
          ("Oviedo deputies investigate deadly stabbing - FOX 35 Orlando", "https://news.google.com/a6", NOW - timedelta(days=3), "https://www.fox35orlando.com", "FOX 35 Orlando"),
          ("Old Sanford robbery case - WESH", "https://news.google.com/a7", NOW - timedelta(days=60), "https://www.wesh.com", "WESH")])   # too old
SCSO = ('<h4>Deputies arrest burglary suspect in Lake Mary</h4> ' + (NOW - timedelta(days=4)).astimezone(CN.ETZ).strftime("%B %-d, %Y") +
        ' - text... </br> <a href="https://www.seminolesheriff.org/output/mediareports/1/x.pdf">Read more</a>')

class T(unittest.TestCase):
    def setUp(self):
        CN._mem.clear(); CN.CACHE_DIR = tempfile.mkdtemp(); self._g = CN._get
        CN._get = lambda u, timeout=5: SCSO if "seminolesheriff" in u else (GN if "news.google" in u else "<rss></rss>")
        self.a = CN.area_for({"kind": "zip", "label": "Sanford, FL 32771", "fips": "12117", "st": "FL", "cc": "US"})
    def tearDown(self): CN._get = self._g; os.environ.pop(CN.FLAG, None)
    def test_items(self):
        d = CN.reports(self.a); ts = [x["title"] for x in d["items"]]
        self.assertIn("Sanford man arrested after shooting on 13th Street", ts)
        self.assertEqual(sum("13th Street" in t for t in ts), 1)            # deduped
        self.assertIn("Oviedo deputies investigate deadly stabbing", ts)
        self.assertIn("Deputies arrest burglary suspect in Lake Mary", ts)   # official release
        for bad in ("Hoodline", "veterans", "Mugshots", "Old Sanford"): self.assertFalse(any(bad in t for t in ts), bad)
        for x in d["items"]: self.assertTrue(x["url"].startswith("https://") and x["date"] and x["source"] and x["place"])
    def test_cache_and_fail(self):
        d1 = CN.reports(self.a); CN._get = lambda *a, **k: (_ for _ in ()).throw(OSError("down"))
        self.assertEqual(CN.reports(self.a)["items"], d1["items"])        # fresh cache
        CN._mem.clear(); CN.CACHE_DIR = tempfile.mkdtemp()
        self.assertEqual(CN.reports(self.a)["items"], [])                 # nothing cached + all down -> [] (stats only)
    def test_flag_and_scope(self):
        os.environ[CN.FLAG] = "0"; self.assertEqual(CN.reports(self.a)["items"], [])
        self.assertIsNone(CN.area_for({"kind": "country", "cc": "GB", "label": "UK"}))
        self.assertIsNone(CN.area_for({"kind": "state", "cc": "US", "st": "FL", "label": "Florida"}))

class V4(unittest.TestCase):
    def test_newsletter_items_render(self):
        import newsletter_v4 as NV4
        src = open(NV4.__file__).read()
        self.assertIn('cr.get("items")', src)

if __name__ == "__main__": unittest.main()
