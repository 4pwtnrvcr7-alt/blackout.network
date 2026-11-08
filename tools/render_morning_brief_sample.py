"""Render one Morning Brief to HTML for layout review. Writes files only. Does not send email
and does not read the live newsletter database or any subscriber address.

The brief is the same render() path as a scheduled issue, fed by newsletter_analysis.write_demo_db
(scanner-shaped fixture: clusters, alerts, an 8-day scan history). 30-day windows stay
"not enough history" because the fixture scanner has not been running that long.
"""
import os, sys, tempfile
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "app")
TMP = tempfile.mkdtemp(prefix="briefsample_")
os.environ["NEWSLETTER_DB"] = os.path.join(TMP, "nl.db")
os.environ["NEWSLETTER_SRC_DB"] = os.path.join(TMP, "src.db")
os.environ["NEWSLETTER_CONFIG"] = os.path.join(TMP, "cfg.json")
os.environ["NEWSLETTER_OUTBOX"] = os.path.join(TMP, "outbox")
os.environ["NEWSLETTER_ENV"] = os.path.join(TMP, "newsletter.env")
os.environ["NEWSLETTER_PASSFILE"] = os.path.join(TMP, "PASS.txt")
os.environ["NEWSLETTER_LOG"] = os.path.join(TMP, "nl.log")
os.environ["NEWSLETTER_BO_CONFIG"] = os.path.join(TMP, "bo.json")
os.environ["NEWSLETTER_NO_WORKER"] = "1"
os.makedirs(TMP, exist_ok=True)
open(os.environ["NEWSLETTER_PASSFILE"], "w").write("x\n")
open(os.environ["NEWSLETTER_BO_CONFIG"], "w").write("{}")
open(os.environ["NEWSLETTER_CONFIG"], "w").write('{"live_sending_approved": false, "base_url": "https://blackout.network"}')
sys.path.insert(0, APP)

import newsletter_analysis as NA
import newsletter as NL

AT = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)  # 7:00 AM ET
OUT = os.environ.get("BRIEF_SAMPLE_HTML", "/opt/cursor/artifacts/morning-brief-sample.html")


def main():
    NA.write_demo_db(NL.P["src"], AT)
    k = NL.db()
    k.execute("""INSERT INTO sent_items(send_id,subscriber_id,cluster_id,title_norm,section,sent_at,rank,kind)
                 VALUES(0,0,'a11ce00000000001','iran hormuz','main',?,6,'new')""",
              ((AT - timedelta(hours=26)).strftime("%Y-%m-%dT%H:%M:%SZ"),))
    k.commit(); k.close()
    issue = NL.build_issue({"id": None, "frequency": "twice", "interests": '["all"]'},
                           at=AT, since=AT - timedelta(hours=24), slot="morning")
    links = {"unsubscribe": "https://blackout.network/newsletter", "manage": "https://blackout.network/newsletter",
             "categories": "https://blackout.network/newsletter", "sources": "https://blackout.network/sources",
             "scoring": "https://blackout.network/scoring", "site": "https://blackout.network/#wire", "_row": None}
    subj, html, _text = NL.render(issue, links)
    banner = ('<div style="background:#FFC21A;color:#0B0D10;font:600 14px/1.45 Inter,system-ui,sans-serif;padding:12px 16px">'
              'Fixture Morning Brief for layout review. Stories and alert history are fixture rows in the scanner schema, '
              'not a live send. Nothing was emailed.</div>')
    needle = '<body class="bnb" style="margin:0;padding:0;background:#0B0D10;-webkit-text-size-adjust:100%">'
    html = html.replace(needle, needle + banner, 1)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: f.write(html)
    an = issue["analysis"]
    print("subject:", subj)
    print("items:", len(an["items"]), "patterns:", [p["name"] for p in an["patterns"]])
    print("cost:", an["cost"])
    for it in an["items"]:
        print(f"- R{it['rank']} {it['trajectory']} {it['confidence']} | {it['title'][:70]}")
    print("html:", OUT)
    print("sender:", NL.env().get("NEWSLETTER_SENDER") or "preview", "live_approved:", bool(NL.cfg().get("live_sending_approved")))


if __name__ == "__main__":
    main()
