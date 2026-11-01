# Downloadable-asset branding standard (QR)

Every image, video or PDF a visitor can download from blackout.network carries:

1. a **QR code** that opens the page the asset relates to,
2. the words **"view more at"** next to (above) the QR code, and
3. **"blackout.network"** directly under the image.

All of it is made on this computer with free libraries: `segno` (QR, error correction Q, 4-module quiet zone, dark modules on a white tile),
Pillow (images), `pypdf` + `reportlab` (PDFs, vector QR) and `ffmpeg` (video). No paid APIs, no ElevenLabs.
The libraries live in the venv `/workspace/.brandenv` (`python3 -m venv --system-site-packages /workspace/.brandenv && /workspace/.brandenv/bin/pip install segno pypdf reportlab opencv-python-headless`).

| Asset type | What is added |
|---|---|
| Image (JPG/PNG) | Footer band in the site's dark theme (`#0b0d10`, red `#ff4d4f` rule): "blackout.network" + "Signal over noise." on the left, "view more at" + QR tile (≥140 px) on the right. JPEG EXIF/XMP are kept. |
| PDF | The same band, in vector, at the bottom of the last page. The page content is scaled down slightly (about 7%), so the paper size stays the same (tabloid still prints 1:1). |
| Video | A 3.5 s end card ("blackout.network", tagline, "view more at", QR, URL) appended at the source resolution and frame rate. The original audio is kept, with silence under the card. An optional corner watermark (`--corner`) is off by default because the ads already carry one. |

Branded files are marked (JPEG comment, PNG text chunk or PDF/MP4 metadata `bn-brand-qr:<url>`), so re-running skips them unless you pass `--force`.

## Which URL to use
There is no per-story permalink on the site. These are real deep links (dashboard `TABHASH`):

- Wire source snapshots (`/snapshots/*.jpg`): `https://blackout.network/#wire`. The item id is already printed in the snapshot's metadata bar.
- Printable maps (`/maps/*.pdf`): `https://blackout.network/#maps`
- Ads and promo videos: `https://blackout.network/`
- Other tabs: `#thread`, `#ranked`, `#maps`, `#bushcraft`, `#medical`, `#tips`, `#solar`, `#network`, `#radio`, `#broadcasts`, `#streams`, `#jets`, `#resources`.

Never point a QR at a route that does not exist.

## Brand a new asset
```
/workspace/.brandenv/bin/python brand_assets.py <file> --url <page-url>            # writes <name>_branded.<ext> alongside
/workspace/.brandenv/bin/python brand_assets.py <file> --url <page-url> --inplace  # backs up <name>_pre_qr_backup.<ext>, replaces in place
/workspace/.brandenv/bin/python brand_assets.py <file> --decode                     # reads the QR back (OpenCV) to verify it
```
From Python: `import brand_assets as BA; BA.brand_pil(img, BA.PAGE["wire"])` or `BA.brand_file(path, url, inplace=True)`.

## Hooked in (automatic)
- `snapshot_worker.py`: every new Wire snapshot is branded before it is saved (`brand()`), falling back to unbranded on any error.
- `/workspace/mapbuild/index.py`: the rendered region maps are branded when they are copied into `static/maps`.
- `/workspace/brief_video/ad_v2/mux.sh`: every ad render also gets `*_branded.mp4` copies with the end card.

Originals: `snapshots_pre_qr_backup/` (box only; never synced or packaged) and `static/maps/*_pre_qr_backup.pdf` (box only).
