"""Public stats page (Nov 1, 2026; t385): GET /stats (HTML) and GET /api/stats (the same aggregates as JSON).
Anyone can view it. It shows ONLY aggregate totals: daily visitors and page views, top pages and stories, traffic channels,
referrer domains and country totals (each bucket under 5 hidden), plus public YouTube @blkoutntw and X @BlkoutNtw numbers.
Data: social_public_stats.json, built on the box by a box-only job from (a) usage_stats.py's privacy-safe daily aggregates
(pulled over the signed reports sync), (b) the YouTube Data API and (c) the X API, then pushed here by the normal data sync.
No API keys or tokens exist on this node for these numbers; this module only reads that JSON. No cookies, no scripts needed.
Never touches scanner.py, scoring, push.py, jets.py, aviation_watch.py or config.json."""
import os, json, html, time, datetime as dt
from zoneinfo import ZoneInfo
import sitenav
BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "social_public_stats.json")
SITE = "https://blackout.network"; BRAND = "BLACKOUT.NETWORK"
ET = ZoneInfo("America/New_York")
E = lambda s: html.escape(str(s if s is not None else ""), quote=True)
TITLE = "Public stats: site traffic, YouTube and X | BLACKOUT.NETWORK"
DESC = ("BLACKOUT.NETWORK's open stats: daily visitors and page views, the most-read pages and stories, where readers come from, "
        "plus YouTube @blkoutntw and X @BlkoutNtw growth. Aggregate totals only.")
_C = {"mt": 0, "d": None}

def load():
    try:
        mt = os.path.getmtime(DATA)
        if _C["d"] is None or mt != _C["mt"]:
            with open(DATA, encoding="utf-8") as f: _C["d"] = json.load(f)
            _C["mt"] = mt
    except Exception: _C["d"] = _C["d"] or {}
    return _C["d"] or {}

def public_json():
    """Only the published aggregates (the file holds nothing else, but keep the allow-list explicit)."""
    d = load(); keep = {}
    for k in ("generated", "min_bucket", "site", "newsletter", "youtube", "x", "growth"): keep[k] = d.get(k)
    if isinstance(keep.get("youtube"), dict): keep["youtube"] = {k: v for k, v in keep["youtube"].items() if k not in ("analytics_note", "daily", "traffic_sources", "views_28d", "minutes_28d", "subs_net_28d", "analytics")}   # audit Nov 1 2026: no YouTube Analytics data on public /stats
    if isinstance(keep.get("youtube"), dict):
        for _v in keep["youtube"].get("trending") or []: _v.pop("views_7d", None)
    return keep

def _t(iso):
    try: return dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone(ET)
    except Exception: return None
def when(iso, fmt="%b %-d, %-I:%M %p ET"):
    t = _t(iso); return t.strftime(fmt) if t else "—"
def ago(iso):
    t = _t(iso)
    if not t: return ""
    s = (dt.datetime.now(ET) - t).total_seconds()
    if s < 3600: return f"{max(1, int(s // 60))} min ago"
    if s < 86400: return f"{int(s // 3600)} h ago"
    return f"{int(s // 86400)} d ago"
def n(v, lt5=False):
    if v is None: return "&lt;5" if lt5 else "—"
    v = int(v)
    if v >= 1_000_000: return f"{v / 1e6:.1f}M".replace(".0M", "M")
    if v >= 10_000: return f"{v / 1e3:.1f}K".replace(".0K", "K")
    return f"{v:,}"
def day_label(d, fmt="%b %-d"):
    try: return dt.date.fromisoformat(d).strftime(fmt)
    except Exception: return d

_CC = {}
def country(cc):
    if not _CC:
        try:
            for c in json.load(open(os.path.join(BASE, "radio_geo.json")))["countries"]: _CC[c["cc"]] = c["name"]
        except Exception: _CC["_"] = ""
    flag = "".join(chr(0x1F1E6 + ord(ch) - 65) for ch in cc) if len(cc) == 2 and cc.isalpha() else ""
    return flag, _CC.get(cc, cc)

I_YT = sitenav.UI.I_YT; I_X = sitenav.UI.I_X
TILE = ('<svg class="st-tile" viewBox="0 0 96 96" aria-hidden="true"><rect x="1" y="1" width="94" height="94" rx="18" fill="#0B0D10" stroke="#2f3742" stroke-width="2"/>'
        '<text x="48" y="58" text-anchor="middle" font-family="Montserrat,system-ui,sans-serif" font-weight="800" font-size="38" fill="#fff" letter-spacing="-1">BN</text>'
        '<rect x="20" y="70" width="17" height="6" rx="2" fill="#2BB673"/><rect x="40" y="70" width="17" height="6" rx="2" fill="#F5A524"/>'
        '<rect x="60" y="70" width="17" height="6" rx="2" fill="#FF4D4F"/></svg>')

CSS = """
.st{--st-red:var(--bn-brand,#FF4D4F);--st-card:var(--bn-surface,#14181D);--st-line:var(--bn-line,#252B33);--st-mu:var(--bn-muted,#8B95A3);
 max-width:none;margin:0 var(--bn-pad-x,16px);padding:8px 0 48px;font-family:var(--bn-font-body,Inter,system-ui,sans-serif);color:var(--bn-text,#E6E9EE)}
.st *{box-sizing:border-box}.st h2,.st h3,.st .st-k b,.st .st-hero h1{font-family:var(--bn-font-ui,Montserrat,system-ui,sans-serif)}
.st a{color:inherit}
.st-hero{position:relative;overflow:hidden;border:1px solid var(--st-line);border-radius:18px;padding:22px 22px 20px;margin:6px 0 18px;
 background:radial-gradient(120% 140% at 100% 0%,rgba(255,77,79,.22),transparent 55%),linear-gradient(180deg,var(--bn-surface-0,#0f1317),var(--st-card))}
.st-hero .row{display:flex;gap:16px;align-items:center;flex-wrap:wrap}.st-tile{width:64px;height:64px;flex:none}
.st-hero h1{font-size:clamp(24px,4.4vw,38px);line-height:1.08;margin:0;letter-spacing:-.02em;font-weight:800}
.st-hero h1 em{font-style:normal;color:var(--st-red)}
.st-hero p{margin:8px 0 0;color:var(--bn-text-2,#c9d0d9);font-size:15px;max-width:720px}
.st-live{display:inline-flex;align-items:center;gap:7px;font:700 11.5px/1 var(--bn-font-ui,Montserrat,sans-serif);letter-spacing:.14em;text-transform:uppercase;
 color:var(--st-red);margin-bottom:6px}.st-live i{width:8px;height:8px;border-radius:50%;background:var(--st-red);box-shadow:0 0 0 4px rgba(255,77,79,.18)}
.st-chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}
.st-chip{font-size:12.5px;color:var(--st-mu);border:1px solid var(--st-line);border-radius:999px;padding:5px 10px;background:rgba(0,0,0,.18)}
.st-chip b{color:var(--bn-text,#E6E9EE);font-weight:600}
.st-kpis{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:0 0 18px}
.st-k{background:var(--st-card);border:1px solid var(--st-line);border-radius:14px;padding:14px 14px 12px;position:relative;overflow:hidden;min-width:0;text-decoration:none;display:block}
.st-k:before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--c,var(--st-red))}
.st-k small{display:flex;align-items:center;gap:6px;font-size:11.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--st-mu);font-weight:600}
.st-k small svg{flex:none}
.st-k b{display:block;font-size:clamp(26px,6vw,36px);font-weight:800;line-height:1.1;margin-top:6px;letter-spacing:-.02em}
.st-k span{display:block;font-size:12.5px;color:var(--st-mu);margin-top:2px;overflow-wrap:anywhere}
a.st-k:hover{border-color:var(--bn-line-2,#2f3742)}
.st-sec{margin:26px 0 10px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.st-sec h2{font-size:20px;margin:0;font-weight:800;letter-spacing:-.01em}
.st-sec .st-mu{flex:1 1 220px}
.st-mu{color:var(--st-mu);font-size:13px}
.st-card{background:var(--st-card);border:1px solid var(--st-line);border-radius:14px;padding:16px;min-width:0}
.st-card h3{font-size:15px;margin:0 0 12px;font-weight:700}
.st-grid{display:grid;grid-template-columns:minmax(0,1fr);gap:12px}
.st-chart{display:flex;justify-content:center;align-items:flex-end;gap:3px;height:190px;padding:6px 0 0;border-bottom:1px solid var(--st-line)}
.st-col{flex:1 1 0;min-width:0;max-width:72px;height:100%;display:flex;align-items:flex-end;position:relative}
.st-col .pv{width:100%;background:rgba(255,77,79,.28);border-radius:4px 4px 0 0;position:relative;min-height:2px}
.st-col .uv{position:absolute;left:18%;right:18%;bottom:0;background:var(--st-red);border-radius:3px 3px 0 0;min-height:2px}
.st-col.today .pv{background:repeating-linear-gradient(45deg,rgba(255,77,79,.30) 0 6px,rgba(255,77,79,.16) 6px 12px)}
.st-col .v{position:absolute;bottom:calc(var(--h) + 4px);left:50%;transform:translateX(-50%);font-size:11px;color:var(--bn-text-2,#c9d0d9);white-space:nowrap;font-weight:600}
.st-axis{display:flex;justify-content:center;gap:3px;margin-top:6px}.st-axis span{flex:1 1 0;min-width:0;max-width:72px;font-size:10.5px;color:var(--st-mu);text-align:center;overflow:hidden;white-space:nowrap}
.st-legend{display:flex;gap:14px;flex-wrap:wrap;font-size:12.5px;color:var(--st-mu);margin-top:10px}
.st-legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:-1px}
.st-bars{list-style:none;margin:0;padding:0}
.st-bars li{position:relative;margin:0 0 8px;border-radius:9px;overflow:hidden;background:var(--bn-surface-0,#0f1317);border:1px solid var(--st-line)}
.st-bars .fill{position:absolute;inset:0 auto 0 0;background:linear-gradient(90deg,rgba(255,77,79,.30),rgba(255,77,79,.10))}
.st-bars .in{position:relative;display:flex;gap:10px;align-items:center;justify-content:space-between;padding:9px 12px;font-size:14px;text-decoration:none;color:inherit}
.st-bars .in span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.st-bars .in b{font-variant-numeric:tabular-nums;flex:none}
.st-empty{border:1px dashed var(--bn-line-2,#2f3742);border-radius:12px;padding:14px;color:var(--st-mu);font-size:13.5px}
.st-stack{display:flex;height:16px;border-radius:999px;overflow:hidden;background:var(--bn-surface-0,#0f1317);border:1px solid var(--st-line);margin:2px 0 12px}
.st-stack i{display:block;height:100%}
.st-plat{display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding:14px 16px;border-radius:14px;border:1px solid var(--st-line);background:var(--st-card);margin:0 0 12px}
.st-plat .nm{display:flex;align-items:center;gap:10px;flex:1 1 220px;min-width:0}.st-plat .nm b{font:800 17px/1.2 var(--bn-font-ui,Montserrat,sans-serif)}
.st-plat .nm span{display:block;font-size:12.5px;color:var(--st-mu)}
.st-btn{display:inline-flex;align-items:center;gap:8px;text-decoration:none;font:700 14px/1 var(--bn-font-ui,Montserrat,sans-serif);border-radius:10px;padding:11px 14px;
 border:1px solid var(--bn-line-2,#2f3742);color:var(--bn-text,#E6E9EE);background:var(--bn-raised,#1B2027);white-space:nowrap}
.st-btn.red{background:var(--st-red);border-color:var(--st-red);color:#fff}.st-btn:hover{filter:brightness(1.08)}
.st-vids{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.st-v{background:var(--st-card);border:1px solid var(--st-line);border-radius:12px;overflow:hidden;text-decoration:none;color:inherit;display:flex;flex-direction:column;min-width:0}
.st-v .th{position:relative;aspect-ratio:16/9;background:#000;overflow:hidden}.st-v .th img{width:100%;height:100%;object-fit:cover;display:block}
.st-v .rk{position:absolute;left:8px;top:8px;background:rgba(11,13,16,.86);color:#fff;font:800 12px/1 var(--bn-font-ui,Montserrat,sans-serif);border-radius:6px;padding:5px 7px}
.st-v .vw{position:absolute;right:8px;bottom:8px;background:var(--st-red);color:#fff;font:700 12px/1 var(--bn-font-ui,Montserrat,sans-serif);border-radius:6px;padding:5px 7px}
.st-v .bd{padding:9px 10px 11px}.st-v h4{margin:0 0 4px;font-size:13.5px;line-height:1.35;font-weight:600;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.st-v .d{font-size:11.5px;color:var(--st-mu)}
.st-posts{display:grid;grid-template-columns:minmax(0,1fr);gap:10px}
.st-p{background:var(--st-card);border:1px solid var(--st-line);border-radius:12px;padding:12px 14px;text-decoration:none;color:inherit;display:block;min-width:0}
.st-p .hd{display:flex;align-items:center;gap:8px;font-size:12.5px;color:var(--st-mu);margin-bottom:6px}.st-p .hd b{color:var(--bn-text,#E6E9EE)}
.st-p .hd .av{width:26px;height:26px;flex:none}
.st-p p{margin:0 0 10px;font-size:14px;line-height:1.45;overflow-wrap:anywhere;display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden}
.st-p .m{display:flex;gap:14px;flex-wrap:wrap;font-size:12.5px;color:var(--st-mu)}.st-p .m b{color:var(--bn-text,#E6E9EE)}
.st-spark{display:flex;align-items:flex-end;gap:3px;height:70px}.st-spark i{flex:1 1 0;background:var(--c,var(--st-red));border-radius:3px 3px 0 0;min-height:2px;opacity:.85}
.st-pmw{display:flex;justify-content:center;gap:3px;height:120px;position:relative;border-top:1px dashed transparent}
.st-pmw:after{content:"";position:absolute;left:0;right:0;top:50%;border-top:1px solid var(--st-line)}
.st-pm{flex:1 1 0;min-width:0;max-width:72px;position:relative}.st-pm i{position:absolute;left:15%;right:15%;display:block}
.st-pm .g{bottom:50%;background:#2BB673;border-radius:3px 3px 0 0;min-height:1px}.st-pm .l{top:50%;background:#FF4D4F;border-radius:0 0 3px 3px;min-height:1px}
.st-cta{display:grid;grid-template-columns:minmax(0,1fr);gap:12px;align-items:center;border-radius:16px;padding:18px;margin:26px 0 0;border:1px solid var(--st-line);
 background:radial-gradient(100% 160% at 0% 0%,rgba(255,77,79,.20),transparent 60%),var(--st-card)}
.st-cta h2{margin:0 0 4px;font-size:20px}.st-cta p{margin:0;color:var(--bn-text-2,#c9d0d9);font-size:14px}
.st-cta .b{display:flex;gap:8px;flex-wrap:wrap}
.st-how{margin-top:14px}.st-how ul{margin:0;padding-left:18px}.st-how li{font-size:13.5px;color:var(--bn-text-2,#c9d0d9);margin:4px 0}
.st-foot{margin:0 var(--bn-pad-x,16px);padding:6px 0 36px;font-size:12.5px;color:var(--st-mu)}.st-foot a{color:var(--st-mu)}
@media(min-width:620px){.st-kpis{grid-template-columns:repeat(4,minmax(0,1fr))}.st-vids{grid-template-columns:repeat(3,minmax(0,1fr))}
 .st-posts{grid-template-columns:repeat(2,minmax(0,1fr))}.st-cta{grid-template-columns:minmax(0,1fr) auto}}
@media(min-width:900px){.st-grid.two{grid-template-columns:repeat(2,minmax(0,1fr))}.st-vids{grid-template-columns:repeat(4,minmax(0,1fr))}
 .st-posts{grid-template-columns:repeat(3,minmax(0,1fr))}.st-hero{padding:28px 30px 24px}.st-tile{width:76px;height:76px}}
@media(min-width:1500px){.st-vids{grid-template-columns:repeat(6,minmax(0,1fr))}.st-posts{grid-template-columns:repeat(4,minmax(0,1fr))}
 .st-kpis{grid-template-columns:repeat(4,minmax(0,1fr))}.st-grid.two{grid-template-columns:repeat(4,minmax(0,1fr))}}
@media(max-width:420px){.st-chart{height:150px}.st-col .v{display:none}.st-btn{flex:1 1 auto;justify-content:center}}
"""

def kpi(label, value, sub="", color=None, href=None, icon=""):
    st = f' style="--c:{color}"' if color else ""
    inner = f'<small>{icon}{E(label)}</small><b>{value}</b>' + (f'<span>{sub}</span>' if sub else "")
    if href:
        ext = href.startswith("http")
        return f'<a class="st-k" href="{E(href)}"{st}' + (' target="_blank" rel="noopener"' if ext else "") + f'>{inner}</a>'
    return f'<div class="st-k"{st}>{inner}</div>'

def bars(items, label_key, val_key, href_key=None, unit="views", prefix=None):
    if not items: return ""
    mx = max(i[val_key] for i in items) or 1; out = ['<ul class="st-bars">']
    for i in items:
        w = max(3, round(100 * i[val_key] / mx)); lab = (prefix(i) if prefix else "") + E(i[label_key])
        tag = "a" if href_key and i.get(href_key) else "div"
        href = f' href="{E(i[href_key])}"' if tag == "a" else ""
        out.append(f'<li><span class="fill" style="width:{w}%"></span><{tag} class="in"{href}><span>{lab}</span><b>{n(i[val_key])} <small class="st-mu">{unit}</small></b></{tag}></li>')
    return "".join(out) + "</ul>"

def chart(series):
    if not series: return '<div class="st-empty">Counting started recently; the first full day appears here tomorrow.</div>'
    mx = max(max(s["pv"] for s in series), 1); cols, axis = [], []
    step = max(1, len(series) // 6)
    for i, s in enumerate(series):
        h = round(100 * s["pv"] / mx, 1); uv = s.get("uv") or 0; hu = round(100 * uv / mx, 1)
        tip = f'{day_label(s["day"], "%a %b %-d")}: {s["pv"]:,} page views, ' + (f'{uv:,} visitors' if s.get("uv") else "fewer than 5 visitors") + (" (today so far)" if s.get("today") else "")
        lab = f'<span class="v">{n(s["pv"])}</span>' if len(series) <= 14 else ""
        cols.append(f'<div class="st-col{" today" if s.get("today") else ""}" style="--h:{h}%" title="{E(tip)}" aria-label="{E(tip)}" role="img">'
                    f'<div class="pv" style="height:{h}%"></div><div class="uv" style="height:{hu}%"></div>{lab}</div>')
        axis.append(f'<span>{E("Today" if s.get("today") else day_label(s["day"])) if (i % step == 0 or i == len(series) - 1) else ""}</span>')
    return (f'<div class="st-chart">{"".join(cols)}</div><div class="st-axis" aria-hidden="true">{"".join(axis)}</div>'
            '<div class="st-legend"><span><i style="background:rgba(255,77,79,.4)"></i>Page views</span><span><i style="background:var(--st-red)"></i>Unique visitors (est.)</span>'
            '<span><i style="background:repeating-linear-gradient(45deg,rgba(255,77,79,.4) 0 3px,transparent 3px 6px)"></i>Today, so far</span></div>')

def spark(vals, color):
    vals = [v for v in vals if v is not None]
    if len(vals) < 2: return ""
    mx = max(vals) or 1
    return f'<div class="st-spark" style="--c:{color}">' + "".join(f'<i style="height:{max(3, round(100 * v / mx))}%" title="{v:,}"></i>' for v in vals) + "</div>"

def dual(rows, a, b, la, lb, ca="#FF0033", cb="#F5A524", fmt_b=lambda v: f"{v:,}"):
    """Two-series daily bar chart (a = main bar, b = inner bar), CSS only."""
    if not rows: return ""
    mxa = max([r[a] for r in rows] + [1]); mxb = max([r[b] for r in rows] + [1]); cols, axis = [], []
    step = max(1, len(rows) // 6)
    for i, r in enumerate(rows):
        ha = round(100 * r[a] / mxa, 1); hb = round(100 * r[b] / mxb, 1)
        tip = f'{day_label(r["day"], "%a %b %-d")}: {r[a]:,} {la.lower()}, {fmt_b(r[b])} {lb.lower()}'
        cols.append(f'<div class="st-col" title="{E(tip)}" aria-label="{E(tip)}" role="img"><div class="pv" style="height:{ha}%;background:{ca}55"></div>'
                    f'<div class="uv" style="height:{hb}%;background:{cb}"></div></div>')
        axis.append(f'<span>{E(day_label(r["day"], "%-m/%-d")) if (i % step == 0 or i == len(rows) - 1) else ""}</span>')
    return (f'<div class="st-chart" style="height:150px">{"".join(cols)}</div><div class="st-axis" aria-hidden="true">{"".join(axis)}</div>'
            f'<div class="st-legend"><span><i style="background:{ca}88"></i>{E(la)}</span><span><i style="background:{cb}"></i>{E(lb)}</span></div>')

def subs_chart(rows):
    if not rows: return ""
    mx = max([max(r["subs_gained"], r["subs_lost"]) for r in rows] + [1]); cols, axis = [], []
    step = max(1, len(rows) // 6)
    for i, r in enumerate(rows):
        g = round(50 * r["subs_gained"] / mx, 1); l = round(50 * r["subs_lost"] / mx, 1)
        tip = f'{day_label(r["day"], "%a %b %-d")}: +{r["subs_gained"]:,} gained, -{r["subs_lost"]:,} lost'
        cols.append(f'<div class="st-pm" title="{E(tip)}" aria-label="{E(tip)}" role="img"><i class="g" style="height:{g}%"></i><i class="l" style="height:{l}%"></i></div>')
        axis.append(f'<span>{E(day_label(r["day"], "%-m/%-d")) if (i % step == 0 or i == len(rows) - 1) else ""}</span>')
    return (f'<div class="st-pmw">{"".join(cols)}</div><div class="st-axis" aria-hidden="true">{"".join(axis)}</div>'
            '<div class="st-legend"><span><i style="background:#2BB673"></i>Subscribers gained</span><span><i style="background:#FF4D4F"></i>Subscribers lost</span></div>')

CH_COLORS = {"Search": "#4aa3ff", "Social": "#FF4D4F", "Direct / bookmarks / apps": "#8B95A3", "Email": "#F5A524", "AI assistants": "#b37feb", "Other sites": "#2BB673"}

def render():
    d = load(); s = d.get("site") or {}; y = d.get("youtube") or {}; x = d.get("x") or {}; nl = d.get("newsletter") or {}; g = (d.get("growth") or {}).get("series") or []
    since = s.get("since"); since_txt = when(since, "%b %-d, %Y") if since else "—"
    today, week = s.get("today") or {}, s.get("week") or {}
    hero = (f'<section class="st-hero"><div class="row">{TILE}<div style="min-width:0;flex:1 1 260px"><div class="st-live"><i></i>Live stats</div>'
            '<h1>BLACKOUT.NETWORK <em>by the numbers</em></h1>'
            '<p>Open, aggregate numbers for our site, our YouTube channel and our X account. Totals only: no cookies, no IP addresses, nothing that identifies a reader.</p></div></div>'
            f'<div class="st-chips"><span class="st-chip">Updated <b>{E(when(d.get("generated")))}</b></span>'
            f'<span class="st-chip">Site counting since <b>{E(since_txt)}</b></span><span class="st-chip">Refreshes every <b>10 min</b> (social hourly)</span></div></section>')
    k = ['<div class="st-kpis">',
         kpi("Visitors today", n(today.get("uv"), True), f'{n(today.get("pv"))} page views so far'),
         kpi("Visitors, 7 days", n(week.get("uv"), True), f'{n(week.get("pv"))} page views'),
         kpi("YouTube subscribers", n(y.get("subscribers")), f'{n(y.get("video_views_total"))} video views · {n(y.get("public_videos"))} videos', "#FF0033", y.get("url") or sitenav.YT_URL, I_YT),
         kpi("X followers", n(x.get("followers")), f'{n(x.get("posts"))} posts · {n(x.get("impressions_7d"))} impressions (7 d)', "#E6E9EE", sitenav.X_URL, I_X),
         "</div>"]
    series = s.get("series") or []
    traffic = (f'<div class="st-sec"><h2>Site traffic</h2><span class="st-mu">Daily page views and estimated unique visitors (UTC days), last 30 days. '
               f'Data since {E(since_txt)}; earlier days were not counted.</span></div><div class="st-card">{chart(series)}</div>')
    tp = s.get("top_pages") or []; ts = s.get("top_stories") or []
    pages = (f'<div class="st-card"><h3>Most-visited pages · 7 days</h3>{bars(tp, "label", "views", "path") or "<div class=st-empty>Not enough visits yet.</div>"}</div>')
    stories = ('<div class="st-card"><h3>Most-read stories · 7 days</h3>' +
               (bars(ts, "title", "views", "path") if ts else '<div class="st-empty">Story pages (<a href="/#wire">/wire</a> and <a href="/social">/story</a>) are counted from today; '
                'each story appears here once it passes 5 readers.</div>') + "</div>")
    tabs = s.get("top_tabs") or []
    tabs_html = f'<div class="st-card"><h3>Most-used dashboard sections · 7 days</h3>{bars(tabs, "label", "requests", unit="loads") or "<div class=st-empty>Not enough data yet.</div>"}</div>'
    chs = s.get("channels") or []; refs = s.get("referrers") or []
    if chs:
        tot = sum(c["views"] for c in chs) or 1
        stack = '<div class="st-stack" role="img" aria-label="Traffic by channel">' + "".join(f'<i style="width:{100 * c["views"] / tot:.2f}%;background:{CH_COLORS.get(c["label"], "#8B95A3")}" title="{E(c["label"])}: {c["views"]:,}"></i>' for c in chs) + "</div>"
        leg = '<div class="st-legend" style="margin:0 0 12px">' + "".join(f'<span><i style="background:{CH_COLORS.get(c["label"], "#8B95A3")}"></i>{E(c["label"])} {round(100 * c["views"] / tot)}%</span>' for c in chs) + "</div>"
        src = f'<div class="st-card"><h3>Where readers come from · 7 days</h3>{stack}{leg}{bars(refs, "domain", "views")}</div>'
    else:
        src = '<div class="st-card"><h3>Where readers come from · 7 days</h3><div class="st-empty">Referrer counts (site names only, like google.com or x.com) started today; channels show once each passes 5 visits.</div></div>'
    cc = s.get("countries") or []
    geo = ('<div class="st-card"><h3>Readers by country · 7 days</h3>' +
           (bars([{**c, "name": country(c["cc"])[1]} for c in cc], "name", "views", prefix=lambda i: country(i["cc"])[0] + " ") if cc else
            '<div class="st-empty">Country totals appear when our network provider supplies a country code; we never look up or store IP addresses.</div>') + "</div>")
    site_html = traffic + f'<div class="st-grid two" style="margin-top:12px">{pages}{stories}{src}{geo}</div><div class="st-grid" style="margin-top:12px">{tabs_html}</div>'

    # YouTube
    vids = y.get("trending") or []
    vcards = "".join(
        f'<a class="st-v" href="{E(v["url"])}" target="_blank" rel="noopener"><div class="th"><img src="{E(v["thumb"])}" alt="{E(v["title"])}" loading="lazy" width="480" height="270">'
        f'<span class="rk">#{i + 1}</span><span class="vw">{n(v.get("views_7d") if v.get("views_7d") is not None else v["views"])} {"views this week" if v.get("views_7d") is not None else "views"}</span></div>'
        f'<div class="bd"><h4>{E(v["title"])}</h4><div class="d">{"Short · " if v.get("short") else ""}{E(when(v.get("published"), "%b %-d"))} · {n(v.get("likes"))} likes</div></div></a>'
        for i, v in enumerate(vids))
    ytg = [r.get("yt_views_day") for r in g]
    daily = y.get("daily") or []; ysrc = y.get("traffic_sources") or []; an = ""
    if daily or y.get("analytics"):
        last = daily[-1]["day"] if daily else None
        akpi = ('<div class="st-kpis" style="margin:12px 0">' +
                kpi("Views, 28 days", n(y.get("views_28d")), "YouTube Analytics", "#FF0033", icon=I_YT) +
                kpi("Watch time, 28 days", n(round((y.get("minutes_28d") or 0) / 60, 1)) + " h", f'{n(y.get("minutes_28d"))} minutes', "#F5A524") +
                kpi("Net subscribers, 28 days", (("+" if (y.get("subs_net_28d") or 0) > 0 else "") + n(y.get("subs_net_28d"))) if y.get("subs_net_28d") is not None else "—",
                    f'{n(sum(d["subs_gained"] for d in daily))} gained · {n(sum(d["subs_lost"] for d in daily))} lost', "#2BB673") +
                kpi("Latest analytics day", E(day_label(last, "%b %-d")) if last else "—", "YouTube reports with a 1–3 day delay", "#8B95A3") + "</div>")
        an += akpi + '<div class="st-grid two">'
        an += f'<div class="st-card"><h3>Daily views and watch time · 28 days</h3>{dual(daily, "views", "minutes", "Views", "Minutes watched") or "<div class=st-empty>No analytics rows yet.</div>"}</div>'
        an += f'<div class="st-card"><h3>Subscribers gained and lost per day · 28 days</h3>{subs_chart(daily) or "<div class=st-empty>No analytics rows yet.</div>"}</div>'
        if ysrc:
            tot = sum(x_["views"] for x_ in ysrc) or 1; pal = ["#FF0033", "#F5A524", "#4aa3ff", "#2BB673", "#b37feb", "#36cfc9", "#8B95A3", "#fa8c16"]
            stack = '<div class="st-stack" role="img" aria-label="YouTube traffic sources">' + "".join(f'<i style="width:{100 * x_["views"] / tot:.2f}%;background:{pal[i % 8]}" title="{E(x_["label"])}: {x_["views"]:,}"></i>' for i, x_ in enumerate(ysrc)) + "</div>"
            leg = '<div class="st-legend" style="margin:0 0 12px">' + "".join(f'<span><i style="background:{pal[i % 8]}"></i>{E(x_["label"])} {round(100 * x_["views"] / tot)}%</span>' for i, x_ in enumerate(ysrc)) + "</div>"
            an += f'<div class="st-card"><h3>How viewers find our videos · 28 days</h3>{stack}{leg}{bars(ysrc, "label", "views")}</div>'
        else:
            an += '<div class="st-card"><h3>How viewers find our videos · 28 days</h3><div class="st-empty">YouTube search, Shorts feed, suggested videos and more show here as soon as YouTube reports them (1–3 days).</div></div>'
        an += "</div>"
    yt_html = ('<div class="st-sec"><h2>YouTube</h2><span class="st-mu">Trending videos on @blkoutntw: the most-watched of the last 7 days.</span></div>'
               f'<div class="st-plat">{I_YT}<div class="nm"><div><b>@blkoutntw</b><span>{n(y.get("subscribers"))} subscribers · {n(y.get("video_views_total"))} views · '
               f'{n(y.get("uploads_7d"))} new videos this week · updated {E(ago(y.get("fetched")))}</span></div></div>'
               f'<a class="st-btn red" href="https://www.youtube.com/@blkoutntw?sub_confirmation=1" target="_blank" rel="noopener">{I_YT} Subscribe</a></div>'
               + (f'<div class="st-vids">{vcards}</div>' if vcards else '<div class="st-empty">Videos load here after the next hourly refresh.</div>') + an
               + (f'<div class="st-card" style="margin-top:12px"><h3>YouTube views per day</h3>{spark(ytg, "#FF0033")}</div>' if len([v for v in ytg if v is not None]) >= 2 else ""))
    # X
    posts = x.get("top") or []
    pcards = "".join(
        f'<a class="st-p" href="{E(p["url"])}" target="_blank" rel="noopener"><div class="hd">{TILE.replace("st-tile", "av")}<span><b>{BRAND}</b> @BlkoutNtw · {E(when(p.get("created"), "%b %-d"))}</span></div>'
        f'<p>{E(html.unescape(p.get("text") or ""))}</p><div class="m"><span><b>{n(p.get("impressions"))}</b> impressions</span><span><b>{n(p.get("likes"))}</b> likes</span>'
        f'<span><b>{n(p.get("reposts"))}</b> reposts</span><span><b>{n(p.get("replies"))}</b> replies</span></div></a>' for p in posts)
    x_html = ('<div class="st-sec"><h2>X</h2><span class="st-mu">Top posts from @BlkoutNtw this week, by impressions.</span></div>'
              f'<div class="st-plat">{I_X}<div class="nm"><div><b>@BlkoutNtw</b><span>{n(x.get("followers"))} followers · {n(x.get("posts"))} posts · '
              f'{n(x.get("impressions_7d"))} impressions and {n(x.get("engagements_7d"))} engagements this week · updated {E(ago(x.get("fetched")))}</span></div></div>'
              f'<a class="st-btn" href="https://x.com/intent/follow?screen_name=BlkoutNtw" target="_blank" rel="noopener">{I_X} Follow @BlkoutNtw</a></div>'
              + (f'<div class="st-posts">{pcards}</div>' if pcards else '<div class="st-empty">Posts load here after the next hourly refresh.</div>'))
    nlv = n(nl.get("subscribers"), nl.get("lt5"))
    cta = ('<section class="st-cta"><div><h2>Get the brief before it trends</h2>'
           f'<p>The free BLACKOUT.NETWORK Morning and Evening Brief: the highest-ranked, source-checked threats, twice a day. Newsletter readers: <b>{nlv}</b>. Be one of the first.</p></div>'
           '<div class="b"><a class="st-btn red" href="/newsletter?utm_source=stats&amp;utm_medium=cta">✉ Get the free brief</a>'
           f'<a class="st-btn" href="https://www.youtube.com/@blkoutntw?sub_confirmation=1" target="_blank" rel="noopener">{I_YT} YouTube</a>'
           f'<a class="st-btn" href="https://x.com/BlkoutNtw" target="_blank" rel="noopener">{I_X} X</a></div></section>')
    bys = nl.get("by_source") or []
    nlsrc = ('<div class="st-card" style="margin-top:12px"><h3>Newsletter signups by source</h3>' +
             (bars(bys, "source", "signups", unit="signups") if bys else '<div class="st-empty">Each signup source appears here once it passes 5 confirmed readers.</div>') + "</div>")
    how = ('<div class="st-card st-how"><h3>How we count (and what we never collect)</h3><ul>'
           '<li>Counted on our own server: page views per page and per day, and an estimate of unique visitors made with a keyed hash that changes every day and lives only in memory. We never store IP addresses or browser details.</li>'
           '<li>No cookies, no third-party analytics, no ad trackers. Browsers that send Do Not Track or Global Privacy Control are not counted.</li>'
           '<li>Referrers are reduced to the site name (for example google.com). Countries are totals only. Any number under 5 is hidden or shown as &lt;5.</li>'
           '<li>Visitor estimates restart if our server restarts, so a returning reader can be counted twice in a day; treat them as approximate. Known bots and crawlers are excluded.</li>'
           '<li>YouTube and X numbers are the public counts from each platform, refreshed hourly. Full details: <a href="/privacy#usage">Privacy Policy</a>. Raw numbers: <a href="/api/stats">/api/stats</a>.</li></ul></div>')
    body = f'<main class="st" id="main">{hero}{"".join(k)}{site_html}{yt_html}{x_html}{cta}{nlsrc}{how}</main>'
    foot = ('<footer class="st-foot">Research only: BLACKOUT.NETWORK is not an official warning service. · <a href="/">The Wire</a> · <a href="/social">Videos &amp; posts</a> · '
            '<a href="/newsletter">Newsletter</a> · <a href="/sources">Sources</a> · <a href="/privacy">Privacy</a> · <a href="/tos">Terms</a> · blackout.network (no .com)</footer>')
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "WebPage", "@id": f"{SITE}/stats#page", "url": f"{SITE}/stats", "name": TITLE, "description": DESC, "inLanguage": "en-US",
         "isPartOf": {"@type": "WebSite", "@id": f"{SITE}/#website", "url": SITE, "name": BRAND}, "dateModified": d.get("generated"),
         "about": {"@id": f"{SITE}/#org"}, "breadcrumb": {"@id": f"{SITE}/stats#crumbs"}},
        {"@type": "Organization", "@id": f"{SITE}/#org", "name": BRAND, "url": SITE, "logo": f"{SITE}/icons/icon-512.png", "email": "hello@blackout.network",
         "sameAs": ["https://x.com/BlkoutNtw", "https://www.youtube.com/@blkoutntw"]},
        {"@type": "BreadcrumbList", "@id": f"{SITE}/stats#crumbs", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": BRAND, "item": SITE + "/"}, {"@type": "ListItem", "position": 2, "name": "Public stats", "item": f"{SITE}/stats"}]},
        {"@type": "Dataset", "name": "BLACKOUT.NETWORK public traffic and audience stats", "description": DESC, "url": f"{SITE}/stats", "creator": {"@id": f"{SITE}/#org"},
         "isAccessibleForFree": True, "license": f"{SITE}/tos", "temporalCoverage": f"{(s.get('first_day') or '')}/..",
         "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": f"{SITE}/api/stats"}]}]}
    head = (sitenav.head_html("stats", "/stats") + '<meta name="robots" content="index,follow,max-image-preview:large">'
            '<meta name="keywords" content="BLACKOUT.NETWORK stats, site traffic, YouTube @blkoutntw, X @BlkoutNtw, open analytics, threat monitor audience">'
            '<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False).replace("</", "<\\/") + '</script>')
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' + head +
            '<link rel="stylesheet" href="/theme.css"><link rel="icon" href="/favicon.ico" sizes="any">'
            f'<style>body{{margin:0;background:var(--bn-bg,#0B0D10);overflow-x:hidden}}{CSS}</style></head><body><a class="skip bn-skip" href="#main" style="position:absolute;left:-999px">Skip to content</a>'
            + sitenav.header_html("@stats") + body + foot + '</body></html>').encode("utf-8")

def handle_get(path, qs):
    if path == "/stats" or path == "/stats/":
        return 200, render(), "text/html; charset=utf-8"
    if path == "/api/stats":
        return 200, public_json()
    return 404, {"error": "not found"}
