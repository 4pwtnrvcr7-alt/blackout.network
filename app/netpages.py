"""Network provider pages (t398, Nov 1 2026): the Network Status tab's big-cloud and DNS/CDN rows become accordions, and each provider
gets a full page at /network/<slug> (aws, azure, m365, gcp, workspace, cloudflare, akamai) plus a hub at /network.

Data, all keyless and official, fetched on request and cached in memory for 10 minutes (stale copy served if a feed fails):
  AWS Health public events JSON + AWS status RSS · Azure status RSS + Azure status history (Post Incident Reviews) ·
  Microsoft 365 consumer status API · Google Cloud incidents.json · Google Workspace incidents.json ·
  Cloudflare and Akamai Statuspage APIs (summary + incidents) · netstatus.db (this site's own 5-minute checks, read-only).
Root causes are only shown when the provider's own report states one; otherwise "Unconfirmed / not yet disclosed".
Starlink (/network/starlink) and "Networks near me" (/network/near) live in netstarlink.py, loaded below.
Never touches scanner.py, scoring, push.py, jets.py, config.json or aviation_watch.py."""
import html, json, math, os, re, sqlite3, threading, time, urllib.request, xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
try:
    import site_page
except Exception:
    site_page = None

BASE = os.path.dirname(os.path.abspath(__file__)); SITE = "https://blackout.network"
UA = "BlackoutNetwork-status/1.0 (+https://blackout.network/network; cached 10 min)"
TTL = 600
E = lambda s: html.escape(str(s if s is not None else ""), quote=True)
LVC = {0: "#2BB673", 1: "#F5A524", 2: "#FF7A1A", 3: "#FF4D4F", -1: "#5b6573"}
LVN = {0: "Operational", 1: "Minor issue", 2: "Degraded", 3: "Major outage", -1: "Feed unreachable"}

# ---------------------------------------------------------------- time (US Eastern without tzdata; python:slim has none)
def _nth_sunday(y, m, n):
    d = datetime(y, m, 1); d += timedelta(days=(6 - d.weekday()) % 7); return d + timedelta(weeks=n - 1)
def to_et(dt):
    if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
    u = dt.astimezone(timezone.utc).replace(tzinfo=None); y = u.year
    start = _nth_sunday(y, 3, 2) + timedelta(hours=7); end = _nth_sunday(y, 11, 1) + timedelta(hours=6)
    dst = start <= u < end
    return u + timedelta(hours=-4 if dst else -5), ("EDT" if dst else "EST")
def fmt_et(dt, with_year=None, dateonly=False):
    if dt is None: return "—"
    l, z = to_et(dt); now = datetime.now(timezone.utc)
    if with_year is None: with_year = abs((now.replace(tzinfo=None) - l).days) > 300
    if dateonly: return l.strftime("%b %-d, %Y")
    return l.strftime("%b %-d" + (", %Y" if with_year else "") + ", %-I:%M %p") + f" {z}"
def pdt(s):
    if not s: return None
    if isinstance(s, (int, float)) or (isinstance(s, str) and s.isdigit()): return datetime.fromtimestamp(int(s), timezone.utc)
    s = str(s).strip()
    m = re.match(r"(.*) (PST|PDT)$", s)
    if m:
        try: return datetime.strptime(m.group(1), "%a, %d %b %Y %H:%M:%S").replace(tzinfo=timezone(timedelta(hours=-8 if m.group(2) == "PST" else -7)))
        except Exception: return None
    for f in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z", "%a, %d %b %Y %H:%M:%S %z", "%m/%d/%Y"):
        try:
            x = s[:-1] + "+00:00" if s.endswith("Z") else s
            x = re.sub(r" Z$", " +0000", x)
            d = datetime.strptime(x, f)
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except Exception: pass
    return None
def iso(d): return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if d else None

# ---------------------------------------------------------------- fetch + cache
_C = {}; _L = threading.Lock(); _KL = {}
def get(url, timeout=9):
    r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json,application/rss+xml,text/xml,text/html,*/*"}), timeout=timeout)
    b = r.read(4_000_000)
    if b[:2] in (b"\xff\xfe", b"\xfe\xff"): return b.decode("utf-16")
    return b.decode("utf-8-sig", "replace")
def cached(key, fn, ttl=TTL):
    hit = _C.get(key)
    if hit and time.time() - hit[0] < ttl: return hit[1]
    with _L: kl = _KL.setdefault(key, threading.Lock())
    with kl:
        hit = _C.get(key)
        if hit and time.time() - hit[0] < ttl: return hit[1]
        try:
            v = fn(); _C[key] = (time.time(), v); return v
        except Exception as e:
            if hit:   # serve the last good copy, retry in 2 minutes
                v = dict(hit[1]); v["stale"] = type(e).__name__; _C[key] = (time.time() - ttl + 120, hit[1]); return v
            raise

# ---------------------------------------------------------------- root cause (only from the provider's own words)
CATS = [
    ("attack", "Cyberattack / DDoS", r"\bd?dos\b|denial[- ]of[- ]service|cyber[- ]?attack|malicious|threat actor|compromised|intrusion|ransomware|\bhack(?:ed|er|ers)?\b"),
    ("ai", "AI / automation", r"automated (?:activity|process|system|tool|workflow|scaling|management|deployment)|\bautomation\b|\bAI\b|machine[- ]learning|race condition"),
    ("config", "Config / deploy error", r"configuration|\bconfig\b|(?:was|were|been|being) deployed|(?:recent|new|a) deployment\b|roll ?out|code change|software (?:update|change|release)|binary|\bbug\b|feature flag|policy change|maintenance|change was|a change to|null pointer|regression|human error|operator error|playbook"),
    ("power", "Hardware / power", r"\bpower\b|utility|generator|\bups\b|cooling|thermal|hardware|fire\b|battery|drone|physical (?:impact|damage)|damage|flood|heat"),
    ("network", "Network / BGP / DNS", r"\bbgp\b|\bdns\b|fib(?:er|re) cut|routing|router|packet loss|network (?:device|congestion|issue|connectivity)|\bwan\b"),
    ("thirdparty", "Third-party dependency", r"third[- ]party|upstream provider|vendor|external provider|crowdstrike|dependency"),
]
CAT_NAME = {k: n for k, n, _ in CATS}; CAT_NAME["unknown"] = "Unconfirmed / not yet disclosed"; CAT_NAME["other"] = "Other (see official report)"
CAT_COL = {"attack": "#FF4D4F", "ai": "#9b6bff", "config": "#F5A524", "power": "#ff8a3d", "network": "#4aa3ff", "thirdparty": "#2bb6a8", "other": "#8a94a3", "unknown": "#5b6573"}
NEG = re.compile(r"\bnot\b[^.]{0,80}(?:attack|malicious|cyber|hijack|security event)", re.I)
ADVICE = re.compile(r"encouraged to|we recommend|customers (?:should|can|may)|please |workaround|contact support", re.I)
def _sentences(t): return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", t or "") if len(s.strip()) > 25]
def classify(text, who):
    """-> dict(cat, name, evidence, who) from official root-cause text, or None when no cause text exists."""
    if not text or len(text.strip()) < 30: return None
    score = {k: 0 for k, _, _ in CATS}; best_ev = {}
    for s in _sentences(text)[:40]:
        if NEG.search(s) or ADVICE.search(s): continue
        for k, _, rx in CATS:
            n = len(re.findall(rx, s, re.I))
            if n:
                score[k] += n
                best_ev.setdefault(k, s)
    order = [x[0] for x in CATS]
    k = max(score, key=lambda c: (score[c], -order.index(c)))
    if score[k] == 0:
        ss = [x for x in _sentences(text) if not ADVICE.search(x)]
        if not ss: return None
        k = "other"; best_ev[k] = ss[0]
    ev = best_ev[k]; ev = ev if len(ev) <= 280 else ev[:277].rsplit(" ", 1)[0] + "…"
    return {"cat": k, "name": CAT_NAME[k], "evidence": ev, "who": who}
def section(text, start_rx, stop_rx, n=3000):
    m = re.search(start_rx, text or "", re.I)
    if not m: return ""
    t = text[m.end(): m.end() + n]; s = re.search(stop_rx, t, re.I)
    return t[: s.start()] if s else t
def clean_md(t): return re.sub(r"\*\*|__|`", "", t or "").strip()
def cover_start(starts):
    """Oldest date a capped feed really covers: drop lone stragglers more than 14 days older than the next entry."""
    st = sorted(starts)
    while len(st) > 2 and (st[1] - st[0]).days > 14: st.pop(0)
    return st[0] if st else None
def inc(**k):
    d = dict(id="", title="", start=None, end=None, sev=1, services=[], regions=[], url="", summary="", cause=None, src="")
    d.update(k); return d

# ---------------------------------------------------------------- feeds
AWS_REG = re.compile(r"-((?:us|eu|ap|me|sa|ca|af|il|mx)(?:-gov)?-[a-z]+-\d)$")
AWS_CAUSE = re.compile(r"root cause|was caused by|were caused by|triggered by|as a result of|due to (?:a |an |the )?(?:localized |ongoing )?(?:power|conflict|network|configuration|change|drone)|drone strike|power issue|physical impact", re.I)
def aws_cause(txt):
    ss = [s for s in _sentences(txt) if AWS_CAUSE.search(s)]
    return classify(" ".join(dict.fromkeys(ss)), "AWS") if ss else None
def aws_data():
    raw = get("https://health.aws.amazon.com/public/currentevents"); ev = json.loads(raw) if raw.strip() else []
    active = []
    for e in ev:
        log = e.get("event_log") if isinstance(e.get("event_log"), list) else []
        imp = e.get("impacted_services") if isinstance(e.get("impacted_services"), dict) else {}
        svcs = sorted({v.get("service_name", "") for v in imp.values()}) or [e.get("service_name", "")]
        last = log[-1] if log else {}
        txt = " ".join((x.get("message") or "") for x in log)
        rm = AWS_REG.search(e.get("service", "")); reg = rm.group(1) if rm else ""
        active.append(inc(id=e.get("arn", "")[-24:], title=f'{e.get("service_name")}: {e.get("summary")}', start=pdt(e.get("date")), sev=min(3, int(e.get("status") or 2)),
                          services=svcs[:60], regions=[f'{e.get("region_name")} ({reg})' if reg else e.get("region_name", "")],
                          url="https://health.aws.amazon.com/health/status", summary=(last.get("message") or "")[:600], cause=aws_cause(txt), src="AWS Health Dashboard",
                          longrun=bool(pdt(e.get("date")) and time.time() - pdt(e.get("date")).timestamp() > 72 * 3600)))
    root = ET.fromstring(get("https://status.aws.amazon.com/rss/all.rss")); hist = []
    for it in root.findall("./channel/item"):
        g = (it.findtext("guid") or "").split("#")[-1]; slug = re.sub(r"_\d+$", "", g); when = pdt(it.findtext("pubDate"))
        desc = it.findtext("description") or ""; title = it.findtext("title") or ""
        h = next((h for h in hist if h["slug"] == slug and when and h["last"] and abs((h["last"] - when).total_seconds()) < 3 * 86400), None)
        if h is None:
            rm = AWS_REG.search(slug)
            h = dict(slug=slug, last=when, texts=[], inc=inc(id=g, title=title, start=when, sev=3 if "disruption" in title.lower() else 2,
                     services=[(slug[: rm.start()] if rm else slug).replace("multipleservices", "Multiple services")], regions=[rm.group(1)] if rm else [],
                     url="https://health.aws.amazon.com/health/status", summary=desc[:600], src="AWS status RSS"))
            hist.append(h)
        h["texts"].append(desc)
        if when and (h["inc"]["start"] is None or when < h["inc"]["start"]): h["inc"]["start"] = when
        h["last"] = when
    past = []
    for h in hist:
        i = h["inc"]; i["cause"] = aws_cause(" ".join(h["texts"]))
        same = [a for a in active if i["regions"] and any(i["regions"][0] in r for r in a["regions"]) and a["start"] and i["start"] and abs((a["start"] - i["start"]).total_seconds()) < 3 * 86400]
        if same:
            if not same[0]["cause"]: same[0]["cause"] = i["cause"]
            continue
        past.append(i)
    past.sort(key=lambda i: i["start"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    regs = {}
    for a in active:
        for r in a["regions"]: regs[r] = max(regs.get(r, 0), a["sev"])
    return dict(active=active, history=past, components=[], regions=[dict(name=k, level=v, note="active event") for k, v in regs.items()], capped=cover_start([i["start"] for i in past if i["start"]]),
                coverage="AWS's public RSS keeps recent status posts only; account-specific events are in your AWS Health Dashboard.", fetched=iso(datetime.now(timezone.utc)))

def azure_data():
    root = ET.fromstring(get("https://azure.status.microsoft/en-us/status/feed/")); active = []
    for it in root.findall("./channel/item"):
        d = re.sub("<[^>]+>", " ", it.findtext("description") or "")
        active.append(inc(id=it.findtext("guid") or "", title=it.findtext("title") or "", start=pdt(it.findtext("pubDate")), sev=2, summary=re.sub(r"\s+", " ", d)[:600],
                          url=it.findtext("link") or "https://azure.status.microsoft/en-us/status", src="Azure status RSS"))
    h = get("https://azure.status.microsoft/en-us/status/history/"); past = []
    for m in re.finditer(r'<span class="hide-text">(\d\d/\d\d/\d{4})</span>\s*<div class="col-md-8 incident-history-title">\s*(.*?)\s*</div>\s*<div class="col-md-3 incident-history-tracking-id">\s*Tracking ID:\s*([A-Z0-9_\-]+)', h, re.S):
        date, title, tid = m.group(1), html.unescape(re.sub(r"\s+", " ", m.group(2))), m.group(3)
        j = h.find(f'id="incident-history-collapse-{tid}"', m.end()); body = h[j: j + 60000] if j > 0 else ""
        k = body.find('class="row incident-history-header"'); body = body[:k] if k > 0 else body
        txt = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body)))
        what = section(txt, r"What happened\??", r"What went wrong", 900).strip()
        why = section(txt, r"What went wrong and why\??", r"How did we respond|How are we making|How can customers", 4000)
        short = re.sub(r"^Post Incident Review \(PIR\)\s*[–-]\s*", "", title)
        parts = [x.strip() for x in re.split(r"\s[–-]\s", short)]
        regs = re.findall(r"(multiple regions|(?:East|West|North|South|Central|North Central|South Central|West Central) US(?: \d)?|UK South|UK West|West Europe|North Europe|Southeast Asia|East Asia|Japan East|Japan West|Brazil South|Australia East|Canada Central|France Central|Germany West Central|Sweden Central|Central India|Korea Central)", title + " " + what[:400])
        past.append(inc(id=tid, title=short, start=(pdt(date) or datetime.now(timezone.utc)).replace(hour=17), dateonly=True, sev=2, services=parts[:1], regions=list(dict.fromkeys(regs))[:6],
                        url=f"https://azure.status.microsoft/en-us/status/history/?trackingId={tid}", summary=what[:600],
                        cause=classify(why, "Microsoft Azure PIR"), pir=True, src="Azure Post Incident Review"))
    return dict(active=active, history=past, components=[], regions=[],
                coverage="Azure publishes Post Incident Reviews for broad issues and keeps them five years; the public page lists the most recent months.", fetched=iso(datetime.now(timezone.utc)))

def m365_data():
    d = json.loads(get("https://status.cloud.microsoft/api/posts/m365Consumer")); comps, active = [], []
    for x in d:
        st = x.get("Status") or ""; lvl = 0 if st == "Operational" else (3 if "outage" in st.lower() else 2)
        comps.append(dict(name=x.get("ServiceDisplayName", ""), level=lvl, status=st))
        if lvl:
            a = str(x.get("AuthoredDateTime") or "")
            active.append(inc(id=x.get("Id") or x.get("ServiceWorkloadName", ""), title=f'{x.get("ServiceDisplayName")}: {x.get("Title") or st}', start=None if a.startswith("0001") else pdt(a[:19] + "+00:00"),
                              sev=lvl, services=[x.get("ServiceDisplayName", "")], summary=re.sub("<[^>]+>", " ", x.get("Message") or "")[:600], url="https://status.cloud.microsoft", src="Microsoft 365 status"))
    return dict(active=active, history=[], components=comps, regions=[],
                coverage="Microsoft does not publish a public Microsoft 365 incident history. Business and enterprise incidents (with root causes) are in the Microsoft 365 admin center under Health > Service health; history here comes from this site's own 5-minute checks.",
                fetched=iso(datetime.now(timezone.utc)))

def google_data(url, base, who):
    d = json.loads(get(url)); active, past = [], []; now = datetime.now(timezone.utc)
    for e in d:
        txt = (e.get("most_recent_update") or {}).get("text", "") or ""
        allt = "\n".join(u.get("text", "") for u in (e.get("updates") or []))
        stop = r"\n\*\*(?:Remediation|Mitigation|Preventi|What is our|Detailed Description of Impact|Customer Impact|Impact)"
        hd = r"(?:^|\n)[ \t*]*Root Cause[ \t]*:?[ \t*]*(?:\n|$)"
        rc = section(txt, hd, stop, 3000) or section(allt, hd, stop, 3000)
        if not rc: rc = " ".join(dict.fromkeys(x for x in _sentences(clean_md(allt)) if re.search(r"root cause|was caused by|were caused by|triggered by", x, re.I)))
        locs = [l.get("title", "") for l in (e.get("currently_affected_locations") or [])] or [l.get("title", "") for l in (e.get("previously_affected_locations") or [])]
        dl = [x.strip() for x in clean_md(e.get("external_desc") or "").split("\n") if x.strip() and not re.fullmatch(r"(?:Title|Summary|Description):?", x.strip(), re.I)]
        desc = re.sub(r"^(?:Title|Summary):\s*", "", dl[0] if dl else "")[:300]
        it = inc(id=e.get("id", ""), title=desc or e.get("service_name", ""), start=pdt(e.get("begin")), end=pdt(e.get("end")), sev={"low": 1, "medium": 2, "high": 3}.get(e.get("severity"), 2),
                 services=[p.get("title", "") for p in (e.get("affected_products") or [])][:40] or [e.get("service_name", "")], regions=locs[:12],
                 url=f'{base}/incidents/{e.get("id", "")}', summary=clean_md(txt)[:700], cause=classify(clean_md(rc), who), src=who)
        (past if e.get("end") else active).append(it)
    regs = {}
    for a in active:
        for r in a["regions"]: regs[r] = max(regs.get(r, 0), a["sev"])
    first = min((i["start"] for i in past + active if i["start"]), default=None)
    return dict(active=active, history=past, components=[], regions=[dict(name=k, level=v, note="active incident") for k, v in regs.items()],
                coverage=f"The public {who} feed lists {len(d)} incident(s)" + (f" since {first:%b %-d, %Y}" if first else "") + ".", fetched=iso(now))

def statuspage_data(base, who):
    s = json.loads(get(base + "/api/v2/summary.json")); ii = json.loads(get(base + "/api/v2/incidents.json")).get("incidents", [])
    comps = s.get("components", []); byid = {c["id"]: c for c in comps}; lv = {"operational": 0, "under_maintenance": 1, "degraded_performance": 2, "partial_outage": 2, "major_outage": 3}
    groups, flat = [], []
    for c in comps:
        if c.get("group") and c.get("components"):
            kids = [byid[k] for k in c["components"] if k in byid]
            bad = [k for k in kids if lv.get(k.get("status"), 0) >= 2]
            groups.append(dict(name=c["name"], total=len(kids), ok=sum(1 for k in kids if k.get("status") == "operational"), maint=sum(1 for k in kids if k.get("status") == "under_maintenance"),
                               bad=len(bad), level=max([lv.get(k.get("status"), 0) for k in kids] or [0]), worst=[f'{k["name"]} ({k.get("status", "").replace("_", " ")})' for k in bad[:6]], small=sum(1 for k in kids if re.search(r"\([A-Z]{3}\)\s*$", k["name"])) < max(3, len(kids) / 2),
                               kids=[dict(name=k["name"], level=lv.get(k.get("status"), 0), status=k.get("status", "").replace("_", " ")) for k in kids] [:40],
                               names={k["name"] for k in kids}))
        elif not c.get("group_id") and not c.get("group"):
            flat.append(dict(name=c["name"], level=lv.get(c.get("status"), 0), status=c.get("status", "").replace("_", " ")))
    active, past = [], []
    for i in ii:
        ups = i.get("incident_updates") or []; body = " ".join(u.get("body") or "" for u in reversed(ups))
        cs = [x for x in _sentences(body) if re.search(r"root cause|was caused by|caused by a|triggered by|identified the (?:cause|issue) as|was due to", x, re.I)]
        cn = [c.get("name", "") for c in (i.get("components") or [])]
        it = inc(id=i["id"], title=i.get("name", ""), start=pdt(i.get("started_at") or i.get("created_at")), end=pdt(i.get("resolved_at")),
                 sev={"none": 0, "minor": 1, "major": 2, "critical": 3}.get(i.get("impact"), 1), services=cn[:20],
                 regions=sorted({g["name"] for g in groups if not g["small"] for n in cn if n in g["names"]})[:6],
                 url=f'{base}/incidents/{i["id"]}', summary=(ups[0].get("body") if ups else "")[:600],
                 cause=classify(" ".join(cs), who) if cs else None, status=i.get("status"), src=who)
        (active if i.get("status") not in ("resolved", "postmortem", "completed") else past).append(it)
    for g in groups: g.pop("names", None)
    first = cover_start([x["start"] for x in past if x["start"]])
    return dict(active=active, history=past, components=flat[:40], groups=groups, regions=[], indicator=s.get("status", {}).get("description", ""),
                capped=first if len(ii) >= 45 else None, coverage=f"The public Statuspage API returns only the latest {len(ii)} incidents" + (f" (back to {first:%b %-d, %Y})" if first else "") + ".", fetched=iso(datetime.now(timezone.utc)))

# ---------------------------------------------------------------- providers (every link verified Nov 1 2026; notable outages quote the official write-up)
X = lambda h: (f"@{h}", f"https://x.com/{h}")
CHECK_COMMON = ["Test from outside your network (a phone on cellular) to rule out your own ISP, DNS or VPN.",
                "Look at your own error rates and latency by region before declaring an incident; official dashboards can lag real impact."]
COMMS = [("Customer heads-up (incident open)", "Status update ({time} ET): Some of our services are slow or unavailable because of an outage at {provider}, a provider we use. Your data is safe. We're working around it and will update you by {next} ET. Live status: {your_status_page}"),
         ("Internal alert", "{provider} incident affecting {services} in {region} since {time} ET. Impact on us: {impact}. Owner: {name}. Failover: {yes_no}. Next check-in {next} ET."),
         ("All clear", "Resolved ({time} ET): {provider} has recovered and our services are back to normal. If anything still looks wrong, reply here or contact {support}. Thank you for your patience.")]
MSPHONE = '<a href="https://support.microsoft.com/en-us/topic/global-customer-service-phone-numbers-c0389ade-5640-e588-8b0e-28de8afeb3f2" target="_blank" rel="noopener">Global customer service phone numbers</a>'
P = {
 "aws": dict(name="AWS", long="Amazon Web Services (AWS)", src="AWS", icon="cloud", fetch=aws_data,
    what="The largest cloud platform: servers, storage, databases and networking behind a large share of apps and websites.",
    status=("AWS Health Dashboard (public)", "https://health.aws.amazon.com/health/status"),
    feeds=[("AWS Health public events", "https://health.aws.amazon.com/health/status"), ("AWS status RSS", "https://status.aws.amazon.com/rss/all.rss")],
    console=[("Your AWS Health Dashboard (account events)", "https://health.aws.amazon.com/health/home"), ("AWS Support Center (open a case)", "https://console.aws.amazon.com/support/home")],
    support=[("Contact AWS", "https://aws.amazon.com/contact-us/", "Sales, billing and account questions"), ("AWS Support plans", "https://aws.amazon.com/premiumsupport/", "Technical support tiers and response times"),
             ("Post-Event Summaries", "https://aws.amazon.com/premiumsupport/technology/pes/", "AWS's official write-ups of major events")],
    phone="AWS does not publish a general support phone line; technical support is opened as a case in the Support Center (chat or call-back on paid plans).",
    x=[X("AWSSupport"), X("awscloud")],
    subscribe=[("Health events to email/Slack via Amazon EventBridge", "https://docs.aws.amazon.com/health/latest/ug/cloudwatch-events-health.html"), ("AWS status RSS feed", "https://status.aws.amazon.com/rss/all.rss")],
    confirm=["Open your AWS Health Dashboard → Open and recent issues: it lists events affecting your account, services and regions.", "Compare the region in the event with the regions your workloads run in (console region picker, top right)."],
    failover=["Run critical workloads in at least two Availability Zones; for must-stay-up services, use a second region with Route 53 health-check failover.", "Keep copies of critical S3 data in another region (Cross-Region Replication) and use DynamoDB global tables for critical data.",
              "Avoid single-region dependencies for login, DNS and deploy pipelines; us-east-1 hosts some global control planes.", "Rehearse failover with game days so it works when the console is slow."],
    monitor=["Subscribe to AWS Health events through EventBridge and route them to email, SMS or Slack.", "Add CloudWatch alarms on your own error rates.", "Follow @AWSSupport and check this page for a one-glance view."],
    tips=["Check your AWS Health Dashboard for events in your account and regions", "If one region is hit, fail over to a second region or zone", "Hold deploys and config changes until AWS reports recovery"],
    notable=[dict(date="Oct 19–20, 2025", title="US-EAST-1 DynamoDB DNS failure", cat="network", quote="The root cause of this issue was a latent race condition in the DynamoDB DNS management system that resulted in an incorrect empty DNS record for the service's regional endpoint.", impact="DynamoDB, EC2 launches and Network Load Balancer errors in N. Virginia, rippling into many apps that depend on them.", src="https://aws.amazon.com/message/101925/", srcn="AWS post-event summary"),
             dict(date="Mar 1, 2026 onward", title="Middle East regions (UAE ME-CENTRAL-1, Bahrain ME-SOUTH-1)", cat="power", quote="Due to the ongoing conflict in the Middle East, both affected regions have experienced physical impacts to infrastructure as a result of drone strikes.", impact="Power and connectivity loss in several Availability Zones; AWS later said it could not restore resources hosted only in one UAE zone (mec1-az2).", src="https://health.aws.amazon.com/health/status", srcn="AWS Health Dashboard posts"),
             dict(date="Dec 7, 2021", title="US-EAST-1 internal network congestion", cat="ai", quote="An automated activity to scale capacity of one of the AWS services hosted in the main AWS network triggered an unexpected behavior from a large number of clients inside the internal network.", impact="Widespread errors in N. Virginia for hours, including AWS's own dashboard and support tools.", src="https://aws.amazon.com/message/12721/", srcn="AWS post-event summary"),
             dict(date="Feb 28, 2017", title="S3 outage in US-EAST-1", cat="config", quote="An authorized S3 team member using an established playbook executed a command which was intended to remove a small number of servers… one of the inputs to the command was entered incorrectly.", impact="S3 in N. Virginia went down, taking many websites and AWS services with it.", src="https://aws.amazon.com/message/41926/", srcn="AWS post-event summary")]),
 "azure": dict(name="Microsoft Azure", long="Microsoft Azure", src="Microsoft Azure", icon="cloud", fetch=azure_data,
    what="Microsoft's cloud platform. It also runs Microsoft's own services, so Azure trouble can spill into Microsoft 365, Xbox and Copilot.",
    status=("Azure status", "https://azure.status.microsoft/en-us/status"),
    feeds=[("Azure status RSS", "https://azure.status.microsoft/en-us/status/feed/"), ("Azure status history (PIRs)", "https://azure.status.microsoft/en-us/status/history/")],
    console=[("Azure Service Health (your subscriptions)", "https://portal.azure.com/#view/Microsoft_Azure_Health/AzureHealthBrowseBlade/~/serviceIssues"), ("Create an Azure support request", "https://azure.microsoft.com/en-us/support/create-ticket/")],
    support=[("Azure support options", "https://azure.microsoft.com/en-us/support/options/", "Plans and how to reach support"), ("Azure Service Health overview", "https://learn.microsoft.com/en-us/azure/service-health/overview", "How Service Health, Resource Health and alerts work")],
    phone=f"Microsoft lists support phone numbers by country on its official page: {MSPHONE}. Azure technical cases are opened in the portal.",
    x=[X("AzureSupport"), X("Azure")],
    subscribe=[("Service Health alerts (email, SMS, push, webhook)", "https://learn.microsoft.com/en-us/azure/service-health/alerts-activity-log-service-notifications-portal"), ("Azure status RSS", "https://azure.status.microsoft/en-us/status/feed/")],
    confirm=["Open Azure Service Health → Service issues: it shows incidents scoped to your subscriptions, regions and services, with tracking IDs.", "Check Resource Health on your key resources to see whether they are affected right now."],
    failover=["Deploy across Availability Zones; for critical apps use a second region with Traffic Manager or Front Door failover.", "Geo-replicate storage (GRS/GZRS) and databases (auto-failover groups).", "If Azure Front Door is the problem, keep a documented DNS fallback that points straight at your origin.", "Keep break-glass admin access that does not depend on the impacted service."],
    monitor=["Create Service Health alerts for your subscriptions.", "Watch Resource Health and Azure Monitor alerts on your own apps.", "Follow @AzureSupport and the Azure status RSS."],
    tips=["Open Azure Service Health for your subscriptions and the tracking ID", "Fail over to another zone or region if yours is named", "Check Microsoft 365 too; it shares infrastructure"],
    notable=[dict(date="Oct 29, 2025", title="Azure Front Door: connectivity issues across multiple regions", cat="config", quote="Microsoft's PIR traces it to a specific sequence of customer configuration changes on the Azure Front Door control plane, which is deployed globally to all edge sites.", impact="Sites and Microsoft services fronted by Azure Front Door, including management portals, failed to load.", src="https://azure.status.microsoft/en-us/status/history/?trackingId=YKYN-BWZ", srcn="Azure PIR YKYN-BWZ"),
             dict(date="Jul 19, 2024", title="CrowdStrike update crashes Windows machines, including Azure VMs", cat="thirdparty", quote="CrowdStrike, an independent cybersecurity company, released a software update that began impacting IT systems globally… CrowdStrike's update affected 8.5 million Windows devices.", impact="Windows VMs and PCs running CrowdStrike Falcon crashed worldwide. Microsoft said this was not a Microsoft incident.", src="https://blogs.microsoft.com/blog/2024/07/20/helping-our-customers-through-the-crowdstrike-outage/", srcn="Microsoft blog"),
             dict(date="Jul 18, 2024", title="Storage: impact to multiple services in Central US", cat="config", quote="Microsoft's PIR says an update to the Storage 'allow list' of VM host addresses was published incorrectly, so Storage rejected disk reads and writes from VMs.", impact="VMs and the services built on them in Central US, with knock-on effects on Microsoft 365.", src="https://azure.status.microsoft/en-us/status/history/?trackingId=1K80-N_8", srcn="Azure PIR 1K80-N_8"),
             dict(date="Jan 25, 2023", title="Global WAN issues", cat="network", quote="A network engineer was performing an operational task to add network capacity to the global Wide Area Network (WAN) in Madrid… The task included steps to modify the IP address for each new router.", impact="Network connectivity problems across Azure regions and Microsoft 365 (Teams, Outlook).", src="https://azure.status.microsoft/en-us/status/history/?trackingId=VSG1-B90", srcn="Azure PIR VSG1-B90")]),
 "m365": dict(name="Microsoft 365", long="Microsoft 365 (Outlook, Teams, OneDrive, Copilot)", src="Microsoft 365 / Outlook / Teams (consumer)", icon="mail", fetch=m365_data,
    what="Outlook, Teams, OneDrive, Word, Excel and Copilot. The public page covers consumer services; business tenants see their own incidents in the admin center.",
    status=("Microsoft 365 status", "https://status.cloud.microsoft"),
    feeds=[("Microsoft 365 public status (consumer)", "https://status.cloud.microsoft")],
    console=[("Microsoft 365 admin center → Service health", "https://admin.microsoft.com/Adminportal/Home#/servicehealth"), ("How to read service health", "https://learn.microsoft.com/en-us/microsoft-365/enterprise/view-service-health")],
    support=[("Get support (admins)", "https://learn.microsoft.com/en-us/microsoft-365/admin/get-help-support", "Open a service request from the admin center"), ("Contact Microsoft Support (consumers)", "https://support.microsoft.com/en-us/contactus", "Personal and family accounts")],
    phone=f"Microsoft lists support phone numbers by country here: {MSPHONE}.",
    x=[X("MSFT365Status")],
    subscribe=[("Admin center: service health email notifications", "https://learn.microsoft.com/en-us/microsoft-365/enterprise/view-service-health"), ("Follow @MSFT365Status on X", "https://x.com/MSFT365Status")],
    confirm=["Admins: Microsoft 365 admin center → Health → Service health shows incidents for your tenant, with an incident ID and Microsoft's latest update.", "Users: check status.cloud.microsoft and @MSFT365Status; try Outlook or Teams on the web to rule out the desktop app."],
    failover=["Keep a backup channel that does not run on Microsoft 365 (SMS tree, a second chat tool, a phone bridge).", "Make key files available offline (OneDrive 'Always keep on this device').", "Have a way to reach customers if Outlook is down (a status page or social account).", "For email-heavy businesses, consider an email continuity service."],
    monitor=["Turn on service health email notifications in the admin center.", "Follow @MSFT365Status for incident IDs.", "Watch this page; it checks Microsoft's public status every 5 minutes."],
    tips=["Admins: check Health → Service health in the admin center", "Try the web version (outlook.office.com, teams.microsoft.com)", "Switch to a backup channel for urgent messages"],
    notable=[dict(date="Jul 19, 2024", title="CrowdStrike update crashes Windows PCs", cat="thirdparty", quote="CrowdStrike, an independent cybersecurity company, released a software update that began impacting IT systems globally. Although this was not a Microsoft incident…", impact="Windows PCs running CrowdStrike Falcon crashed, so many people could not reach Microsoft 365 at work.", src="https://blogs.microsoft.com/blog/2024/07/20/helping-our-customers-through-the-crowdstrike-outage/", srcn="Microsoft blog"),
             dict(date="Jul 18, 2024", title="Azure Central US storage incident", cat="config", quote="Microsoft's Azure PIR describes an incorrectly published Storage allow list in Central US; Microsoft 365 services were among those affected.", impact="Microsoft 365 services hosted in Central US were disrupted along with Azure.", src="https://azure.status.microsoft/en-us/status/history/?trackingId=1K80-N_8", srcn="Azure PIR 1K80-N_8"),
             dict(date="Jan 25, 2023", title="Microsoft WAN outage hits Teams and Outlook", cat="network", quote="A network engineer was performing an operational task to add network capacity to the global Wide Area Network (WAN)… steps to modify the IP address for each new router.", impact="Teams, Outlook and other Microsoft 365 services were unreachable for many users.", src="https://azure.status.microsoft/en-us/status/history/?trackingId=VSG1-B90", srcn="Azure PIR VSG1-B90")]),
 "gcp": dict(name="Google Cloud", long="Google Cloud (GCP)", src="Google Cloud", icon="cloud", fetch=lambda: google_data("https://status.cloud.google.com/incidents.json", "https://status.cloud.google.com", "Google Cloud"),
    what="Google's cloud platform: Compute Engine, Cloud Storage, BigQuery, Kubernetes Engine and the APIs many apps call.",
    status=("Google Cloud Service Health", "https://status.cloud.google.com"),
    feeds=[("Google Cloud incidents feed", "https://status.cloud.google.com/incidents.json")],
    console=[("Personalized Service Health (your projects)", "https://console.cloud.google.com/servicehealth"), ("Google Cloud support hub", "https://cloud.google.com/support-hub")],
    support=[("Google Cloud support", "https://cloud.google.com/support", "Support plans and how to open a case"), ("Contact Google Cloud", "https://cloud.google.com/contact", "Sales and account questions"), ("Service Health docs", "https://cloud.google.com/service-health/docs/overview", "Set up project-specific incident alerts")],
    phone="Google Cloud does not publish a general support phone number; technical cases are opened in the console.",
    x=[X("googlecloud")],
    subscribe=[("Personalized Service Health alerts", "https://cloud.google.com/service-health/docs/overview"), ("Incidents feed (JSON)", "https://status.cloud.google.com/incidents.json")],
    confirm=["Open Personalized Service Health in the console: it lists incidents that affect your projects, products and locations.", "Compare the affected locations (e.g. us-central1) with where your resources run."],
    failover=["Spread instances across zones with regional managed instance groups; use multi-region buckets for critical data.", "Keep a tested path to a second region for databases (cross-region replicas, multi-region Spanner).", "Add retries with exponential backoff and jitter so you recover cleanly.", "Keep a break-glass deploy path that does not depend on a single region."],
    monitor=["Turn on Personalized Service Health alerts (email, Pub/Sub, webhooks).", "Use Cloud Monitoring uptime checks on your own endpoints.", "Watch this page for the public feed at a glance."],
    tips=["Check Personalized Service Health for your projects", "Compare affected locations with your regions", "Retry with backoff; fail over if your region is named"],
    notable=[dict(date="Jun 12, 2025", title="Global API outage (Service Control)", cat="config", quote="A policy change was inserted into the regional Spanner tables that Service Control uses for policies… This policy data contained unintended blank fields… [it] exercised the code path that hit the null pointer causing the binaries to go into a crash loop.", impact="Google Cloud, Google Workspace and Security Operations returned 503 errors worldwide; services built on them (including Cloudflare's Workers KV) failed too.", src="https://status.cloud.google.com/incidents/ow5i3PPK96RduMcb1SsW", srcn="Google Cloud incident report")]),
 "workspace": dict(name="Google Workspace", long="Google Workspace (Gmail, Drive, Meet, Calendar)", src="Google Workspace (Gmail, Drive, Meet)", icon="mail", fetch=lambda: google_data("https://www.google.com/appsstatus/dashboard/incidents.json", "https://www.google.com/appsstatus/dashboard", "Google Workspace"),
    what="Gmail, Drive, Docs, Meet, Calendar and Chat for businesses, schools and personal Google accounts.",
    status=("Google Workspace Status Dashboard", "https://www.google.com/appsstatus/dashboard/"),
    feeds=[("Google Workspace incidents feed", "https://www.google.com/appsstatus/dashboard/incidents.json")],
    console=[("Google Workspace Status Dashboard (public)", "https://www.google.com/appsstatus/dashboard/"), ("Contact Workspace support (admins)", "https://support.google.com/a/answer/1047213")],
    support=[("Contact Google Workspace support", "https://support.google.com/a/answer/1047213", "Admins open cases by chat, email or phone from the Admin console"), ("Status dashboard summary", "https://www.google.com/appsstatus/dashboard/summary", "Every Workspace product at a glance")],
    phone="Google gives Workspace admins support contact options, including phone, inside the Admin console (Help → Contact support); there is no general public number.",
    x=[X("GoogleWorkspace")],
    subscribe=[("Status dashboard (each incident has updates)", "https://www.google.com/appsstatus/dashboard/"), ("Incidents feed (JSON)", "https://www.google.com/appsstatus/dashboard/incidents.json")],
    confirm=["Check the Workspace Status Dashboard for the product (Gmail, Drive, Meet…) and its incident updates.", "Admins: the Admin console alert center shows tenant-specific issues; try another browser or the mobile app to rule out local problems."],
    failover=["Keep a backup meeting link on another platform for important calls.", "Make critical Docs available offline (Drive offline mode).", "Have a non-Gmail way to reach customers and staff (SMS, a status page, social accounts).", "Export key contacts and calendars periodically."],
    monitor=["Watch the Workspace Status Dashboard and this page.", "Admins: turn on alert center notifications.", "Follow @GoogleWorkspace for major announcements."],
    tips=["Check the Workspace dashboard for your product", "Try the mobile app or another browser", "Move urgent calls to a backup meeting link"],
    notable=[dict(date="Jun 12, 2025", title="Google API outage hits Workspace", cat="config", quote="Google Cloud, Google Workspace and Google Security Operations products experienced increased 503 errors in external API requests… This policy data contained unintended blank fields.", impact="Workspace services that depend on Google's API control plane returned errors for hours.", src="https://status.cloud.google.com/incidents/ow5i3PPK96RduMcb1SsW", srcn="Google incident report")]),
 "cloudflare": dict(name="Cloudflare", long="Cloudflare (CDN, DNS 1.1.1.1, Zero Trust)", src="Cloudflare (CDN, DNS 1.1.1.1)", icon="shield", fetch=lambda: statuspage_data("https://www.cloudflarestatus.com", "Cloudflare"),
    what="A network in front of a large share of websites: CDN, DDoS protection, DNS (including the 1.1.1.1 resolver), WARP and Zero Trust access.",
    status=("Cloudflare status", "https://www.cloudflarestatus.com"),
    feeds=[("Cloudflare Statuspage API", "https://www.cloudflarestatus.com")],
    console=[("Cloudflare dashboard", "https://dash.cloudflare.com"), ("Cloudflare support", "https://www.cloudflare.com/support/")],
    support=[("Contacting Cloudflare support", "https://developers.cloudflare.com/support/contacting-cloudflare-support/", "Which plans get chat, email or phone, and how to open a ticket"), ("Cloudflare support portal", "https://support.cloudflare.com", "Help center and tickets")],
    phone="Cloudflare lists which plans include phone support in its official contact guide (linked above); there is no general public number.",
    x=[X("CloudflareHelp"), X("Cloudflare")],
    subscribe=[("Dashboard notifications (incident and health alerts)", "https://developers.cloudflare.com/notifications/"), ("Subscribe on cloudflarestatus.com (email, SMS, webhook, RSS)", "https://www.cloudflarestatus.com")],
    confirm=["Check cloudflarestatus.com for the data center nearest you (e.g. Miami MIA, Atlanta ATL) and the product you use (CDN, DNS, WARP, Workers).", "On a Cloudflare error page, note the error code and Ray ID: 520–526 usually point at your origin server, other 5xx pages branded Cloudflare at Cloudflare itself."],
    failover=["Document your DNS records and know how to point DNS straight at your origin if the proxy fails.", "If you rely on 1.1.1.1, set a second resolver from another company (e.g. 8.8.8.8 or 9.9.9.9).", "For critical sites, consider a multi-CDN setup.", "Make sure your origin can take traffic directly, and is protected, if you must bypass the proxy."],
    monitor=["Turn on dashboard notifications for incidents affecting your products.", "Subscribe to cloudflarestatus.com.", "This site checks Cloudflare and 1.1.1.1 every 5 minutes and flags data centers near Florida."],
    tips=["Check cloudflarestatus.com for your nearest data center", "Switch your DNS resolver to 8.8.8.8 or 9.9.9.9 if 1.1.1.1 fails", "Site owners: know how to bypass the proxy to your origin"],
    notable=[dict(date="Dec 5, 2025", title="Body-parsing change breaks ~28% of HTTP traffic", cat="config", quote="The issue was not caused, directly or indirectly, by a cyber attack… Instead, it was triggered by changes being made to our body parsing logic while attempting to detect and mitigate an industry-wide vulnerability.", impact="About 25 minutes of failures for a subset of customers (about 28% of HTTP traffic Cloudflare serves).", src="https://blog.cloudflare.com/5-december-2025-outage/", srcn="Cloudflare post-mortem"),
             dict(date="Nov 18, 2025", title="Global outage from a Bot Management feature file", cat="config", quote="The issue was not caused, directly or indirectly, by a cyber attack… it was triggered by a change to one of our database systems' permissions which caused the database to output multiple entries into a 'feature file' used by our Bot Management system.", impact="Error pages on a large share of websites behind Cloudflare worldwide for several hours.", src="https://blog.cloudflare.com/18-november-2025-outage/", srcn="Cloudflare post-mortem"),
             dict(date="Jul 14, 2025", title="1.1.1.1 DNS resolver offline worldwide", cat="config", quote="The root cause was an internal configuration error and not the result of an attack or a BGP hijack.", impact="62 minutes of downtime for the 1.1.1.1 resolver; for many users almost nothing on the Internet would load.", src="https://blog.cloudflare.com/cloudflare-1-1-1-1-incident-on-july-14-2025/", srcn="Cloudflare post-mortem"),
             dict(date="Jun 12, 2025", title="Workers KV outage from a third-party storage provider", cat="thirdparty", quote="Part of this infrastructure is backed by a third-party cloud provider, which experienced an outage today and directly impacted availability of our KV service.", impact="2 hours 28 minutes of impact on Workers KV, WARP, Access, Gateway, Turnstile and more.", src="https://blog.cloudflare.com/cloudflare-service-outage-june-12-2025/", srcn="Cloudflare post-mortem"),
             dict(date="Jul 2, 2019", title="WAF rule exhausts CPU worldwide", cat="config", quote="The CPU exhaustion was caused by a single WAF rule that contained a poorly written regular expression that ended up creating excessive backtracking.", impact="Cloudflare's HTTP/HTTPS service went offline for 27 minutes.", src="https://blog.cloudflare.com/details-of-the-cloudflare-outage-on-july-2-2019/", srcn="Cloudflare post-mortem")]),
 "akamai": dict(name="Akamai", long="Akamai (CDN, Edge DNS, security)", src="Akamai", icon="shield", fetch=lambda: statuspage_data("https://www.akamaistatus.com", "Akamai"),
    what="One of the oldest and largest CDN and edge-security networks, used by banks, airlines, retailers and media sites.",
    status=("Akamai status", "https://www.akamaistatus.com"),
    feeds=[("Akamai Statuspage API", "https://www.akamaistatus.com")],
    console=[("Akamai Control Center", "https://control.akamai.com"), ("Akamai TechDocs", "https://techdocs.akamai.com/")],
    support=[("Akamai Control Center → Support", "https://control.akamai.com", "Customers open cases from Control Center"), ("Akamai status (subscribe)", "https://www.akamaistatus.com", "Email and webhook updates")],
    phone="Akamai gives customers their support contacts inside Control Center; there is no general public support number.",
    x=[X("Akamai")],
    subscribe=[("Subscribe on akamaistatus.com", "https://www.akamaistatus.com")],
    confirm=["Check akamaistatus.com for the product you use (Edge DNS, CDN delivery, security).", "Compare with your own synthetic checks from more than one location."],
    failover=["Keep a secondary DNS provider for critical zones.", "Have a documented origin-direct or second-CDN path for critical sites.", "Cache-friendly design (long cache times for static files) softens short edge incidents."],
    monitor=["Subscribe on akamaistatus.com.", "Use synthetic monitoring from several regions on your key URLs."],
    tips=["Check akamaistatus.com for your product", "Use a secondary DNS provider for critical zones", "Run checks from several locations to confirm"],
    notable=[dict(date="Jul 22, 2021", title="Edge DNS component bug takes down major sites", cat="config", quote="A software configuration update triggered a bug in our Secure Edge Content Delivery Network impacting that network's domain name service (DNS) system… Akamai can confirm this was not a cyberattack.", impact="Many big websites were unreachable for up to an hour.", src="https://www.akamai.com/blog/news/akamai-summarizes-service-disruption-resolved", srcn="Akamai blog")]),
}
ORDER = ["aws", "azure", "m365", "gcp", "workspace", "cloudflare", "akamai"]
SRC2SLUG = {P[s]["src"]: s for s in ORDER}

def data(slug):
    try: return cached("np:" + slug, P[slug]["fetch"])
    except Exception as e: return dict(active=[], history=[], components=[], regions=[], coverage="", error=f"{type(e).__name__}: feed unreachable right now", fetched=None)

# ---------------------------------------------------------------- our own 5-minute checks (netstatus.db, read-only)
def monitor(src, days=7):
    out = dict(days=[], hours=[], pct=None, runs=[], latest=None, first=None)
    try:
        c = sqlite3.connect(f"file:{os.path.join(BASE, 'netstatus.db')}?mode=ro", uri=True, timeout=8)
        since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        rows = c.execute("SELECT ts, level, status, detail FROM checks WHERE src=? AND ts>=? ORDER BY ts", (src, since)).fetchall(); c.close()
    except Exception: return out
    if not rows: return out
    now = datetime.now(timezone.utc); start = (now - timedelta(days=days)).replace(minute=0, second=0, microsecond=0)
    hours = [None] * (days * 24 + 1); per = {}
    for ts, lvl, st, det in rows:
        if lvl is None or lvl < 0: continue
        t = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc); i = int((t - start).total_seconds() // 3600)
        if 0 <= i < len(hours): hours[i] = lvl if hours[i] is None else max(hours[i], lvl)
        dk = to_et(t)[0].strftime("%a %-m/%-d"); p = per.setdefault(dk, [0, 0]); p[1] += 1; p[0] += (lvl <= 1)
    out["hours"] = hours; out["days"] = [dict(day=k, pct=round(100 * v[0] / v[1], 1), n=v[1]) for k, v in per.items()]
    ok = sum(v[0] for v in per.values()); tot = sum(v[1] for v in per.values()); out["pct"] = round(100 * ok / tot, 2) if tot else None
    run = None
    for ts, lvl, st, det in rows:
        if lvl is None or lvl < 0: continue
        if lvl >= 1:
            if run is None: run = dict(start=ts, end=ts, level=lvl, status=st, detail=det or "")
            else: run["end"] = ts; run["level"] = max(run["level"], lvl)
        elif run is not None: out["runs"].append(run); run = None
    if run: run["open"] = True; out["runs"].append(run)
    out["runs"] = out["runs"][-12:][::-1]; out["first"] = rows[0][0]; out["latest"] = dict(ts=rows[-1][0], level=rows[-1][1], status=rows[-1][2])
    return out

def weekly(incs, weeks=13, capped=None):
    now = datetime.now(timezone.utc); out = [[0, 0] for _ in range(weeks)]   # [count, worst severity]; count None = before the feed's history
    if capped:
        for w in range(weeks):
            if now - timedelta(days=7 * w + 7) < capped - timedelta(days=0) and now - timedelta(days=7 * w) <= capped: out[weeks - 1 - w] = [None, 0]
    for i in incs:
        s = i.get("start")
        if not s: continue
        w = (now - s).days // 7
        if 0 <= w < weeks: k = weeks - 1 - w; out[k][0] = (out[k][0] or 0) + 1; out[k][1] = max(out[k][1], i.get("sev", 1))
    return out

def level_of(d, mon):
    # same rule as the Network Status tab: an event open for more than 72 h is long-running (shown as a notice), fresh ones carry their severity
    lv = max([(1 if i.get("longrun") else i["sev"]) for i in d.get("active", [])] or [0])
    la = mon.get("latest") or {}
    fresh = la.get("ts") and (datetime.now(timezone.utc) - datetime.strptime(la["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)).total_seconds() < 1800
    if fresh and (la.get("level") or 0) > lv: lv = la["level"]   # same reading as the Network Status tab row (e.g. Cloudflare major-hub rule)
    if d.get("error") and not d.get("active"): lv = -1 if not fresh else max(0, la.get("level") or 0)
    return lv

def when(i): return fmt_et(i.get("start"), dateonly=bool(i.get("dateonly")))
def jsonable(i):
    j = {k: v for k, v in i.items()}; j["start"] = iso(i.get("start")); j["end"] = iso(i.get("end")); j["start_et"] = when(i); j["end_et"] = fmt_et(i.get("end")) if i.get("end") else None; return j

def brief(slug):
    p = P[slug]; d = data(slug); mon = monitor(p["src"]); allinc = d.get("active", []) + d.get("history", [])
    latest = sorted([i for i in allinc if i.get("start")], key=lambda i: i["start"], reverse=True)
    pick = (d.get("active") or latest or [None])[0]; lv = level_of(d, mon)
    nl = sum(1 for i in d.get("active", []) if i.get("longrun"))
    st = (f'{len(d["active"])} active incident(s)' + (f', {nl} long-running (open more than 72 h)' if nl else "")) if d.get("active") else (d.get("indicator") or "No active incidents in the official feed")
    return dict(slug=slug, name=p["name"], level=lv, level_name=LVN.get(lv, ""), status=st, active=len(d.get("active", [])), latest=jsonable(pick) if pick else None,
                weeks=weekly(allinc, capped=d.get("capped")), uptime7=mon["days"][-8:], uptime_pct=mon["pct"], tips=p["tips"], page=f"/network/{slug}",
                status_url=p["status"][1], status_name=p["status"][0], console=p["console"][0], coverage=d.get("coverage", ""), error=d.get("error"), stale=d.get("stale"),
                fetched=d.get("fetched"), fetched_et=fmt_et(pdt(d.get("fetched"))) if d.get("fetched") else None)

# ---------------------------------------------------------------- graphics (inline SVG, no images, no third-party logos)
IC = {
 "cloud": '<path d="M7 18h10a4 4 0 0 0 .5-7.97A6 6 0 0 0 6.1 9.2 4.5 4.5 0 0 0 7 18z"/>',
 "mail": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
 "shield": '<path d="M12 3 4 6v6c0 4.5 3.4 8.2 8 9 4.6-.8 8-4.5 8-9V6z"/>',
 "config": '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1 7 17M17 7l2.1-2.1"/>',
 "power": '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
 "network": '<circle cx="12" cy="5" r="2"/><circle cx="5" cy="19" r="2"/><circle cx="19" cy="19" r="2"/><path d="M12 7v5M12 12l-6 5M12 12l6 5"/>',
 "attack": '<path d="M12 3 4 6v6c0 4.5 3.4 8.2 8 9 4.6-.8 8-4.5 8-9V6z"/><path d="M12 8v5M12 16h.01"/>',
 "ai": '<rect x="5" y="7" width="14" height="11" rx="2"/><path d="M12 3v4M9 12h.01M15 12h.01M9 15h6"/>',
 "thirdparty": '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
 "unknown": '<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1 .9-1 1.7M12 17h.01"/>',
 "other": '<circle cx="12" cy="12" r="9"/><path d="M8 12h.01M12 12h.01M16 12h.01"/>',
 "check": '<path d="m5 12 4 4 10-10"/>', "phone": '<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z"/>',
 "bell": '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10 21h4"/>', "link": '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
 "x": '<path d="M4 4l16 16M20 4 4 20"/>', "chart": '<path d="M4 20V4M4 20h16M8 16v-5M12 16V8M16 16v-3"/>', "list": '<path d="M9 6h11M9 12h11M9 18h11M4 6h.01M4 12h.01M4 18h.01"/>',
 "msg": '<path d="M4 5h16v11H8l-4 4z"/>', "eye": '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
 "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
}
def ic(n, cls="np-ic"): return f'<svg class="{cls} icon-{n}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{IC.get(n, IC["unknown"])}</svg>'
TILE = ('<svg class="np-tile" viewBox="0 0 1024 1024" aria-hidden="true"><rect x="8" y="8" width="1008" height="1008" rx="192" fill="#0B0D10" stroke="#2f3742" stroke-width="16"/><path fill="#FFFFFF" d="M527.26 681.57V342.43H606.23L755.93 523.16V342.43H849.92V681.57H770.95L621.25 500.84V681.57ZM279.21 681.57V612.29H349.46Q374.17 612.29 387.01 603.81Q399.84 595.33 399.84 577.89Q399.84 560.45 387.01 551.97Q374.17 543.49 349.46 543.49H279.21V477.12H334.93Q359.15 477.12 371.26 468.88Q383.37 460.65 383.37 444.17Q383.37 427.7 371.26 419.71Q359.15 411.71 334.93 411.71H279.21V342.43H347.52Q414.38 342.43 447.32 366.9Q480.27 391.37 480.27 431.09Q480.27 457.25 466.46 476.88Q454.56 493.79 434.38 504.58Q437.52 505.68 440.54 506.91Q467.19 517.81 481.96 538.4Q496.74 558.99 496.74 588.55Q496.74 632.63 461.13 657.1Q425.52 681.57 357.21 681.57Z"/><path fill="#C8102E" d="M180.86 342.43H262.25C266 342.43 269.04 345.47 269.04 349.22V392.63C269.04 396.37 266 399.41 262.25 399.41H180.86C177.12 399.41 174.08 396.37 174.08 392.63V349.22C174.08 345.47 177.12 342.43 180.86 342.43Z"/><path fill="#FFC21A" d="M180.86 483.51H262.25C266 483.51 269.04 486.55 269.04 490.3V533.7C269.04 537.45 266 540.49 262.25 540.49H180.86C177.12 540.49 174.08 537.45 174.08 533.7V490.3C174.08 486.55 177.12 483.51 180.86 483.51ZM180.86 412.97H262.25C266 412.97 269.04 416.01 269.04 419.76V463.17C269.04 466.91 266 469.95 262.25 469.95H180.86C177.12 469.95 174.08 466.91 174.08 463.17V419.76C174.08 416.01 177.12 412.97 180.86 412.97Z"/><path fill="#3FAE80" d="M180.86 624.59H262.25C266 624.59 269.04 627.63 269.04 631.37V674.78C269.04 678.53 266 681.57 262.25 681.57H180.86C177.12 681.57 174.08 678.53 174.08 674.78V631.37C174.08 627.63 177.12 624.59 180.86 624.59ZM180.86 554.05H262.25C266 554.05 269.04 557.09 269.04 560.83V604.24C269.04 607.99 266 611.03 262.25 611.03H180.86C177.12 611.03 174.08 607.99 174.08 604.24V560.83C174.08 557.09 177.12 554.05 180.86 554.05Z"/></svg>')   # logo V2-final tile (Nov 1 2026)
def gauge(lv):
    c = LVC.get(lv, "#5b6573"); frac = {0: 1.0, 1: .7, 2: .45, 3: .2}.get(lv, 0); R_ = 44; L = 2 * math.pi * R_
    return (f'<svg class="np-gauge" viewBox="0 0 110 110" role="img" aria-label="Status: {E(LVN.get(lv, ""))}"><circle cx="55" cy="55" r="{R_}" fill="none" stroke="#1f252c" stroke-width="10"/>'
            f'<circle cx="55" cy="55" r="{R_}" fill="none" stroke="{c}" stroke-width="10" stroke-linecap="round" stroke-dasharray="{L * frac:.1f} {L:.1f}" transform="rotate(-90 55 55)"/>'
            f'<circle class="np-pulse" cx="55" cy="55" r="10" fill="{c}"/></svg>')
def hour_strip(hours):
    if not hours or all(h is None for h in hours): return '<p class="np-mu">No checks stored yet for this provider.</p>'
    n = len(hours); w = 100 / n
    cells = "".join(f'<rect x="{i * w:.3f}" y="0" width="{w + .03:.3f}" height="22" fill="{LVC.get(h) if h is not None else "#1f252c"}"/>' for i, h in enumerate(hours))
    return f'<svg class="np-strip" viewBox="0 0 100 22" preserveAspectRatio="none" role="img" aria-label="Hourly status over the last 7 days">{cells}</svg>'
def bars_weeks(wk, W=260):
    mx = max([c or 0 for c, _ in wk] or [1]) or 1; n = len(wk); H = 70; bw = W / n; out = []
    for i, (c, s) in enumerate(wk):
        if c is None:
            out.append(f'<rect x="{i * bw + 2:.1f}" y="{H - 20}" width="{bw - 4:.1f}" height="20" rx="2" fill="none" stroke="#3a424d" stroke-dasharray="2 2"><title>Before the feed history: no data</title></rect>'); continue
        h = 4 if c == 0 else 8 + (H - 20) * c / mx
        out.append(f'<rect x="{i * bw + 2:.1f}" y="{H - h:.1f}" width="{bw - 4:.1f}" height="{h:.1f}" rx="2" fill="{LVC[min(3, max(1, s))] if c else "#232a33"}"><title>{c} incident(s)</title></rect>'
                   + (f'<text x="{i * bw + bw / 2:.1f}" y="{H - h - 3:.1f}" text-anchor="middle" font-size="9" fill="#c9d1db">{c}</text>' if c else ""))
    return (f'<svg class="np-bars" viewBox="0 0 {W} {H + 14}" role="img" aria-label="Incidents per week, last 13 weeks">{"".join(out)}'
            f'<text x="0" y="{H + 12}" font-size="9" fill="#8a94a3">13 weeks ago</text><text x="{W}" y="{H + 12}" font-size="9" fill="#8a94a3" text-anchor="end">this week</text></svg>')
def months_chart(incs, months=12, capped=None, W=600, cls="np-months"):
    now = datetime.now(timezone.utc); keys = []; y, m = now.year, now.month
    for _ in range(months):
        keys.append((y, m)); m -= 1
        if m == 0: y, m = y - 1, 12
    keys = keys[::-1]; cnt = {k: [0, 0, 0, 0] for k in keys}
    for i in incs:
        s = i.get("start")
        if s and (s.year, s.month) in cnt: cnt[(s.year, s.month)][max(0, min(3, i.get("sev", 1)))] += 1
    mx = max([sum(v) for v in cnt.values()] or [1]) or 1; H = 150; bw = W / months; parts = []
    for gi in range(4):
        yv = H - (H - 18) * gi / 3; parts.append(f'<line x1="0" x2="{W}" y1="{yv:.1f}" y2="{yv:.1f}" stroke="#1f252c"/>')
    for i, k in enumerate(keys):
        v = cnt[k]; y0 = H
        for sv in (1, 2, 3, 0):
            if v[sv]:
                h = (H - 18) * v[sv] / mx; y0 -= h
                parts.append(f'<rect x="{i * bw + 6:.1f}" y="{y0:.1f}" width="{bw - 12:.1f}" height="{h:.1f}" fill="{LVC[sv] if sv else "#4a5563"}"><title>{datetime(k[0], k[1], 1):%b %Y}: {v[sv]} {LVN[sv].lower()}</title></rect>')
        if sum(v): parts.append(f'<text x="{i * bw + bw / 2:.1f}" y="{y0 - 4:.1f}" text-anchor="middle" font-size="12" fill="#e6e9ee" font-weight="700">{sum(v)}</text>')
        if capped and (k[0], k[1]) < (capped.year, capped.month):
            parts.append(f'<rect x="{i * bw + 6:.1f}" y="{H - 30}" width="{bw - 12:.1f}" height="30" fill="none" stroke="#3a424d" stroke-dasharray="3 3"><title>No data: before the feed history</title></rect>')
        parts.append(f'<text x="{i * bw + bw / 2:.1f}" y="{H + 16}" text-anchor="middle" font-size="12" fill="#8a94a3">{datetime(k[0], k[1], 1):%b}</text>')
    return f'<svg class="{cls}" viewBox="0 0 {W} {H + 22}" role="img" aria-label="Incidents per month, last {months} months">{"".join(parts)}</svg>'
def donut(counts):
    tot = sum(counts.values()) or 1; R_ = 40; L = 2 * math.pi * R_; off = 0; seg = []
    for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
        if not v: continue
        f = v / tot; seg.append(f'<circle cx="55" cy="55" r="{R_}" fill="none" stroke="{CAT_COL[k]}" stroke-width="16" stroke-dasharray="{L * f:.2f} {L:.2f}" stroke-dashoffset="{-off:.2f}" transform="rotate(-90 55 55)"><title>{E(CAT_NAME[k])}: {v}</title></circle>'); off += L * f
    return (f'<svg class="np-donut" viewBox="0 0 110 110" role="img" aria-label="Incidents by cause">{"".join(seg)}<text x="55" y="55" text-anchor="middle" font-size="20" font-weight="800" fill="currentColor">{sum(counts.values())}</text>'
            '<text x="55" y="69" text-anchor="middle" font-size="9" fill="#8a94a3">incidents</text></svg>')
def chip(cat): return f'<span class="np-cause" style="--c:{CAT_COL[cat]}">{ic(cat, "np-ic sm")}{E(CAT_NAME[cat])}</span>'
def lvchip(lv): return f'<span class="np-lv" style="--c:{LVC.get(lv, "#5b6573")}"><i></i>{E(LVN.get(lv, ""))}</span>'
def ext(url, text): return f'<a href="{E(url)}" target="_blank" rel="noopener">{E(text)}</a>'

# ---------------------------------------------------------------- page styles (Signal: near-black + red, Montserrat headings, Inter body)
CSS = """
.wrap{max-width:1120px!important}
.np{--hot:#FF4D4F;--line:var(--bd,#232a33);font-family:var(--bn-font-body,Inter,system-ui,sans-serif)}
.np h1,.np h2,.np h3{font-family:var(--bn-font-ui,Montserrat,system-ui,sans-serif);letter-spacing:-.01em}
.np-ic{width:20px;height:20px;flex:none}.np-ic.sm{width:14px;height:14px}
.np-hero{position:relative;overflow:hidden;border:1px solid var(--line);border-radius:18px;padding:20px;margin:6px 0 16px;background:radial-gradient(120% 140% at 100% 0,rgba(200,16,46,.2),transparent 55%),var(--pn,#12161b)}
.np-hero:after{content:"";position:absolute;inset:0;pointer-events:none;background-image:radial-gradient(rgba(255,255,255,.05) 1px,transparent 1px);background-size:14px 14px;-webkit-mask-image:linear-gradient(90deg,transparent,#000 75%);mask-image:linear-gradient(90deg,transparent,#000 75%)}
.np-hrow{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:18px;align-items:center;position:relative;z-index:1}
.np-tile{width:58px;height:58px}.np-gauge{width:110px;height:110px}
.np-pulse{transform-origin:55px 55px;animation:npp 2.4s ease-in-out infinite}@keyframes npp{50%{transform:scale(1.25);opacity:.75}}@media(prefers-reduced-motion:reduce){.np-pulse{animation:none}}
.np-kick{font:700 11.5px/1.3 var(--bn-font-ui,Montserrat,sans-serif);letter-spacing:.14em;text-transform:uppercase;color:var(--hot);margin:0 0 6px;display:flex;gap:7px;align-items:center}
.np-kick i{width:8px;height:8px;border-radius:50%;background:var(--hot);box-shadow:0 0 0 4px rgba(255,77,79,.18);flex:none}
.np-hero h1{font-size:clamp(24px,4vw,38px);line-height:1.08;margin:0 0 6px;font-weight:800;overflow-wrap:anywhere}.np-hero h1 em{font-style:normal;color:var(--hot)}
.np-hero p{margin:0;color:var(--bn-text-2,#c9d1db);font-size:15px;max-width:760px}
.np-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:16px 0 0;position:relative;z-index:1}
.np-kpi{background:rgba(0,0,0,.25);border:1px solid var(--line);border-radius:12px;padding:10px 12px;min-width:0}.np-kpi b{display:block;font:800 22px/1.15 var(--bn-font-ui,Montserrat,sans-serif);overflow-wrap:anywhere}.np-kpi span{font-size:12px;color:var(--mu,#8a94a3);display:block}
.np-lv{display:inline-flex;align-items:center;gap:6px;font-weight:800;font-size:13px;color:var(--c)}.np-lv i{width:10px;height:10px;border-radius:50%;background:var(--c);box-shadow:0 0 0 3px rgba(255,255,255,.06)}
.np-sec{background:var(--pn,#12161b);border:1px solid var(--line);border-radius:14px;padding:16px;margin:0 0 14px;min-width:0}
.np-sec>h2{display:flex;align-items:center;gap:9px;font-size:18px;margin:0 0 4px}.np-sec>h2 .np-ic{color:var(--hot)}
.np-sub{font-size:13px;color:var(--mu,#8a94a3);margin:0 0 12px}.np-mu{color:var(--mu,#8a94a3);font-size:13px}
.np-grid2{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:14px}.np-grid2>.np-sec{margin-bottom:0}.np-gap{margin-bottom:14px}
.np-act{border:1px solid var(--line);border-left:4px solid var(--c);border-radius:10px;padding:10px 12px;margin:0 0 10px;background:var(--bn-surface,#161b21);overflow-wrap:anywhere}
.np-act h3{font-size:15px;margin:0 0 4px}.np-act .m{font-size:12.5px;color:var(--mu,#8a94a3)}.np-act p{font-size:13.5px;margin:6px 0 0;color:var(--bn-text-2,#c9d1db)}
.np-tags{display:flex;flex-wrap:wrap;gap:5px;margin:6px 0 0}.np-tag{font-size:11.5px;border:1px solid var(--line);border-radius:6px;padding:1px 7px;background:rgba(0,0,0,.25);max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.np-tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(175px,100%),1fr));gap:8px}
.np-t{border:1px solid var(--line);border-radius:10px;padding:9px 10px;background:var(--bn-surface,#161b21);min-width:0}.np-t b{display:flex;gap:6px;align-items:center;font-size:13px;overflow-wrap:anywhere}.np-t b i{width:9px;height:9px;border-radius:50%;flex:none}
.np-t small{display:block;color:var(--mu,#8a94a3);font-size:11.5px;margin-top:3px;overflow-wrap:anywhere}
.np-meter{height:6px;border-radius:4px;background:#232a33;overflow:hidden;margin-top:6px;display:flex}.np-meter span{display:block;height:100%}
.np-h3{font-size:14px;margin:14px 0 8px}
.np-strip{width:100%;height:30px;border-radius:6px;display:block}
.np-axis{display:flex;justify-content:space-between;font-size:11px;color:var(--mu,#8a94a3);margin-top:3px}
.np-days{display:grid;grid-template-columns:repeat(auto-fit,minmax(62px,1fr));gap:6px;margin-top:10px}.np-day{text-align:center;font-size:11px;color:var(--mu,#8a94a3)}.np-day b{display:block;font-size:15px}
.np-months,.np-bars{width:100%;height:auto;display:block}
.np-tl{list-style:none;margin:0;padding:0}.np-tl li{position:relative;padding:0 0 14px 20px;border-left:2px solid #2a313a;margin-left:7px;overflow-wrap:anywhere}
.np-tl li:before{content:"";position:absolute;left:-7px;top:3px;width:12px;height:12px;border-radius:50%;background:var(--c);box-shadow:0 0 0 3px var(--pn,#12161b)}
@media(min-width:1000px){.np-cols{columns:2;column-gap:28px}.np-cols li{break-inside:avoid}}
.np-tl .w{font-size:12px;color:var(--mu,#8a94a3)}.np-tl h3{font-size:14.5px;margin:2px 0}.np-tl p{font-size:13px;margin:4px 0 0;color:var(--bn-text-2,#c9d1db)}
.np-cause{display:inline-flex;align-items:center;gap:5px;font-size:11.5px;font-weight:700;color:var(--c);border:1px solid var(--c);background:rgba(255,255,255,.03);border-radius:999px;padding:2px 9px;margin:4px 6px 0 0;max-width:100%}
.np-ev{font-size:12.5px;color:var(--bn-text-2,#c9d1db);border-left:3px solid #2f3742;padding:2px 0 2px 9px;margin:6px 0 0;font-style:italic}
.np-dwrap{display:grid;grid-template-columns:130px minmax(0,1fr);gap:16px;align-items:center}.np-donut{width:130px;height:130px;color:var(--tx,#e6e9ee)}
.np-leg{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(210px,100%),1fr));gap:6px}.np-leg div{display:flex;gap:7px;align-items:center;font-size:13px}.np-leg i{width:10px;height:10px;border-radius:3px;flex:none}
.np-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(300px,100%),1fr));gap:12px}
.np-card{border:1px solid var(--line);border-radius:12px;padding:12px 14px;background:var(--bn-surface,#161b21);display:flex;flex-direction:column;gap:4px;min-width:0}
.np-card .d{font-size:12px;color:var(--mu,#8a94a3);font-weight:700;letter-spacing:.04em;text-transform:uppercase}.np-card h3{font-size:15px;margin:0}.np-card p{font-size:13px;margin:2px 0;color:var(--bn-text-2,#c9d1db)}
.np-card a.s{display:inline-flex;gap:5px;align-items:center;font-size:12.5px;margin-top:auto;padding-top:6px}
.np-steps{counter-reset:s;list-style:none;margin:0;padding:0}.np-steps li{counter-increment:s;position:relative;padding:8px 0 8px 40px;border-top:1px solid var(--line);font-size:14px}.np-steps li:first-child{border-top:0}
.np-steps li:before{content:counter(s);position:absolute;left:0;top:7px;width:28px;height:28px;border-radius:8px;background:rgba(200,16,46,.16);color:#ff6b6e;font:800 13px/28px var(--bn-font-ui,Montserrat,sans-serif);text-align:center}
.np-steps label{display:flex;gap:10px;align-items:flex-start;cursor:pointer}.np-steps input{margin-top:4px;accent-color:#c8102e;flex:none}
.np-tpl{border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin:0 0 10px;background:rgba(0,0,0,.25)}.np-tpl b{font-size:13px}.np-tpl p{font-size:13px;margin:6px 0 0;color:var(--bn-text-2,#c9d1db);white-space:pre-wrap;overflow-wrap:anywhere}
.np-btn{display:inline-flex;align-items:center;gap:6px;font:700 13px/1.1 var(--bn-font-ui,Montserrat,sans-serif);border-radius:9px;padding:9px 12px;border:1px solid var(--bd2,#2f3742);color:var(--tx,#e6e9ee);background:var(--bn-surface,#161b21);text-decoration:none;cursor:pointer}
.np-btn.p{background:#c8102e;border-color:#c8102e;color:#fff}.np-btns{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 0;position:relative;z-index:1}
.np-links{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(min(320px,100%),1fr));column-gap:20px}.np-links li{display:flex;gap:10px;align-items:flex-start;padding:8px 0;border-top:1px solid var(--line);font-size:14px;overflow-wrap:anywhere;min-width:0}
.np-links .np-ic{color:var(--hot);margin-top:1px}.np-links small{display:block;color:var(--mu,#8a94a3);font-size:12px}
.np-note{font-size:12.5px;color:var(--mu,#8a94a3);border:1px dashed #2f3742;border-radius:10px;padding:8px 10px;margin:10px 0 0;position:relative;z-index:1}
.np-crumb{font-size:13px;color:var(--mu,#8a94a3);margin:0 0 8px;overflow-wrap:anywhere}.np-crumb a{color:var(--mu,#8a94a3)}
.np-provs{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(250px,100%),1fr));gap:12px}
.np-pv{display:flex;flex-direction:column;gap:6px;border:1px solid var(--line);border-radius:14px;padding:14px;background:var(--pn,#12161b);text-decoration:none;color:var(--tx,#e6e9ee);min-width:0}
.np-pv:hover,.np-pv:focus-visible{border-color:#c8102e}.np-pv h2{font-size:17px;margin:0;display:flex;gap:8px;align-items:center}.np-pv h2 .np-ic{color:var(--hot)}.np-pv p{font-size:13px;color:var(--bn-text-2,#c9d1db);margin:0;overflow-wrap:anywhere}
.np-nl{display:flex;flex-wrap:wrap;gap:10px;align-items:center;justify-content:space-between;border:1px solid rgba(200,16,46,.5);background:linear-gradient(90deg,rgba(200,16,46,.18),transparent);border-radius:14px;padding:14px 16px;margin:0 0 14px}
.np-nl b{font-family:var(--bn-font-ui,Montserrat,sans-serif);font-size:16px}
.np-legend{display:flex;flex-wrap:wrap;gap:12px;font-size:12px;color:var(--mu,#8a94a3);margin-top:8px}.np-legend span{display:inline-flex;gap:5px;align-items:center}.np-legend i{width:10px;height:10px;border-radius:3px}
.np-mb{display:none}@media(max-width:640px){.np-dk{display:none}.np-mb{display:block}}
@media(max-width:900px){.np-grid2{grid-template-columns:1fr}.np-grid2>.np-sec{margin-bottom:14px}.np-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:560px){.np-hrow{grid-template-columns:auto minmax(0,1fr)}.np-hrow .np-gauge{display:none}.np-tile{width:44px;height:44px}.np-hero{padding:15px}.np-dwrap{grid-template-columns:1fr}.np-donut{margin:0 auto}.np-btn{flex:1 1 auto;justify-content:center}.np-kpi b{font-size:19px}}
html[data-theme=light] .np-hero,html[data-theme=light] .np-sec,html[data-theme=light] .np-pv{background:#fff}html[data-theme=light] .np-tpl,html[data-theme=light] .np-tag,html[data-theme=light] .np-kpi{background:#f3f4f6}
.np-hubq{display:flex;flex-wrap:wrap;gap:10px;align-items:center;justify-content:space-between;border:1px solid var(--line);border-radius:14px;padding:12px 14px;margin:0 0 14px;background:var(--pn,#12161b)}
.np-hubq form{display:flex;gap:8px;flex:1 1 320px;margin:0}.np-hubq b{font-family:var(--bn-font-ui,Montserrat,sans-serif);font-size:15px;display:flex;gap:8px;align-items:center}
.np-attr{font-size:12.5px;line-height:1.45;color:var(--mu,#8a94a3);margin:8px 0 0}.np-attr b{color:var(--tx,#e6e9ee)}
@media(max-width:560px){.np-hubq form{flex-wrap:wrap}.np-hubq .np-btn{flex:1 1 100%;justify-content:center}}
"""
JS = """<script>document.addEventListener("click",function(e){var b=e.target.closest&&e.target.closest("[data-copy]");if(!b)return;var el=document.getElementById(b.dataset.copy),t=el.innerText;
(navigator.clipboard?navigator.clipboard.writeText(t):Promise.reject()).then(function(){b.textContent="Copied";setTimeout(function(){b.textContent="Copy"},1800)}).catch(function(){var r=document.createRange();r.selectNodeContents(el);var s=getSelection();s.removeAllRanges();s.addRange(r)})});
document.querySelectorAll(".np-steps input[type=checkbox]").forEach(function(c){var k="np_ck_"+c.id;try{c.checked=localStorage.getItem(k)==="1"}catch(_){}c.addEventListener("change",function(){try{localStorage.setItem(k,c.checked?"1":"0")}catch(_){}})});</script>"""
LEG = '<div class="np-legend"><span><i style="background:#2BB673"></i>Operational</span><span><i style="background:#F5A524"></i>Minor</span><span><i style="background:#FF7A1A"></i>Degraded</span><span><i style="background:#FF4D4F"></i>Major</span><span><i style="border:1px dashed #3a424d"></i>No data</span></div>'

def inc_card(i, active=False):
    c = LVC.get(i.get("sev", 1), "#F5A524")
    w = when(i) + (f' → {fmt_et(i["end"])}' if i.get("end") else (" · long-running, still open" if i.get("longrun") else (" · ongoing" if active else "")))
    sv = i.get("services") or []
    tags = "".join(f'<span class="np-tag" title="{E(x)}">{ic("globe", "np-ic sm")} {E(x)}</span>' for x in (i.get("regions") or [])[:6]) + "".join(f'<span class="np-tag" title="{E(x)}">{E(x)}</span>' for x in sv[:8])
    more = len(sv) - 8
    return (f'<div class="np-act" style="--c:{c}"><h3>{E(i["title"])}</h3><div class="m">{E(w)} · {E(LVN.get(i.get("sev"), ""))} · source: {ext(i["url"], i.get("src") or "official status")}</div>'
            + (f'<div class="np-tags">{tags}' + (f'<span class="np-tag">+{more} more services</span>' if more > 0 else "") + '</div>' if tags else "")
            + (f'<p>{E(i["summary"][:420])}{"…" if len(i["summary"]) > 420 else ""}</p>' if i.get("summary") else "") + '</div>')

def render(slug):
    p = P[slug]; d = data(slug); mon = monitor(p["src"]); lv = level_of(d, mon)
    act = d.get("active", []); hist = d.get("history", []); allinc = act + hist; now = datetime.now(timezone.utc)
    yr = [i for i in allinc if i.get("start") and (now - i["start"]).days <= 365]
    n90 = sum(1 for i in allinc if i.get("start") and (now - i["start"]).days <= 90)
    k_mon = f'{mon["pct"]:.2f}%' if mon.get("pct") is not None else "—"
    hero = (f'<section class="np-hero page-header-band"><div class="np-hrow">{TILE}<div style="min-width:0"><div class="np-kick"><i></i>BLACKOUT.NETWORK · NETWORK STATUS</div>'
            f'<h1>{E(p["name"])} status <em>right now</em></h1><p>{E(p["what"])}</p></div>{gauge(lv)}</div>'
            f'<div class="np-kpis"><div class="np-kpi">{lvchip(lv)}<span>{E(("Official: " + d["indicator"]) if d.get("indicator") else (str(len(act)) + " active incident(s)" if act else "No active incidents in the official feed"))}</span>'
            + (f'<span>Our check: {E((mon.get("latest") or {}).get("status", ""))}</span>' if (mon.get("latest") or {}).get("level") else "") + '</div>'
            f'<div class="np-kpi"><b>{len(act)}</b><span>active incidents now</span></div><div class="np-kpi"><b>{n90}</b><span>incidents in the last 90 days (official feed)</span></div>'
            f'<div class="np-kpi"><b>{k_mon}</b><span>of our 5-minute checks with no degraded or major status, last 7 days</span></div></div>'
            f'<div class="np-btns"><a class="np-btn p" href="{E(p["status"][1])}" target="_blank" rel="noopener">{ic("link", "np-ic sm")}Official status page</a>'
            f'<a class="np-btn" href="{E(p["console"][0][1])}" target="_blank" rel="noopener">{ic("eye", "np-ic sm")}{E(p["console"][0][0])}</a><a class="np-btn" href="#checklist">{ic("check", "np-ic sm")}If your business runs on {E(p["name"])}</a></div>'
            + (f'<p class="np-note">The official feed could not be reached just now ({E(d["error"])}); figures below use our stored checks.</p>' if d.get("error") else "")
            + (f'<p class="np-note">Showing the last good copy of the official feed (refresh failed: {E(d["stale"])}).</p>' if d.get("stale") else "") + '</section>')
    live = "".join(inc_card(i, True) for i in act) or (f'<div class="np-act" style="--c:{LVC[0]}"><h3>No active incidents reported by {E(p["name"])}</h3><div class="m">Checked '
                                                     f'{E(fmt_et(pdt(d.get("fetched"))) if d.get("fetched") else "—")} · official feed, refreshed every 10 minutes</div></div>')
    comp = ""
    if d.get("groups"):
        tiles = []
        for g in d["groups"]:
            if g["small"]: continue
            tot = max(1, g["total"]); okp = 100 * g["ok"] / tot; mp = 100 * g["maint"] / tot; bp = max(0, 100 - okp - mp)
            tiles.append(f'<div class="np-t"><b><i style="background:{LVC[0 if g["bad"] == 0 else (1 if g["bad"] < 3 else 2)]}"></i>{ic("globe", "np-ic sm")}{E(g["name"])}</b><small>{g["ok"]} of {g["total"]} sites normal'
                         + (f' · {g["maint"]} in maintenance' if g["maint"] else "") + (f' · {g["bad"]} degraded or re-routed' if g["bad"] else "") + '</small>'
                         f'<div class="np-meter" role="img" aria-label="{g["ok"]} normal, {g["maint"]} maintenance, {g["bad"]} degraded"><span style="width:{okp:.1f}%;background:#2BB673"></span><span style="width:{mp:.1f}%;background:#4aa3ff"></span><span style="width:{bp:.1f}%;background:#FF7A1A"></span></div>'
                         + (f'<small>{E(", ".join(g["worst"][:3]))}</small>' if g["worst"] else "") + '</div>')
        svc = [k for g in d["groups"] if g["small"] for k in g["kids"]] + (d.get("components") or [])
        if tiles: comp += f'<h3 class="np-h3">Edge data centers by region</h3><div class="np-tiles">{"".join(tiles)}</div><p class="np-mu" style="margin-top:6px">Green = normal, blue = planned maintenance, orange = degraded or re-routed. A few sites re-routed at any time is normal; traffic moves to the next site.</p>'
        if svc:
            bad = [x for x in svc if x["level"] > 0]; shown = sorted(svc, key=lambda x: -x["level"])[:24]
            comp += (f'<h3 class="np-h3">Services and components · {len(svc) - len(bad)} of {len(svc)} normal</h3><div class="np-tiles">'
                     + "".join(f'<div class="np-t"><b><i style="background:{LVC.get(x["level"], "#5b6573")}"></i>{E(x["name"])}</b><small>{E(x["status"])}</small></div>' for x in shown) + '</div>')
    elif d.get("components"):
        comp += f'<h3 class="np-h3">Services</h3><div class="np-tiles">' + "".join(f'<div class="np-t"><b><i style="background:{LVC.get(x["level"], "#5b6573")}"></i>{E(x["name"])}</b><small>{E(x["status"])}</small></div>' for x in d["components"]) + '</div>'
    if d.get("regions"):
        comp += f'<h3 class="np-h3">Regions with active problems</h3><div class="np-tiles">' + "".join(f'<div class="np-t"><b><i style="background:{LVC.get(r["level"], "#5b6573")}"></i>{ic("globe", "np-ic sm")}{E(r["name"])}</b><small>{E(r["note"])}</small></div>' for r in d["regions"]) + '</div>'
    elif not d.get("groups") and not d.get("components"):
        comp += f'<p class="np-mu" style="margin-top:10px">{E(p["name"])} does not publish a public per-region component list; when an incident is open, its regions and services appear on the incident above.</p>'
    sec_live = f'<section class="np-sec" id="live"><h2>{ic("eye")}Live status</h2><p class="np-sub">From {E(", ".join(f[0] for f in p["feeds"]))}. Times in Eastern (ET).</p>{live}{comp}</section>'
    days = "".join(f'<div class="np-day"><b style="color:{LVC[0] if x["pct"] >= 99.5 else (LVC[1] if x["pct"] >= 95 else LVC[3])}">{x["pct"]:.0f}%</b>{E(x["day"])}</div>' for x in mon.get("days", [])[-8:])
    runs = "".join(f'<li style="--c:{LVC.get(r["level"], "#F5A524")}"><div class="w">{E(fmt_et(pdt(r["start"])))} → {"ongoing" if r.get("open") else E(fmt_et(pdt(r["end"])))}</div><h3>{E(r["status"])}</h3>'
                   + (f'<p>{E(r["detail"][:240])}</p>' if r.get("detail") else "") + '</li>' for r in mon.get("runs", [])[:6])
    sec_mon = (f'<section class="np-sec"><h2>{ic("chart")}Our 5-minute checks · last 7 days</h2><p class="np-sub">We read {E(p["name"])}\'s official status every 5 minutes. Each sliver is one hour, colored by the worst status seen; the daily figure is the share of checks with no degraded or major status.'
               + (f' Stored since {E(fmt_et(pdt(mon["first"])))}.' if mon.get("first") else "") + '</p>' + hour_strip(mon.get("hours"))
               + ('<div class="np-axis"><span>7 days ago</span><span>now</span></div>' if mon.get("hours") else "") + f'<div class="np-days">{days}</div>'
               + (f'<h3 class="np-h3">Periods flagged by our checks</h3><ul class="np-tl">{runs}</ul>' if runs else '<p class="np-mu" style="margin-top:10px">No problems flagged by our checks in this window.</p>') + '</section>')
    first = d.get("capped") or min((i["start"] for i in allinc if i.get("start")), default=None)
    short = first is None or (now - first).days < 330
    sec_hist = (f'<section class="np-sec"><h2>{ic("chart")}Incident history</h2><p class="np-sub">Incidents per month from the official feed, by severity. {E(d.get("coverage", ""))}'
                + (' <b>History is short:</b> dashed boxes and empty months before the feed\'s first entry mean no published data, not a clean record.' if short else "") + '</p>'
                f'<div class="np-dk">{months_chart(allinc, capped=d.get("capped"))}</div><div class="np-mb">{months_chart(allinc, months=6, capped=d.get("capped"), W=320)}</div>'
                f'<h3 class="np-h3">Last 13 weeks</h3><div class="np-dk">{bars_weeks(weekly(allinc, capped=d.get("capped")), W=600)}</div><div class="np-mb">{bars_weeks(weekly(allinc, capped=d.get("capped")))}</div>{LEG}</section>')
    counts, rows = {}, []
    for i in sorted(yr, key=lambda i: i["start"], reverse=True):
        cz = i.get("cause"); cat = (cz or {}).get("cat", "unknown"); counts[cat] = counts.get(cat, 0) + 1
        if len(rows) < 25:
            rows.append(f'<li style="--c:{LVC.get(i.get("sev", 1))}"><div class="w">{E(when(i))}' + (f' · resolved {E(fmt_et(i["end"]))}' if i.get("end") else (" · ongoing" if i in act else "")) + f'</div><h3>{E(i["title"][:200])}</h3>'
                        + chip(cat) + (f'<p class="np-ev">“{E(cz["evidence"])}” <span class="np-mu">— {E(cz["who"])}</span></p>' if cz else '<p class="np-mu">No cause stated in the official record yet.</p>')
                        + f'<p>{ext(i["url"], "Official incident report" if (i.get("pir") or cz) else "Official incident page")}</p></li>')
    leg = "".join(f'<div><i style="background:{CAT_COL[k]}"></i>{E(CAT_NAME[k])}: <b>{v}</b></div>' for k, v in sorted(counts.items(), key=lambda kv: -kv[1]))
    sec_rc = (f'<section class="np-sec"><h2>{ic("unknown")}Root causes: hack, AI, config error or something else?</h2><p class="np-sub">For each incident in the past year we show a cause only when {E(p["name"])}\'s own report states one, quoting the sentence. '
              'The category is our label for that sentence; anything else is marked <b>Unconfirmed / not yet disclosed</b>.</p>'
              + (f'<div class="np-dwrap">{donut(counts)}<div class="np-leg">{leg}</div></div><ul class="np-tl np-cols" style="margin-top:14px">{"".join(rows)}</ul>' if rows else
                 f'<p class="np-mu">No incidents in the public feed for the past year. {E(d.get("coverage", ""))} See the notable outages below.</p>') + '</section>')
    cards = "".join(f'<article class="np-card"><span class="d">{E(n["date"])}</span><h3>{E(n["title"])}</h3><div>{chip(n["cat"])}</div><p class="np-ev">“{E(n["quote"])}”</p><p><b>Impact:</b> {E(n["impact"])}</p>'
                    f'<a class="s" href="{E(n["src"])}" target="_blank" rel="noopener">{ic("link", "np-ic sm")}{E(n["srcn"])}</a></article>' for n in p["notable"])
    sec_nt = f'<section class="np-sec"><h2>{ic("list")}Notable past outages</h2><p class="np-sub">The big ones, with the cause in the official write-up\'s own words.</p><div class="np-cards">{cards}</div></section>'
    steps = [("1 · Confirm the impact", p["confirm"] + CHECK_COMMON), ("2 · Fail over and limit the damage", p["failover"]), ("3 · Monitor and get alerts", p["monitor"])]
    ck = "".join(f'<h3 class="np-h3" style="font-size:15px">{E(h)}</h3><ol class="np-steps">' + "".join(f'<li><label><input type="checkbox" id="{slug}-{si}-{ii}">{E(t)}</label></li>' for ii, t in enumerate(items)) + '</ol>' for si, (h, items) in enumerate(steps))
    tpls = "".join(f'<div class="np-tpl"><div style="display:flex;justify-content:space-between;gap:8px;align-items:center"><b>{E(t)}</b><button class="np-btn" type="button" data-copy="tpl-{slug}-{k}">Copy</button></div><p id="tpl-{slug}-{k}">{E(b.replace("{provider}", p["name"]))}</p></div>' for k, (t, b) in enumerate(COMMS))
    sec_ck = (f'<section class="np-sec" id="checklist"><h2>{ic("check")}If your business runs on {E(p["name"])}</h2><p class="np-sub">A short playbook. Tick items as you go (saved on this device only).</p>'
              f'<div class="np-grid2"><div>{ck}</div><div><h3 class="np-h3" style="font-size:15px">4 · Communication templates</h3>{tpls}<p class="np-mu">Fill in the {{curly}} parts. Post updates somewhere not hosted on the affected provider.</p></div></div></section>')
    li = lambda icon, items: "".join(f'<li>{ic(icon)}<div>{ext(u, t)}' + (f'<small>{E(n)}</small>' if n else "") + '</div></li>' for t, u, n in items)
    links = (li("eye", [(p["status"][0], p["status"][1], "Public status page")] + [(t, u, "Official feed we read") for t, u in p["feeds"] if u != p["status"][1]])
             + li("config", [(t, u, "Your own account view") for t, u in p["console"]]) + li("msg", p["support"])
             + f'<li>{ic("phone")}<div><b>Phone support</b><small style="font-size:13px">{p["phone"]}</small></div></li>'
             + li("x", [(h, u, "Official account on X") for h, u in p["x"]]) + li("bell", [(t, u, "Get alerts") for t, u in p["subscribe"]]))
    sec_ln = f'<section class="np-sec"><h2>{ic("link")}Official links, contacts and alerts</h2><p class="np-sub">Every link checked before publishing. Phone numbers only where {E(p["name"])} publishes them.</p><ul class="np-links">{links}</ul></section>'
    others = " · ".join(f'<a href="/network/{s}">{E(P[s]["name"])}</a>' for s in ORDER if s != slug) + ' · <a href="/network/starlink">Starlink</a> · <a href="/network/near">Networks near me</a>'
    nl = ('<div class="np-nl"><div><b>Know about the next big outage first</b><div class="np-mu">The free BLACKOUT.NETWORK newsletter: major outages, threats and what to do. Follow us on YouTube and X too.</div></div>'
          '<a class="np-btn p" href="/newsletter?utm_source=site&amp;utm_medium=network_page&amp;utm_campaign=' + slug + '">Get the free newsletter</a></div>')
    body = (f'<div class="np"><p class="np-crumb"><a href="/">BLACKOUT.NETWORK</a> › <a href="/#net">Network Status</a> › <a href="/network">Providers</a> › {E(p["name"])}</p>'
            + hero + sec_live + f'<div class="np-grid2 np-gap">{sec_mon}{sec_hist}</div>' + sec_rc + sec_nt + nl + sec_ck + sec_ln
            + f'<p class="np-mu">Other providers: {others} · <a href="/#net">All network checks</a>. Research only; not affiliated with {E(p["long"])}. Names identify services only.</p></div>'
            f'<style>{CSS}</style>{JS}')
    title = f"Is {p['name']} down? Live status, outages and root causes"
    desc = (f"Live {p['name']} status from the official feed, incident history, root causes (config error, cyberattack, power, DNS), notable past outages, "
            f"a business action checklist and official support links. Checked every 5 minutes.")[:300]
    ld = [{"@context": "https://schema.org", "@type": "WebPage", "name": title, "description": desc, "url": f"{SITE}/network/{slug}", "dateModified": iso(now),
           "isPartOf": {"@type": "WebSite", "name": "BLACKOUT.NETWORK", "url": SITE}, "about": {"@type": "Organization", "name": p["long"], "url": p["status"][1]},
           "publisher": {"@type": "Organization", "name": "BLACKOUT.NETWORK", "url": SITE, "logo": {"@type": "ImageObject", "url": f"{SITE}/icons/icon-512.png"}}},
          {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
              {"@type": "ListItem", "position": 1, "name": "BLACKOUT.NETWORK", "item": SITE + "/"}, {"@type": "ListItem", "position": 2, "name": "Network providers", "item": SITE + "/network"},
              {"@type": "ListItem", "position": 3, "name": p["name"], "item": f"{SITE}/network/{slug}"}]},
          {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
              {"@type": "Question", "name": f"Is {p['name']} down right now?", "acceptedAnswer": {"@type": "Answer", "text": (f"{p['name']} reports {len(act)} active incident(s)." if act else f"{p['name']}'s official feed shows no active incidents.") + f" Latest status: {p['status'][1]}"}},
              {"@type": "Question", "name": f"Where do I check {p['name']} status for my own account?", "acceptedAnswer": {"@type": "Answer", "text": f"{p['console'][0][0]}: {p['console'][0][1]}"}},
              {"@type": "Question", "name": f"What caused past {p['name']} outages?", "acceptedAnswer": {"@type": "Answer", "text": " ".join(f"{n['date']}: {n['title']} ({CAT_NAME[n['cat']]})." for n in p["notable"][:3])}}]}]
    return site_page.page(title, desc, body, f"/network/{slug}", active="net", jsonld=ld, og_type="website")

def render_hub():
    with ThreadPoolExecutor(8) as ex:
        fsl = ex.submit(sl_brief); bs = list(ex.map(lambda s: (s, brief(s)), ORDER)); slb = fsl.result()
    cards = []
    for s, b in bs:
        p = P[s]; lt = b.get("latest")
        cards.append(f'<a class="np-pv" href="/network/{s}"><h2>{ic(p["icon"])}{E(p["name"])}</h2>{lvchip(b["level"])}<p>{E(b["status"])}</p>'
                     + (f'<p class="np-mu">Latest: {E(lt["title"][:110])} · {E(lt["start_et"])}</p>' if lt else "") + f'{bars_weeks(b["weeks"])}<span class="np-mu">Full analysis →</span></a>')
    lt = slb.get("latest")
    try: attr = sl().ioda_credit_html(_sys_mod(), fmt_et(datetime.now(timezone.utc)))
    except Exception: attr = ""
    cards.append(f'<div class="np-pv"><a href="/network/starlink" style="display:flex;flex-direction:column;gap:6px;color:inherit;text-decoration:none"><h2>{ic("network")}Starlink</h2>{lvchip(slb["level"])}<p>{E(slb["status"])}</p>'
                 + (f'<p class="np-mu">Latest signal: {E(lt["title"][:110])} · {E(lt["start_et"])}</p>' if lt else '<p class="np-mu">Satellite internet. Independent measurements (IODA); live constellation map.</p>')
                 + (bars_weeks(slb["weeks"]) if slb.get("weeks") else "") + '<span class="np-mu">Status, satellites and speeds →</span></a>' + attr + '</div>')
    body = (f'<div class="np"><p class="np-crumb"><a href="/">BLACKOUT.NETWORK</a> › <a href="/#net">Network Status</a> › Providers</p>'
            f'<section class="np-hero page-header-band"><div class="np-hrow">{TILE}<div style="min-width:0"><div class="np-kick"><i></i>BLACKOUT.NETWORK · NETWORK STATUS</div><h1>Is the cloud down? <em>Provider by provider</em></h1>'
            '<p>Live status, incident history, root causes and a what-to-do checklist for the clouds and networks most businesses run on. Official feeds; times in ET.</p></div></div></section>'
            + HUBQ.replace("{pin}", ic("network")) + f'<div class="np-provs">{"".join(cards)}</div>{LEG}<p class="np-mu" style="margin-top:8px">Bars: incidents per week over the last 13 weeks from each official feed (Starlink: IODA outage signals). <a href="/#net">See every network check</a> · <a href="/network/near">Networks near me</a>.</p></div><style>{CSS}</style>')
    desc = "Is AWS, Azure, Microsoft 365, Google Cloud, Google Workspace, Cloudflare, Akamai or Starlink down? Live status, incidents, root causes and what to do, plus a networks-near-me check."
    ld = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Cloud and network provider status", "url": SITE + "/network", "description": desc,
          "hasPart": [{"@type": "WebPage", "name": f"{P[s]['name']} status", "url": f"{SITE}/network/{s}"} for s in ORDER] + [{"@type": "WebPage", "name": "Starlink status", "url": f"{SITE}/network/starlink"}]}
    return site_page.page("Is the cloud down? AWS, Azure, Microsoft 365, Google, Cloudflare status", desc, body, "/network", active="net", jsonld=ld, og_type="website")

# ---------------------------------------------------------------- Starlink + Networks near me (netstarlink.py; reloaded when that file changes)
_SLM = [None, None]
def sl():
    import importlib, sys as _sys
    f = os.path.join(BASE, "netstarlink.py"); mt = os.path.getmtime(f)
    if _SLM[0] != mt or _SLM[1] is None:
        _SLM[1] = importlib.reload(_SLM[1]) if _SLM[1] is not None else (importlib.reload(_sys.modules["netstarlink"]) if "netstarlink" in _sys.modules else importlib.import_module("netstarlink"))
        _SLM[0] = mt
    return _SLM[1]
def sl_brief():
    try: return sl().brief(_sys_mod())
    except Exception as e: return dict(slug="starlink", name="Starlink", level=-1, level_name=LVN[-1], status=f"Measurements unavailable ({type(e).__name__})", latest=None, weeks=[], page="/network/starlink")
def _sys_mod():
    import sys as _sys
    return _sys.modules[__name__]
HUBQ = ('<div class="np-hubq"><b>{pin}Networks near me</b><form action="/network/near" method="get" role="search"><label for="hub_q" class="np-mu" style="position:absolute;left:-9999px">ZIP code or city</label>'
        '<input id="hub_q" name="where" placeholder="ZIP code or city, e.g. 32771" maxlength="120" style="flex:1 1 200px;min-width:0;font:500 15px/1.2 var(--bn-font-body,Inter,sans-serif);padding:10px 12px;border-radius:10px;border:1px solid var(--bd2,#2f3742);background:var(--bn-surface,#161b21);color:var(--tx,#e6e9ee)">'
        '<button class="np-btn p" type="submit">Check status and weather</button></form></div>')

# ---------------------------------------------------------------- accordion for the dashboard's Network Status tab (enhances #ns_list rows in place)
ACC_JS = r"""(function(){
var MAP=__MAP__,OPEN={},CACHE={},C={0:"#2BB673",1:"#F5A524",2:"#FF7A1A",3:"#FF4D4F","-1":"#5b6573"};
function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]})}
function css(){if(document.getElementById("nsa-css"))return;var s=document.createElement("style");s.id="nsa-css";s.textContent=
".nsa{margin:3px 0;border-radius:8px;background:var(--bn-surface,#161b21);border:1px solid transparent;min-width:0}.nsa.open{border-color:rgba(200,16,46,.55)}"+
".nsa>.nsa-b{appearance:none;-webkit-appearance:none;background:none;border:0;margin:0;font:inherit;text-align:left;box-sizing:border-box;width:100%;cursor:pointer;display:grid;grid-template-columns:14px minmax(140px,1.1fr) minmax(0,1.6fr) minmax(150px,1.3fr) 20px;gap:10px;align-items:center;padding:7px 8px;border-radius:8px;font-size:12.5px;color:var(--tx)}"+
".nsa>.nsa-b:hover{background:#1c232b}.nsa>.nsa-b:focus-visible{outline:2px solid #c8102e;outline-offset:1px}.nsa-b .nm{font-weight:700;color:var(--tx);overflow-wrap:anywhere;min-width:0}.nsa-b .nm small{display:block;font-weight:700;color:#ff6b6e;font-size:10px;letter-spacing:.08em}"+
".nsa-b .d{width:11px;height:11px;border-radius:50%}.nsa-b .c3{min-width:0}.nsa-b .st{color:var(--tx)}.nsa-b .dt{color:var(--mu);font-size:11.5px;display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.nsa-b .ns-h{min-width:0}"+
".nsa-chev{width:18px;height:18px;transition:transform .25s;color:var(--mu)}.nsa.open .nsa-chev{transform:rotate(180deg);color:#ff6b6e}"+
".nsa-p{display:grid;grid-template-rows:0fr;transition:grid-template-rows .28s ease}.nsa.open .nsa-p{grid-template-rows:1fr}.nsa-p>div{overflow:hidden;min-height:0}.nsa-p[aria-hidden=true]>div{visibility:hidden}"+
".nsa-in{padding:4px 12px 14px 32px;display:grid;grid-template-columns:minmax(0,1.5fr) minmax(0,1fr);gap:16px;font-size:13px}"+
".nsa-in h4{font:700 10.5px/1.2 Montserrat,system-ui,sans-serif;letter-spacing:.1em;text-transform:uppercase;color:var(--mu);margin:10px 0 6px}"+
"html[data-theme=light] .nsa-inc{background:#f3f4f6!important}.nsa-inc{border-left:3px solid var(--c);padding:7px 10px;background:rgba(0,0,0,.22);border-radius:6px;overflow-wrap:anywhere}.nsa-inc b{display:block;font-size:13.5px}.nsa-inc .m{font-size:11.5px;color:var(--mu)}.nsa-inc p{margin:5px 0 0;color:var(--bn-text-2,#c9d1db);font-size:12.5px}"+
".nsa-tags{display:flex;flex-wrap:wrap;gap:4px;margin-top:5px}.nsa-tags span{font-size:11px;border:1px solid var(--bd);border-radius:5px;padding:0 6px;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}"+
".nsa-tips{margin:0;padding:0;list-style:none}.nsa-tips li{display:flex;gap:8px;align-items:flex-start;padding:3px 0}.nsa-tips li:before{content:'';flex:none;width:7px;height:7px;margin-top:6px;border-radius:2px;background:#c8102e}"+
".nsa-sp{width:100%;height:46px;display:block}.nsa-cap{font-size:11px;color:var(--mu)}.nsa-up{display:flex;gap:3px;margin-top:4px}.nsa-up i{flex:1;height:18px;border-radius:3px}"+
".nsa-acts{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}.nsa-acts a{display:inline-flex;align-items:center;gap:6px;font:700 12.5px/1.1 Montserrat,system-ui,sans-serif;padding:8px 11px;border-radius:8px;text-decoration:none;border:1px solid var(--bd2,#2f3742);color:var(--tx)}.nsa-acts a.p{background:#c8102e;border-color:#c8102e;color:#fff}"+
"@media(max-width:760px){.nsa>.nsa-b{grid-template-columns:12px minmax(0,1fr) 20px;row-gap:4px}.nsa-b .c3,.nsa-b .ns-h{grid-column:2/3}.nsa-b .nsa-chev{grid-row:1;grid-column:3}.nsa-in{grid-template-columns:1fr;padding:2px 10px 12px;gap:4px}.nsa-acts a{flex:1 1 auto;justify-content:center}}"+
"@media(prefers-reduced-motion:reduce){.nsa-p,.nsa-chev{transition:none}}.np-attr{font-size:11.5px;line-height:1.45;color:var(--mu);margin:8px 0 0}.np-attr a{color:inherit}";document.head.appendChild(s)}
var CHEV='<svg class="nsa-chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>';
function spark(w){if(!w||!w.length)return"";var mx=1;w.forEach(function(x){if(x[0]>mx)mx=x[0]});var n=w.length,bw=260/n,o="";
 w.forEach(function(x,i){if(x[0]==null){o+='<rect x="'+(i*bw+2).toFixed(1)+'" y="26" width="'+(bw-4).toFixed(1)+'" height="14" rx="2" fill="none" stroke="#3a424d" stroke-dasharray="2 2"><title>No data in the feed for this week</title></rect>';return}
  var h=x[0]?6+30*x[0]/mx:3;o+='<rect x="'+(i*bw+2).toFixed(1)+'" y="'+(40-h).toFixed(1)+'" width="'+(bw-4).toFixed(1)+'" height="'+h.toFixed(1)+'" rx="2" fill="'+(x[0]?C[Math.max(1,Math.min(3,x[1]))]:"#2a313a")+'"><title>'+x[0]+' incident(s)</title></rect>'});
 return '<svg class="nsa-sp" viewBox="0 0 260 42" preserveAspectRatio="none" role="img" aria-label="Incidents per week, last 13 weeks">'+o+'</svg>'}
function panel(b){var L=b.latest,h='<div class="nsa-in"><div>';
 h+='<h4>'+(b.latest_label||(b.active?"Active incident":"Latest incident in the official feed"))+'</h4>';
 if(L){var tg=(L.regions||[]).slice(0,4).concat((L.services||[]).slice(0,5));h+='<div class="nsa-inc" style="--c:'+(C[L.sev]||C[1])+'"><b>'+esc(L.title)+'</b><span class="m">'+esc(L.start_et)+(L.end_et?' → '+esc(L.end_et):(b.active?(L.longrun?' · long-running, still open':' · ongoing'):''))+' · <a href="'+esc(L.url)+'" target="_blank" rel="noopener">'+esc(b.source_label||"official source")+'</a></span>'+
   (tg.length?'<div class="nsa-tags">'+tg.map(function(t){return'<span title="'+esc(t)+'">'+esc(t)+'</span>'}).join("")+'</div>':"")+(L.summary?'<p>'+esc(L.summary.slice(0,260))+(L.summary.length>260?"…":"")+'</p>':"")+
   '<p style="font-size:12px">'+(L.cause?'Cause per '+esc(L.cause.who)+': <b>'+esc(L.cause.name)+'</b>':'Cause: <b>Unconfirmed / not yet disclosed</b>')+'</p></div>'}
 else h+='<div class="nsa-inc" style="--c:'+C[0]+'"><b>No incidents listed in the official feed right now</b><span class="m">'+esc(b.coverage||"")+'</span></div>';
 h+='<h4>What to do now</h4><ul class="nsa-tips">'+b.tips.map(function(t){return"<li>"+esc(t)+"</li>"}).join("")+'</ul></div><div>';
 h+='<h4>'+(b.slug==="starlink"?"Outage signals per week":"Incidents per week")+' · last 13 weeks</h4>'+spark(b.weeks)+'<div class="nsa-cap">'+(b.weeks_note?esc(b.weeks_note):'From the official feed. '+esc((b.coverage||"").split(";")[0].split(". ")[0]))+'</div>'+(b.attribution_html||'');
 if(b.uptime7&&b.uptime7.length){h+='<h4>Our 5-minute checks'+(b.uptime_pct!=null?' · '+b.uptime_pct.toFixed(2)+'% clean':'')+'</h4><div class="nsa-up">'+b.uptime7.map(function(d){var c=d.pct>=99.5?C[0]:d.pct>=95?C[1]:C[3];return'<i style="background:'+c+'" title="'+esc(d.day)+': '+d.pct+'% of checks with no degraded or major status"></i>'}).join("")+'</div><div class="nsa-cap">One bar per day (ET), last 7 days.</div>'}
 h+='<div class="nsa-acts"><a class="p" href="'+esc(b.page)+'">'+(b.slug==="starlink"?"Status, satellites and speeds →":"Full analysis →")+'</a><a href="'+esc(b.status_url)+'" target="_blank" rel="noopener">Official status</a><a href="'+esc(b.console[1])+'" target="_blank" rel="noopener">'+esc(b.console[0].split(" (")[0].split(" → ")[0])+'</a></div>';
 return h+'</div></div>'}
function load(slug,box){if(CACHE[slug]&&Date.now()-CACHE[slug].t<300000){box.innerHTML=panel(CACHE[slug].b);return}
 if(!box.innerHTML)box.innerHTML='<div class="nsa-in"><div class="nsa-cap">Loading the official feed…</div></div>';
 fetch("/api/network/"+slug+"/brief").then(function(r){if(!r.ok)throw 0;return r.json()}).then(function(b){CACHE[slug]={t:Date.now(),b:b};box.innerHTML=panel(b)}).catch(function(){box.innerHTML='<div class="nsa-in"><div class="nsa-cap">Could not load right now. <a href="/network/'+slug+'">Open the full page</a>.</div></div>'})}
function toggle(w,force){var o=force!=null?force:!w.classList.contains("open"),slug=w.dataset.slug,b=w.querySelector(".nsa-b"),p=w.querySelector(".nsa-p");
 w.classList.toggle("open",o);b.setAttribute("aria-expanded",o?"true":"false");p.setAttribute("aria-hidden",o?"false":"true");if(o){OPEN[slug]=1;load(slug,p.firstChild)}else delete OPEN[slug]}
var SLB=null,SLT=0;
function slRow(list){if(list.querySelector('.nsa[data-slug="starlink"],.ns-row[data-sl]'))return;var b=SLB,lv=b?b.level:null;
 var row='<div class="ns-row" data-sl="1"><span class="d'+(lv!=null&&lv>=0?' ns-l'+lv:'')+'"></span><span>Starlink</span><span><span class=st>'+esc(b?b.status:"Loading independent measurements…")+'</span><span class=dt>Satellite internet · IODA measurements of AS14593</span></span><span class=ns-h></span></div>';
 if(list.querySelector("details.bn-acc")){var block='<details class="bn-acc bn-acc-ns" id="acc-ns-satellite-internet" open><summary aria-expanded="true"><span class="bn-acc-t"><b>Satellite internet</b><small>Starlink</small></span></summary><div class="bn-acc-body"><h3>Satellite internet</h3>'+row+'</div></details>';
  var dns=null,cloud=null;list.querySelectorAll("details.bn-acc").forEach(function(d){var h=d.querySelector("h3"),n=h&&h.firstChild,t=((n&&n.nodeType===3?n.textContent:h&&h.textContent)||"").trim();if(t==="DNS & CDN")dns=d;else if(t==="Big cloud")cloud=d});
  var after=dns||cloud;if(after)after.insertAdjacentHTML("afterend",block);else list.insertAdjacentHTML("beforeend",block);return}
 var hs=[].slice.call(list.querySelectorAll("h3")),afterH=null;hs.forEach(function(h){var n=h.firstChild,t=((n&&n.nodeType===3?n.textContent:h.textContent)||"").trim();if(t==="Big cloud"||t==="DNS & CDN")afterH=h});
 var html='<h3>Satellite internet</h3>'+row,next=null;if(afterH){next=afterH.nextElementSibling;while(next&&next.tagName!=="H3")next=next.nextElementSibling}
 if(next)next.insertAdjacentHTML("beforebegin",html);else list.insertAdjacentHTML("beforeend",html)}
function slFetch(){if(Date.now()-SLT<300000)return;SLT=Date.now();fetch("/api/network/starlink/brief",{credentials:"same-origin"}).then(function(r){if(!r.ok)throw 0;return r.json()}).then(function(b){SLB=b;CACHE.starlink={t:Date.now(),b:b};
 var w=document.querySelector('.nsa[data-slug="starlink"]');if(w){var st=w.querySelector(".nsa-b .st"),d=w.querySelector(".nsa-b .d");if(st&&b.status)st.textContent=b.status;if(d&&b.level!=null&&b.level>=0)d.className="d ns-l"+b.level}
 var row=document.querySelector(".ns-row[data-sl]");if(row){var st2=row.querySelector(".st");if(st2&&b.status)st2.textContent=b.status}}).catch(function(){})}
function enhance(){var list=document.getElementById("ns_list");if(!list)return;css();if(list.querySelector(".ns-row")){slRow(list);slFetch()}
 list.querySelectorAll("h3").forEach(function(h){if(h.querySelector(".nsa-hub"))return;var n=h.firstChild,t=((n&&n.nodeType===3?n.textContent:h.textContent)||"").trim();if(t==="Big cloud"||t==="DNS & CDN"){h.insertAdjacentHTML("beforeend",' <a class="nsa-hub" href="'+(t==="Big cloud"?"/network/near":"/network")+'" style="float:right;font-size:11px;letter-spacing:.04em;color:#ff6b6e;text-decoration:none;text-transform:none">'+(t==="Big cloud"?"Networks near me &rarr;":"Provider pages &rarr;")+'</a>')}});
 list.querySelectorAll(".ns-row").forEach(function(r){var nmEl=r.children[1],nm=(nmEl&&nmEl.textContent||"").trim(),slug=MAP[nm];if(!slug)return;
  var w=document.createElement("div");w.className="nsa";w.dataset.slug=slug;var id="nsa-p-"+slug;
  w.innerHTML='<button type="button" class="nsa-b" aria-expanded="false" aria-controls="'+id+'">'+r.children[0].outerHTML+'<span class="nm">'+esc(nm)+'<small>DETAILS &amp; WHAT TO DO</small></span><span class="c3">'+(r.children[2]?r.children[2].innerHTML:"")+'</span>'+(r.children[3]?r.children[3].outerHTML:"")+CHEV+'</button><div class="nsa-p" id="'+id+'" role="region" aria-hidden="true" aria-label="'+esc(nm)+' details"><div></div></div>';
  r.replaceWith(w);w.querySelector(".nsa-b").addEventListener("click",function(){toggle(w)});if(OPEN[slug])toggle(w,true)})}
function watch(){var list=document.getElementById("ns_list");if(!list)return setTimeout(watch,600);enhance();var mo=new MutationObserver(function(){mo.disconnect();enhance();mo.observe(list,{childList:true})});mo.observe(list,{childList:true})}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",watch);else watch()})();"""

def acc_js(): return ACC_JS.replace("__MAP__", json.dumps(dict(SRC2SLUG, Starlink="starlink"))).encode()

def handle_get(path, qs, headers=None):
    p = path.rstrip("/") or "/"
    if p in ("/network/starlink", "/network/near") or p.startswith("/api/network/starlink") or p == "/api/network/near":
        r = sl().handle_get(p, qs or {}, _sys_mod(), headers)
        if r is not None: return r
    if p == "/network": return 200, render_hub(), "text/html"
    m = re.fullmatch(r"/network/([a-z0-9]+)", p)
    if m and m.group(1) in P: return 200, render(m.group(1)), "text/html"
    if p == "/api/network/accordion.js": return 200, acc_js(), "application/javascript; charset=utf-8"
    m = re.fullmatch(r"/api/network/([a-z0-9]+)/brief", p)
    if m and m.group(1) in P: return 200, brief(m.group(1))
    m = re.fullmatch(r"/api/network/([a-z0-9]+)", p)
    if m and m.group(1) in P:
        d = data(m.group(1))
        return 200, {"slug": m.group(1), "active": [jsonable(i) for i in d.get("active", [])], "history": [jsonable(i) for i in d.get("history", [])[:60]],
                     "coverage": d.get("coverage"), "fetched": d.get("fetched"), "error": d.get("error")}
    if p == "/api/network": return 200, {"providers": [{"slug": s, "name": P[s]["name"], "page": f"/network/{s}", "api": f"/api/network/{s}/brief"} for s in ORDER]
                                         + [{"slug": "starlink", "name": "Starlink", "page": "/network/starlink", "api": "/api/network/starlink/brief"}],
                                         "near_me": {"page": "/network/near", "api": "/api/network/near?q=<ZIP or place>"}}
    return 404, {"error": "not found"}
