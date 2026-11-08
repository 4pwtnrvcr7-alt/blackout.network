"""Rasterize the v3 menu engravings and matching story scenes into email PNGs.

The live menu art is the path markup in app/static/bn-menu-art.json (shipped with the
Engraved menu). This script wraps those paths in the same viewBox the menu uses and
draws the story types the menu does not have (storm, quake, outbreak, missile, conflict,
fire, flood, grid, cyber, sun) in the same ivory-and-gold crosshatch. Chrome paints the
SVG; Pillow keeps each PNG near 30–60 KB. The newsletter loads the PNGs. It does not
need Chrome at send time.
"""
import json, math, os, shutil, subprocess, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, "app", "static", "bn-menu-art.json")
OUT = os.path.join(ROOT, "app", "static", "newsletter", "engraved")
ACC = {
    "latest": "#FFC21A", "threats": "#E0662E", "prepare": "#3FAE80", "politics": "#5B8DEF",
    "markets": "#2BB3A3", "community": "#B07CE8", "about": "#A3ADBA",
}
IVORY = "#E6E1D6"
GOLD = "#FFC21A"


def menu_svg(key, inner):
    acc = ACC[key]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="640" height="440" viewBox="560 0 640 440">
<rect x="560" y="0" width="640" height="440" fill="#0B0D10"/>
<style>.m3-acc{{stroke:{acc}}} .m3-bg{{fill:#0B0D10;stroke:none}}</style>
<g fill="none" stroke="{IVORY}" stroke-linecap="round" stroke-linejoin="round">{inner}</g>
</svg>'''


def frame(body, w=640, h=360):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<rect width="{w}" height="{h}" fill="#0B0D10"/>
<g fill="none" stroke="{IVORY}" stroke-linecap="round" stroke-linejoin="round">
<rect x="14" y="14" width="{w-28}" height="{h-28}" stroke-width="1.2"/>
<rect x="20" y="20" width="{w-40}" height="{h-40}" stroke="{GOLD}" stroke-width="0.6"/>
<path d="M28 44 H92 M28 50 H70" stroke="{GOLD}" stroke-width="1.1"/>
<path d="M{w-92} {h-44} H{w-28} M{w-70} {h-50} H{w-28}" stroke="{GOLD}" stroke-width="1.1"/>
{body}
</g></svg>'''


def ellipse_hatch(cx, cy, rx, ry, gap=5, sw=0.75, op=0.8, stroke=IVORY):
    out = []
    y = cy - ry
    while y <= cy + ry + 0.1:
        t = (y - cy) / ry if ry else 0
        if abs(t) < 1:
            hw = rx * math.sqrt(max(0.0, 1 - t * t))
            out.append(f'<path d="M{cx-hw:.1f} {y:.1f}H{cx+hw:.1f}" stroke="{stroke}" stroke-width="{sw}" stroke-opacity="{op}"/>')
        y += gap
    out.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" stroke="{stroke}" stroke-width="1.35"/>')
    return "\n".join(out)


def clip_hatch(cid, d_clip, gap=6, angle="diag", sw=0.7):
    """Crosshatch inside an arbitrary clip path."""
    lines = []
    if angle == "diag":
        for i in range(-40, 80):
            x = -80 + i * gap
            lines.append(f'<path d="M{x} -20 L{x+520} 500" stroke-width="{sw}" stroke-opacity="0.8"/>')
    else:
        for y in range(0, 400, gap):
            lines.append(f'<path d="M0 {y} H640" stroke-width="{sw}" stroke-opacity="0.75"/>')
    return (f'<clipPath id="{cid}"><path d="{d_clip}"/></clipPath>'
            f'<g clip-path="url(#{cid})">{"".join(lines)}</g>')


def scene_storm():
    parts = []
    for i in range(26):
        y = 48 + i * 9
        amp = 10 + (i % 3)
        pts = []
        x = 40
        while x <= 600:
            yy = y + amp * math.sin(x / 34.0 + i * 0.4)
            pts.append(f"{x:.0f},{yy:.1f}")
            x += 8
        parts.append(f'<polyline points="{" ".join(pts)}" stroke-width="0.7" stroke-opacity="0.55"/>')
    parts.append(ellipse_hatch(200, 118, 120, 46, 4.5))
    parts.append(ellipse_hatch(360, 100, 150, 52, 4.5))
    parts.append(ellipse_hatch(510, 128, 90, 36, 4.5))
    parts.append(ellipse_hatch(280, 150, 70, 26, 4, sw=0.6, op=0.65))
    parts.append('<path d="M430 78 L392 168 H438 L386 268" stroke="#FFC21A" stroke-width="2.4" stroke-linejoin="miter"/>')
    parts.append('<path d="M404 168 H446" stroke="#FFC21A" stroke-width="2.2"/>')
    for i in range(18):
        x = 70 + i * 28
        parts.append(f'<path d="M{x} 250 l-8 28" stroke-width="0.8" stroke-opacity="0.7"/>')
    parts.append('<path d="M40 300 H600" stroke-width="1.2"/>')
    for y in range(312, 340, 6):
        parts.append(f'<path d="M40 {y} H600" stroke-width="0.55" stroke-opacity="0.45"/>')
    return frame("\n".join(parts))


def scene_quake():
    parts = ['<path d="M40 168 H600" stroke-width="0.6" stroke-opacity="0.4"/>']
    for y in range(186, 332, 7):
        fault = 268 + (y - 186) * 0.42
        parts.append(f'<path d="M48 {y:.0f} H{fault:.0f}" stroke-width="0.95"/>')
        parts.append(f'<path d="M{fault+14:.0f} {y+26:.0f} H592" stroke-width="0.95"/>')
        # short cross ticks, the engraving tooth
        parts.append(f'<path d="M{fault:.0f} {y:.0f} L{fault+14:.0f} {y+26:.0f}" stroke="#FFC21A" stroke-width="0.7" stroke-opacity="0.9"/>')
    parts.append('<path d="M250 36 L292 120 L262 188 L318 250 L286 340" stroke="#FFC21A" stroke-width="1.7"/>')
    pts = []
    for i in range(0, 520):
        x = 60 + i
        env = 4 if i < 160 else (22 if i < 340 else 8)
        y = 118 + env * math.sin(i / 7.5) * math.sin(i / 28.0)
        if i % 3 == 0:
            pts.append(f"{x:.0f},{y:.1f}")
    parts.append(f'<polyline points="{" ".join(pts)}" stroke="#FFC21A" stroke-width="1.5"/>')
    parts.append('<path d="M60 118 H580" stroke-width="0.5" stroke-opacity="0.4"/>')
    return frame("\n".join(parts))


def scene_outbreak():
    cx, cy, r = 320, 180, 92
    parts = []
    # diagonal hatch clipped to the disc
    lines = []
    for i in range(-30, 40):
        x = cx - 180 + i * 6
        lines.append(f'<path d="M{x} {cy-160} L{x+220} {cy+160}" stroke-width="0.7" stroke-opacity="0.75"/>')
    parts.append(f'<clipPath id="disc"><circle cx="{cx}" cy="{cy}" r="{r}"/></clipPath>')
    parts.append(f'<g clip-path="url(#disc)">{"".join(lines)}</g>')
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" stroke-width="1.6"/>')
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r+10}" stroke-width="0.6" stroke-opacity="0.6"/>')
    for i in range(18):
        a = math.radians(i * 20 - 90)
        x1, y1 = cx + math.cos(a) * (r + 8), cy + math.sin(a) * (r + 8)
        x2, y2 = cx + math.cos(a) * (r + 36), cy + math.sin(a) * (r + 36)
        parts.append(f'<path d="M{x1:.1f} {y1:.1f} L{x2:.1f} {y2:.1f}" stroke-width="1.15"/>')
        parts.append(f'<circle cx="{x2:.1f}" cy="{y2:.1f}" r="4.2" stroke="#FFC21A" stroke-width="1.1"/>')
    # small cross, not covering the hatch
    parts.append(f'<path d="M{cx} {cy-16} V{cy+16} M{cx-16} {cy} H{cx+16}" stroke="#FFC21A" stroke-width="2.2"/>')
    return frame("\n".join(parts))


def scene_missile():
    parts = []
    # launch arc
    parts.append('<path d="M80 300 C 180 300, 220 80, 520 70" stroke="#FFC21A" stroke-width="1.3" stroke-dasharray="2 6"/>')
    # body
    parts.append('<path d="M300 78 L332 118 L332 250 L268 250 L268 118 Z" stroke-width="1.5"/>')
    for y in range(126, 246, 6):
        parts.append(f'<path d="M272 {y} H328" stroke-width="0.65" stroke-opacity="0.8"/>')
    parts.append('<path d="M268 168 H332 M268 210 H332" stroke-width="1"/>')
    parts.append('<path d="M268 250 L248 286 H288 L268 250 M332 250 L352 286 H312 L332 250" stroke-width="1.2"/>')
    # exhaust hatch
    for i in range(8):
        y = 292 + i * 6
        inset = i * 6
        parts.append(f'<path d="M{286+inset} {y} H{314-inset}" stroke="#FFC21A" stroke-width="0.9" stroke-opacity="{0.85 - i*0.08:.2f}"/>')
    parts.append('<path d="M40 312 H600" stroke-width="1"/>')
    for x in range(60, 600, 18):
        parts.append(f'<path d="M{x} 312 l-8 22" stroke-width="0.55" stroke-opacity="0.45"/>')
    return frame("\n".join(parts))


def scene_conflict():
    parts = []
    # distant ridgeline
    pts = []
    for x in range(40, 610, 8):
        y = 210 + 16 * math.sin(x / 40.0) + 8 * math.sin(x / 15.0)
        pts.append(f"{x},{y:.0f}")
    parts.append(f'<polyline points="{" ".join(pts)}" stroke-width="1.1"/>')
    for i, base in enumerate((150, 250, 350)):
        y = 248 - i * 8
        parts.append(f'<path d="M{base} {y+70} L{base+70} {y} L{base+140} {y+70}" stroke-width="1.4"/>')
        # hatch inside the chevron via short lines
        for k in range(8):
            yy = y + 12 + k * 7
            half = int((yy - y) * 0.95)
            parts.append(f'<path d="M{base+70-half} {yy} H{base+70+half}" stroke-width="0.6" stroke-opacity="0.75"/>')
    parts.append('<path d="M468 150 l18 46 h-14 l16 40" stroke="#FFC21A" stroke-width="1.6"/>')
    parts.append('<path d="M40 318 H600" stroke-width="1.15"/>')
    for y in range(326, 344, 5):
        parts.append(f'<path d="M40 {y} H600" stroke-width="0.5" stroke-opacity="0.4"/>')
    return frame("\n".join(parts))


def scene_fire():
    flame = "M320 48 C 360 110, 410 120, 400 190 C 460 200, 450 280, 360 300 C 340 330, 300 330, 280 300 C 180 280, 190 190, 250 180 C 230 120, 280 100, 320 48 Z"
    parts = [clip_hatch("flame", flame, gap=7)]
    parts.append(f'<path d="{flame}" stroke-width="1.6"/>')
    inner = "M320 110 C 348 150, 370 160, 360 210 C 390 220, 380 270, 330 286 C 300 300, 280 280, 292 250 C 250 240, 260 180, 300 170 C 292 140, 308 130, 320 110 Z"
    parts.append(f'<path d="{inner}" stroke="#FFC21A" stroke-width="1.15"/>')
    parts.append('<path d="M80 318 H560" stroke-width="1.1"/>')
    for x in range(100, 560, 16):
        h = 10 + (x % 3) * 4
        parts.append(f'<path d="M{x} 318 V{318-h}" stroke-width="0.6" stroke-opacity="0.5"/>')
    return frame("\n".join(parts))


def scene_flood():
    parts = []
    # house
    parts.append('<path d="M250 150 L320 96 L390 150 V280 H250 Z" stroke-width="1.5"/>')
    parts.append('<path d="M300 200 H340 V280 H300 Z" stroke-width="1.1"/>')
    parts.append('<path d="M268 168 H292 V192 H268 Z M348 168 H372 V192 H348 Z" stroke-width="1"/>')
    for i in range(6):
        parts.append(f'<path d="M258 {168+i*16} H382" stroke-width="0.45" stroke-opacity="0.35"/>')
    # water
    for i, y in enumerate(range(230, 340, 8)):
        pts = []
        for x in range(40, 610, 8):
            yy = y + 5 * math.sin(x / 22.0 + i)
            pts.append(f"{x},{yy:.1f}")
        col = GOLD if i == 0 else IVORY
        op = 1 if i == 0 else 0.75
        parts.append(f'<polyline points="{" ".join(pts)}" stroke="{col}" stroke-width="1" stroke-opacity="{op}"/>')
    return frame("\n".join(parts))


def scene_grid():
    def tower(x):
        s = [f'<path d="M{x} 300 L{x+46} 70 L{x+92} 300" stroke-width="1.4"/>',
             f'<path d="M{x+46} 70 V108" stroke-width="1.2"/>',
             f'<path d="M{x+16} 250 H{x+76} M{x+24} 200 H{x+68} M{x+32} 150 H{x+60}" stroke-width="0.9"/>']
        # cross braces
        s.append(f'<path d="M{x+10} 280 L{x+78} 210 M{x+14} 210 L{x+80} 280" stroke-width="0.7"/>')
        s.append(f'<path d="M{x+24} 200 L{x+68} 150 M{x+32} 150 L{x+68} 200" stroke-width="0.7"/>')
        return "\n".join(s)
    parts = [tower(70), tower(250), tower(450)]
    parts.append('<path d="M116 108 C 200 150, 250 150, 296 108" stroke="#FFC21A" stroke-width="1.3"/>')
    parts.append('<path d="M296 112 C 380 160, 430 158, 496 108" stroke="#FFC21A" stroke-width="1.3"/>')
    parts.append('<path d="M116 118 C 200 168, 250 168, 296 122" stroke-width="0.7" stroke-opacity="0.7"/>')
    parts.append('<path d="M496 100 l8 18 -16 4" stroke="#FFC21A" stroke-width="1.4"/>')
    parts.append('<path d="M40 300 H600" stroke-width="1.15"/>')
    return frame("\n".join(parts))


def scene_cyber():
    parts = ['<rect x="70" y="54" width="500" height="250" rx="8" stroke-width="1.4"/>']
    # circuit traces
    y = 78
    while y < 280:
        parts.append(f'<path d="M90 {y} H240 V{y+18} H360 V{y} H550" stroke-width="0.7" stroke-opacity="0.85"/>')
        parts.append(f'<circle cx="240" cy="{y}" r="3" stroke="#FFC21A" stroke-width="1"/>')
        parts.append(f'<circle cx="360" cy="{y+18}" r="3" stroke-width="0.9"/>')
        y += 28
    parts.append('<rect x="250" y="120" width="140" height="110" stroke="#FFC21A" stroke-width="1.3"/>')
    for i in range(-2, 12):
        parts.append(f'<path d="M{258+i*12} 128 L{258+i*12+90} 222" stroke-width="0.55" stroke-opacity="0.7"/>')
    parts.append('<path d="M300 156 H340 V188 H300 Z" stroke-width="1.3"/>')
    parts.append('<path d="M292 156 V148 H348 V156" stroke="#FFC21A" stroke-width="1.4"/>')
    return frame("\n".join(parts))


def scene_space():
    cx, cy, r = 250, 180, 78
    parts = []
    for i in range(36):
        a = math.radians(i * 10)
        x1, y1 = cx + math.cos(a) * (r + 8), cy + math.sin(a) * (r + 8)
        length = 36 if i % 3 else 58
        x2, y2 = cx + math.cos(a) * (r + length), cy + math.sin(a) * (r + length)
        col = GOLD if i % 3 == 0 else IVORY
        parts.append(f'<path d="M{x1:.1f} {y1:.1f} L{x2:.1f} {y2:.1f}" stroke="{col}" stroke-width="0.9"/>')
    parts.append(ellipse_hatch(cx, cy, r, r, gap=6, sw=0.7))
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r-18}" stroke="#FFC21A" stroke-width="1.1"/>')
    # flare
    parts.append('<path d="M330 150 C 420 80, 520 60, 580 90" stroke="#FFC21A" stroke-width="1.8"/>')
    parts.append('<path d="M336 168 C 430 120, 520 110, 590 130" stroke="#FFC21A" stroke-width="0.8" stroke-opacity="0.8"/>')
    # earth limb
    parts.append('<path d="M470 250 A90 90 0 0 0 590 300" stroke-width="1.4"/>')
    parts.append('<path d="M490 268 A70 70 0 0 0 580 308" stroke-width="0.6" stroke-opacity="0.6"/>')
    return frame("\n".join(parts))


def scene_missile():
    """Large launch vehicle. Replaces the smaller first drawing."""
    parts = []
    parts.append('<path d="M90 300 C 180 300, 240 70, 560 48" stroke="#FFC21A" stroke-width="1.5" stroke-dasharray="1.5 7"/>')
    parts.append('<path d="M250 46 L310 110 L310 250 L190 250 L190 110 Z" stroke-width="1.7"/>')
    for y in range(122, 246, 7):
        parts.append(f'<path d="M198 {y} H302" stroke-width="0.7" stroke-opacity="0.85"/>')
    parts.append('<path d="M190 168 H310 M190 214 H310" stroke-width="1.15"/>')
    parts.append('<path d="M190 250 L150 310 H210 L190 250 M310 250 L350 310 H290 L310 250" stroke-width="1.4"/>')
    for i in range(9):
        y = 318 + i * 4
        inset = i * 8
        parts.append(f'<path d="M{214+inset} {y} H{286-inset}" stroke="#FFC21A" stroke-width="1" stroke-opacity="{0.9 - i*0.08:.2f}"/>')
    parts.append('<path d="M40 312 H600" stroke-width="1.1"/>')
    return frame("\n".join(parts))


def scene_rights():
    """Scales and a scroll. Ivory crosshatch, one gold beam."""
    parts = []
    parts.append('<path d="M64 78 H268 V292 H64 Z" stroke-width="1.45"/>')
    parts.append('<path d="M64 78 q18 -22 36 0 q18 -22 36 0 q18 -22 36 0 q18 -22 36 0 q18 -22 36 0 q18 -22 24 0" stroke-width="1.15"/>')
    for y in range(108, 250, 7):
        parts.append(f'<path d="M82 {y} H250" stroke-width="0.6" stroke-opacity="0.8"/>')
    parts.append('<circle cx="166" cy="262" r="16" stroke="#FFC21A" stroke-width="1.4"/>')
    parts.append('<circle cx="166" cy="262" r="6" stroke="#FFC21A" stroke-width="1"/>')
    parts.append('<path d="M430 64 V300" stroke-width="1.6"/>')
    parts.append('<path d="M318 108 H542" stroke="#FFC21A" stroke-width="1.8"/>')
    parts.append('<path d="M318 108 L292 176 M542 108 L568 176" stroke-width="1.15"/>')
    for i in range(6):
        y = 118 + i * 12
        parts.append(f'<circle cx="318" cy="{y}" r="3.4" stroke-width="0.8"/>')
        parts.append(f'<circle cx="542" cy="{y}" r="3.4" stroke-width="0.8"/>')
    parts.append(ellipse_hatch(292, 198, 52, 15, 3.2))
    parts.append(ellipse_hatch(568, 198, 52, 15, 3.2))
    parts.append('<path d="M40 312 H600" stroke-width="1.05"/>')
    return frame("\n".join(parts))


def scene_surveillance():
    """A large eye, scan lines, viewfinder corners."""
    parts = []
    for y in range(36, 330, 8):
        parts.append(f'<path d="M36 {y} H604" stroke-width="0.45" stroke-opacity="0.35"/>')
    parts.append('<path d="M48 48 H120 M48 48 V110 M592 48 H520 M592 48 V110 M48 312 H120 M48 312 V250 M592 312 H520 M592 312 V250" stroke="#FFC21A" stroke-width="1.3"/>')
    cx, cy, rx, ry = 320, 176, 210, 96
    parts.append(f'<path d="M{cx-rx} {cy} C {cx-rx*0.4} {cy-ry*1.7}, {cx+rx*0.4} {cy-ry*1.7}, {cx+rx} {cy} C {cx+rx*0.4} {cy+ry*1.7}, {cx-rx*0.4} {cy+ry*1.7}, {cx-rx} {cy} Z" stroke-width="1.6"/>')
    parts.append(f'<clipPath id="eye"><path d="M{cx-rx} {cy} C {cx-rx*0.4} {cy-ry*1.7}, {cx+rx*0.4} {cy-ry*1.7}, {cx+rx} {cy} C {cx+rx*0.4} {cy+ry*1.7}, {cx-rx*0.4} {cy+ry*1.7}, {cx-rx} {cy} Z"/></clipPath>')
    hatch = []
    for i in range(-18, 28):
        x = cx - 260 + i * 8
        hatch.append(f'<path d="M{x} {cy-160} L{x+180} {cy+160}" stroke-width="0.6" stroke-opacity="0.7"/>')
    parts.append(f'<g clip-path="url(#eye)">{"".join(hatch)}</g>')
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="62" stroke-width="1.3"/>')
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="40" stroke-width="0.8" stroke-opacity="0.8"/>')
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="16" stroke="#FFC21A" stroke-width="1.8"/>')
    return frame("\n".join(parts))


def scene_protest():
    """A crowd of hatched figures under contour lines. Signs carry no words."""
    parts = []
    for i in range(16):
        y = 40 + i * 7
        pts = []
        for x in range(40, 610, 10):
            yy = y + 8 * math.sin(x / 36.0 + i * 0.3)
            pts.append(f"{x},{yy:.1f}")
        parts.append(f'<polyline points="{" ".join(pts)}" stroke-width="0.6" stroke-opacity="0.55"/>')
    for i in range(11):
        x = 58 + i * 50
        h = 150 + (i % 4) * 18
        head_y = 300 - h
        parts.append(f'<circle cx="{x}" cy="{head_y}" r="11" stroke-width="1.15"/>')
        parts.append(f'<path d="M{x-16} 300 L{x-10} {head_y+16} H{x+10} L{x+16} 300" stroke-width="1.15"/>')
        for k in range(6):
            yy = head_y + 28 + k * 12
            if yy > 292: break
            half = 8 + (300 - yy) // 16
            parts.append(f'<path d="M{x-half} {yy} H{x+half}" stroke-width="0.55" stroke-opacity="0.75"/>')
        if i in (2, 6, 9):
            parts.append(f'<path d="M{x} {head_y-8} V{head_y-52}" stroke-width="1"/>')
            parts.append(f'<path d="M{x-18} {head_y-52} H{x+22} V{head_y-28} H{x-18} Z" stroke="#FFC21A" stroke-width="1.15"/>')
    parts.append('<path d="M40 300 H600" stroke-width="1.15"/>')
    return frame("\n".join(parts))


def scene_border():
    """A gate and fence. No lettering."""
    parts = []
    for x in range(48, 600, 16):
        parts.append(f'<path d="M{x} 86 V292" stroke-width="0.9"/>')
    parts.append('<path d="M48 110 H592 M48 250 H592" stroke-width="1.35"/>')
    parts.append('<path d="M48 86 H592" stroke-width="1.5"/>')
    for x in range(48, 600, 16):
        parts.append(f'<path d="M{x-5} 86 L{x} 74 L{x+5} 86" stroke-width="0.7"/>')
    parts.append('<path d="M250 86 V292 M390 86 V292" stroke="#FFC21A" stroke-width="2"/>')
    parts.append('<path d="M250 86 H390" stroke="#FFC21A" stroke-width="1.6"/>')
    parts.append('<path d="M268 292 V150 H372 V292" stroke-width="1.2"/>')
    for y in range(160, 280, 10):
        parts.append(f'<path d="M276 {y} H364" stroke-width="0.55" stroke-opacity="0.7"/>')
    parts.append('<path d="M40 292 H600" stroke-width="1.15"/>')
    return frame("\n".join(parts))


SCENES = {
    "scene-storm": scene_storm, "scene-quake": scene_quake, "scene-outbreak": scene_outbreak,
    "scene-missile": scene_missile, "scene-conflict": scene_conflict, "scene-fire": scene_fire,
    "scene-flood": scene_flood, "scene-grid": scene_grid, "scene-cyber": scene_cyber,
    "scene-space": scene_space, "scene-rights": scene_rights, "scene-surveillance": scene_surveillance,
    "scene-protest": scene_protest, "scene-border": scene_border,
}


def write_svgs():
    os.makedirs(OUT, exist_ok=True)
    menu = json.load(open(ART))
    for key, inner in menu.items():
        path = os.path.join(OUT, f"banner-{key}.svg")
        with open(path, "w") as fh:
            fh.write(menu_svg(key, inner))
    for name, fn in SCENES.items():
        with open(os.path.join(OUT, name + ".svg"), "w") as fh:
            fh.write(fn())


def rasterize(only=None):
    from PIL import Image
    chrome = shutil.which("google-chrome") or shutil.which("google-chrome-stable")
    if not chrome:
        raise SystemExit("chrome not found")
    for name in sorted(os.listdir(OUT)):
        if not name.endswith(".svg"): continue
        if only and name[:-4] not in only: continue
        svg = os.path.join(OUT, name)
        png = os.path.join(OUT, name[:-4] + ".png")
        raw = svg.replace(".svg", ".raw.png")
        html = os.path.join(tempfile.gettempdir(), name + ".html")
        body = open(svg).read()
        w, h = (640, 440) if name.startswith("banner-") else (640, 360)
        with open(html, "w") as fh:
            fh.write(f'<!doctype html><html><head><meta charset="utf-8"><style>html,body{{margin:0;background:#0B0D10}}svg{{display:block;width:{w}px;height:{h}px}}</style></head><body>{body}</body></html>')
        ud = tempfile.mkdtemp(prefix="engr-")
        cmd = [chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
               f"--user-data-dir={ud}", "--virtual-time-budget=2500", f"--window-size={w},{h}",
               f"--screenshot={raw}", "file://" + html]
        try:
            subprocess.run(cmd, timeout=12, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            subprocess.run(["pkill", "-f", ud], check=False)
        if not os.path.exists(raw) or os.path.getsize(raw) < 1000:
            raise SystemExit(f"chrome did not write {raw}")
        im = Image.open(raw).convert("RGB")
        im = im.crop((0, 0, w, h)) if im.size[0] >= w and im.size[1] >= h else im.resize((w, h))
        # palette keeps the engraving (black, ivory, one accent) small
        for colors, scale in ((32, 1.0), (24, 1.0), (16, 1.0), (24, 0.8), (16, 0.72)):
            pic = im if scale == 1 else im.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
            q = pic.quantize(colors=colors, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
            q.save(png, optimize=True)
            if os.path.getsize(png) <= 60_000:
                break
        os.remove(raw)
        print(f"{name[:-4]}.png {os.path.getsize(png)}")


if __name__ == "__main__":
    import sys
    write_svgs()
    rasterize(set(sys.argv[1:]) or None)
