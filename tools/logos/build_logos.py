"""Builds app/netmap_static/logos.svg: one white mark per status card on The Grid (Matt, Nov 24 2026).
Brand marks: Simple Icons (CC0-1.0, https://simpleicons.org), path data copied unchanged and filled white.
Services Simple Icons does not carry get an original generic white icon for their type (never a made-up brand mark).
Run: npm pack simple-icons && tar xzf simple-icons-*.tgz && python3 tools/logos/build_logos.py package/icons"""
import os, re, sys, json
ICONS = sys.argv[1] if len(sys.argv) > 1 else "package/icons"
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "app", "netmap_static", "logos.svg")
BRAND = {"verizonfios": "verizon", "verizonwireless": "verizon", "googlefiber": "google", "gcp": "googlecloud", "workspace": "google",
         "cloudflare": "cloudflare", "akamai": "akamai", "linode": "akamai", "digitalocean": "digitalocean", "github": "github", "vercel": "vercel",
         "netlify": "netlify", "godaddy": "godaddy", "stripe": "stripe", "square": "square", "cashapp": "cashapp", "shopify": "shopify", "visa": "visa",
         "mastercard": "mastercard", "amex": "americanexpress", "discover": "discover", "paypal": "paypal", "venmo": "venmo", "zelle": "zelle",
         "applepay": "applepay", "googlepay": "googlepay", "brex": "brex", "discord": "discord", "zoom": "zoom", "reddit": "reddit", "proton": "proton",
         "ring": "ring", "tailscale": "tailscale", "1password": "1password", "klarna": "klarna", "wise": "wise", "coinbase": "coinbase",
         "wellsfargo": "wellsfargo", "chase": "chase", "bofa": "bankofamerica", "robinhood": "robinhood", "gusto": "gusto"}
# original generic icons (24x24, white strokes), one per service type
S = 'fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"'
GEN = {
 "bank": f'<path {S} d="M3 9.5 12 4l9 5.5M4.5 10v8M9 10v8M15 10v8M19.5 10v8M3 20h18"/>',
 "cards": f'<rect {S} x="2.5" y="5.5" width="19" height="13" rx="2"/><path {S} d="M2.5 10h19M6 15h4"/>',
 "isp": f'<circle {S} cx="12" cy="12" r="9"/><path {S} d="M3 12h18M12 3c3 3.2 3 14.8 0 18M12 3c-3 3.2-3 14.8 0 18"/>',
 "mobile": f'<rect {S} x="6.5" y="2.5" width="11" height="19" rx="2.2"/><path {S} d="M10.5 18.5h3"/>',
 "sat": f'<path {S} d="M5 13a7 7 0 0 0 7 7l-7-7zM5 13l7 7M9.5 14.5 13 11M15 3a6 6 0 0 1 6 6M15 6.5a2.5 2.5 0 0 1 2.5 2.5"/>',
 "cloud": f'<path {S} d="M7 18.5h10.5a4 4 0 0 0 .6-7.95A6 6 0 0 0 6.6 9.6 4.5 4.5 0 0 0 7 18.5z"/>',
 "pay": f'<rect {S} x="3" y="6" width="18" height="13" rx="2.2"/><path {S} d="M3 9.5h13.5M16 13.5h5v-3h-5a1.5 1.5 0 0 0 0 3z"/>',
 "rails": f'<path {S} d="M4 8h14l-3.5-3.5M20 16H6l3.5 3.5"/>',
 "apps": f'<path {S} d="M4 5.5h16v10.5H10l-4.5 3.5V16H4z"/>',
 "gov": f'<path {S} d="M12 3v2.5M7 10a5 5 0 0 1 10 0M5 10h14M6.5 10v8M10 10v8M14 10v8M17.5 10v8M3.5 20.5h17"/>',
}
def main():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "app"))
    import netmap
    syms, used = [], {}
    for n in netmap.NETS:
        nid, grp = n[0], n[2]
        slug = BRAND.get(nid)
        f = os.path.join(ICONS, f"{slug}.svg") if slug else None
        if f and os.path.exists(f):
            d = re.search(r'<path d="([^"]+)"', open(f).read()).group(1)
            syms.append(f'<symbol id="l-{nid}" viewBox="0 0 24 24"><path fill="#fff" d="{d}"/></symbol>'); used[nid] = "simple-icons:" + slug
        else:
            g = "isp" if grp == "isp" else grp if grp in GEN else "apps"
            syms.append(f'<symbol id="l-{nid}" viewBox="0 0 24 24">{GEN[g]}</symbol>'); used[nid] = "generic:" + g
    for g, body in GEN.items(): syms.append(f'<symbol id="l-g-{g}" viewBox="0 0 24 24">{body}</symbol>')
    svg = ('<svg xmlns="http://www.w3.org/2000/svg"><!-- The Grid status card marks. Brand marks: Simple Icons, CC0-1.0 (simpleicons.org); '
           'trademarks belong to their owners and identify the services only. Generic type icons: original, BLACKOUT.NETWORK. -->' + "".join(syms) + "</svg>")
    open(OUT, "w").write(svg)
    print(json.dumps(used, indent=0)); print(len(svg), "bytes")
main()
