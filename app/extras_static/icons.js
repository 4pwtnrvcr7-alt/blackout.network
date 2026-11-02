/* BLACKOUT.NETWORK emoji -> SVG icons (Nov 1 2026, Matt's rule: no emojis on the site, SVG icons only).
   Runs synchronously at the end of <body> (so the first paint already has icons) and then watches for content the pages render later.
   Emoji in text become small inline SVG line icons (24px grid, 2px stroke, currentColor: the same style as the site's other icons);
   emoji with no matching icon (faces, flags, rare symbols) are dropped. Inside <option>, title/aria-label/placeholder/alt and the
   document title (where SVG can't go) emoji are simply removed. Plain controls/typography are kept: arrows, check/cross marks, stars,
   play/pause glyphs. Nothing is sent anywhere. */
(function () {
  "use strict";
  if (window.__bnIcons) return; window.__bnIcons = 1;
  var P = {
    globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.8 2.6 4.2 5.6 4.2 9s-1.4 6.4-4.2 9c-2.8-2.6-4.2-5.6-4.2-9S9.2 5.6 12 3z"/>',
    clock: '<circle cx="12" cy="13" r="8"/><path d="M12 9v4l2.5 2M9.5 2.5h5"/>',
    cal: '<rect x="3.5" y="5" width="17" height="15.5" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
    lock: '<rect x="5" y="11" width="14" height="9.5" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    antenna: '<path d="M12 12v9M8.5 21h7"/><circle cx="12" cy="10" r="2"/><path d="M7.8 5.8a6 6 0 0 0 0 8.4M16.2 5.8a6 6 0 0 1 0 8.4M5 3a10 10 0 0 0 0 14M19 3a10 10 0 0 1 0 14"/>',
    radio: '<rect x="3" y="8" width="18" height="12" rx="2"/><path d="M7 8l9-5"/><circle cx="15.5" cy="14" r="3"/><path d="M6.5 12.5h3M6.5 16h3"/>',
    mic: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M8.5 21h7"/>',
    sat: '<path d="M13 7 9 3 5 7l4 4M17 11l4 4-4 4-4-4M9.5 10.5l4 4"/><path d="M6 16a4 4 0 0 0 2 2M3.5 16.5a7 7 0 0 0 4 4"/>',
    eye: '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/>',
    fire: '<path d="M12 21c-3.9 0-6.5-2.6-6.5-6.2 0-3.4 2.4-5.4 3.6-8.3.9 1.6 1.7 2.5 2.9 3 .2-2.9 1.3-5.1 3.3-6.5-.3 3.1 3.2 6.1 3.2 11.4C18.5 18.4 15.9 21 12 21z"/>',
    burst: '<path d="M12 2.5l1.8 5 5-2-2 5 5 1.5-5 1.8 2 5-5-2-1.8 5-1.8-5-5 2 2-5-5-1.8 5-1.5-2-5 5 2z"/>',
    bolt: '<path d="M13 2.5 4.5 13.5H11L10 21.5l8.5-11H12z"/>',
    battery: '<rect x="2.5" y="7" width="17" height="10" rx="2"/><path d="M21.5 10.5v3M6 10v4M9.5 10v4"/>',
    plug: '<path d="M9 2.5v5M15 2.5v5M6.5 7.5h11V11a5.5 5.5 0 0 1-11 0zM12 16.5v5"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8"/>',
    cloud: '<path d="M7 18.5h10.5a4 4 0 0 0 .4-8 6 6 0 0 0-11.6 1.3A3.4 3.4 0 0 0 7 18.5z"/>',
    rain: '<path d="M7 14.5h10.5a4 4 0 0 0 .4-8 6 6 0 0 0-11.6 1.3A3.4 3.4 0 0 0 7 14.5z"/><path d="M8.5 17.5l-1 3M12.5 17.5l-1 3M16.5 17.5l-1 3"/>',
    storm: '<path d="M7 14.5h10.5a4 4 0 0 0 .4-8 6 6 0 0 0-11.6 1.3A3.4 3.4 0 0 0 7 14.5z"/><path d="M13 14.5l-2.5 3.5h3l-2 3.5"/>',
    wind: '<path d="M3 9h11a3 3 0 1 0-3-3M3 13h15a3 3 0 1 1-3 3M3 17h7"/>',
    snow: '<path d="M12 2.5v19M3.8 7.2l16.4 9.6M3.8 16.8l16.4-9.6M9.5 4.5 12 6.5l2.5-2M9.5 19.5 12 17.5l2.5 2"/>',
    drop: '<path d="M12 3c3.2 4 6 7.2 6 10.6A6 6 0 0 1 6 13.6C6 10.2 8.8 7 12 3z"/>',
    wave: '<path d="M2.5 10c2.4 0 2.4-2 4.8-2s2.4 2 4.7 2 2.4-2 4.8-2 2.3 2 4.7 2M2.5 16c2.4 0 2.4-2 4.8-2s2.4 2 4.7 2 2.4-2 4.8-2 2.3 2 4.7 2"/>',
    pin: '<path d="M12 21.5s-6.5-6-6.5-11a6.5 6.5 0 0 1 13 0c0 5-6.5 11-6.5 11z"/><circle cx="12" cy="10.5" r="2.4"/>',
    book: '<path d="M4 4.5h6a2 2 0 0 1 2 2V20a1.8 1.8 0 0 0-1.8-1.8H4zM20 4.5h-6a2 2 0 0 0-2 2V20a1.8 1.8 0 0 1 1.8-1.8H20z"/>',
    doc: '<path d="M6 2.5h8l4.5 4.5v14.5H6z"/><path d="M14 2.5V7h4.5M9 12h6M9 15.5h6"/>',
    news: '<rect x="3" y="4.5" width="15" height="15" rx="1.5"/><path d="M18 8.5h3v9.5a1.5 1.5 0 0 1-3 0M6.5 8.5h8M6.5 12h8M6.5 15.5h5"/>',
    folder: '<path d="M3 6.5a1.5 1.5 0 0 1 1.5-1.5h5l2 2.5h8a1.5 1.5 0 0 1 1.5 1.5v9a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 18z"/>',
    mail: '<rect x="3" y="5.5" width="18" height="13" rx="2"/><path d="m3.5 7 8.5 6.5L20.5 7"/>',
    pack: '<path d="M8 6.5V5a4 4 0 0 1 8 0v1.5"/><rect x="5" y="6.5" width="14" height="14.5" rx="3"/><path d="M9 13.5h6v3.5H9z"/>',
    cart: '<path d="M3 4h2.5l2.2 10.5h10l2-7.5H7"/><circle cx="9" cy="19" r="1.4"/><circle cx="17" cy="19" r="1.4"/>',
    tools: '<path d="M14.5 6.5a4 4 0 0 0 5 5l-8 8a2.1 2.1 0 0 1-3-3l8-8a4 4 0 0 0-2-2z"/><path d="M3 7l3-3 3 3-3 3z"/>',
    map: '<path d="M3 6.5 9 4l6 2.5L21 4v13.5L15 20l-6-2.5L3 20z"/><path d="M9 4v13.5M15 6.5V20"/>',
    compass: '<circle cx="12" cy="12" r="9"/><path d="m15.5 8.5-2 5-5 2 2-5z"/>',
    gov: '<path d="M3 9.5 12 4l9 5.5M5 10v8M9.5 10v8M14.5 10v8M19 10v8M3 20.5h18"/>',
    home: '<path d="M3.5 11 12 4l8.5 7M6 9.5v10.5h12V9.5"/><path d="M10 20v-5h4v5"/>',
    hosp: '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M12 8v8M8 12h8"/>',
    med: '<path d="M10.5 3.5h3v6h6v3h-6v6h-3v-6h-6v-3h6z"/>',
    pill: '<rect x="2.8" y="8.2" width="18.4" height="7.6" rx="3.8" transform="rotate(-45 12 12)"/><path d="m8.8 8.8 6.4 6.4"/>',
    bandage: '<rect x="2.5" y="8" width="19" height="8" rx="4" transform="rotate(-45 12 12)"/><path d="M10.5 10.5h.01M13.5 13.5h.01M10.5 13.5h.01M13.5 10.5h.01"/>',
    flask: '<path d="M9.5 3h5M10 3v6L4.5 19a1.5 1.5 0 0 0 1.3 2h12.4a1.5 1.5 0 0 0 1.3-2L14 9V3"/><path d="M7.3 15h9.4"/>',
    virus: '<circle cx="12" cy="12" r="5"/><path d="M12 2.5V7M12 17v4.5M2.5 12H7M17 12h4.5M5.3 5.3l3.2 3.2M15.5 15.5l3.2 3.2M5.3 18.7l3.2-3.2M15.5 8.5l3.2-3.2"/>',
    siren: '<path d="M6.5 17v-5a5.5 5.5 0 0 1 11 0v5M4.5 17h15v3.5h-15zM12 3V1.5M4 6 3 5M20 6l1-1"/>',
    alert: '<path d="M12 3.5 2.5 20h19z"/><path d="M12 10v4.5M12 17.5h.01"/>',
    flag: '<path d="M5 21V4M5 4h12l-2.5 4L17 12H5"/>',
    dot: '<circle cx="12" cy="12" r="5"/>',
    mega: '<path d="M3.5 10v4h3l9 5V5l-9 5zM18.5 9.5a3.5 3.5 0 0 1 0 5"/>',
    tent: '<path d="M12 4 2.5 20h19zM12 4v16M8.5 20l3.5-6 3.5 6"/>',
    mountain: '<path d="m2.5 20 7-12 4 6.5 2.5-3.5 5.5 9z"/>',
    thread: '<circle cx="12" cy="12" r="8"/><path d="M6 8.5c4 1 8 1 12 0M5 13c4.5 1.5 9.5 1.5 14 0M7.5 17.5c3 1 6 1 9 0"/>',
    blade: '<path d="M4 20 17 7l3-3-1 4L7 21zM14 10l1.5 1.5"/>',
    torch: '<path d="M8 3h8l-1.5 6h-5zM9.5 9h5V21h-5zM12 13v2"/>',
    ext: '<rect x="7.5" y="7" width="9" height="14" rx="3"/><path d="M12 7V4.5M9 4.5h6M16.5 9.5l3-1.5"/>',
    chart: '<path d="M3.5 3.5v17h17"/><path d="m7 15 4-4.5 3 3L20 7"/>',
    down: '<path d="M3.5 3.5v17h17"/><path d="m7 8 4 4.5 3-3L20 16"/>',
    bars: '<path d="M4 20.5h16M7 17v-5M12 17V6M17 17v-8"/>',
    ruler: '<rect x="2.5" y="8" width="19" height="8" rx="1.5"/><path d="M6.5 8v3M10 8v4M13.5 8v3M17 8v4"/>',
    calc: '<rect x="5" y="2.5" width="14" height="19" rx="2"/><path d="M8 6.5h8M8.5 11h.01M12 11h.01M15.5 11h.01M8.5 14.5h.01M12 14.5h.01M15.5 14.5h.01M8.5 18h.01M12 18h.01M15.5 18h.01"/>',
    ballot: '<path d="M4 12.5h16v8H4zM8 12.5V4h8v8.5"/><path d="m9.8 8 1.6 1.6L14.4 6.5"/>',
    therm: '<path d="M14 14.8V4.5a2 2 0 0 0-4 0v10.3a4 4 0 1 0 4 0z"/><path d="M12 9v7"/>',
    robot: '<rect x="4" y="8" width="16" height="12" rx="3"/><path d="M12 4.5V8M9 13h.01M15 13h.01M9 16.5h6M2 13v3M22 13v3"/><circle cx="12" cy="3.5" r="1"/>',
    shield: '<path d="M12 3 4.5 6v6c0 4.5 3.2 7.8 7.5 9 4.3-1.2 7.5-4.5 7.5-9V6z"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4.5 21a7.5 7.5 0 0 1 15 0"/>',
    users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.8a3.5 3.5 0 0 1 0 6.4M18 14a6.5 6.5 0 0 1 3.5 6"/>',
    hands: '<path d="m11 17 2 2a1.4 1.4 0 0 0 2-2l-3-3M14 14l2.5 2.5a1.4 1.4 0 0 0 2-2L13 9l-3 2.5a1.4 1.4 0 0 1-2-2L11.5 6h3L21 12M3 12l5-5.5"/>',
    scale: '<path d="M12 3.5v17M7 20.5h10M4.5 7.5h15M7 7.5 4 14a3 3 0 0 0 6 0zM17 7.5 14 14a3 3 0 0 0 6 0z"/>',
    phone: '<path d="M5 3.5h4l2 5-2.5 1.5a11 11 0 0 0 5.5 5.5l1.5-2.5 5 2v4a2 2 0 0 1-2 2A17 17 0 0 1 3 5.5a2 2 0 0 1 2-2z"/>',
    food: '<path d="M4 10.5h16a8 8 0 0 1-16 0zM9 4c-1 1 1 2 0 3.5M13 4c-1 1 1 2 0 3.5"/>',
    can: '<path d="M6 5.5h12v14a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 6 19.5zM6 5.5a6 1.5 0 0 0 12 0M6 10h12"/>',
    cup: '<path d="M4 8.5h12v6a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5zM16 10h1.5a2.5 2.5 0 0 1 0 5H16M8 2.5c-1 1 1 2 0 3.5M12 2.5c-1 1 1 2 0 3.5"/>',
    fruit: '<circle cx="12" cy="14" r="7"/><path d="M12 7c0-2 1-3.5 3-4.5"/>',
    leaf: '<path d="M5 19C5 10 10 4.5 20 4c-.5 10-6 15-15 15z"/><path d="M5 19 14 10"/>',
    tree: '<path d="M12 2.5 5 12h4l-3.5 5h13L15 12h4zM12 17v4.5"/>',
    flower: '<circle cx="12" cy="9" r="2.5"/><path d="M12 6.5a2.5 2.5 0 1 1 2.4 3.2M12 6.5a2.5 2.5 0 1 0-2.4 3.2M14.4 9.7a2.5 2.5 0 1 1-1.2 3.6M9.6 9.7a2.5 2.5 0 1 0 1.2 3.6M12 13v8.5M12 18c-2.5 0-4-1.5-4-3.5"/>',
    rocket: '<path d="M12 2.5c3.5 2.5 5 6.5 4.5 11.5h-9C7 9 8.5 5 12 2.5z"/><path d="M7.5 14 5 17.5h4M16.5 14l2.5 3.5h-4M10.5 17.5 12 21.5l1.5-4"/><circle cx="12" cy="9" r="1.6"/>',
    target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.5"/>',
    vol: '<path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4zM15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11"/>',
    mute: '<path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4zM16 9.5l5 5M21 9.5l-5 5"/>',
    head: '<path d="M4 15v-3a8 8 0 0 1 16 0v3"/><rect x="3.5" y="14" width="4" height="6" rx="1.5"/><rect x="16.5" y="14" width="4" height="6" rx="1.5"/>',
    star: '<path d="m12 3 2.7 5.6 6.1.8-4.4 4.3 1 6.1L12 17l-5.4 2.8 1-6.1-4.4-4.3 6.1-.8z"/>',
    skull: '<path d="M12 2.5a8 8 0 0 0-8 8c0 2.6 1.2 4.3 3 5.4V20h10v-4.1c1.8-1.1 3-2.8 3-5.4a8 8 0 0 0-8-8z"/><circle cx="9" cy="11" r="1.6"/><circle cx="15" cy="11" r="1.6"/><path d="M10.5 20v-2.5M13.5 20v-2.5"/>',
    soap: '<rect x="3.5" y="9" width="17" height="11" rx="3"/><circle cx="9" cy="5" r="2"/><circle cx="15.5" cy="4" r="1.3"/>',
    paw: '<circle cx="6.5" cy="10" r="1.8"/><circle cx="10" cy="6" r="1.8"/><circle cx="14" cy="6" r="1.8"/><circle cx="17.5" cy="10" r="1.8"/><path d="M12 11.5c-3 0-5.5 4-5.5 6.5 0 1.8 1.5 2.5 3 2 1.2-.4 1.8-.8 2.5-.8s1.3.4 2.5.8c1.5.5 3-.2 3-2 0-2.5-2.5-6.5-5.5-6.5z"/>',
    bird: '<path d="M3 13c3 0 5-1 7-4 1.5-2.5 3.5-4 6-4 2 0 3 1 4 2l-2 1c0 6-4.5 11-11 11 1-1.5 1.5-3 1-4.5C6.5 14 4.5 13.5 3 13z"/>',
    tv: '<rect x="2.5" y="6" width="19" height="13" rx="2"/><path d="m8 2.5 4 3.5 4-3.5"/>',
    camera: '<path d="M3 8.5a1.5 1.5 0 0 1 1.5-1.5h3l1.5-2.5h6L16.5 7h3A1.5 1.5 0 0 1 21 8.5v10a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 18.5z"/><circle cx="12" cy="13" r="3.5"/>',
    plane: '<path d="M21 12.5 13.5 9V4a1.5 1.5 0 0 0-3 0v5L3 12.5v2l7.5-2v4.5L8 19v1.5l4-1 4 1V19l-2.5-2v-4.5l7.5 2z"/>',
    search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m15.5 15.5 5 5"/>',
    print: '<path d="M7 9V3.5h10V9M7 17H4.5V9h15v8H17"/><rect x="7" y="14" width="10" height="6.5"/>',
    chat: '<path d="M4 5.5h16v10.5H10l-4.5 3.5V16H4z"/>',
    heart: '<path d="M12 20s-8-4.8-8-10.5A4.5 4.5 0 0 1 12 7a4.5 4.5 0 0 1 8 2.5C20 15.2 12 20 12 20z"/>',
    moon: '<path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5z"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5h.01"/>',
    ok: '<circle cx="12" cy="12" r="9"/><path d="m8 12.3 2.8 2.8 5.4-5.6"/>',
    no: '<circle cx="12" cy="12" r="9"/><path d="m5.6 5.6 12.8 12.8"/>',
    link: '<path d="M10 14a4.5 4.5 0 0 0 6.4 0l3-3a4.5 4.5 0 0 0-6.4-6.4l-1 1M14 10a4.5 4.5 0 0 0-6.4 0l-3 3a4.5 4.5 0 0 0 6.4 6.4l1-1"/>',
    refresh: '<path d="M20 12a8 8 0 1 1-2.3-5.7M20.5 3.5v5h-5"/>',
    car: '<path d="M4 16.5v-4l2-5.5h12l2 5.5v4zM4 12.5h16M4 16.5V19M20 16.5V19"/><circle cx="7.5" cy="14.5" r=".8"/><circle cx="16.5" cy="14.5" r=".8"/>',
    light: '<rect x="8" y="2.5" width="8" height="19" rx="3"/><circle cx="12" cy="7" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="12" cy="17" r="1.5"/>',
    fuel: '<path d="M4.5 21V4.5A1.5 1.5 0 0 1 6 3h7a1.5 1.5 0 0 1 1.5 1.5V21M3 21h13M4.5 10h10M14.5 8l3 2v7.5a1.5 1.5 0 0 0 3 0V8l-3-3"/>',
    bed: '<path d="M3 18V6M3 13.5h18V18M21 13.5V11a2.5 2.5 0 0 0-2.5-2.5H11v5"/><circle cx="7" cy="10.5" r="1.8"/>',
    money: '<rect x="2.5" y="6" width="19" height="12" rx="1.5"/><circle cx="12" cy="12" r="2.8"/><path d="M6 9.5v5M18 9.5v5"/>',
    grad: '<path d="m2.5 9 9.5-5 9.5 5-9.5 5zM6.5 11v5c3 2.5 8 2.5 11 0v-5M21.5 9v6"/>',
    game: '<rect x="2.5" y="7.5" width="19" height="10" rx="5"/><path d="M7.5 10.5v4M5.5 12.5h4M15.5 11.5h.01M17.5 13.5h.01"/>',
    bone: '<path d="M8 8 16 16M6.5 9.5a2 2 0 1 1-1-3.5 2 2 0 1 1 3.5-1M17.5 14.5a2 2 0 1 1 1 3.5 2 2 0 1 1-3.5 1"/>',
    lungs: '<path d="M12 3.5V11M12 11c0 2-2.5 2.5-2.5 2.5M12 11c0 2 2.5 2.5 2.5 2.5M8.5 7C5.5 7 3.5 12 3.5 17c0 2 1.5 3 3 3 2.5 0 3-1.5 3-3.5V9a2 2 0 0 0-1-2zM15.5 7c3 0 5 5 5 10 0 2-1.5 3-3 3-2.5 0-3-1.5-3-3.5V9a2 2 0 0 1 1-2z"/>',
    brain: '<path d="M12 4.5a3 3 0 0 0-5.5 1A3.5 3.5 0 0 0 4 10a3.5 3.5 0 0 0 1 6 3.5 3.5 0 0 0 7 2zM12 4.5a3 3 0 0 1 5.5 1A3.5 3.5 0 0 1 20 10a3.5 3.5 0 0 1-1 6 3.5 3.5 0 0 1-7 2"/>',
    spark: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6"/>',
    knot: '<path d="M4 8c4 0 6 8 10 8s6-8 6-8M4 16c4 0 6-8 10-8s6 8 6 8"/>',
    hook: '<path d="M12 2.5v11a4 4 0 0 1-8 0v-2l2 2"/><circle cx="12" cy="2.5" r=".8"/>',
    broom: '<path d="M18 3 11 10M7.5 10.5l6 6-2 4.5c-3 0-7-2.5-8.5-6.5z"/><path d="M8 15.5 6 18"/>',
    mag: '<path d="M6 3.5v7a6 6 0 0 0 12 0v-7h-4v7a2 2 0 0 1-4 0v-7zM6 7h4M14 7h4"/>',
    hand: '<path d="M8 13V5.5a1.5 1.5 0 0 1 3 0V11M11 10.5V4a1.5 1.5 0 0 1 3 0v6.5M14 10.5V5.5a1.5 1.5 0 0 1 3 0V14a7 7 0 0 1-7 7 6 6 0 0 1-5-3l-2.5-4.5a1.5 1.5 0 0 1 2.6-1.5L8 15"/>',
    ribbon: '<path d="M12 3.5a3.5 3.5 0 0 0-3.5 3.5c0 3 3.5 6.5 3.5 6.5S15.5 10 15.5 7A3.5 3.5 0 0 0 12 3.5zM10 12 6 20.5l2.5-1 1.5 2 3-6.5M14 12l4 8.5-2.5-1-1.5 2-3-6.5"/>',
    pager: '<rect x="3" y="6" width="18" height="12" rx="2"/><path d="M6.5 9.5h11v3h-11zM7 15h.01M10 15h.01"/>',
    clean: '<path d="M7 21h10M8.5 21l1-9h5l1 9M10 12V7h4v5M14 4.5h-4"/>',
    gloves: '<path d="M7 21v-4L4.5 12a1.5 1.5 0 0 1 2.7-1.3L8.5 13V5a1.5 1.5 0 0 1 3 0v6M11.5 10.5V4a1.5 1.5 0 0 1 3 0v6.5M14.5 10.5V6a1.5 1.5 0 0 1 3 0v8a7 7 0 0 1-2 5V21z"/>',
    coat: '<path d="M8.5 3.5 12 6l3.5-2.5L20 6v15h-4v-8M8 13v8H4V6zM12 6v15"/>',
    baby: '<path d="M9 3.5h6M10 3.5v3h4v-3M8.5 6.5h7l1 3v10a1.5 1.5 0 0 1-1.5 1.5h-6A1.5 1.5 0 0 1 7.5 19.5v-10z"/>',
    shower: '<path d="M4 21V7a3.5 3.5 0 0 1 7 0M8 7h6a1 1 0 0 1 0 2H8zM9.5 12v.01M12 12.5v.01M14.5 12v.01M10 15.5v.01M13 15.5v.01M11.5 18.5v.01"/>',
    tub: '<path d="M3 12h18v3a5 5 0 0 1-5 5H8a5 5 0 0 1-5-5zM6 12V5.5a2 2 0 0 1 4 0M7 20l-1 1.5M17 20l1 1.5"/>',
    rope: '<path d="M4 20c4-6 12-2 16-8M6 16c2-4 8-4 10-8M8 20c1-3 5-3 6-6"/>',
    log: '<ellipse cx="6" cy="12" rx="3" ry="5"/><path d="M6 7h13a3 5 0 0 1 0 10H6"/><ellipse cx="6" cy="12" rx="1" ry="2"/>',
    trap: '<rect x="3" y="12" width="18" height="7" rx="1.5"/><path d="M6 12V8a6 6 0 0 1 12 0v4"/>',
    worm: '<path d="M3 15c2-4 4-4 6 0s4 4 6 0 4-4 6 0"/>',
    magnet2: '<path d="M10 3 6 7l2 2M17 10l4 4-2 2M8.5 9.5 14.5 15.5"/>',
    minus: '<path d="M5 12h14"/>', plus: '<path d="M12 5v14M5 12h14"/>', arrow: '<path d="M4 12h15M13 6l6 6-6 6"/>',
    play: '<path d="M8 5.5v13l10-6.5z" class="bn-eif"/>', back: '<path d="M16 5.5v13L6 12z" class="bn-eif"/>',
    pause: '<path d="M8.5 5.5v13M15.5 5.5v13"/>', stop: '<rect x="6.5" y="6.5" width="11" height="11" rx="1.5"/>',
    next: '<path d="M6 5.5v13l8.5-6.5zM18 5.5v13"/>', prev: '<path d="M18 5.5v13L9.5 12zM6 5.5v13"/>', rec: '<circle cx="12" cy="12" r="5.5" class="bn-eif"/>',
    sq: '<rect x="5" y="5" width="14" height="14" rx="2"/>'
  };
  var M = {};
  function add(k, list) { list.split(" ").forEach(function (e) { if (e) M[e] = k; }); }
  add("globe", "🌐 🌍 🌎 🌏"); add("clock", "⏱ 🕒 ⏰ ⌚ ⏳ ⌛"); add("cal", "📅 📆 🗓"); add("lock", "🔒 🔐 🔏");
  add("antenna", "📡"); add("radio", "📻"); add("mic", "🎙 🎤"); add("sat", "🛰"); add("eye", "👁 👀");
  add("fire", "🔥 ♨"); add("burst", "💥 🧨"); add("bolt", "⚡"); add("battery", "🔋"); add("plug", "🔌");
  add("sun", "☀ 🌅 🌤 🌞"); add("cloud", "☁ ⛅ 🌫 🌥"); add("rain", "🌦 🌧 ☂ ☔"); add("storm", "⛈ 🌩"); add("wind", "💨 🌬 🌪 🌀");
  add("snow", "❄ 🌨 🧊 ☃"); add("drop", "💧 🚰 🥤 🩸"); add("wave", "🌊"); add("pin", "📍 📌");
  add("book", "📚 📖 📕 📗 📘"); add("doc", "📜 📑 📄 📋 📇 📃"); add("news", "📰 🗞"); add("folder", "🗂 📁 📂 🗄");
  add("mail", "✉ 📧 📨 📩"); add("pack", "🎒"); add("cart", "🛒"); add("tools", "🧰 🔨 🔧 🛠 ⚒"); add("map", "🗺"); add("compass", "🧭");
  add("gov", "🏛"); add("home", "🏠 🏘 🏡"); add("hosp", "🏥 🚑"); add("med", "⛑ ⚕ 🩺"); add("pill", "💊"); add("bandage", "🩹");
  add("flask", "🧪 🔬"); add("virus", "🦠"); add("siren", "🚨 🚓 🚒"); add("alert", "⚠"); add("flag", "🚩"); add("dot", "🔴 🟠 🟦 🟢 🟡 🔵 ⚫ ⚪");
  add("mega", "📣 📢 📯"); add("tent", "⛺ 🏕"); add("mountain", "⛰ 🏞 🌋 🏔"); add("thread", "🧵 🧶"); add("blade", "🔪 🗡 🏹");
  add("torch", "🔦"); add("ext", "🧯"); add("chart", "📈 💹"); add("down", "📉"); add("bars", "📊"); add("ruler", "📐 📏"); add("calc", "🧮 🔢");
  add("ballot", "🗳"); add("therm", "🌡"); add("robot", "🤖"); add("game", "👾 🎮"); add("shield", "🛡 🦺"); add("user", "👤 🧍 👩 👨 🧑");
  add("users", "👥"); add("hands", "🤝"); add("scale", "⚖"); add("phone", "📞 ☎ 📱 📵"); add("food", "🍲 🍳 🥣"); add("can", "🥫 🧂");
  add("cup", "☕ 🍵"); add("fruit", "🍏 🍎 🫐 🌶"); add("leaf", "🌱 🌿 🍂 🍃 🌾 🍁 🪴"); add("tree", "🌳 🌴 🌲"); add("flower", "🌼 🌻 🌸 🌺 🌷");
  add("rocket", "🚀"); add("target", "🎯"); add("vol", "🔉 🔊 🔈"); add("mute", "🔇"); add("head", "🎧"); add("star", "⭐ ✨ 🌟");
  add("skull", "☠ 💀"); add("soap", "🧼 🧴 🧻"); add("paw", "🐾 🐝 🐜"); add("bird", "🕊"); add("tv", "📺"); add("camera", "📸 📷");
  add("plane", "✈ 🛩"); add("search", "🔍 🔎"); add("print", "🖨"); add("chat", "💬 🗨"); add("heart", "❤ 💜 💙 🧡 💚");
  add("moon", "🌙 🌗 🌘 🌖"); add("info", "ℹ"); add("ok", "✅ ☑"); add("no", "❌ 🚫 🚷 ⛔"); add("link", "🔗"); add("refresh", "🔁 🔄 🔀");
  add("car", "🚗 🚙"); add("light", "🚦 🚥"); add("fuel", "⛽"); add("bed", "🛏 🛌"); add("money", "💵 💰 💲"); add("grad", "🎓");
  add("bone", "🦴"); add("lungs", "🫁"); add("brain", "🧠"); add("knot", "🪢"); add("hook", "🪝 🎣"); add("broom", "🧹");
  add("mag", "🧲"); add("hand", "✋ 🖐"); add("ribbon", "🎗"); add("pager", "📟"); add("gloves", "🧤"); add("coat", "🧥"); add("baby", "🍼 👶");
  add("shower", "🚿"); add("tub", "🛁"); add("rope", "🪢"); add("log", "🪵"); add("trap", "🪤"); add("worm", "🪱"); add("clean", "🪞"); add("minus", "➖"); add("plus", "➕"); add("arrow", "➡"); add("play", "▶ ⏵"); add("back", "◀ ⏴"); add("pause", "⏸"); add("stop", "⏹"); add("next", "⏭ ⏩"); add("prev", "⏮ ⏪"); add("rec", "⏺"); add("play", "⏯");
  // emoji-presentation pictographs (and regional-indicator flags); arrows, ✓ ✗ ✕ ★ ☆ ☰ ❚ ⏸ ⏭ ▶ ◀ etc. are not matched
  var RE = /(?:[\uD83C][\uDDE6-\uDDFF]){2}|(?:\uD83C[\uDF00-\uDFFF]|\uD83D[\uDC00-\uDEFF]|\uD83E[\uDD00-\uDEFF]|[\u2600-\u26FF]|[\u23E9-\u23EF\u23F4-\u23FA\u25B6\u25C0]|[\u2702\u2705\u2708-\u270D\u270F\u2712\u2714\u2716\u271D\u2721\u2728\u2733\u2734\u2744\u2747\u274C\u274E\u2753-\u2755\u2757\u2763\u2764\u2795-\u2797\u27A1\u27B0\u27BF\u2B50\u2B55\u231A\u231B\u23F0-\u23F3\u2139\u303D\u3297\u3299])(?:\uFE0F|\u200D(?:\uD83C[\uDF00-\uDFFF]|\uD83D[\uDC00-\uDEFF]|\uD83E[\uDD00-\uDEFF]|[\u2600-\u27BF])\uFE0F?|\uD83C[\uDFFB-\uDFFF])*/g;
  var KEEP = { "\u2605": 1, "\u2606": 1, "\u2610": 1, "\u2611": 0, "\u2630": 1, "\u2713": 1, "\u2714": 1, "\u2716": 1, "\u2717": 1, "\u2715": 1, "\u2B50": 0, "\u2668": 0 };
  var TEST = new RegExp(RE.source);
  function base(e) { return e.replace(/[\uFE0F\u200D]|\uD83C[\uDFFB-\uDFFF]/g, ""); }
  function keepIt(e) { var b = base(e); return KEEP[b] === 1 || (b.length === 1 && "\u2702\u270D\u270F\u2712\u271D\u2721\u2733\u2734\u2747\u2763\u303D\u3297\u3299\u2654\u2655\u2656\u2657\u2658\u2659\u265A\u265B\u265C\u265D\u265E\u265F\u2660\u2663\u2665\u2666".indexOf(b) >= 0 && !M[b]); }
  function key(e) { var b = base(e); if (M[b]) return M[b]; var f = b.match(/^(?:[\uD800-\uDBFF][\uDC00-\uDFFF]|.)/); return f && M[f[0]] || null; }
  function svg(k) {
    var s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    s.setAttribute("class", "bn-ei bn-ei-" + k); s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("aria-hidden", "true"); s.setAttribute("focusable", "false");
    s.innerHTML = P[k]; return s;
  }
  var SKIP = { SCRIPT: 1, STYLE: 1, TEXTAREA: 1, NOSCRIPT: 1, TEMPLATE: 1, svg: 1, SVG: 1, CANVAS: 1, INPUT: 1, IFRAME: 1 };
  function fixText(n) {
    var t = n.nodeValue; if (!t || !TEST.test(t)) return;
    var p = n.parentNode; if (!p || SKIP[p.nodeName] || (p.closest && p.closest("svg,[contenteditable=''],[contenteditable=true],.bn-noicons"))) return;
    if (p.nodeName === "OPTION" || p.nodeName === "TITLE") { n.nodeValue = t.replace(RE, function (e) { return keepIt(e) ? e : ""; }).replace(/^\s+/, "").replace(/\s{2,}/g, " "); return; }
    var frag = document.createDocumentFragment(), last = 0, m, changed = false; RE.lastIndex = 0;
    while ((m = RE.exec(t))) {
      if (keepIt(m[0])) continue;
      changed = true; var before = t.slice(last, m.index), k = key(m[0]), after = m.index + m[0].length;
      if (before) frag.appendChild(document.createTextNode(before));
      if (k) frag.appendChild(svg(k));
      else if (t.charAt(after) === " " && (!before || /\s$/.test(before))) after++;   // dropped emoji: no double space left behind
      last = after; RE.lastIndex = after;
    }
    if (!changed) return;
    if (last < t.length) frag.appendChild(document.createTextNode(t.slice(last)));
    p.replaceChild(frag, n);
  }
  var ATTRS = ["title", "aria-label", "placeholder", "alt", "data-tip"];
  function fixAttrs(el) {
    for (var i = 0; i < ATTRS.length; i++) { var v = el.getAttribute && el.getAttribute(ATTRS[i]); if (v && TEST.test(v)) { var nv = v.replace(RE, function (e) { return keepIt(e) ? e : ""; }).replace(/^\s+/, "").replace(/\s{2,}/g, " "); if (nv !== v) el.setAttribute(ATTRS[i], nv); } }
    if (el.nodeName === "INPUT" && (el.type === "button" || el.type === "submit") && TEST.test(el.value || "")) el.value = el.value.replace(RE, "").trim();
  }
  function walk(root) {
    if (!root) return;
    if (root.nodeType === 3) return fixText(root);
    if (root.nodeType !== 1 && root.nodeType !== 11) return;
    if (root.nodeType === 1) { if (SKIP[root.nodeName]) return; fixAttrs(root); }
    var w = document.createTreeWalker(root, 1 | 4, null), n, texts = [];
    while ((n = w.nextNode())) { if (n.nodeType === 3) { if (TEST.test(n.nodeValue)) texts.push(n); } else fixAttrs(n); }
    for (var i = 0; i < texts.length; i++) fixText(texts[i]);
  }
  function fixTitle() { if (TEST.test(document.title)) document.title = document.title.replace(RE, function (e) { return keepIt(e) ? e : ""; }).replace(/^\s+/, "").replace(/\s{2,}/g, " "); }
  var st = document.createElement("style");
  st.textContent = ".bn-ei{display:inline-block;width:1.05em;height:1.05em;vertical-align:-.16em;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;flex:none}" +
    ".bn-ei .bn-eif{fill:currentColor;stroke:none}";
  (document.head || document.documentElement).appendChild(st);
  window.bnIconize = walk;
  walk(document.body); fixTitle();
  var q = [], sched = false;
  function flush() { sched = false; var a = q; q = []; for (var i = 0; i < a.length; i++) if (a[i].isConnected !== false) walk(a[i]); fixTitle(); }
  try {
    new MutationObserver(function (ms) {
      for (var i = 0; i < ms.length; i++) {
        var m = ms[i];
        if (m.type === "characterData") q.push(m.target);
        else if (m.type === "attributes") fixAttrs(m.target);
        else for (var j = 0; j < m.addedNodes.length; j++) q.push(m.addedNodes[j]);
      }
      if (q.length && !sched) { sched = true; (window.requestAnimationFrame || setTimeout)(flush); }
    }).observe(document.documentElement, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTRS });
  } catch (e) {}
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", function () { walk(document.body); fixTitle(); });
})();
