import os, sys, unittest
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["NEWSLETTER_SECRET"] = "x" * 40
import newsletter_wx as X, newsletter_v4 as V4, nlwx

T0 = datetime(2026, 11, 27, 20, 0, tzinfo=timezone(timedelta(hours=-5)))
def hours(n=24, **kw):
    H = []
    for i in range(n):
        t = T0 + timedelta(hours=i)
        H.append({"t": t.isoformat(), "h": t.hour, "temp": 58 - i // 3, "rh": 90 - i, "wind": 5, "dir": 11, "pop": 0, "day": 6 <= t.hour < 18, "text": "Mostly Cloudy"})
    for k, v in kw.items():
        for h in H: h[k] = v
    return H
def wx(**kw):
    w = {"scope": "local", "label": "Sanford, FL 32771", "fc": {"days": [{"name": "Today", "hi": 63, "lo": 52, "pop": 0, "text": ""}], "unit": "F", "src": "National Weather Service", "url": "https://x"},
         "alerts": [], "alerts_ok": True, "nat_alerts": [], "storms": [], "lat": 28.81, "lon": -81.32,
         "hourly": {"hours": hours(), "tz": "America/New_York", "tzname": "EST", "src": "National Weather Service", "url": "https://forecast.weather.gov/x"}}
    w.update(kw); return w

class Verdict(unittest.TestCase):
    now = T0.astimezone(timezone.utc)
    def test_clear(self):
        v = X.storm_verdict(wx(), 28.81, -81.32, self.now)
        self.assertEqual(v["state"], "clear"); self.assertEqual(v["line"], "No major storms headed your way in the next 24 hours.")
    def test_storm_names_alert_and_time(self):
        a = {"event": "Winter Storm Warning", "onset": (self.now + timedelta(hours=2)).isoformat(), "until": (self.now + timedelta(hours=20)).isoformat(), "red": False, "storm": True}
        v = X.storm_verdict(wx(alerts=[a]), 28.81, -81.32, self.now)
        self.assertEqual(v["state"], "storm"); self.assertTrue(v["line"].startswith("Major storm headed your way: Winter Storm Warning"))
        self.assertIn("until", v["detail"]); self.assertIn("National Weather Service", v["detail"]); self.assertFalse(v["red"])
    def test_red_only_when_flagged(self):
        a = {"event": "Tornado Warning", "onset": self.now.isoformat(), "until": (self.now + timedelta(hours=1)).isoformat(), "red": True, "storm": True}
        self.assertTrue(X.storm_verdict(wx(alerts=[a]), 28.81, -81.32, self.now)["red"])
    def test_heat_is_not_a_storm(self):
        a = {"event": "Extreme Heat Warning", "onset": self.now.isoformat(), "until": self.now.isoformat(), "red": False, "storm": False}
        self.assertEqual(X.storm_verdict(wx(alerts=[a]), 28.81, -81.32, self.now)["state"], "clear")
    def test_alert_beyond_24h_is_looking_ahead(self):
        a = {"event": "Winter Storm Watch", "onset": (self.now + timedelta(hours=40)).isoformat(), "until": (self.now + timedelta(hours=60)).isoformat(), "red": False, "storm": True}
        v = X.storm_verdict(wx(alerts=[a]), 28.81, -81.32, self.now)
        self.assertEqual(v["state"], "clear"); self.assertIn("Looking ahead: Winter Storm Watch", v["ahead"])
    def test_failed_feed_never_says_all_clear(self):
        v = X.storm_verdict(wx(alerts_ok=False), 28.81, -81.32, self.now)
        self.assertEqual(v["state"], "unknown"); self.assertNotIn("No major storms", v["line"])
    def test_nhc_storm_only_when_close(self):
        near = {"name": "Hurricane Test", "mph": 90, "lat": 27.0, "lon": -80.0, "url": "https://nhc"}
        far = {"name": "Hurricane Far", "mph": 90, "lat": 15.0, "lon": -50.0, "url": "https://nhc"}
        self.assertEqual(X.storm_verdict(wx(storms=[far]), 28.81, -81.32, self.now)["state"], "clear")
        v = X.storm_verdict(wx(storms=[near]), 28.81, -81.32, self.now)
        self.assertEqual(v["state"], "storm"); self.assertIn("miles away", v["detail"])
    def test_national_scope_and_non_us_have_no_verdict(self):
        self.assertIsNone(X.storm_verdict({"scope": "national"}, None, None))
        self.assertIsNone(X.storm_verdict(wx(fc={"days": [], "unit": "C"}), 1, 1))

class Strip(unittest.TestCase):
    def test_series_and_png(self):
        s = nlwx.series_from_hours({"hours": hours(), "tzname": "EST"}, [])
        png = nlwx.render(s)
        self.assertTrue(png.startswith(b"\x89PNG")); self.assertLess(len(png), 110_000)
        from PIL import Image; import io
        im = Image.open(io.BytesIO(png)); self.assertEqual(im.size[0], 1200)
    def test_png_handles_missing_values_and_calm(self):
        H = hours(); H[3]["rh"] = None; H[4]["wind"] = None; H[5]["dir"] = None; H[6]["wind"] = 0
        self.assertTrue(nlwx.render(nlwx.series_from_hours({"hours": H, "tzname": "EST"}, [])).startswith(b"\x89PNG"))
    def test_signed_url_roundtrip_and_tamper(self):
        s = nlwx.series_from_hours({"hours": hours(), "tzname": "EST"}, [])
        u = nlwx.url(s, "https://blackout.network"); self.assertTrue(u.startswith("https://blackout.network/nlwx/") and u.endswith(".png"))
        path = u.replace("https://blackout.network", "")
        st, body, ct = nlwx.handle_get(path); self.assertEqual((st, ct), (200, "image/png")); self.assertTrue(body.startswith(b"\x89PNG"))
        tok, sig = path[len("/nlwx/"):-4].rsplit(".", 1)
        self.assertEqual(nlwx.handle_get(f"/nlwx/{tok}.{'0' * 20}.png")[0], 404)                    # bad signature
        self.assertEqual(nlwx.handle_get(f"/nlwx/{tok[:-2]}AA.{sig}.png")[0], 404)                   # tampered data
        self.assertEqual(nlwx.handle_get("/nlwx/zzzz.png")[0], 404)
    def test_no_secret_no_url(self):
        old = os.environ.pop("NEWSLETTER_SECRET")
        import newsletter as N; env0 = N.env; N.env = lambda: {}
        try:
            self.assertIsNone(nlwx.url(nlwx.series_from_hours({"hours": hours(), "tzname": "EST"}, []), "https://b"))
        finally:
            os.environ["NEWSLETTER_SECRET"] = old; N.env = env0
    def test_token_is_small(self):
        self.assertLess(len(nlwx.pack(nlwx.series_from_hours({"hours": hours(), "tzname": "EST"}, []))), 600)

class Sections(unittest.TestCase):
    issue = {"end": datetime(2026, 11, 27, 19, tzinfo=timezone(timedelta(hours=-5))), "slot": "evening", "loc_label": "Sanford, FL 32771"}
    def test_photo_pool_files_and_credits(self):
        P = V4.sec_pool()
        for k in ("storm", "rain", "snow", "clouds", "clear", "crime"): self.assertTrue(P.get(k), k)
        for ims in P.values():
            for im in ims:
                self.assertTrue(os.path.exists(os.path.join(os.path.dirname(V4.__file__), "theme_static", "media", im["name"] + ".b64")))
                self.assertIn(im["license"], ("Public domain", "CC0", "CC BY 2.0", "CC BY 3.0", "CC BY 4.0")); self.assertTrue(im["page"].startswith("https://commons.wikimedia.org/"))
    def test_weather_local_has_verdict_tiles_strip(self):
        w = wx(); iss = dict(self.issue, weather=w)
        html = "".join(V4._weather(iss, {"base_url": "https://blackout.network"}))
        self.assertIn("No major storms headed your way in the next 24 hours.", html)
        for lab in ("TEMPERATURE", "CHANCE OF RAIN", "WIND", "HUMIDITY"): self.assertIn(lab, html)
        self.assertIn("/nlwx/", html); self.assertIn("/bnt/media/nl", html)
        self.assertNotIn("FFC21A", html.upper())
    def test_weather_storm_line(self):
        now = datetime.now(timezone.utc)
        a = {"event": "Winter Storm Warning", "onset": now.isoformat(), "until": (now + timedelta(hours=9)).isoformat(), "red": False, "storm": True, "url": "https://x"}
        html = "".join(V4._weather(dict(self.issue, weather=wx(alerts=[a])), {"base_url": "https://blackout.network"}))
        self.assertIn("Major storm headed your way:", html); self.assertIn("Winter Storm Warning", html)
    def test_weather_falls_back_without_hourly(self):
        w = wx(); w.pop("hourly")
        html = "".join(V4._weather(dict(self.issue, weather=w), {"base_url": "https://blackout.network"}))
        self.assertIn("Sanford, FL 32771", html); self.assertNotIn("/nlwx/", html)
    def test_text_fallback(self):
        t = "\n".join(X.text_lines(wx()))
        self.assertIn("No major storms headed your way", t); self.assertIn("Chance of rain", t); self.assertIn("Humidity", t)
    def test_crime_header_items_and_bars(self):
        import newsletter as N
        cr = {"label": "Sanford, FL 32771", "url": "https://blackout.network/crime?place=x", "lines": ["County line."],
              "items": [{"title": "Headline", "url": "https://u", "date": "2026-11-21T21:12-05:00", "place": "Lake Mary", "source": "WESH"}],
              "rates": [{"name": "Seminole County", "v": 211, "p": 987, "year": 2025}, {"name": "Florida", "v": 245, "p": 1062, "year": 2025}, {"name": "United States", "v": 329, "p": 1546, "year": 2025}]}
        html = "".join(V4._crime(dict(self.issue, crime=cr), {"base_url": "https://blackout.network"}, N))
        self.assertIn("CRIME NEAR YOU", html); self.assertIn("Headline", html); self.assertIn("VIOLENT CRIME", html); self.assertIn("FBI figures for 2025", html)
        self.assertNotIn("County line.", html)   # the bars replace the sentence
        cr["rates"] = []
        self.assertIn("County line.", "".join(V4._crime(dict(self.issue, crime=cr), {"base_url": "https://blackout.network"}, N)))

if __name__ == "__main__":
    unittest.main()
