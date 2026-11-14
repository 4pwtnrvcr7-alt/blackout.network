#!/usr/bin/env python3
"""QA gate (TOPIC-CARDS-1): fail if any homepage topic card draws an empty day bar.

Usage: python3 qa/check_topic_cards.py [URL]   (default https://blackout.network/api/apple/dash)
Exit 0 = every card has a story on all 7 ET days; exit 1 = lists card -> empty days.
"""
import json, os, sys, urllib.request
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import topic_cards as TC

url = sys.argv[1] if len(sys.argv) > 1 else "https://blackout.network/api/apple/dash"
dash = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "bn-qa"}), timeout=60))
bad = TC.check_dash(dash)
for g, k in TC.TOPIC_CARDS:
    c = (dash.get(g) or {}).get(k) or {}
    row = " ".join(f"{d[0][5:]}:{d[1] + d[2]}" for d in c.get("days") or [])
    print(f"{'FAIL' if f'{g}/{k}' in bad else 'ok  '} {g}/{k:<8} {row}")
if bad:
    print("EMPTY DAYS:", json.dumps(bad)); sys.exit(1)
print("all topic cards: 7/7 days filled")
