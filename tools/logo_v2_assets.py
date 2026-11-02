#!/usr/bin/env python3
"""Build every site/email icon from the logo V2-final masters (app/static/brand/v2/*.svg, 'Meter in the letters', Nov 1 2026).
Box only: needs cairosvg + Pillow (/workspace/.brandenv/bin/python tools/logo_v2_assets.py).
Dark surfaces get the dark version (#0B0D10 tile, white BN, #FFC21A elevated cells); light surfaces get the light version
(#C97B00 elevated cells) on a white tile with a #DDE1E6 border. Writes:
  app/static/bimi/logo.svg                 BIMI, SVG Tiny PS (square, solid background, no text, <title>, no scripts/external refs)
  app/static/img/favicon.svg, favicon.ico, safari-pinned-tab.svg
  app/static/pwa/icon-*.png, apple-touch-icon.png, icon-maskable-512.png, icon-mstile-150.png
  app/static/alerts/icon.png, badge.png    web-push icon + monochrome badge
  app/static/social/brand_tile_{dark,light}_168.png and brand_tile_v2_{dark,light}_168.png (email masthead)
  app/static/pwa/icon-og-newsletter-bn3.png + icon-og-newsletter-v2.png (newsletter share card)"""
import io, os, re, sys
import cairosvg
from PIL import Image
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V2 = f"{ROOT}/app/static/brand/v2"; ST = f"{ROOT}/app/static"
BG_D, BG_L = "#0B0D10", "#F6F7F9"

def rd(n): return open(f"{V2}/{n}.svg").read()
def body(svg):
    """Drawable children of a master SVG (drops the <svg> wrapper and <title>)."""
    s = re.sub(r"^.*?<svg[^>]*>", "", svg, flags=re.S); s = re.sub(r"</svg>\s*$", "", s)
    return re.sub(r"<title>.*?</title>", "", s)
MARK_W, MARK_H = 199.29, 100.0
def mark_g(theme, size, frac=0.66, mono=None):
    """Mark (BN + meter) centred in a size x size box, frac of the width (master icon uses 0.66)."""
    b = body(rd(f"mark-{theme}"))
    if mono: b = re.sub(r'fill="#[0-9A-Fa-f]{6}"', f'fill="{mono}"', b)
    k = size * frac / MARK_W; x = (size - MARK_W * k) / 2; y = (size - MARK_H * k) / 2
    return f'<g transform="translate({x:.3f} {y:.3f}) scale({k:.5f})">{b}</g>'
def tile(theme, size=1024, rx=0.0, canvas=None, stroke=None, sw=0.0, frac=0.66, fill=None):
    fill = fill or (BG_D if theme == "dark" else BG_L)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">']
    if canvas: out.append(f'<rect width="{size}" height="{size}" fill="{canvas}"/>')
    h = sw / 2
    out.append(f'<rect x="{h}" y="{h}" width="{size - sw}" height="{size - sw}" rx="{rx}" fill="{fill}"' + (f' stroke="{stroke}" stroke-width="{sw}"' if stroke else '') + '/>')
    out.append(mark_g(theme, size, frac)); out.append('</svg>'); return "".join(out)
def png(svg, px, mode="RGBA"):
    im = Image.open(io.BytesIO(cairosvg.svg2png(bytestring=svg.encode(), output_width=px, output_height=px))).convert("RGBA")
    if mode == "RGB":
        bg = Image.new("RGB", im.size, (11, 13, 16)); bg.paste(im, (0, 0), im); return bg
    return im
def save(im, path):
    os.makedirs(os.path.dirname(path), exist_ok=True); im.save(path, optimize=True); print("wrote", os.path.relpath(path, ROOT), im.size)
def master_png(name, px, mode="RGBA"):
    return png(re.sub(r'<svg ', f'<svg width="{px}" height="{px}" ', rd(name), count=1), px, mode)

def bimi():
    """BIMI logo = the designer's validated SVG Tiny PS (app/static/brand/v2/blackout-network-bimi.svg; RelaxNG SVG_PS-latest PASS).
    Copied verbatim, never regenerated."""
    import shutil; shutil.copyfile(f"{V2}/blackout-network-bimi.svg", f"{ST}/bimi/logo.svg"); print("copied app/static/bimi/logo.svg")

def favicon_svg():
    s = rd("icon-32-dark").replace('role="img">', 'width="32" height="32" role="img" aria-label="BLACKOUT.NETWORK">'
         '<style>@media (prefers-color-scheme:dark){.t{stroke:#3A414B;stroke-width:.6}}</style>', 1)
    s = s.replace('<rect width="32" height="32" rx="6" fill="#0B0D10"/>', '<rect class="t" x="0.3" y="0.3" width="31.4" height="31.4" rx="6" fill="#0B0D10"/>')
    open(f"{ST}/img/favicon.svg", "w").write(s); print("wrote app/static/img/favicon.svg")

def pinned():
    """Safari pinned tab / mask icon: one colour, the mark only."""
    s = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96">{mark_g("dark", 96, 0.86, mono="#000")}</svg>'
    open(f"{ST}/img/safari-pinned-tab.svg", "w").write(s); print("wrote app/static/img/safari-pinned-tab.svg")

def newsletter_og(path):
    sys.path.insert(0, '/workspace/launch/brand'); import bn_signal as B
    from PIL import ImageDraw, ImageFilter
    W, H = 1200, 630
    im = Image.new('RGB', (W, H), B.BG)
    g = Image.new('L', (W, H), 0); gd = ImageDraw.Draw(g); gd.ellipse((780, -260, 1420, 380), fill=60); g = g.filter(ImageFilter.GaussianBlur(120))
    im = Image.composite(Image.new('RGB', (W, H), B.AC), im, g); d = ImageDraw.Draw(im)
    t = png(tile("dark", 1024, rx=200, stroke="#2A3038", sw=8), 270); im.paste(t, (868, 128), t)
    X = 72
    d.text((X, 70), "FREE NEWSLETTER", font=B.inter(24, 700), fill=B.AC)
    f = B.mont(58, 800); d.text((X, 116), "BLACKOUT.", font=f, fill=B.TX); d.text((X + d.textlength("BLACKOUT.", font=f), 116), "NETWORK", font=f, fill=B.AC)
    d.text((X, 214), "Free 7 AM / 7 PM brief,", font=B.mont(48, 700), fill=B.TX)
    d.text((X, 274), "tailored to your area.", font=B.mont(48, 700), fill=B.TX)
    d.text((X, 360), "Global threats ranked 0–10, with what's", font=B.inter(28, 500), fill=B.MU)
    d.text((X, 398), "near you first. One click to unsubscribe.", font=B.inter(28, 500), fill=B.MU)
    B.meter(d, X, 462, 30, 7)
    d.line((X, 532, W - X, 532), fill=B.LINE, width=2)
    d.text((X, 552), "blackout.network/newsletter", font=B.mont(30, 800), fill=B.TX)
    x2 = X + d.textlength("blackout.network/newsletter", font=B.mont(30, 800)) + 30
    d.text((x2, 557), "·  X @BlkoutNtw  ·  YouTube @blkoutntw", font=B.inter(25, 500), fill=B.MU)
    save(im, path)

if __name__ == "__main__":
    bimi(); favicon_svg(); pinned()
    # favicon.ico: 16 + 32 pixel-fitted masters, 48 from the full master
    i16, i32 = master_png("icon-16-dark", 16), master_png("icon-32-dark", 32); i48 = png(tile("dark", 1024, rx=200), 48)   # 48: full master (5 cells) rendered at size; scaling the 32 grid blurs
    i48.save(f"{ST}/img/favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)], append_images=[i16, i32]); print("wrote app/static/img/favicon.ico")
    P = f"{ST}/pwa"
    save(i16, f"{P}/icon-16.png"); save(i32, f"{P}/icon-32.png"); save(i48, f"{P}/icon-48.png")
    rounded = tile("dark", 1024, rx=200)                 # 'any' purpose: rounded dark tile, transparent corners
    for px, names in ((96, ["icon-96-bn3.png", "icon-96-v2.png"]), (192, ["icon-192.png", "icon-192-bn3.png", "icon-192-v2.png"]), (512, ["icon-512.png"])):
        im = png(rounded, px)
        for n in names: save(im, f"{P}/{n}")
    full = rd("icon-dark")                               # full-bleed square: iOS / maskable / Windows tile add their own mask
    save(master_png("icon-dark", 180, "RGB"), f"{P}/apple-touch-icon.png")
    save(master_png("icon-dark", 512, "RGB"), f"{P}/icon-maskable-512.png")    # mark radius 0.37 < 0.40 safe zone
    save(master_png("icon-dark", 150, "RGB"), f"{P}/icon-mstile-150.png")
    save(png(rounded, 192), f"{ST}/alerts/icon.png")
    save(png(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96">{mark_g("dark", 96, 0.86, mono="#FFFFFF")}</svg>', 96), f"{ST}/alerts/badge.png")
    # email masthead tiles (168 = 48 px @3.5x): dark tile with a hairline on the dark email; light version on a white bordered tile
    dk = png(tile("dark", 1024, rx=196, canvas=BG_D, stroke="#2A3038", sw=10), 168, "RGB")
    lt = png(tile("light", 1024, rx=196, canvas=BG_L, stroke="#DDE1E6", sw=10, fill="#FFFFFF"), 168, "RGB")
    for n, im in (("dark", dk), ("light", lt)):
        save(im, f"{ST}/social/brand_tile_{n}_168.png"); save(im, f"{ST}/social/brand_tile_v2_{n}_168.png")
    newsletter_og(f"{P}/icon-og-newsletter-v2.png"); newsletter_og(f"{P}/icon-og-newsletter-bn3.png")
