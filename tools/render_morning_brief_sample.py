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

import json, urllib.request
import newsletter_analysis as NA
import newsletter as NL

AT = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)  # fixture clock; live mode uses now
OUT = os.environ.get("BRIEF_SAMPLE_HTML", "/opt/cursor/artifacts/morning-brief-sample.html")
UA = "Mozilla/5.0 (Macintosh) Safari/605"


def _live_db(path):
    """Clusters from the public API. No alert rows: the public feed does not include them."""
    req = urllib.request.Request("https://blackout.network/api/state", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        data = json.load(r)
    rows = list(data.get("main") or []) + list(data.get("watchlist") or [])
    if os.path.exists(path): os.remove(path)
    c = __import__("sqlite3").connect(path)
    c.executescript("""
    CREATE TABLE alerts(id TEXT PRIMARY KEY, source TEXT, family TEXT, title TEXT, category TEXT, source_url TEXT,
      event_time TEXT, lat REAL, lon REAL, location TEXT, base INTEGER, official INTEGER, extra TEXT,
      first_seen TEXT, last_seen TEXT, cluster_id TEXT);
    CREATE TABLE clusters(cluster_id TEXT PRIMARY KEY, title TEXT, category TEXT, location TEXT, lat REAL, lon REAL,
      event_time TEXT, first_seen TEXT, updated TEXT, score INTEGER, confidence TEXT, n_items INTEGER, n_families INTEGER,
      families TEXT, links TEXT, watchlist INTEGER, brief TEXT, high_at TEXT, rising INTEGER, mentions_3h INTEGER,
      eff_families INTEGER, rank INTEGER, pushed_at TEXT);
    CREATE TABLE scans(id INTEGER PRIMARY KEY, started TEXT, finished TEXT, trigger TEXT, fetched INTEGER, new_items INTEGER, ok_sources INTEGER, failed_sources INTEGER, error TEXT);
    """)
    earliest = None
    n = 0
    for it in rows:
        cid = it.get("cluster_id")
        if not cid: continue
        fs = it.get("first_seen") or it.get("event_time")
        if fs and (earliest is None or fs < earliest): earliest = fs
        fams = it.get("families") if isinstance(it.get("families"), list) else []
        links = it.get("links") if isinstance(it.get("links"), list) else []
        c.execute("""INSERT OR REPLACE INTO clusters(cluster_id,title,category,location,lat,lon,event_time,first_seen,updated,score,confidence,
                     n_items,n_families,families,links,watchlist,brief,high_at,rising,mentions_3h,eff_families,rank)
                     VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (cid, it.get("title"), it.get("category") or "other", it.get("location"), it.get("lat"), it.get("lon"),
                   it.get("event_time"), fs, it.get("updated") or fs, int(it.get("score") or 0), it.get("confidence") or "",
                   int(it.get("n_items") or 0), int(it.get("n_families") or it.get("eff_families") or 0),
                   json.dumps(fams), json.dumps(links), int(it.get("watchlist") or 0), it.get("brief"),
                   it.get("high_at"), int(it.get("rising") or 0), int(it.get("mentions_3h") or 0),
                   int(it.get("eff_families") or 0), int(it.get("rank") or 0)))
        n += 1
    if earliest:
        c.execute("INSERT INTO scans(started,finished,trigger,fetched,new_items,ok_sources,failed_sources) VALUES(?,?,?,?,?,?,?)",
                  (earliest, earliest, "public-api", n, n, 1, 0))
    c.commit(); c.close()
    return n, data.get("generated")


def _card(it):
    return NL._item_html(it, {"unsubscribe": "https://blackout.network/newsletter", "manage": "https://blackout.network/newsletter",
                               "scoring": "https://blackout.network/scoring", "site": "https://blackout.network/#wire", "_row": None}, NL.cfg())


def _compare(issue, links):
    """One weather card and one political card, side by side, from the same render path."""
    import newsletter_art as ART
    pool = []
    for sec in ("main", "politics", "notable", "developing", "near", "updates", "follow"):
        pool.extend(issue.get(sec) or [])
    political = next((it for it in pool if it.get("category") == "political" or ART.event_kind(it.get("title"), it.get("category")) in ("politics", "rights", "surveillance", "protest")), None)
    weather = next((it for it in pool if ART.event_kind(it.get("title"), it.get("category")) in ("storm", "flood", "fire")), None)
    if weather is None or political is None:
        # The live brief drops routine weather. Pull a matching cluster from the snapshot for the illustration only.
        c = __import__("sqlite3").connect(NL.P["src"])
        rows = c.execute("SELECT * FROM clusters").fetchall()
        c.close()
        for r in rows:
            it = NL.item_of(r, "main", 0)
            kind = ART.event_kind(it.get("title"), it.get("category"))
            if weather is None and kind in ("storm", "flood", "fire"):
                weather = it
            if political is None and (it.get("category") == "political" or kind in ("politics", "rights")):
                political = it
    if not weather or not political:
        print("compare skipped", bool(weather), bool(political))
        return
    page = f'''<!doctype html><html><head><meta charset="utf-8"><style>body{{margin:0;background:#0B0D10;color:#F5F5F7;font-family:Inter,system-ui,sans-serif}}</style></head>
<body><table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
<td width="50%" valign="top" style="padding:12px"><div style="font:700 13px/1.3 system-ui;color:#FFC21A;padding:0 8px 8px">WEATHER CARD</div><table width="100%">{_card(weather)}</table></td>
<td width="50%" valign="top" style="padding:12px"><div style="font:700 13px/1.3 system-ui;color:#FFC21A;padding:0 8px 8px">POLITICAL CARD</div><table width="100%">{_card(political)}</table></td>
</tr></table></body></html>'''
    path = "/opt/cursor/artifacts/morning-brief-weather-politics.html"
    open(path, "w").write(page)
    print("compare", path, "weather", (weather.get("title") or "")[:70], "| political", (political.get("title") or "")[:70])


def main():
    live = False
    try:
        n, generated = _live_db(NL.P["src"])
        live = n > 0
        print(f"live clusters: {n} generated {generated}")
    except Exception as ex:
        print("live fetch failed, using fixture:", type(ex).__name__)
        NA.write_demo_db(NL.P["src"], AT)
    at = NL.now() if live else AT
    if not live:
        k = NL.db()
        k.execute("""INSERT INTO sent_items(send_id,subscriber_id,cluster_id,title_norm,section,sent_at,rank,kind)
                     VALUES(0,0,'a11ce00000000001','iran hormuz','main',?,6,'new')""",
                  ((at - timedelta(hours=26)).strftime("%Y-%m-%dT%H:%M:%SZ"),))
        k.commit(); k.close()
    issue = NL.build_issue({"id": None, "frequency": "twice", "interests": '["all"]'},
                           at=at, since=at - timedelta(hours=24), slot="morning")
    links = {"unsubscribe": "https://blackout.network/newsletter", "manage": "https://blackout.network/newsletter",
             "categories": "https://blackout.network/newsletter", "sources": "https://blackout.network/sources",
             "scoring": "https://blackout.network/scoring", "site": "https://blackout.network/#wire", "_row": None}
    subj, html, _text = NL.render(issue, links)
    note = ("Live cluster snapshot from blackout.network/api/state. Per-alert history is not in that feed, so 24h/7d/30d series say not enough history. Nothing was emailed."
            if live else
            "Fixture Morning Brief. Nothing was emailed.")
    banner = ('<div style="background:#FFC21A;color:#0B0D10;font:600 14px/1.45 Inter,system-ui,sans-serif;padding:12px 16px">'
              + note + '</div>')
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
    print("leads:", {s: len(issue.get(s) or []) for s in ("main", "politics", "notable", "developing", "watchlist")})
    print("html:", OUT, "bytes", len(html.encode()))
    msg = NL.build_mime("preview@outbox.invalid", subj, html, _text, None, "issue")
    mime_n = len(msg.as_bytes())
    print("mime bytes", mime_n)
    print("sender:", NL.env().get("NEWSLETTER_SENDER") or "preview", "live_approved:", bool(NL.cfg().get("live_sending_approved")))
    _compare(issue, links)


if __name__ == "__main__":
    main()
