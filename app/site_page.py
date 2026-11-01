"""Shared page shell for BLACKOUT.NETWORK story pages (t303/t311): /wire/<id> (story.py), /social and /story/<slug> (social.py).
Uses sitenav.py's header, tab bar and SEO conventions when available, so these pages carry the same header and menu as the dashboard.
No scripts except the small click-to-load video embed. Never touches scanner.py, scoring, push.py, jets.py or config.json."""
import html, json, re
try:
    import sitenav
except Exception:   # never let a header problem take the page down
    sitenav = None

SITE = "https://blackout.network"; BRAND = "BLACKOUT.NETWORK"
E = lambda s: html.escape(str(s if s is not None else ""), quote=True)

CSS = """
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg,#0b0d10);color:var(--tx,#e6e9ee);font:15px/1.6 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;overflow-x:hidden}
a{color:var(--ac,#4aa3ff)}a:focus-visible,button:focus-visible{outline:2px solid var(--ac,#4aa3ff);outline-offset:2px;border-radius:4px}
.skip{position:absolute;left:-999px}.skip:focus{left:12px;top:8px;background:var(--pn,#12161b);padding:6px 10px;z-index:9}
.wrap{max-width:860px;margin:0 auto;padding:16px 16px 40px}
.crumb{font-size:13px;color:var(--mu,#8a94a3);margin:0 0 8px}.crumb a{color:var(--mu,#8a94a3)}
h1.t{font-size:26px;line-height:1.25;margin:6px 0 8px;letter-spacing:.1px;overflow-wrap:anywhere}
.dek{font-size:16.5px;color:#c9d1db;margin:0 0 12px}
.meta{font-size:13px;color:var(--mu,#8a94a3);margin:0 0 14px}
.pill{display:inline-block;font-size:11.5px;font-weight:700;letter-spacing:.4px;border-radius:6px;padding:2px 8px;margin:0 6px 4px 0;border:1px solid var(--bd2,#2f3742);background:#14181d;white-space:nowrap}
.card{background:var(--pn,#12161b);border:1px solid var(--bd,#232a33);border-radius:12px;padding:14px 16px;margin:0 0 14px}
.card h2{font-size:17px;margin:0 0 8px}
.article h2{font-size:19px;margin:22px 0 6px}.article p,.article li{font-size:16px;overflow-wrap:anywhere}.article ul{padding-left:22px}
.btns{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}
.btn{display:inline-block;text-decoration:none;font-weight:700;font-size:14px;border-radius:9px;padding:10px 14px;border:1px solid var(--bd2,#2f3742);color:var(--tx,#e6e9ee);background:#161b21}
.btn.p{background:#c8102e;border-color:#c8102e;color:#fff}
.vid{position:relative;aspect-ratio:16/9;width:100%;border-radius:12px;overflow:hidden;background:#000;border:1px solid var(--bd,#232a33)}
.vid img,.vid iframe{position:absolute;inset:0;width:100%;height:100%;border:0;object-fit:cover}
.vid button{position:absolute;inset:0;width:100%;height:100%;border:0;background:transparent;cursor:pointer;padding:0}
.vid .play{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:76px;height:54px;border-radius:14px;background:rgba(200,16,46,.92);display:flex;align-items:center;justify-content:center}
.vid .play:after{content:"";border-style:solid;border-width:12px 0 12px 20px;border-color:transparent transparent transparent #fff;margin-left:5px}
.vid .note{position:absolute;left:8px;bottom:8px;font-size:11.5px;background:rgba(0,0,0,.7);color:#dfe5ec;padding:3px 7px;border-radius:6px}
.tl{list-style:none;margin:0;padding:0}.tl li{border-left:2px solid var(--bd2,#2f3742);padding:4px 0 10px 12px;margin-left:4px;overflow-wrap:anywhere}
.tl li.new{border-left-color:#f5a524}.tl .when{font-size:12px;color:var(--mu,#8a94a3)}.tl .src{font-size:12.5px;color:var(--mu,#8a94a3)}
.tag{font-size:10.5px;font-weight:800;letter-spacing:.5px;color:#111;background:#f5a524;border-radius:4px;padding:1px 5px;margin-right:6px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(260px,100%),1fr));gap:14px}
.sc{background:var(--pn,#12161b);border:1px solid var(--bd,#232a33);border-radius:12px;overflow:hidden;display:flex;flex-direction:column}
.sc .th{display:block;aspect-ratio:16/9;background:#000}.sc .th img{width:100%;height:100%;object-fit:cover;display:block}
.sc .bd{padding:10px 12px 12px}.sc h3{font-size:15px;line-height:1.35;margin:0 0 4px}.sc h3 a{color:var(--tx,#e6e9ee);text-decoration:none}
.sc .d{font-size:12px;color:var(--mu,#8a94a3)}.sc .btns{margin:8px 0 0}.sc .btn{font-size:12.5px;padding:7px 10px}
.empty{text-align:center;padding:28px 16px}.empty b{display:block;font-size:20px;margin-bottom:6px}
.xp{border-top:1px solid var(--bd,#232a33);padding:10px 0}.xp:first-child{border-top:0}.xp p{margin:0 0 4px;white-space:pre-wrap;overflow-wrap:anywhere}
footer.ft{max-width:860px;margin:0 auto;padding:12px 16px 30px;font-size:12.5px;color:var(--mu,#8a94a3)}footer.ft a{color:var(--mu,#8a94a3)}
@media(max-width:520px){h1.t{font-size:22px}.dek{font-size:15.5px}.btn{flex:1 1 auto;text-align:center}}
"""

EMBED_JS = """<script>document.addEventListener("click",function(e){var b=e.target.closest&&e.target.closest("button[data-yt]");if(!b)return;
var f=document.createElement("iframe");f.src="https://www.youtube-nocookie.com/embed/"+b.dataset.yt+"?autoplay=1&rel=0&modestbranding=1&playsinline=1";
f.title=b.getAttribute("aria-label")||"Video";f.allow="accelerometer;autoplay;clipboard-write;encrypted-media;gyroscope;picture-in-picture";f.allowFullscreen=true;
f.referrerPolicy="strict-origin-when-cross-origin";var v=b.closest(".vid");v.innerHTML="";v.appendChild(f)});</script>"""

def _title_tag(title):
    # server.pwa_head keeps titles that contain BLACKOUT.NETWORK
    t = title if BRAND in title else f"{title} | {BRAND}"
    return t

def page(title, desc, body, path, active="", noindex=False, image=None, jsonld=None, og_type="article", script=False):
    t = _title_tag(title); url = SITE + path; img = image or f"{SITE}/icons/icon-512.png"
    head = (f'<title>{E(t)}</title><meta name="description" content="{E(desc)}"><link rel="canonical" href="{E(url)}">'
            f'<meta property="og:type" content="{og_type}"><meta property="og:site_name" content="{BRAND}"><meta property="og:title" content="{E(t)}">'
            f'<meta property="og:description" content="{E(desc)}"><meta property="og:url" content="{E(url)}"><meta property="og:image" content="{E(img)}">'
            f'<meta name="twitter:card" content="{"summary_large_image" if image else "summary"}"><meta name="twitter:site" content="@BlkoutNtw">'
            f'<meta name="twitter:title" content="{E(t)}"><meta name="twitter:description" content="{E(desc)}"><meta name="twitter:image" content="{E(img)}">'
            '<link rel="stylesheet" href="/sitenav.css">')
    if noindex: head += '<meta name="robots" content="noindex,nofollow">'
    if jsonld: head += '<script type="application/ld+json">' + json.dumps(jsonld, ensure_ascii=False).replace("</", "<\\/") + '</script>'
    top = ""
    if sitenav is not None:
        try: top = sitenav.header_html() + sitenav.nav_html(active)
        except Exception: top = ""
    if not top:
        top = '<header class="bn-hd"><h1><a href="/" style="color:inherit;text-decoration:none">BLACKOUT.<b style="color:#c8102e">NETWORK</b></a></h1></header>'
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' + head +
            '<link rel="stylesheet" href="/theme.css"><link rel="icon" href="/favicon.ico" sizes="any">'
            f'<style>{CSS}</style></head><body><a class="skip" href="#main">Skip to content</a>{top}<main class="wrap" id="main">{body}</main>'
            '<footer class="ft">Research only: BLACKOUT.NETWORK is not an official warning service. Always follow official instructions from local authorities. · '
            '<a href="/#wire">The Wire</a> · <a href="/social">Videos &amp; posts</a> · <a href="/newsletter">Newsletter</a> · <a href="/scoring">How we score</a> · '
            '<a href="/sources">Sources</a> · <a href="/privacy">Privacy</a> · <a href="/tos">Terms</a></footer>'
            + (EMBED_JS if script else "") + '</body></html>').encode()

_LINK = re.compile(r"\[([^\]]{1,200})\]\((https?://[^\s)]{1,500}|/[^\s)]{0,300})\)")
def inline(s):
    """Escape text, then turn [text](url) into links (http(s) or site-relative only). Outbound links open in a new tab."""
    out, i = [], 0
    for m in _LINK.finditer(s or ""):
        out.append(E(s[i:m.start()])); u = m.group(2)
        ext = u.startswith("http") and not u.startswith(SITE)
        out.append(f'<a href="{E(u)}"' + (' target="_blank" rel="noopener"' if ext else "") + f'>{E(m.group(1))}</a>'); i = m.end()
    out.append(E((s or "")[i:])); return "".join(out)

def blocks(article):
    h = []
    for b in article or []:
        if "h" in b: h.append(f'<h2>{E(b["h"])}</h2>')
        elif "p" in b: h.append(f'<p>{inline(b["p"])}</p>')
        elif "ul" in b: h.append('<ul>' + "".join(f'<li>{inline(x)}</li>' for x in b["ul"]) + '</ul>')
    return "".join(h)

def plain(article):
    t = []
    for b in article or []:
        for x in ([b["p"]] if "p" in b else b.get("ul") or []): t.append(_LINK.sub(lambda m: m.group(1), x))
    return " ".join(t)

_LEAD = re.compile(r"^[^\w(\"'“‘\[]+")
def clean_title(t):
    t = re.sub(r"\s+", " ", t or "").strip(); c = _LEAD.sub("", t)
    c = re.sub(r"(\s+@[A-Za-z0-9_.]{2,30})+\.?$", "", c).strip()
    return c or t
