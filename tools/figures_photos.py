#!/usr/bin/env python3
"""Key Figures photos (t370). Builds self-hosted, face-centred 400x400 WebP headshots for every person in app/figures.py
(BASE_LIST + POOL) and writes app/figures_photos.json (source page, author, license, license URL per photo).

Source: the person's Wikidata P18 image (looked up from their Wikipedia profile link), or a file pinned in PICK below when P18 is a
poor headshot. Only freely licensed files are used: public domain, CC0, CC BY, CC BY-SA, GODL-India, OGL, plain "Attribution".
NC / ND / non-free / fair-use files are refused (the card keeps its initials tile).
Run on the box after adding someone to figures.py:   python3 tools/figures_photos.py [key ...]   (needs Pillow; OpenCV optional)
Then eyeball app/static/img/figures/*.webp before committing. People with no approved file fall back to initials on the site, and
figures.py also looks up P18 live (license-checked, 400px Commons thumb, cached) for anyone not in the manifest."""
import json, os, re, sys, time, html, urllib.parse
from io import BytesIO
import requests
from PIL import Image
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); APP = os.path.join(ROOT, "app")
OUT = os.path.join(APP, "static", "img", "figures"); MAN = os.path.join(APP, "figures_photos.json")
UA = "BlackoutNetworkBot/1.0 (https://blackout.network; hello@blackout.network)"
# key -> Commons file name, when the first P18 image is not the best clean, recent, front-facing headshot
PICK = {"putin": "Vladimir Putin 2 September 2026.jpg", "hobbs": "Katie Hobbs in 2025.jpg", "tusk": "Premier Donald Tusk KPRM.jpg"}
OK = re.compile(r"public domain|^pd\b|cc0|cc[ -]by|^attribution|godl|\bogl\b|open government licen", re.I)
BAD = re.compile(r"\bnc\b|\bnd\b|non-?commercial|no ?deriv|non-?free|fair use|all rights reserved", re.I)
S = requests.Session(); S.headers.update({"User-Agent": UA})

def get(u, params=None, raw=False):
    for i in range(6):
        try:
            r = S.get(u, params=params, timeout=40)
            if r.status_code in (429, 503): time.sleep(8 + 4 * i); continue
            r.raise_for_status(); return r.content if raw else r.json()
        except Exception: time.sleep(3 + 2 * i)
    raise RuntimeError("fetch failed: " + u)

def strip(s): return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s or ""))).strip()

def license_ok(lic): return bool(lic) and bool(OK.search(lic)) and not BAD.search(lic)

def p18(wiki_title):
    r = get("https://en.wikipedia.org/w/api.php", {"action": "query", "prop": "pageprops", "titles": wiki_title, "redirects": 1, "format": "json"})
    qid = next(iter(r["query"]["pages"].values())).get("pageprops", {}).get("wikibase_item")
    if not qid: return None, []
    c = get("https://www.wikidata.org/w/api.php", {"action": "wbgetclaims", "entity": qid, "property": "P18", "format": "json"})
    return qid, [x["mainsnak"]["datavalue"]["value"] for x in c.get("claims", {}).get("P18", []) if x["mainsnak"].get("datavalue")]

def commons(fn, width=960):
    r = get("https://commons.wikimedia.org/w/api.php", {"action": "query", "titles": "File:" + fn, "prop": "imageinfo",
            "iiprop": "url|extmetadata|size", "iiurlwidth": width, "format": "json"})
    ii = next(iter(r["query"]["pages"].values()))["imageinfo"][0]; m = ii.get("extmetadata", {}); v = lambda k: (m.get(k) or {}).get("value", "")
    return {"file": fn, "source": ii["descriptionurl"], "thumb": ii.get("thumburl") or ii["url"], "license": strip(v("LicenseShortName")),
            "license_url": v("LicenseUrl") or None, "author": re.sub(r"^(?:Autor|Author|Auteur|Photo)\s*:\s*", "", strip(v("Artist")), flags=re.I)[:120] or strip(v("Credit"))[:120] or "Wikimedia Commons",
            "date": strip(v("DateTimeOriginal"))[:10]}

def crop(b):
    """Square, face-centred crop with headroom (largest/topmost frontal face via OpenCV if installed, else top-centre), 400x400."""
    im = Image.open(BytesIO(b)).convert("RGB"); W, H = im.size; face = None
    try:
        import cv2, numpy as np
        g = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2GRAY)
        fs = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml").detectMultiScale(g, 1.1, 6, minSize=(W // 7, W // 7))
        if len(fs):
            mx = max(f[2] * f[3] for f in fs); face = min([f for f in fs if f[2] * f[3] >= .5 * mx], key=lambda f: f[1])
    except ImportError: pass
    if face is not None:
        x, y, w, h = face; side = min(w * 2.7, W, H); cx, cy = x + w / 2, y - .5 * h + side / 2
    else:
        side = min(W, H * .6, H); cx, cy = W / 2, side / 2
    l = min(max(cx - side / 2, 0), W - side); t = min(max(cy - side / 2, 0), H - side)
    out = im.crop((int(l), int(t), int(l + side), int(t + side))).resize((400, 400), Image.LANCZOS)
    buf = BytesIO(); out.save(buf, "WEBP", quality=80, method=6); return buf.getvalue(), face is not None

def fix_lic_url(u, lic):
    """Prefer stable, reachable license pages (data.gov.in's GODL PDF does not load from many networks)."""
    if re.search(r"godl", lic or "", re.I): return "https://commons.wikimedia.org/wiki/Template:GODL-India"
    if u and re.match(r"https://creativecommons\.org/(licenses|publicdomain)/[a-z-]+/\d\.\d(/[a-z]{2})?$", u): return u + "/"
    return u or None

def people():
    sys.path.insert(0, APP); os.chdir(APP)
    import figures as F
    return [(p[0], p[1], [l for l in p[-1] if "wikipedia.org/wiki/" in l[1]]) for p in F.BASE_LIST + F.POOL]

def main(keys):
    os.makedirs(OUT, exist_ok=True)
    man = json.load(open(MAN)) if os.path.exists(MAN) else {}
    for key, name, wl in people():
        if keys and key not in keys: continue
        if not wl: print(key, "no Wikipedia link: initials"); continue
        title = urllib.parse.unquote(wl[0][1].split("/wiki/", 1)[1])
        qid, files = p18(title)
        files = ([PICK[key]] if key in PICK else []) + files
        chosen = None
        for fn in files:
            info = commons(fn)
            if license_ok(info["license"]): chosen = info; break
            print(key, "skip (license):", fn, info["license"])
        if not chosen: print(key, "no freely licensed image: initials"); man.pop(key, None); continue
        webp, had_face = crop(get(chosen["thumb"], raw=True))
        open(os.path.join(OUT, key + ".webp"), "wb").write(webp)
        man[key] = {"name": name, "wikidata": qid, "file": chosen["file"], "source": chosen["source"], "author": chosen["author"],
                    "license": chosen["license"], "license_url": fix_lic_url(chosen["license_url"], chosen["license"]), "date": chosen["date"],
                    "img": f"{key}.webp", "bytes": len(webp), "face_detected": had_face}
        print(key, "ok", chosen["license"], "|", chosen["author"][:40], "|", len(webp), "B", "" if had_face else "(no face found: top-centre crop)")
        time.sleep(.5)
    with open(MAN + ".tmp", "w") as f: json.dump(dict(sorted(man.items())), f, indent=1, ensure_ascii=False)
    os.replace(MAN + ".tmp", MAN)

if __name__ == "__main__": main(set(sys.argv[1:]))
