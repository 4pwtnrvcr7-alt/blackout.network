"""On-site detail page for every service on the Network Status board: /grid/status/<id> (Nov 23 2026, pt1785u).
Matt: each item needs a scrollable history of uptime and downtime and how many users were affected, hosted on our own site,
with the original sources kept but secondary. History is ours (netboard tables in votes.db); user counts are only ever our own
"Down for me" reports or a number the provider itself publishes, labeled as such. Nothing is estimated or invented."""
from urllib.parse import urlparse
import html, json
from datetime import datetime, timezone, timedelta
E = lambda s: html.escape(str(s if s is not None else ""), quote=True)
LVC = {3: "#FF4D4F", 2: "#FF7A1A", 1: "#FFA040", 0: "#2BB673", -1: "#2a3039"}
WORD = {3: "Major outage", 2: "Disruption", 1: "Minor issue", 0: "Normal", -1: "No live feed"}

def _et(ts, day=False):
    try:
        import netpages as NP
        return NP.fmt_et(datetime.fromisoformat(str(ts).replace("Z", "+00:00")), dateonly=day)
    except Exception:
        return str(ts or "")[:16].replace("T", " ") + " UTC"
def _dur(m):
    if m is None: return ""
    m = max(1, int(m)); return f"{m} min" if m < 60 else (f"{m // 60} h" + (f" {m % 60} min" if m % 60 else "")) if m < 1440 else f"{round(m / 1440)} d"
def _p(s):
    try: return datetime.fromisoformat(str(s).replace("Z", "+00:00")) if s else None
    except Exception: return None
def short(n): return n.split(" (")[0]
def sub(n): return n[n.index("(") + 1: n.rindex(")")] if "(" in n and n.endswith(")") else ""
def word(n, lv):
    if n.get("watch") and lv < 0: return "No live signal"
    return WORD.get(lv, WORD[-1])

CSS = """
.sd{max-width:1080px;margin:0 auto;padding:8px 0 40px;color:#e6e9ef}
.sd a{color:#cfd6e2}.sd-crumb{font-size:12px;color:#8a94a3;margin:0 0 14px}.sd-crumb a{color:#8a94a3;text-decoration:none}
.sd-h{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:12px;border-bottom:1px solid #1c2129;padding-bottom:16px}
.sd-h h1{font-size:30px;letter-spacing:.02em;margin:0;font-weight:600}.sd-h p{margin:4px 0 0;color:#8a94a3;font-size:13px}
.sd-pill{display:inline-flex;align-items:center;gap:8px;border:1px solid var(--c);color:#fff;border-radius:999px;padding:7px 14px;font-size:13px;letter-spacing:.06em;text-transform:uppercase}
.sd-pill i{width:9px;height:9px;border-radius:50%;background:var(--c);box-shadow:0 0 10px var(--c)}
.sd-st{font-size:16px;margin:14px 0 4px;color:#fff}.sd-mu{color:#8a94a3;font-size:12.5px;line-height:1.5}
.sd-g{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin:18px 0}
.sd-c{background:#0b0e13;border:1px solid #1c2129;border-radius:10px;padding:12px 14px}
.sd-c span{display:block;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#8a94a3}.sd-c b{display:block;font-size:17px;margin-top:6px;font-weight:600}
.sd-c small{display:block;color:#8a94a3;font-size:11.5px;margin-top:4px;line-height:1.4}
.sd h2{font-size:13px;letter-spacing:.12em;text-transform:uppercase;color:#aab3c2;margin:28px 0 10px;font-weight:600}
.sd-bar{display:grid;grid-template-columns:repeat(90,1fr);gap:2px;height:44px}.sd-bar i{border-radius:2px;background:var(--c)}
.sd-bar i.nd{background:transparent;border:1px dashed #2a3039}
.sd-ax{display:flex;justify-content:space-between;font-size:11px;color:#6f7988;margin-top:6px}
.sd-leg{display:flex;flex-wrap:wrap;gap:14px;font-size:11.5px;color:#8a94a3;margin-top:8px}.sd-leg i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:-1px}
.sd-hr{display:grid;grid-template-columns:repeat(24,1fr);gap:3px;align-items:end;height:56px}.sd-hr i{background:var(--c);border-radius:2px}
.sd-rp{display:grid;grid-template-columns:repeat(30,1fr);gap:3px;align-items:end;height:70px;border-bottom:1px solid #1c2129}.sd-rp i{background:#7fd3ff;border-radius:2px 2px 0 0;min-height:1px}
.sd-log{max-height:440px;overflow:auto;-webkit-overflow-scrolling:touch;border:1px solid #1c2129;border-radius:10px;background:#0b0e13}
.sd-log ul{list-style:none;margin:0;padding:0}.sd-log li{display:flex;gap:12px;padding:12px 14px;border-bottom:1px solid #151a21}.sd-log li:last-child{border:0}
.sd-log li>i{flex:0 0 auto;width:9px;height:9px;border-radius:50%;margin-top:5px;background:var(--c)}.sd-log b{font-weight:600;font-size:14px}.sd-log p{margin:3px 0 0;font-size:12px;color:#8a94a3}
.sd-empty{padding:16px;color:#8a94a3;font-size:13px}
.sd-act{display:flex;flex-wrap:wrap;gap:10px;margin:16px 0 0}
.sd-btn{appearance:none;background:transparent;border:1px solid #3a424d;color:#fff;border-radius:999px;padding:10px 18px;font:inherit;font-size:13px;letter-spacing:.06em;text-transform:uppercase;cursor:pointer;text-decoration:none}
.sd-btn:hover{border-color:#8a94a3}.sd-btn[disabled]{opacity:.6}
.sd-news{list-style:none;padding:0;margin:0}.sd-news li{padding:8px 0;border-bottom:1px solid #151a21;font-size:13px}.sd-news small{color:#8a94a3;display:block;margin-top:2px}
.sd-src{font-size:12px;color:#8a94a3;margin-top:26px;line-height:1.7}.sd-src a{color:#aab3c2}
@media (max-width:600px){.sd-h h1{font-size:24px}.sd-bar{height:36px;gap:1px}.sd-g{grid-template-columns:1fr 1fr}.sd-c b{font-size:15px}}
"""
JS = """<script>(function(){var b=document.getElementById("sd_down");if(!b)return;var k="bn_nb_rep",id=b.dataset.id;
function mine(){try{var m=JSON.parse(localStorage.getItem(k)||"{}");return m[id]&&Date.now()-m[id]<9e5}catch(e){return false}}
if(mine()){b.textContent="Reported. Thanks";b.disabled=true}
b.onclick=function(){if(b.disabled)return;b.disabled=true;b.textContent="Sending";fetch("/api/vote/netdown",{method:"POST",headers:{"Content-Type":"application/json"},credentials:"same-origin",body:JSON.stringify({svc:id})})
.then(function(r){return r.json().then(function(j){if(r.ok||r.status===429){try{var m=JSON.parse(localStorage.getItem(k)||"{}");m[id]=Date.now();localStorage.setItem(k,JSON.stringify(m))}catch(e){}b.textContent=r.ok?"Reported. Thanks":"Already counted. Thanks"}else{b.textContent=j.error||"Could not send";b.disabled=false}})},function(){b.textContent="Could not send. Try again";b.disabled=false})}})();</script>"""

def render(n, hist, rep, generated=None, prov_inc=()):
    nm = short(n["name"]); lv = n.get("level", -1); c = LVC.get(lv, "#7C8190") if lv >= 0 else "#7C8190"; sg = n.get("sig") or {}; r = rep or {}
    days = hist.get("days") or []; prov = n.get("days_full") or n.get("days") or []
    # merge the provider's own 30-day incident history (when it publishes one) into our stored daily levels
    if prov:
        off = len(days) - len(prov)
        for i, v in enumerate(prov):
            j = off + i
            if 0 <= j < len(days) and v is not None: days[j] = dict(days[j], lv=max(days[j]["lv"], v) if days[j]["lv"] >= 0 else v, prov=True)
    bar = "".join(f'<i style="--c:{LVC.get(d["lv"], LVC[-1])}" class="{"nd" if d["lv"] < 0 else ""}" title="{E(d["day"])}: {E(WORD.get(d["lv"], "No data"))}"></i>' for d in days)
    h24 = n.get("h24") or [-1] * 24
    hrs = "".join(f'<i style="--c:{LVC.get(v, LVC[-1])};height:{[10, 30, 55, 78, 100][v + 1] if v is not None else 10}%"></i>' for v in h24)
    d30 = days[-30:]; mx = max([d["reports"] for d in d30] + [1])
    rp = "".join(f'<i style="height:{(100 * d["reports"] / mx) if d["reports"] else 0:.0f}%" title="{E(d["day"])}: {d["reports"]} reports"></i>' for d in d30)
    rep30 = sum(d["reports"] for d in d30)
    since = hist.get("since"); upt = hist.get("uptime")
    upline = (f'{upt:.2f}% of the hours we tracked had no disruption' if upt is not None else "Not enough history yet") + (f' (our own checks start {E(_et(since, True))})' if since else "")
    if n.get("uptime") is not None: upline += f' · {n["uptime"]:.2f}% over 30 days by the provider\'s own incident reports, shown in the bar'
    elif n.get("watch"): upline += f' · {E(nm)} publishes no incident history, so earlier days show no data'
    # signals
    cards = []
    if n.get("watch"):
        cards.append(("Official status page", "None published", f"{nm} does not publish a public status page we can read."))
        cards.append(("News reports, last 6 h", str(sg.get("news", 0)) if sg.get("news_ok") is not False else "Search unavailable",
                      f'{sg.get("news48", 0)} in the last 48 h that name {nm} and an outage' + (" (one of our two news searches failed on the last check)" if sg.get("news_ok") == "partial" else "") if sg.get("news_ok") is not False else "The news search did not answer on the last check; showing the last good result."))
        w = sg.get("web"); code = sg.get("web_code"); ms = sg.get("web_ms")
        cards.append(("Website reachable", {"reachable": "Yes", "connection only": "Connects", "server error": "Server errors", "unreachable": "No"}.get(w, "Unknown"),
                      (f"HTTP {code} in {ms} ms. " if code else "Secure connection made; the site refused a plain page request. " if w == "connection only" else "")
                      + f'We load {E(urlparse(sg.get("web_url") or "").netloc or "the sign-in site")} every 4 min. It shows the site answers, not that logins, the app or card payments work.'))
    elif n.get("kind") == "asn":
        cards.append(("Official status page", "None published", "Measured with IODA internet signals (Georgia Tech) for this provider's networks."))
    else:
        cards.append(("Official status page", word(n, lv), n.get("status") or ""))
    cards.append(("Reports on this page", f'{r.get("h1", 0)} in the last hour', f'{r.get("h24", 0)} in 24 h · {rep30} in 30 days. People who tapped Down for me here.'))
    if n.get("affected"):
        cards.append(("People affected", n["affected"]["text"], "Published by " + n["affected"]["src"]))
    else:
        cards.append(("People affected", "Not published", f"{nm} does not publish affected-user numbers. Our report count is shown instead, and it is not a total."))
    cg = "".join(f'<div class="sd-c"><span>{E(a)}</span><b>{E(b)}</b><small>{E(s)}</small></div>' for a, b, s in cards)
    # incident log: everything we stored, newest first
    inc = list(hist.get("incidents") or []); have = {(str(i.get("title"))[:60].lower(), str(i.get("start"))[:13]) for i in inc}
    for x in prov_inc or []:   # the provider's own published incidents, including ones from before our tracking began
        k = (str(x.get("t"))[:60].lower(), str(x.get("s"))[:13])
        if k in have or not x.get("s"): continue
        have.add(k); s0 = _p(x["s"]); e0 = _p(x.get("e"))
        inc.append(dict(title=x.get("t") or "Incident", start=x["s"], end=x.get("e"), level=x.get("lv") or 1, src=n.get("basis") or "provider status page",
                        mins=int(((e0 or datetime.now(timezone.utc)) - s0).total_seconds() // 60) if s0 else None))
    inc.sort(key=lambda i: str(i.get("start")), reverse=True)
    if inc:
        li = []
        for i in inc:
            ic = LVC[1] if i.get("end") else LVC.get(int(i.get("level") or 1), LVC[1])
            when = ("Resolution notice " + _et(i["end"] or i["start"]) + " · start time and duration not published") if "resolution notice; start not published" in i["title"] else _et(i["start"]) + (f' · recovered {_et(i["end"])} · {_dur(i.get("mins"))}' if i.get("end") else f' · still going, {_dur(i.get("mins"))} so far')
            li.append(f'<li><i style="--c:{"#5b6573" if i.get("end") else ic}"></i><div><b>{E(i["title"])}</b><p>{E(when)} · {E(i.get("src") or "")}</p></div></li>')
        log = '<div class="sd-log"><ul>' + "".join(li) + '</ul></div>'
    else:
        log = '<div class="sd-log"><p class="sd-empty">No incidents logged for ' + E(nm) + (' since ' + E(_et(since, True)) if since else "") + '.</p></div>'
    news = n.get("news") or []
    nl = ("<h2>News that names " + E(nm) + " and an outage, last 48 h</h2><ul class=\"sd-news\">" + "".join(
        f'<li><a href="{E(x["url"])}"' + ('' if str(x.get("url", "")).startswith("/") else ' target="_blank" rel="noopener"') + f'>{E(x["t"])}</a><small>{E(x.get("src") or "")} · {E(_et(x.get("at")))}</small></li>' for x in news) + "</ul>") if news else ""
    links = []
    if n.get("status_url"): links.append(f'<a href="{E(n["status_url"])}" target="_blank" rel="noopener">{E(nm)} official status page</a>')
    if n.get("support"): links.append(f'<a href="{E(n["support"])}" target="_blank" rel="noopener">{E(nm)} support</a>')
    if n.get("page"): links.append(f'<a href="{E(n["page"])}">Full provider analysis</a>')
    if n.get("ioda"): links.append(f'<a href="{E(n["ioda"])}" target="_blank" rel="noopener">IODA</a>')
    body = (f'<div class="sd"><p class="sd-crumb"><a href="/">BLACKOUT.NETWORK</a> › <a href="/grid">The Grid</a> › {E(nm)}</p>'
            f'<div class="sd-h"><div><h1>{E(nm)}</h1>' + (f'<p>{E(sub(n["name"]))}</p>' if sub(n["name"]) else "") + '</div>'
            f'<span class="sd-pill" style="--c:{c}"><i></i>{E(word(n, lv))}</span></div>'
            f'<p class="sd-st">{E(n.get("status") or "")}</p><p class="sd-mu">' + (f'Checked {E(_et(generated))} · ' if generated else "") + f'{E(n.get("basis") or "")}</p>'
            f'<div class="sd-act"><button type="button" class="sd-btn" id="sd_down" data-id="{E(n["id"])}">Down for me</button><a class="sd-btn" href="/grid">All services</a></div>'
            f'<div class="sd-g">{cg}</div>'
            f'<h2>Uptime, last 90 days</h2><div class="sd-bar" role="img" aria-label="Daily status for the last 90 days">{bar}</div>'
            '<div class="sd-ax"><span>90 days ago</span><span>Today</span></div>'
            f'<p class="sd-mu">{upline}</p>'
            f'<div class="sd-leg"><span><i style="background:{LVC[0]}"></i>Normal</span><span><i style="background:{LVC[1]}"></i>Minor</span><span><i style="background:{LVC[2]}"></i>Disruption</span><span><i style="background:{LVC[3]}"></i>Major outage</span><span><i style="border:1px dashed #3a424d"></i>No data</span></div>'
            f'<h2>Last 24 hours</h2><div class="sd-hr" role="img" aria-label="Hourly status, last 24 hours">{hrs}</div><div class="sd-ax"><span>24 h ago</span><span>Now</span></div>'
            f'<h2>Reports on this page, last 30 days</h2><div class="sd-rp" role="img" aria-label="Daily Down for me reports, last 30 days">{rp}</div><div class="sd-ax"><span>30 days ago</span><span>{rep30} total</span><span>Today</span></div>'
            f'<h2>Incident history</h2>{log}{nl}'
            f'<p class="sd-src">Sources: ' + E(n.get("basis") or "official status feed") + '. Times are Eastern. ' + (" · ".join(links) if links else "") + '</p></div>')
    return body + "<style>" + CSS + "</style>" + JS
