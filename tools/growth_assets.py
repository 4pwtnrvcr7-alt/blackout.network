#!/usr/bin/env python3
"""Build static growth/SEO graphics (box only; needs Pillow + Natural Earth in /workspace/geodata):
  app/growth_static/world.webp   2:1 equirectangular dark locator base map (Natural Earth, public domain) used for Wire thumbnails
  app/static/pwa/icon-og-1200x630.png  branded Open Graph / Twitter card image (all pages)"""
import json, sys, os
from PIL import Image, ImageDraw, ImageFilter
sys.path.insert(0, '/workspace/launch/brand'); import bn_signal as B
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEO = json.load(open('/workspace/geodata/ne_50m_admin_0_countries.geojson'))
def polys():
    for f in GEO['features']:
        g = f['geometry']
        for p in (g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]): yield p[0]
def world(W, H, bg, land, line, ox=0, oy=0, img=None):
    im = img or Image.new('RGB', (W, H), bg); d = ImageDraw.Draw(im)
    for ring in polys():
        pts = [(ox + (x + 180) / 360 * W, oy + (90 - y) / 180 * H) for x, y in ring]
        if len(pts) > 2: d.polygon(pts, fill=land, outline=line)
    return im
# 1) locator base map 1600x800 (cropped by CSS around the event)
m = world(1600, 800, (12, 15, 20), (30, 36, 45), (52, 60, 72))
d = ImageDraw.Draw(m)
for x in range(0, 1600, 1600 // 24): d.line([(x, 0), (x, 800)], fill=(17, 21, 27))
for y in range(0, 800, 800 // 12): d.line([(0, y), (1600, y)], fill=(17, 21, 27))
m = world(1600, 800, None, (30, 36, 45), (58, 66, 80), img=m)
m.save(f'{ROOT}/app/growth_static/world.webp', 'WEBP', quality=78, method=6)
# 2) OG image 1200x630
W, H = 1200, 630
og = Image.new('RGB', (W, H), B.BG if hasattr(B, 'BG') else (11, 13, 16))
wm = world(1500, 750, (11, 13, 16), (24, 29, 36), (36, 42, 52)).crop((150, 60, 150 + W, 60 + H))
og.paste(wm, (0, 0))
shade = Image.new('L', (W, H)); sd = ImageDraw.Draw(shade)
for x in range(W): sd.line([(x, 0), (x, H)], fill=int(235 * max(0, 1 - x / (W * .78))))
og = Image.composite(Image.new('RGB', (W, H), (11, 13, 16)), og, shade)
dots = [(77, 16.5, 8), (31, 49, 9), (139, 36, 5), (24, 0, 6), (51, 32, 7), (168, -15, 4)]
glow = Image.new('RGBA', (W, H), (0, 0, 0, 0)); gd = ImageDraw.Draw(glow)
for lon, lat, r in dots:
    x = (lon + 180) / 360 * 1500 - 150; y = (90 - lat) / 180 * 750 - 60
    col = B.sev(r); gd.ellipse([x - 16, y - 16, x + 16, y + 16], fill=col + (70,))
glow = glow.filter(ImageFilter.GaussianBlur(6)); og.paste(glow, (0, 0), glow)
gd = ImageDraw.Draw(og)
for lon, lat, r in dots:
    x = (lon + 180) / 360 * 1500 - 150; y = (90 - lat) / 180 * 750 - 60
    gd.ellipse([x - 5, y - 5, x + 5, y + 5], fill=B.sev(r))
d = ImageDraw.Draw(og)
B.icon(d, 72, 70, 96, bg=True)
d.text((72, 210), 'BLACKOUT.', font=B.mont(64, 900), fill=(236, 239, 243))
d.text((72 + d.textlength('BLACKOUT.', font=B.mont(64, 900)), 210), 'NETWORK', font=B.mont(64, 900), fill=B.RED)
d.text((74, 292), 'Ask better questions.', font=B.inter(34, 600), fill=(201, 209, 219))
y = 360
for line in ['Global threats, ranked 0–10 and linked', 'to their sources. Free, updated hourly.']:
    d.text((74, y), line, font=B.inter(27, 400), fill=(150, 160, 174)); y += 38
B.meter(d, 74, 462, 30, 7)
d.text((74, 548), 'blackout.network', font=B.mont(28, 800), fill=(236, 239, 243))
x2 = 74 + d.textlength('blackout.network', font=B.mont(28, 800)) + 22
d.text((x2, 553), '·   X @BlkoutNtw   ·   YouTube @blkoutntw', font=B.inter(23, 500), fill=(150, 160, 174))
og.save(f'{ROOT}/app/static/pwa/icon-og-1200x630.png', optimize=True)
print('ok')
