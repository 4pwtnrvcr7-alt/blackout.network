"""pt2098u: per-region cloud status and Cloudflare edge cities on /grid. Offline: parsers run on small fixtures shaped like the live feeds."""
import json, os, sys, time, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import netcloud as C

def aws_event(region, status="3", age_days=0, name="Multiple services"):
    ts = int(time.time()) - age_days * 86400
    return dict(date=str(ts), arn=f"arn:aws:health:{region}::event/X/Y/Z", region_name=region, status=status, service_name=name, summary="Region Availability",
                event_log=[dict(summary="s", message="We are investigating issues.", status=1, timestamp=ts)])

class Cloud(unittest.TestCase):
    def test_aws_quiet_feed_is_green_for_every_region_it_covers(self):
        r = C.aws_regions("[]")
        self.assertEqual(len(r), len(C.AWS_REGIONS)); self.assertTrue(all(v["level"] == 0 for v in r.values()))
    def test_aws_event_marks_only_its_region(self):
        r = C.aws_regions(json.dumps([aws_event("me-south-1", age_days=200)]))
        self.assertEqual(r["me-south-1"]["level"], 3); self.assertIn("Open since", r["me-south-1"]["status"])
        self.assertEqual(r["us-east-1"]["level"], 0)
    def test_aws_old_informational_event_is_degraded_not_outage(self):
        r = C.aws_regions(json.dumps([aws_event("us-east-1", status="2", age_days=10)]))
        self.assertEqual(r["us-east-1"]["level"], 1); self.assertIn("Long-running", r["us-east-1"]["status"])
    def test_aws_decodes_utf16(self):
        self.assertEqual(C.decode("[]".encode("utf-16")), "[]"); self.assertEqual(C.decode(b"\xef\xbb\xbf[]"), "[]")
    def test_azure_empty_feed_green(self):
        x = '<rss><channel><title>Azure Status</title></channel></rss>'
        self.assertTrue(all(v["level"] == 0 for v in C.azure_regions(x).values()))
    def test_azure_region_named_in_title_not_substring_of_longer_name(self):
        x = '<rss><channel><item><title>Storage - East US 2</title></item><item><title>Compute - South Central US</title></item></channel></rss>'
        r = C.azure_regions(x)
        self.assertEqual(r["East US"]["level"], 0, "East US 2 must not mark East US")
        self.assertEqual(r["South Central US"]["level"], 1); self.assertEqual(r["Central US"]["level"], 0, "South Central US must not mark Central US")
    def test_azure_item_with_no_region_is_degraded_everywhere_not_green(self):
        x = '<rss><channel><item><title>Azure Portal sign-in issues</title></item></channel></rss>'
        self.assertTrue(all(v["level"] == 1 for v in C.azure_regions(x).values()))
    def test_gcp_open_incident_region_from_text_and_closed_ignored(self):
        d = [dict(end=None, external_desc="Elevated errors in us-central1", status_impact="SERVICE_DISRUPTION", most_recent_update=dict(affected_locations=[], text="")),
             dict(end="2026-01-01T00:00:00+00:00", external_desc="old in europe-west1", status_impact="SERVICE_OUTAGE", most_recent_update=dict(affected_locations=[]))]
        r = C.gcp_regions(json.dumps(d))
        self.assertEqual(r["us-central1"]["level"], 1); self.assertEqual(r["europe-west1"]["level"], 0); self.assertEqual(r["us-east4"]["level"], 0)
    def test_oci_only_regions_in_feed_and_incident_marks_region(self):
        rep = [dict(regionCanonicalName="us-ashburn-1", serviceHealthReports=[dict(serviceName="Compute", serviceStatus="NormalPerformance", incidents=[])]),
               dict(regionCanonicalName="uk-london-1", serviceHealthReports=[dict(serviceName="Compute", serviceStatus="PartialOutage", incidents=[])])]
        r = C.oci_regions(json.dumps(dict(regionHealthReports=rep)))
        self.assertEqual(set(r), {"us-ashburn-1", "uk-london-1"}); self.assertEqual(r["us-ashburn-1"]["level"], 0); self.assertEqual(r["uk-london-1"]["level"], 3)
    def test_cloudflare_pops(self):
        d = dict(components=[dict(name="Atlanta, United States - (ATL)", status="partial_outage"), dict(name="Amsterdam, Netherlands - (AMS)", status="operational"),
                             dict(name="CDN/Cache", status="operational"), dict(name="Nowhere - (ZZZ)", status="operational"), dict(name="Sydney, Australia - (SYD)", status="under_maintenance")])
        p = {x["code"]: x for x in C.cloudflare_pops(json.dumps(d))}
        self.assertEqual(set(p), {"ATL", "AMS", "SYD"}); self.assertEqual(p["ATL"]["level"], 1); self.assertEqual(p["AMS"]["level"], 0)
        self.assertTrue(-90 < p["ATL"]["lat"] < 90)
    def test_dead_feed_is_grey_never_green(self):
        def http(u, **k): raise OSError("down")
        C._LAST.clear()
        m, src = C.fetch(http)
        self.assertTrue(m and all(x["level"] == -1 for x in m)); self.assertTrue(all(not s["ok"] for s in src))
    def test_blinking_feed_keeps_last_good_reading_for_30_minutes(self):
        good = {"https://health.aws.amazon.com/public/currentevents": json.dumps([aws_event("me-south-1")]).encode()}
        def ok(u, **k):
            if u in good: return good[u]
            raise OSError("down")
        C._LAST.clear(); m, _ = C.fetch(ok)
        self.assertEqual([x["level"] for x in m if x["name"] == "Middle East (Bahrain)"], [3])
        def dead(u, **k): raise OSError("down")
        m, src = C.fetch(dead)
        self.assertEqual([x["level"] for x in m if x["name"] == "Middle East (Bahrain)"], [3], "kept")
        self.assertTrue(next(s for s in src if s["id"] == "aws")["ok"])
        C._LAST["aws"] = (time.time() - C.KEEP_S - 5, C._LAST["aws"][1]); m, _ = C.fetch(dead)
        self.assertEqual([x["level"] for x in m if x["name"] == "Middle East (Bahrain)"], [-1], "stale reading is dropped to grey")
    def test_notes_say_why_dc_and_towers_are_grey(self):
        self.assertIn("no free", C.NOTES["dc"]); self.assertIn("DIRS", C.NOTES["towers"])
if __name__ == "__main__": unittest.main()
