"""Tips add-on: returns the PayPal.me handle from tips.json so the Tips tab can build https://www.paypal.me/<handle>/<amount>USD.
No payments are processed here; no accounts, no personal info, no Stripe/SDKs."""
import json, os, re
BASE = os.path.dirname(os.path.abspath(__file__))
def handle_get(path, qs):
    try: h = str(json.load(open(os.path.join(BASE, "tips.json"))).get("paypal_me", "")).strip()
    except Exception: h = ""
    ok = bool(re.fullmatch(r"[A-Za-z0-9]{1,40}", h))
    return 200, {"paypal_me": h if ok else "", "configured": ok}
