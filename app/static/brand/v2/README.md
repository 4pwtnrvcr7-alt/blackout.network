# V2 final: Meter in the letters (selected), with the new yellow

Only one thing changed from `../v2-meter-in-letters/`, which is kept untouched as a backup: the elevated (yellow) cells.

| | Old | New | Contrast of new |
|---|---|---|---|
| Dark | #D6A243 (mustard) | **#FFC21A** | 12.03:1 on #0B0D10, 11.02:1 on #14181D |
| Light | #8C5800 (brown) | **#C97B00** | 3.10:1 on #F6F7F9, 3.32:1 on #FFFFFF |

- **Light-version colour:** #FFC21A is only 1.51:1 on #F6F7F9, and the suggested #E0A000 is only 2.13:1. A yellow that reaches 3:1 on the light page has to be fairly deep. #C97B00 is a fully saturated amber, chosen over darker, browner values.
- **Colour-vision check:** simulated deuteranopia and protanopia (Machado 2009, full severity); see `cvd-check/`. The elevated cells stay separate from green and red in lightness, and each colour also keeps its fixed position in the stack.
  - Colour difference (dE) between yellow and green: dark 71 (deuteranopia) and 60 (protanopia); light 58 and 44.
  - Yellow vs red: dark 52 and 76; light 27 and 45.
  - The closest pair is light-version yellow vs red under deuteranopia (dE 27). It is still clearly distinct.
- **Other colours are unchanged:** low #3FAE80 / #1D7350, critical #C8102E, monogram and wordmark #FFFFFF / #0B0D10, tagline #C9D0D9 / #2C333C.

## Files
- **`svg/`** (dark and light):
  - `icon` (square 1024)
  - `app-icon-squircle`
  - `icon-32`, `icon-16` (pixel-fitted)
  - `mark` (transparent)
  - `lockup-horizontal`, `lockup-tagline` ("Signal over noise.")
  - All text is outlined.
- **`png/`** (dark and light):
  - `icon-{16,32,180,512,1024}`
  - `app-icon-squircle-1024`
  - `mark@2x`
  - `lockup-{horizontal,tagline}@2x`
- `sheet-v2-final.png`: presentation sheet.
- `compare-old-vs-new-yellow.png`: old vs new comparison, dark and light, with the colour-vision strip.
- `cvd-check/`: deuteranopia and protanopia simulations of the 512 px icon.
