#!/usr/bin/env python3
"""Homepage link health (run after each posting slot; social_links_sync.after_slot calls it).

Reads the live homepage data (/api/apple/home: the same list the homepage row is built from) and checks, for every story:
  story page   <site>/wire/<cluster_id>  -> 200 (and not the "Story not found" page)
  X post       publish.twitter.com oEmbed -> 200
  YouTube      youtube.com oEmbed         -> 200
Any broken X/YouTube/story link is hidden at once: its cluster gets hidden=[...] in social_links.json, which is pushed to the site
(the homepage never renders a hidden or unverified link). Results: <BN_LINKCHECK_DIR>/last.json and a timestamped copy.
CLI: python3 home_linkcheck.py [--site URL] [--no-push]"""
import os, sys, json, time, argparse, urllib.request
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import social_links_sync as S

OUTDIR = os.environ.get("BN_LINKCHECK_DIR", "/workspace/launch/site/linkcheck")

def home(site):
    req = urllib.request.Request(site + "/api/apple/home", headers={"User-Agent": S.UA})
    with urllib.request.urlopen(req, timeout=20) as r: return json.loads(r.read())

def run(site=None, do_push=True, summary=False, top=10):
    site = (site or S.SITE).rstrip("/"); S.SITE = site
    d = home(site); items = (d.get("main") or [])
    rows = [x for x in items if x.get("social")] + [x for x in items[:top] if not x.get("social")]   # every posted story + the top of the row
    jobs = []
    for x in rows:
        cid = x.get("cluster_id") or ""
        if S.CID.match(cid): jobs.append((cid, "site", cid))
        so = x.get("social") or {}
        if so.get("x"): jobs.append((cid, "x", so["x"]))
        if so.get("yt"): jobs.append((cid, "yt", so["yt"]))
    fn = {"x": S.check_x, "yt": S.check_yt, "site": S.check_site}
    with ThreadPoolExecutor(6) as ex: codes = list(ex.map(lambda j: fn[j[1]](j[2]), jobs))
    res = [{"cluster_id": j[0], "kind": j[1], "url": (site + "/wire/" + j[2]) if j[1] == "site" else j[2], "code": c, "ok": c == 200} for j, c in zip(jobs, codes)]
    bad = [r for r in res if not r["ok"]]
    hid = []
    if bad:
        try: L = json.load(open(S.OUT))
        except Exception: L = {}
        st = L.setdefault("stories", {})
        for r in bad:
            s = st.get(r["cluster_id"])
            if s is None: continue                       # not a posted story: nothing to hide on our side (story page reported)
            h = set(s.get("hidden") or []); h.add(r["kind"]); s["hidden"] = sorted(h); s[f"{r['kind']}_ok"] = False if r["kind"] != "site" else s.get("x_ok")
            hid.append(f"{r['cluster_id']}:{r['kind']}")
        if hid:
            tmp = S.OUT + ".tmp"; json.dump(L, open(tmp, "w"), indent=1, sort_keys=True); os.replace(tmp, S.OUT)
    from datetime import datetime; from zoneinfo import ZoneInfo
    out = {"at": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET"), "site": site, "data_generated": d.get("generated"), "stories_checked": len(rows),
           "links_checked": len(res), "ok": len(res) - len(bad), "broken": bad, "hidden_now": hid}
    if hid and do_push:
        try: out["push"] = S.push()
        except Exception as e: out["push"] = {"pushed": False, "error": f"{type(e).__name__}: {str(e)[:160]}"}
    os.makedirs(OUTDIR, exist_ok=True)
    full = dict(out, results=res)
    json.dump(full, open(os.path.join(OUTDIR, "last.json"), "w"), indent=1)
    json.dump(full, open(os.path.join(OUTDIR, time.strftime("%Y%m%d-%H%M") + ".json"), "w"), indent=1)
    return out if summary else full

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--site"); ap.add_argument("--no-push", action="store_true"); a = ap.parse_args()
    r = run(a.site, do_push=not a.no_push)
    print(json.dumps({k: v for k, v in r.items() if k != "results"}, indent=1))
