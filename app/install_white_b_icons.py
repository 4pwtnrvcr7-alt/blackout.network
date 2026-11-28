"""Materialize white-B raster icons from the committed base64 master (text-safe in git).
Run at Docker build (see Dockerfile). Pillow is already in requirements.txt.
Matt, Nov 25 2026 5:24 PM ET: plain white serif B on black (no slash, no chrome).
"""
from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageFilter

BASE = Path(__file__).resolve().parent
B64 = BASE / "static" / "brand" / "white_b_master.b64"
SHARE_B64 = BASE / "static" / "brand" / "share-logo-1200.b64"
IMG = BASE / "static" / "img"
PWA = BASE / "static" / "pwa"
SOC = BASE / "static" / "social"


def _master() -> Image.Image:
    raw = base64.b64decode("".join(B64.read_text().split()))
    im = Image.open(BytesIO(raw)).convert("RGB")
    if im.size != (512, 512):
        im = im.resize((512, 512), Image.Resampling.LANCZOS)
    return im


def _resize(master: Image.Image, size: int, sharpen: bool = False) -> Image.Image:
    out = master.resize((size, size), Image.Resampling.LANCZOS)
    if sharpen and size <= 48:
        out = out.filter(ImageFilter.UnsharpMask(radius=0.6, percent=80, threshold=2))
    return out.convert("RGB")


def _maskable(master: Image.Image, size: int = 512, frac: float = 0.72) -> Image.Image:
    canvas = Image.new("RGB", (size, size), (0, 0, 0))
    inner = int(round(size * frac))
    mark = master.resize((inner, inner), Image.Resampling.LANCZOS)
    off = (size - inner) // 2
    canvas.paste(mark, (off, off))
    return canvas


def _save(im: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    im.convert("RGB").save(path, "PNG", optimize=True)


def install() -> None:
    if not B64.is_file():
        raise SystemExit(f"missing {B64}")
    master = _master()
    _save(master, IMG / "white-b.png")
    _save(_resize(master, 32, True), IMG / "favicon-32.png")
    _resize(master, 256, False).save(IMG / "favicon.ico", format="ICO", sizes=[(16, 16), (32, 32), (48, 48)])
    rasters = {
        PWA / "icon-16.png": (16, True),
        PWA / "icon-32.png": (32, True),
        PWA / "icon-48.png": (48, True),
        PWA / "icon-96.png": (96, False),
        PWA / "icon-96-v2.png": (96, False),
        PWA / "icon-96-bn3.png": (96, False),
        PWA / "icon-mstile-150.png": (150, False),
        PWA / "apple-touch-icon.png": (180, False),
        PWA / "icon-192.png": (192, False),
        PWA / "icon-192-v2.png": (192, False),
        PWA / "icon-192-bn3.png": (192, False),
        PWA / "icon-512.png": (512, False),
    }
    for path, (size, sharp) in rasters.items():
        _save(_resize(master, size, sharp), path)
    _save(_maskable(master), PWA / "icon-maskable-512.png")
    _save(_resize(master, 168, False), SOC / "white_b_168.png")
    if SHARE_B64.is_file():
        raw = base64.b64decode("".join(SHARE_B64.read_text().split()))
        share = Image.open(BytesIO(raw)).convert("RGB")
        if share.size != (1200, 1200):
            share = share.resize((1200, 1200), Image.Resampling.LANCZOS)
        _save(share, IMG / "share-logo-1200.png")
    print(f"install_white_b_icons: wrote mark and icons under {IMG} and {PWA}", flush=True)


if __name__ == "__main__":
    install()
