#!/usr/bin/env python3
"""BLACKOUT.NETWORK link checker (t338): every link on every public page and tab works AND goes where its label says.

  collect   crawl a running site (live or local) with Playwright: every page + every dashboard tab, <details> opened, lists
            scrolled; collects rendered <a href> links (with their visible text) AND every URL inside the JSON the pages load
            (sources, preppers, broadcasts, government profiles, gun laws, midterms, ...), plus a rotating sample of the
            global Sources directory (414k rows; --dir-sample N).
  check     checks each URL: real-browser User-Agent, GET, redirects followed, per-host politeness.
              dead        404/410, DNS failure (host does not exist), or a soft 404: redirected to a homepage/generic page,
                          or a title/heading that says "not found" / "page doesn't exist"
              unverified  401/403/429/999 or a bot-challenge page; rechecked once in a real (headless) Chromium; still blocked = unverified
              unreachable timeouts / TLS / 5xx after a retry and a browser recheck (reported, not auto-hidden on first sight)
              mismatch    reachable, but the landing page's title/host shares nothing with the link's label (flagged for review)
  gate      PRE-PUBLISH GATE (tools/prepublish.sh runs it): every URL added by the commits/changes you are about to push is
            checked; exit 1 if any is dead/soft-404 or matches a known-dead URL. Unverified/mismatch = warnings (--strict fails them).
  nightly   collect (live site) + check, write the report and the dead-link flags (data-level, never deletes anything):
              /workspace/blackout/linkcheck_report.json   full report
              /workspace/blackout/linkcheck_dead.json     {url: {...}} -> synced to the site (render_sync), served at
                                                          /api/linkcheck/dead; sitenav.js un-links/hides those links on every page.
            A link is flagged after 2 consecutive dead results and unflagged as soon as it works again.

usage: linkcheck.py collect --base https://blackout.network --out inv.json
       linkcheck.py check --inv inv.json --out report.json
       linkcheck.py gate [--base-ref gh/main] [--strict]
       linkcheck.py nightly [--base https://blackout.network]
       linkcheck.py url URL [URL...]          (quick check, prints verdicts)"""
import argparse, concurrent.futures as cf, datetime as dt, gzip, glob, html, json, os, random, re, socket, subprocess, sys, threading, time
import urllib.parse as up
try: import requests, urllib3; urllib3.disable_warnings()
except ImportError: sys.exit("pip install requests")

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
APP = os.path.join(REPO, "app") if os.path.isdir(os.path.join(REPO, "app")) else REPO   # repo copy (app/) or the box copy
BOX = os.environ.get("BN_BOX_DIR", "/workspace/blackout")
REPORT_F = os.path.join(BOX, "linkcheck_report.json"); DEAD_F = os.path.join(BOX, "linkcheck_dead.json")
HIST_F = os.path.join(BOX, "logs", "linkcheck_history.json")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
HDRS = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.9"}
PAGES = ["/", "/sources", "/newsletter", "/scoring", "/privacy", "/tos", "/social", "/report-status", "/guides/bushcraft.html"]
URL_KEYS = {"url", "link", "href", "website", "homepage", "site", "source_url", "page", "web", "profile_url", "wiki", "wikipedia", "docket_url",
            "bill_url", "case_url", "official", "official_url", "results_url", "stream", "stream_url", "more", "info_url", "link_url", "sources"}
LABEL_KEYS = ["name", "title", "label", "org", "source", "src", "office", "candidate", "text", "station", "outlet", "agency", "headline"]
# never link-checked: API/feed endpoints the pages call (not links people click), tiles, our own assets, tracking/CDNs
SKIP_RE = re.compile(r"^(mailto:|tel:|javascript:|data:|blob:|sms:)|\{|\$\{|%7B|/tiles?/|tile\.|\.(png|jpe?g|webp|gif|svg|ico|woff2?|css|js|mp4|m3u8|geojson|pbf)(\?|$)|"
                     r"fonts\.(googleapis|gstatic)|googletagmanager|/api/|/fdsnws/|api\.weather\.gov/(points|gridpoints|alerts)|services\.swpc|"
                     r"basemaps\.|openfreemap\.org/(styles|planet)|tiles\.|rainviewer\.com/v2|nominatim|overpass|youtube\.com/embed|youtube-nocookie|"
                     r"x\.com/intent/|twitter\.com/intent/|platform\.twitter|schema\.org|w3\.org/|xmlns", re.I)
SOFT_TITLE_RE = re.compile(r"\b(404|410)\b|page not found|not found|page (cannot|can't|could not|couldn.t) be found|page (does not|doesn.t) exist|"
                           r"no longer (available|exists)|page (is )?unavailable|page has (been )?(moved|removed|deleted)|nothing (was )?found|"
                           r"error 404|oops|seite nicht gefunden|página no encontrada|page introuvable|pagina non trovata", re.I)
CHALLENGE_RE = re.compile(r"just a moment|attention required|access denied|are you a robot|verify you are human|cf-chl|captcha|request rejected|"
                          r"pardon our interruption|security check|bot detection|incapsula|perimeterx|datadome", re.I)
STOP = set("the and for with from this that your you our are was were has have not but all any can more most about into over under news home page "
           "site official website web www com org gov net info free live online data report reports read view open click here link links "
           "source sources latest full list tool tools guide guides service services center centre http https html index main".split())
_host_locks, _hl = {}, threading.Lock()

def now(): return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def norm(u):
    u = html.unescape((u or "").strip())
    if u.startswith("//"): u = "https:" + u
    p = up.urlsplit(u)
    if p.scheme not in ("http", "https") or not p.netloc: return None
    return up.urlunsplit((p.scheme, p.netloc.lower(), p.path or "/", p.query, ""))   # fragment dropped
def host(u): return up.urlsplit(u).netloc.lower().split(":")[0]
def toks(s):
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", s or "")
    return {w for w in re.findall(r"[a-z0-9]{3,}", s.lower()) if w not in STOP and not w.isdigit()}

# ------------------------------------------------------------------ collect
def walk_json(o, out, ctx_label="", depth=0):
    if depth > 12: return
    if isinstance(o, dict):
        lab = next((str(o[k]) for k in LABEL_KEYS if isinstance(o.get(k), str) and o.get(k).strip()), ctx_label)
        for k, v in o.items():
            if isinstance(v, str) and (k.lower() in URL_KEYS or k.lower().endswith(("_url", "url", "link", "href"))) and v.startswith(("http://", "https://", "//")):
                out.append((v, lab[:160]))
            elif isinstance(v, list) and k.lower() in URL_KEYS:
                for x in v:
                    if isinstance(x, str) and x.startswith(("http://", "https://")): out.append((x, lab[:160]))
                    else: walk_json(x, out, lab, depth + 1)
            elif isinstance(v, (dict, list)): walk_json(v, out, lab, depth + 1)
    elif isinstance(o, list):
        for x in o: walk_json(x, out, ctx_label, depth + 1)

def collect(base, tabs=None, dir_sample=1500, quick=False):
    from playwright.sync_api import sync_playwright
    sys.path.insert(0, APP)
    import sitenav
    tab_slugs = [it[1] for g, items in sitenav.NAV for it in items if not it[1].startswith("/")]
    if tabs: tab_slugs = [t for t in tab_slugs if t in tabs]
    base = base.rstrip("/"); inv = {}
    def add(u, label, where, kind):
        if not u or SKIP_RE.search(u): return
        if u.startswith("/") and not u.startswith("//"): u = base + u
        n = norm(u)
        if not n: return
        if host(n) in (host(base), "blackout.network", "www.blackout.network") and re.search(r"/(api|internal)/", n): return
        e = inv.setdefault(n, {"url": n, "labels": [], "where": [], "kind": kind})
        label = re.sub(r"\s+", " ", label or "").strip()[:160]
        if label and label not in e["labels"] and len(e["labels"]) < 6: e["labels"].append(label)
        if where not in e["where"] and len(e["where"]) < 12: e["where"].append(where)
        if kind == "rendered": e["kind"] = "rendered"
    with sync_playwright() as p:
        br = p.chromium.launch(args=["--no-sandbox"])
        ctx = br.new_context(viewport={"width": 1280, "height": 900}, user_agent=UA)
        ctx.add_init_script("try{localStorage.setItem('bn_installed','1')}catch(e){}")
        targets = [(u, u) for u in PAGES] + [("/#" + t, "#" + t) for t in tab_slugs]
        for path, where in targets:
            pg = ctx.new_page(); jsons = []
            def on_resp(r, jsons=jsons):
                try:
                    if r.request.method == "GET" and "json" in (r.headers.get("content-type") or "") and r.status == 200 and len(jsons) < 60:
                        jsons.append((r.url, r.json()))
                except Exception: pass
            pg.on("response", on_resp)
            try:
                pg.goto(base + path, wait_until="domcontentloaded", timeout=90000); pg.wait_for_timeout(4000 if quick else 7000)
                for _ in range(2 if quick else 5):    # open accordions, scroll lazy lists, press "show more"
                    pg.evaluate("""()=>{document.querySelectorAll('details:not([open])').forEach(d=>d.open=true);
                      const vis=[...document.querySelectorAll('main,#main')].find(m=>m.offsetWidth>0)||document.body;
                      [...vis.querySelectorAll('button')].filter(b=>/^(show|load|see) (more|all)|more\\b.*▾|^more$/i.test(b.textContent.trim())&&b.offsetWidth>0).slice(0,6).forEach(b=>{try{b.click()}catch(e){}});
                      scrollBy(0,4000)}""")
                    pg.wait_for_timeout(900)
                links = pg.evaluate("""()=>{const vis=[...document.querySelectorAll('body>main,#main')].filter(m=>m.offsetWidth>0);
                  const roots=vis.length?vis.concat([...document.querySelectorAll('header.bn-top,#bn-menu,footer,#site_foot')]):[document.body];
                  const out=[];for(const r of roots)for(const a of r.querySelectorAll('a[href]')){const h=a.getAttribute('href');if(!h||h.startsWith('#'))continue;
                   let t=(a.innerText||a.getAttribute('aria-label')||a.title||'').trim();if(t.length<3){const c=a.closest('li,tr,.card,article,section');t=(t+' '+(c?c.innerText.slice(0,120):'')).trim()}
                   out.push([a.href,t])}return out}""")
                for u, t in links: add(u, t, where, "rendered")
            except Exception as e:
                print("collect error", where, str(e)[:120], file=sys.stderr)
            for ju, data in jsons:
                found = []; walk_json(data, found)
                feed = bool(re.search(r"/api/(state|timeline|wire_history|noise|stream|search|broadcasts|live_archive|intel|elon|figures|spacex|politics|trends|netstatus|streams|tabfeeds|ai|finance|solar|weather)", ju))
                for u, lab in found: add(u, lab, where, "feed" if feed else "data")
            pg.close()
        br.close()
    # global Sources directory: a rotating random sample of its 414k rows (the page only shows search results)
    rows = []
    for f in sorted(glob.glob(os.path.join(APP, "sources_dir_data", "*.ndjson.gz"))):
        with gzip.open(f, "rt") as fh:
            for line in fh:
                try: rows.append(json.loads(line))
                except Exception: pass
    random.seed(int(time.time() // 86400))
    for r in random.sample(rows, min(dir_sample, len(rows))): add(r[2], r[1], "/sources (directory)", "directory")
    return {"base": base, "collected": now(), "links": sorted(inv.values(), key=lambda e: e["url"])}

# ------------------------------------------------------------------ check
def host_lock(h):
    with _hl:
        return _host_locks.setdefault(h, threading.Semaphore(4))
def fetch(u, timeout=(6, 12)):
    s = requests.Session(); s.headers.update(HDRS); s.max_redirects = 12
    r = s.get(u, timeout=timeout, allow_redirects=True, stream=True, verify=True)
    ct = r.headers.get("content-type", "")
    body = b""; t0 = time.time()
    if ("html" in ct or "xml" in ct or not ct) and not re.search(r"audio|video|mpegurl|octet", ct, re.I):
        for chunk in r.iter_content(16384):
            body += chunk
            if len(body) > 400_000 or time.time() - t0 > 20: break   # slow-drip / endless responses
    r.close()
    return r, ct, body.decode(r.encoding or "utf-8", "replace") if body else ""
def page_bits(text):
    t = re.search(r"<title[^>]*>(.*?)</title>", text, re.S | re.I); h1 = re.search(r"<h1[^>]*>(.*?)</h1>", text, re.S | re.I)
    clean = lambda s: re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()[:200]
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
    vis = clean(re.sub(r"<[^>]+>", " ", body))
    og = re.search(r'property=["\']og:site_name["\'][^>]*content=["\']([^"\']+)', text, re.I)
    return clean(t.group(1) if t else ""), clean(h1.group(1) if h1 else ""), vis, (og.group(1) if og else "")
def soft404(orig, final, title, h1, vis):
    po, pf = up.urlsplit(orig), up.urlsplit(final)
    deep = po.path.strip("/") != "" or po.query
    if deep and host(final).replace("www.", "") == host(orig).replace("www.", "") or deep:
        fp = pf.path.rstrip("/")
        if fp in ("", "/index.html", "/index.php", "/en", "/home", "/en-us", "/default.aspx") and not pf.query and po.path.rstrip("/") != fp:
            return "redirects to the homepage"
        if re.search(r"/(404|not-?found|error|page-not-found|pagenotfound)(\.\w+)?$", fp, re.I) and not re.search(r"404|not-?found|error", po.path, re.I):
            return "redirects to an error page"
    if SOFT_TITLE_RE.search(title) and not SOFT_TITLE_RE.search(up.unquote(po.path)): return f"title says: {title[:80]}"
    if SOFT_TITLE_RE.search(h1) and len(vis) < 4000: return f"heading says: {h1[:80]}"
    if len(vis) < 1200 and re.search(r"page not found|404 not found|does not exist|no longer available", vis, re.I): return "page body says not found"
    return None
def mismatch(labels, final, title, h1, og):
    hay = toks(title) | toks(h1) | toks(og) | toks(host(final).replace("www.", "")) | toks(up.unquote(up.urlsplit(final).path))
    hay_pref = {w[:5] for w in hay}
    good = [l for l in labels if len(toks(l)) >= 1 and not re.fullmatch(r"(read|more|link|source|here|open|visit|website|↗|→|\W)+", l.strip().lower())]
    if not good: return None
    for l in good:
        lt = toks(l)
        if lt & hay or {w[:5] for w in lt} & hay_pref: return None
        if any(w in host(final) for w in lt if len(w) >= 4): return None
    return f"label {good[0][:60]!r} vs page {title[:60] or host(final)!r}"
_doh = {}
def dns_exists(h):
    """Real DNS answer via DNS-over-HTTPS (some networks, like this box's, answer every name locally, so getaddrinfo can't tell)."""
    if h in _doh: return _doh[h]
    ans = None
    for url in ("https://cloudflare-dns.com/dns-query", "https://dns.google/resolve"):
        try:
            j = requests.get(url, params={"name": h, "type": "A"}, headers={"Accept": "application/dns-json"}, timeout=10).json()
            if j.get("Status") == 3: ans = False; break               # NXDOMAIN
            if j.get("Status") == 0:
                if j.get("Answer"): ans = True; break
                j6 = requests.get(url, params={"name": h, "type": "AAAA"}, headers={"Accept": "application/dns-json"}, timeout=10).json()
                ans = bool(j6.get("Answer")) or None; break
        except Exception: continue
    _doh[h] = ans; return ans
def check_one(e):
    u = e["url"]; res = {"url": u}
    for attempt in range(2):
        try:
            with host_lock(host(u)):
                r, ct, text = fetch(u)
            res.update(code=r.status_code, final=r.url, ctype=ct.split(";")[0])
            title, h1, vis, og = page_bits(text) if text else ("", "", "", "")
            res["title"] = title
            if r.status_code in (404, 410): res.update(status="dead", why=f"HTTP {r.status_code}")
            elif r.status_code in (401, 403, 429, 999) or (r.status_code in (503, 202) and CHALLENGE_RE.search(title + " " + vis[:2000])):
                res.update(status="unverified", why=f"HTTP {r.status_code} (bot block)")
            elif r.status_code >= 500:
                res.update(status="unreachable", why=f"HTTP {r.status_code}")
                if attempt == 0: time.sleep(3); continue
            elif r.status_code >= 400: res.update(status="dead", why=f"HTTP {r.status_code}")
            else:
                if CHALLENGE_RE.search(title): res.update(status="unverified", why=f"bot challenge page: {title[:60]}")
                else:
                    s4 = soft404(u, r.url, title, h1, vis)
                    if s4: res.update(status="dead", why="soft 404: " + s4)
                    else:
                        res["status"] = "ok"
                        mm = mismatch(e.get("labels", []), r.url, title, h1, og) if "html" in ct else None
                        if mm: res.update(status="mismatch", why=mm)
            break
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as ex:
            msg = re.sub(r"\s+", " ", str(ex))
            ok = dns_exists(host(u))
            if ok is False: res.update(status="dead", why="DNS: host does not exist"); break
            if ok is None and not host(u).count("."): res.update(status="dead", why="DNS: invalid host"); break
            kind = "timeout" if isinstance(ex, requests.exceptions.Timeout) else "TLS" if "SSL" in msg else "connection"
            res.update(status="unreachable", why=f"{kind}: {msg[-110:]}")
        except requests.exceptions.TooManyRedirects: res.update(status="dead", why="redirect loop"); break
        except Exception as ex: res.update(status="unreachable", why=f"{type(ex).__name__}: {str(ex)[:100]}")
        if attempt == 0: time.sleep(2)
    return res
def browser_recheck(results, entries):
    """Second opinion in a real Chromium for bot-blocked / unreachable links (and to confirm dead ones)."""
    todo = [r for r in results if r["status"] in ("unverified", "unreachable") or (r["status"] == "dead" and not r.get("why", "").startswith(("DNS", "HTTP 404", "HTTP 410")))]
    kinds = {e["url"]: e.get("kind") for e in entries}
    todo.sort(key=lambda r: kinds.get(r["url"]) == "feed")      # curated/rendered links first; live feed links last
    todo = todo[:int(os.environ.get("BN_LC_BROWSER_MAX", "300"))]
    deadline = time.time() + int(os.environ.get("BN_LC_BROWSER_SECONDS", "1200"))
    if not todo: return
    from playwright.sync_api import sync_playwright
    labels = {e["url"]: e.get("labels", []) for e in entries}
    with sync_playwright() as p:
        br = p.chromium.launch(args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        ctx = br.new_context(user_agent=UA, viewport={"width": 1280, "height": 900}, locale="en-US")
        for r in todo:
            if time.time() > deadline: r.setdefault("browser", {"skipped": "time budget"}); continue
            pg = ctx.new_page()
            try:
                resp = pg.goto(r["url"], wait_until="domcontentloaded", timeout=20000); pg.wait_for_timeout(1500)
                code = resp.status if resp else 0; title = pg.title() or ""; final = pg.url
                h1 = pg.evaluate("()=>{const h=document.querySelector('h1');return h?h.innerText:''}") or ""
                vis = pg.evaluate("()=>document.body?document.body.innerText.slice(0,6000):''") or ""
                r["browser"] = {"code": code, "title": title[:120], "final": final}
                if code in (404, 410): r.update(status="dead", why=f"HTTP {code} (browser)")
                elif CHALLENGE_RE.search(title + " " + vis[:600]) or code in (401, 403, 429, 999): r.update(status="unverified", why=r.get("why", "") + f"; browser HTTP {code} {title[:40]}")
                elif code and code < 400:
                    s4 = soft404(r["url"], final, title, h1, vis)
                    if s4: r.update(status="dead", why="soft 404 (browser): " + s4)
                    else:
                        mm = mismatch(labels.get(r["url"], []), final, title, h1, "")
                        r.update(status="mismatch" if mm else "ok", why=mm or f"works in a browser (was: {r.get('why','')})", title=title[:200], final=final)
                elif code >= 500: r.update(status="unreachable", why=f"HTTP {code} (browser)")
            except Exception as ex:
                r["browser"] = {"error": str(ex)[:120]}
            finally: pg.close()
        br.close()
def sample_feed(entries):
    """Live feed items (quake/alert/post pages from a handful of hosts) are machine-generated and churn every hour:
    check every curated/rendered/directory link, but only a rotating sample of feed links per host so one big host
    (gdacs, usgs, news.google, bsky...) can't stall the run. BN_LC_FEED_PER_HOST=0 checks them all."""
    cap = int(os.environ.get("BN_LC_FEED_PER_HOST", "40"))
    if not cap: return entries, 0
    import random
    rnd = random.Random(time.strftime("%Y%m%d")); keep = []; per = {}; feeds = [e for e in entries if e.get("kind") == "feed"]
    rnd.shuffle(feeds)
    for e in feeds:
        h = host(e["url"]); per[h] = per.get(h, 0) + 1
        if per[h] <= cap: keep.append(e)
    rest = [e for e in entries if e.get("kind") != "feed"]
    return rest + keep, len(feeds) - len(keep)
def check(entries, workers=24, browser=True):
    out = []
    entries, skipped = sample_feed(entries)
    if skipped: print(f"  feed sample: skipping {skipped} feed links this run (rotating sample per host)", file=sys.stderr, flush=True)
    ex = cf.ThreadPoolExecutor(workers)              # not a with-block: a hung server must not hold up the whole run
    futs = {ex.submit(check_one, e): e for e in entries}
    done_urls = set()
    try:
        for i, f in enumerate(cf.as_completed(futs, timeout=int(os.environ.get("BN_LC_SECONDS", str(max(900, len(entries) // 4)))))):
            done_urls.add(futs[f]["url"])
            try: out.append(f.result())
            except Exception as x: out.append({"url": futs[f]["url"], "status": "unreachable", "why": str(x)[:100]})
            if (i + 1) % 500 == 0: print(f"  checked {i + 1}/{len(entries)}", file=sys.stderr, flush=True)
    except cf.TimeoutError:
        for f, e in futs.items():
            if e["url"] not in done_urls: out.append({"url": e["url"], "status": "unreachable", "why": "check timed out (slow server)"})
    ex.shutdown(wait=False, cancel_futures=True)
    if browser: browser_recheck(out, entries)
    meta = {e["url"]: e for e in entries}
    for r in out:
        e = meta.get(r["url"], {}); r["labels"] = e.get("labels", []); r["where"] = e.get("where", []); r["kind"] = e.get("kind", "")
    return sorted(out, key=lambda r: (r["status"], r["url"]))
def summarize(results):
    tot = {}; by_page = {}
    for r in results:
        tot[r["status"]] = tot.get(r["status"], 0) + 1
        for w in r.get("where") or ["?"]:
            d = by_page.setdefault(w, {}); d[r["status"]] = d.get(r["status"], 0) + 1; d["total"] = d.get("total", 0) + 1
    return {"total": len(results), **tot}, by_page

# ------------------------------------------------------------------ gate (pre-publish)
def added_urls(base_ref):
    diffs = []
    for args in (["diff", "-U0", f"{base_ref}...HEAD"], ["diff", "-U0", "--cached"], ["diff", "-U0"]):
        try: diffs.append(subprocess.run(["git", "-C", REPO] + args, capture_output=True, text=True, timeout=60).stdout)
        except Exception: pass
    found = {}
    cur = None
    for d in diffs:
        for line in d.splitlines():
            if line.startswith("+++ "): cur = line[6:] if line.startswith("+++ b/") else None; continue
            if not line.startswith("+") or line.startswith("+++") or not cur: continue
            if re.search(r"(\.csv|\.ndjson\.gz|linkcheck.*\.json|/archive/|_backup|\.pre)", cur) or cur.startswith("tools/"): continue
            for m in re.finditer(r"""https?://[^\s"'<>`\\)\]]+""", line):
                u = m.group(0).rstrip(".,;:'\"")
                if SKIP_RE.search(u) or re.search(r"//(www\.)?example\.(org|com|net)|//(127\.0\.0\.1|localhost)", u): continue
                lab = re.sub(r"<[^>]+>|\s+", " ", line[max(0, m.start() - 100):m.start()])[-80:]
                n = norm(u)
                if n: found.setdefault(n, {"url": n, "labels": [], "where": [cur], "kind": "diff"})
    return list(found.values())
def gate(base_ref, strict=False):
    entries = added_urls(base_ref)
    known_dead = set()
    try: known_dead = set(json.load(open(DEAD_F)).get("dead", {}))
    except Exception: pass
    print(f"link gate: {len(entries)} new/changed URL(s) to check against {base_ref}")
    if not entries: print("link gate: PASS (no new links)"); return 0
    res = check(entries, workers=12, browser=True)
    bad = [r for r in res if r["status"] == "dead" or r["url"] in known_dead]
    warn = [r for r in res if r["status"] in ("unverified", "unreachable", "mismatch")]
    for r in res:
        if r["status"] != "ok": print(f"  {r['status'].upper():11} {r['url']}  ({r.get('why','')})  in {', '.join(r['where'])}")
    if bad or (strict and warn):
        print(f"link gate: FAIL: {len(bad)} dead link(s){' + %d warning(s) (strict)' % len(warn) if strict and warn else ''}. Fix or remove them before pushing.")
        return 1
    print(f"link gate: PASS ({len(res)} checked, {len(warn)} warning(s) to review)"); return 0

# ------------------------------------------------------------------ nightly + dead flags
def update_flags(results):
    hist = {}
    try: hist = json.load(open(HIST_F))
    except Exception: pass
    flags = {}
    for r in results:
        u = r["url"]; h = hist.get(u, {"dead_runs": 0})
        if r["status"] == "dead":
            h["dead_runs"] = h.get("dead_runs", 0) + 1; h.setdefault("first_dead", now())
        elif r["status"] in ("ok", "mismatch"): h = {"dead_runs": 0}
        hist[u] = h
        if r["status"] == "dead" and h["dead_runs"] >= 2:
            flags[u] = {"dead": True, "why": r.get("why", ""), "since": h.get("first_dead"), "checked": now(), "where": r.get("where", [])[:5]}
    # keep flags for links not seen this run (e.g. a list that did not load) unless they were seen working
    try:
        old = json.load(open(DEAD_F)).get("dead", {})
        seen = {r["url"] for r in results}
        for u, f in old.items():
            if u not in seen and u not in flags: flags[u] = f
    except Exception: pass
    os.makedirs(os.path.dirname(HIST_F), exist_ok=True)
    json.dump(hist, open(HIST_F + ".tmp", "w")); os.replace(HIST_F + ".tmp", HIST_F)
    json.dump({"generated": now(), "count": len(flags), "dead": flags}, open(DEAD_F + ".tmp", "w"), indent=1); os.replace(DEAD_F + ".tmp", DEAD_F)
    return flags
def write_report(path, inv, results, extra=None):
    tot, by_page = summarize(results)
    rep = {"generated": now(), "base": inv.get("base"), "totals": tot, "by_page": by_page,
           "problems": [r for r in results if r["status"] != "ok"], "ok_count": tot.get("ok", 0), **(extra or {})}
    json.dump(rep, open(path + ".tmp", "w"), indent=1); os.replace(path + ".tmp", path)
    return rep

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["collect", "check", "gate", "nightly", "url"])
    ap.add_argument("urls", nargs="*")
    ap.add_argument("--base", default="https://blackout.network"); ap.add_argument("--inv"); ap.add_argument("--out")
    ap.add_argument("--tabs"); ap.add_argument("--dir-sample", type=int, default=1500); ap.add_argument("--base-ref", default="gh/main")
    ap.add_argument("--strict", action="store_true"); ap.add_argument("--no-browser", action="store_true"); ap.add_argument("--workers", type=int, default=24)
    a = ap.parse_args()
    if a.cmd == "collect":
        inv = collect(a.base, a.tabs.split(",") if a.tabs else None, a.dir_sample)
        json.dump(inv, open(a.out or "linkcheck_inventory.json", "w"), indent=1); print(f"{len(inv['links'])} links collected")
    elif a.cmd == "check":
        inv = json.load(open(a.inv)); res = check(inv["links"], a.workers, not a.no_browser)
        rep = write_report(a.out or "linkcheck_report.json", inv, res); print(json.dumps(rep["totals"]))
    elif a.cmd == "gate": sys.exit(gate(a.base_ref, a.strict))
    elif a.cmd == "url":
        for r in check([{"url": norm(u) or u, "labels": [], "where": ["cli"]} for u in a.urls], 8, not a.no_browser):
            print(r["status"], r["url"], r.get("code"), r.get("why", ""), "->", r.get("final", ""))
    elif a.cmd == "nightly":
        t0 = time.time(); inv = collect(a.base, None, a.dir_sample)
        json.dump(inv, open(os.path.join(BOX, "logs", "linkcheck_inventory.json"), "w"))
        res = check(inv["links"], a.workers, True); flags = update_flags(res)
        rep = write_report(a.out or REPORT_F, inv, res, {"flagged_dead": len(flags), "seconds": round(time.time() - t0)})
        print(json.dumps(rep["totals"]), "flagged:", len(flags))
if __name__ == "__main__":
    main(); sys.stdout.flush(); os._exit(0)   # daemon-less exit even if a hung request thread remains
