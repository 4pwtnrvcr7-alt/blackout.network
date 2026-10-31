# Blackout Network illustration style

One style for every illustration on blackout.network. It extends the site's existing
"How it works" line icons (`hwI()` in dashboard.html), so new art sits beside them cleanly.

## Drawing rules
- **Flat monoline SVG**, hand-authored. No gradients, photos, raster images, AI imagery or third-party art.
- **Canvas:** `viewBox="0 0 200 110"` (same as the existing `hw-svg` icons). Keep ~6px clear margin.
- **Stroke:** 2.4px main lines, 1.2–1.6px for detail (grid lines, hatching, fishing line). `stroke-linecap="round"`, `stroke-linejoin="round"`, `fill="none"` by default.
- **Colour** (from theme.css):
  - Line colour: `currentColor`, set to `#e6e9ee` (--tx). Print switches it to near-black.
  - Accent: `#ff4d4f` (--hi), **one** focal element per illustration (the thing the section teaches: the ridge line, the needle, the pressure arrows).
  - Muted: `#8b95a3` (--mu) for ground, secondary objects and context.
  - Semantic tones only where they carry meaning: water `#4aa3ff` (--ac), flame/heat `#faad14` (--md), OK/check `#52c41a` (--lo).
  - Small solid fills only for tiny marks (stars, a bobber half, a deadbolt).
- **Background:** transparent; it sits on a `#0f1317` panel with a 1px `--bd` border and 10px radius (`.bc-ill` in guide.css).
- **No text inside the SVG** (except a single-letter mark if unavoidable), so the translate feature has nothing to miss.
- **Accuracy beats detail.** If a technique can't be drawn correctly at this size, draw less.
- **Weight:** under 10 KB per SVG (these are ~1–2.5 KB).

## Markup
```html
<figure class="bc-ill bc-ill-NAME">
  <svg viewBox="0 0 200 110" role="img" aria-label="What it shows" translate="no" ...><title>What it shows</title>…</svg>
  <figcaption>Illustration by Blackout Network</figcaption>
</figure>
```
- Every illustration carries the caption **exactly** "Illustration by Blackout Network" (small, muted, translatable).
- `aria-label` + `<title>` describe what is drawn and what it teaches.
- Inline the SVG in the page (the static route serves flat files only). The files in this folder are the masters, so keep them in sync with the inline copies.

## Motion
- Optional, subtle and slow: flame flicker (`.bc-flame`), rising bubbles (`.bc-bub`), drips (`.bc-drop`), ripples (`.bc-ripple`), wind (`.bc-wind`), pulses (`.bc-blast`, `.bc-glow`).
- CSS only, transform/opacity only, 1.6–3 s loops. Always disabled under `prefers-reduced-motion: reduce` and in print.

## Files (Bushcraft tab)
first72 (First 72 hours), water, shelter, fire, food, aid (First aid), nav (Navigation), signal (Signaling), sec (Security), plants.
