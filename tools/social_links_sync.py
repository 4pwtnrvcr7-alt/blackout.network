#!/usr/bin/env python3
"""Box -> site: "Follow this story" links for the homepage (Nov 8).

Reads the posting pipeline's log (posts.jsonl) READ-ONLY, keeps the stories posted in the last 7 days that have a Wire
cluster id, drops X posts listed in x_deletions.jsonl, and verifies every link before it can be shown:
  X        https://publish.twitter.com/oembed?url=<post>  -> 200 means the post is up (404 = deleted/unavailable)
  YouTube  https://www.youtube.com/oembed?url=<video>     -> 200 means public/unlisted and playable (401/403/404 = not)
  Site     https://blackout.network/wire/<cluster_id>     -> 200
Only links that returned 200 are marked ok, and each story is run through the current social topic policy
(weather_policy.weather_reason): stories that fail it (minor quakes, routine weather, NWS products...) get policy_ok=false and
the site neither links nor pins them, even if they were posted in the past. The result is written to <BN_BOX>/social_links.json and pushed to Render over
the signed sync channel (render_sync.push, file pattern social_*.json). Secrets are read by render_sync and never printed.

Hook (posting pipeline, after a successful publish):  import social_links_sync as SLS; S['social_links'] = SLS.after_slot(dry=a.dry)
CLI:  python3 social_links_sync.py [--days 7] [--no-push] [--force] [--no-check]"""
import os, re, sys, json, time, hashlib, argparse, urllib.request, urllib.error, urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta

SOCIAL = os.environ.get("BN_SOCIAL_DIR", "/workspace/launch/social")
POSTS, DELS = os.path.join(SOCIAL, "posts.jsonl"), os.path.join(SOCIAL, "x_deletions.jsonl")
BOX = os.environ.get("BN_BOX", "/workspace/blackout")                      # where social_links.json is written (box node data dir)
RS_DIR = os.environ.get("BN_RENDER_SYNC_DIR", "/workspace/blackout")        # render_sync.py (signed push client)
OUT = os.path.join(BOX, "social_links.json")
CACHE = os.environ.get("BN_LINK_CACHE", "/workspace/launch/site/state/social_links_cache.json")
SITE = os.environ.get("BN_SITE", "https://blackout.network").rstrip("/")
UA = "Mozilla/5.0 (Macintosh) Safari/605 BlackoutNetwork-Internal linkcheck"
CID = re.compile(r"^[0-9a-f]{16}$")
X_RE = re.compile(r"^https://(x|twitter)\.com/BlkoutNtw/status/(\d{5,25})$", re.I)
YT_RE = re.compile(r"^https://(www\.)?youtube\.com/(shorts/|watch\?v=)([A-Za-z0-9_\-]{11})$")
OK_TTL = 6 * 3600          # a link that passed is re-checked after 6 h (the homepage link check re-checks shown ones every slot)

def now(): return datetime.now(timezone.utc)
def _jl(p):
    out = []
    try:
        with open(p, encoding="utf-8") as f:
            for ln in f:
                try: out.append(json.loads(ln))
                except Exception: pass
    except FileNotFoundError: pass
    return out
def _ts(s):
    try: return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception: return None

def http_status(url, timeout=10):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json,text/html;q=0.9"})
        with urllib.request.urlopen(req, timeout=timeout) as r: return r.status, r.read(65536)
    except urllib.error.HTTPError as e: return e.code, b""
    except Exception as e: return 0, str(e)[:80].encode()

def check_x(url):
    c, _ = http_status("https://publish.twitter.com/oembed?omit_script=1&url=" + urllib.parse.quote(url, safe=""))
    return c
def check_yt(url):
    c, _ = http_status("https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(url, safe=""))
    return c
def check_site(cid):
    c, body = http_status(f"{SITE}/wire/{cid}")
    if c == 200 and b"Story not found" in body: return 404
    return c

def collect(days=7):
    """Newest verified-able post per cluster in the window: {cid: {x_url, yt_url, posted_at, headline, kind}}."""
    deleted = {str(d.get("x_id")) for d in _jl(DELS) if d.get("platform") == "x" and d.get("action") == "delete" and d.get("x_id")}
    cut = now() - timedelta(days=days); out = {}
    for p in _jl(POSTS):
        cid = str(p.get("cluster_id") or ""); at = _ts(p.get("at"))
        if not CID.match(cid) or not at or at < cut: continue
        x = p.get("x_url") if X_RE.match(str(p.get("x_url") or "")) else None
        if x and (str(p.get("x_id") or X_RE.match(x).group(2)) in deleted or X_RE.match(x).group(2) in deleted): x = None
        yt = p.get("yt_url") if YT_RE.match(str(p.get("yt_url") or "")) else None
        if not yt and re.fullmatch(r"[A-Za-z0-9_\-]{11}", str(p.get("yt_id") or "")): yt = f"https://www.youtube.com/shorts/{p['yt_id']}"
        if not x and not yt: continue
        cur = out.setdefault(cid, {"x_url": None, "yt_url": None, "posted_at": None, "headline": None, "kind": p.get("kind")})
        if x and (not cur.get("_xt") or at > cur["_xt"]): cur["x_url"], cur["_xt"] = x, at
        if yt and (not cur.get("_yt") or at > cur["_yt"]): cur["yt_url"], cur["_yt"] = yt, at
        if not cur["posted_at"] or at.isoformat() > cur["posted_at"]: cur["posted_at"] = at.strftime("%Y-%m-%dT%H:%M:%SZ"); cur["headline"] = str(p.get("headline") or "")[:200]
    for v in out.values(): v.pop("_xt", None); v.pop("_yt", None)
    return out, sorted(deleted)

def policy(headline):
    """Current social topic policy (the posting pipeline's weather_policy.weather_reason, imported read-only).
    Returns (ok, reason). Fails closed: if the policy can't be loaded, nothing is pinned or linked."""
    try:
        if SOCIAL not in sys.path: sys.path.insert(0, SOCIAL)
        dwb, sys.dont_write_bytecode = sys.dont_write_bytecode, True     # don't write .pyc into the social pipeline's folder
        try: from weather_policy import weather_reason
        finally: sys.dont_write_bytecode = dwb
        why = weather_reason({"title": headline or ""})
        return why is None, why
    except Exception as e:
        return False, f"policy unavailable: {type(e).__name__}"

def verify(stories, force=False):
    try: cache = json.load(open(CACHE))
    except Exception: cache = {}
    t = time.time(); jobs = []
    for cid, s in stories.items():
        for kind, url in (("x", s.get("x_url")), ("yt", s.get("yt_url")), ("site", cid)):
            if not url: continue
            key = f"{kind}:{url}"; c = cache.get(key)
            if not force and c and c.get("code") == 200 and t - c.get("t", 0) < OK_TTL: continue
            jobs.append((key, kind, url))
    fn = {"x": check_x, "yt": check_yt, "site": check_site}
    with ThreadPoolExecutor(6) as ex:
        for key, code in zip([j[0] for j in jobs], ex.map(lambda j: fn[j[1]](j[2]), jobs)):
            cache[key] = {"code": code, "t": t}
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    tmp = CACHE + ".tmp"; json.dump(cache, open(tmp, "w"), indent=0); os.replace(tmp, CACHE)
    res = {}
    for cid, s in stories.items():
        cx = (cache.get(f"x:{s['x_url']}") or {}).get("code") if s.get("x_url") else None
        cy = (cache.get(f"yt:{s['yt_url']}") or {}).get("code") if s.get("yt_url") else None
        cs = (cache.get(f"site:{cid}") or {}).get("code")
        pok, why = policy(s.get("headline"))
        res[cid] = dict(s, policy_ok=pok, policy_reason=why, x_ok=cx == 200, yt_ok=cy == 200, x_code=cx, yt_code=cy, site_code=cs, checked_at=now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                        hidden=([] if cs == 200 else ["site"]))
    return res, len(jobs)

def write(stories, deleted):
    """Writes OUT only when the content changed. Keeps hides set by home_linkcheck for links that are still broken."""
    try: old = json.load(open(OUT))
    except Exception: old = {}
    for cid, s in stories.items():
        prev = ((old.get("stories") or {}).get(cid) or {})
        for h in prev.get("hidden") or []:
            if h in ("x", "yt") and h not in s["hidden"] and not s.get(f"{h}_ok"): s["hidden"].append(h)
    body = {"version": 1, "source": "box social pipeline (posts.jsonl)", "window_days": 7, "stories": stories, "skipped_deleted_x": deleted}
    sig = lambda d: hashlib.sha256(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "checked_at"} for k, v in (d.get("stories") or {}).items()}, sort_keys=True).encode()).hexdigest()
    changed = sig(body) != sig(old)
    body["generated"] = now().strftime("%Y-%m-%dT%H:%M:%SZ")
    if changed or not os.path.exists(OUT):
        tmp = OUT + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f: json.dump(body, f, indent=1, sort_keys=True)
        os.replace(tmp, OUT)
    return changed

def push():
    """Signed push of social_links.json to Render (same channel and HMAC as the data sync). Never prints the secret."""
    if RS_DIR not in sys.path: sys.path.insert(0, RS_DIR)
    import render_sync as R
    env = R.load_env()
    if not env.get("BN_RENDER_URL") or len(env.get("BN_SYNC_SECRET", "")) < 32: return {"pushed": False, "why": "sync not configured"}
    cl = R.Client(env["BN_RENDER_URL"], env.get("BN_SYNC_SECRET", ""))
    sent, batches = R.push(cl, [("social_links.json", OUT, R.sha_file(OUT))], {})
    return {"pushed": bool(sent), "files": sent}

def run(days=7, do_push=True, force=False):
    stories, deleted = collect(days)
    res, checked = verify(stories, force=force)
    changed = write(res, deleted)
    out = {"stories": len(res), "x_ok": sum(1 for s in res.values() if s["x_ok"]), "yt_ok": sum(1 for s in res.values() if s["yt_ok"]),
           "x_bad": sorted(c for c, s in res.items() if s.get("x_url") and not s["x_ok"]), "yt_bad": sorted(c for c, s in res.items() if s.get("yt_url") and not s["yt_ok"]),
           "site_bad": sorted(c for c, s in res.items() if s["site_code"] != 200),
           "policy_rejected": {c: s["policy_reason"] for c, s in sorted(res.items()) if not s["policy_ok"]}, "checked_now": checked, "changed": changed, "file": OUT}
    if do_push and (changed or force):
        try: out["push"] = push()
        except Exception as e: out["push"] = {"pushed": False, "error": f"{type(e).__name__}: {str(e)[:160]}"}
    return out

def after_slot(dry=False):
    """One call after each posting slot: sync verified links (push only when they changed), then check every homepage link."""
    if dry: return {"skipped": "dry run"}
    out = {"sync": run()}
    try:
        import home_linkcheck as HL
        out["linkcheck"] = HL.run(summary=True)
    except Exception as e: out["linkcheck"] = {"error": f"{type(e).__name__}: {str(e)[:160]}"}
    return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--days", type=int, default=7); ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--force", action="store_true"); a = ap.parse_args()
    print(json.dumps(run(a.days, do_push=not a.no_push, force=a.force), indent=1))
