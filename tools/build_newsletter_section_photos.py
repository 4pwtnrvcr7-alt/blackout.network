#!/usr/bin/env python3
"""Build the Weather and Crime-near-you newsletter header photos (v5).

Real, licensed photographs only (public domain / CC0 / CC BY) from Wikimedia Commons. Each source is downloaded at <=2400 px,
cropped to 1200x520 (600x260 css @2x), graded to the site's cool dark look (crime: near-monochrome, so no yellow tape or red
lights; weather: slightly muted so the sky stays natural), and faded to pure black over the bottom third so the section label
sits on the photo's own fade in the email's #000 background. Output: app/theme_static/media/<name>.b64 (served at /bnt/media/<name>)
and app/newsletter_sections_pool.json (credits at /credits#newsletter). Run on the box; the email never needs Pillow."""
import base64, io, json, os, re, sys, time, requests
from PIL import Image, ImageEnhance, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEDIA = os.path.join(ROOT, "app", "theme_static", "media")
POOL = os.path.join(ROOT, "app", "newsletter_sections_pool.json")
H = {"User-Agent": "blackout.network-newsletter-research/1.0 (contact via blackout.network)"}
W, HT = 1200, 520
# (name, kind, Commons search query, title key, crop focus y 0..1, saturation, brightness)
SRC = [
    ("nlwxstorma-d.jpg", "storm", "Nssl0225 Flickr NOAA Photo Library", "Nssl0225", 0.45, 0.85, 0.95),
    ("nlwxstormb-d.jpg", "storm", "Nssl0378 Flickr NOAA Photo Library", "Nssl0378", 0.40, 0.80, 1.05),
    ("nlwxstormc-d.jpg", "storm", "Supercell thunderstorm in Kansas", "Supercell-thunderstorm-in-Kansas", 0.40, 0.80, 1.00),
    ("nlwxraina-d.jpg", "rain", "After a day of monsoonal showers near Williamson Valley", "monsoonal", 0.40, 0.38, 0.95),
    ("nlwxsnowa-d.jpg", "snow", "Snowfall descending on the Buffalo Southtowns", "Snowfall descending", 0.25, 0.85, 0.95),
    ("nlwxcloudsa-d.jpg", "clouds", "Crepuscular rays8 NOAA", "Crepuscular rays8", 0.35, 0.85, 1.10),
    ("nlwxcleara-d.jpg", "clear", "Cumulus16 NOAA", "Cumulus16", 0.50, 0.85, 1.00),
    ("nlcrimea-d.jpg", "crime", "Police Line Do Not Cross 42422022254", "Police Line Do Not Cross", 0.50, 0.10, 1.00),
    ("nlcrimeb-d.jpg", "crime", "Crime-scene-do-not-cross", "Crime-scene-do-not-cross", 0.50, 0.05, 1.10),
]

def strip(s): return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s or "")).strip()

def find(q, key):
    r = requests.get("https://commons.wikimedia.org/w/api.php", headers=H, timeout=40, params=dict(
        action="query", generator="search", gsrsearch=q + " filetype:bitmap", gsrnamespace=6, gsrlimit=10, prop="imageinfo",
        iiprop="url|size|extmetadata", iiurlwidth=1600, format="json")).json()
    for p in (r.get("query", {}).get("pages") or {}).values():
        if key.lower() in p["title"].lower():
            return p
    raise SystemExit(f"not found: {q}")

def get(url):
    """Commons answers 429 to python-requests from some networks but not to curl with the same User-Agent, so download with curl."""
    import subprocess
    for i in range(5):
        r = subprocess.run(["curl", "-sL", "-m", "90", "-A", H["User-Agent"], "-w", "%{http_code}", "-o", "/tmp/_nlsec.bin", url], capture_output=True, text=True)
        if r.stdout.strip() == "200":
            b = open("/tmp/_nlsec.bin", "rb").read()
            if b[:3] == b"\xff\xd8\xff" or b[:3] == b"\x89PN": return b
        time.sleep(10 + 10 * i)
    raise SystemExit(f"download failed {url} {r.stdout}")

def grade(im, focus, sat, bri):
    im = im.convert("RGB"); w, h = im.size
    th = int(w * HT / W)
    if th > h:   # too short for the ratio: crop width instead
        nw = int(h * W / HT); x = (w - nw) // 2; im = im.crop((x, 0, x + nw, h))
    else:
        y = int((h - th) * focus); im = im.crop((0, y, w, y + th))
    im = im.resize((W, HT), Image.LANCZOS)
    im = ImageEnhance.Color(im).enhance(sat); im = ImageEnhance.Brightness(im).enhance(bri)
    px = im.load()
    for y in range(HT):   # bottom third fades to pure black; a hint of top darkening keeps the edge off the preheader
        t = max(0.0, (y - HT * 0.58) / (HT * 0.42)); k = 1 - min(1.0, t) ** 1.25
        if y > HT - 6: k = 0.0
        for x in range(W):
            r, g, b = px[x, y]; px[x, y] = (int(r * k), int(g * k), int(b * k))
    return im

def main():
    os.makedirs(MEDIA, exist_ok=True); man = []
    for name, kind, q, key, focus, sat, bri in SRC:
        p = find(q, key); ii = p["imageinfo"][0]; m = ii["extmetadata"]
        out = os.path.join(MEDIA, name + ".b64")
        if os.path.exists(out) and "--force" not in sys.argv:
            b = io.BytesIO(base64.b64decode(open(out).read()))   # already built: keep it, only refresh the credit metadata
        else:
            raw = get(ii["thumburl"].split("?")[0]); time.sleep(6)
            im = grade(Image.open(io.BytesIO(raw)), focus, sat, bri)
            for qlt in (80, 74, 68):
                b = io.BytesIO(); im.save(b, "JPEG", quality=qlt, optimize=True, progressive=True, subsampling=0 if qlt > 74 else 2)
                if b.tell() < 95_000: break
            open(out, "w").write(base64.b64encode(b.getvalue()).decode())
        b.seek(0, 2)
        man.append({"name": name, "topic": kind, "title": re.sub(r"^File:", "", p["title"]), "page": ii["descriptionurl"],
                    "license": strip(m.get("LicenseShortName", {}).get("value")), "artist": strip(m.get("Artist", {}).get("value"))[:160] or "NOAA",
                    "bytes": b.tell()})
        print(name, kind, man[-1]["license"], b.tell() // 1024, "KB", flush=True)
    json.dump({"note": "Newsletter v5 Weather and Crime-near-you header photos (Wikimedia Commons: public domain, CC0 or CC BY; credits on /credits#newsletter). "
                       "Weather picks the photo that matches the forecast sky.", "images": man}, open(POOL, "w"), indent=1)

if __name__ == "__main__":
    main()
