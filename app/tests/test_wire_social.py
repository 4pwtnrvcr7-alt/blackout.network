import json
import os
import sqlite3
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import wire_social as WS  # noqa: E402

BS = json.dumps([{"source": "Bluesky firehose", "url": "https://bsky.app/profile/x/post/1"}])


class SocialGate(unittest.TestCase):
    def ok(self, t, k="cyber"):
        return WS.verdict(t, k)[0]

    def test_keeps_concrete_events(self):
        self.assertTrue(self.ok("CVE-2026-135202 air-wp-sync (CVSS Score 9.8) #WordPress plugin #vulnerability allows remote code execution"))
        self.assertTrue(self.ok("GMO Pepabo data breach: 510,000 records (Japan) Exposed: Passwords and emails"))
        self.assertTrue(self.ok("Korea Post confirmed a data breach affecting at least 113,000 customers after a cyberattack"))
        self.assertTrue(self.ok("M5.4 earthquake strikes near Tonga, USGS reports, no tsunami threat issued", "quake"))

    def test_drops_chatter(self):
        junk = [
            ("Because all signs point to that. I expect that even if the far right gets pried out of power it goes on", "other"),
            ("definitely agreed here and that's where it gets really ethically bad, given the ongoing copyright lawsuits", "other"),
            ("#trends today for donald trump broncos steelers & hackers breach Click/Tap below to read more", "cyber"),
            ("I think I'm coming to an acceptance that it is, in fact, an AI fueled techno hellscape of hacks", "other"),
            ("SpaceX putting one million data centers in space sounds like a flex unless you read the fine print", "other"),
            ("Is it me or it seems pretty clear the U.S. is under a sustained cyberattack from several countries?", "cyber"),
            ("I think it is China that is hacking all of these government networks again and again.", "cyber"),
            ("Ironic all these hacks happen after trump meets with the others within the axis of evil.", "cyber"),
            ("Hacked", "cyber"),
            ("AI NEWS Nov.27.26 Story 1: LA schools block Google AI features Story 2: OpenAI fixes GPT-6.2 billing error", "cyber"),
            ("cyber Monday?? sexting hackers everywhere today", "cyber"),
            ("Is Pedostan behind all the hacks?", "cyber"),
            ("Just having read Steven Levy's Hackers: Heroes of the Computer Revolution and loving the culture", "cyber"),
        ]
        for t, k in junk:
            self.assertFalse(WS.verdict(t, k)[0], t)

    def test_other_category_always_dropped(self):
        self.assertFalse(WS.verdict("CVE-2026-135202 air-wp-sync (CVSS Score 9.8) plugin allows remote code execution", "other")[0])

    def test_only_social_only_rows(self):
        self.assertTrue(WS.junk_row("lol", "cyber", BS))
        mixed = json.dumps([{"source": "Bluesky firehose"}, {"source": "Reuters"}])
        self.assertFalse(WS.junk_row("lol", "cyber", mixed))
        self.assertFalse(WS.junk_row("lol", "cyber", json.dumps([{"source": "USGS"}])))

    def test_hide_mode(self):
        os.environ["BN_WIRE_SOCIAL_GATE"] = "hide"
        try:
            self.assertFalse(WS.verdict("GMO Pepabo data breach: 510,000 records (Japan) Exposed: Passwords and emails", "cyber")[0])
        finally:
            os.environ.pop("BN_WIRE_SOCIAL_GATE")

    def test_wire_row_gate(self):
        os.environ.setdefault("NEWSLETTER_NO_WORKER", "1")
        import wire_timeline as WT
        c = sqlite3.connect(":memory:")
        c.row_factory = sqlite3.Row
        c.execute("create table t(id, title, category, links)")
        c.execute("insert into t values('a','Because all signs point to that. I expect that even if the far right','other',?)", (BS,))
        c.execute("insert into t values('b','GMO Pepabo data breach: 510,000 records (Japan) Exposed: Passwords and emails','cyber',?)", (BS,))
        c.execute("insert into t values('c','Because all signs point to that','other',?)", (json.dumps([{"source": "Reuters"}]),))
        a, b, cc = [WT._social_junk(r) for r in c.execute("select * from t order by id")]
        self.assertTrue(a)
        self.assertFalse(b)
        self.assertFalse(cc)


if __name__ == "__main__":
    unittest.main()
