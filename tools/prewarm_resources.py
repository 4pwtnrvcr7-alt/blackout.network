#!/usr/bin/env python3
"""Box-side prewarm of the Local Resources Overpass cache (t480 follow-up). Run from the app dir on the box, e.g. nightly:
    cd /workspace/blackout && python3 /path/to/prewarm_resources.py
Florida is served from the offline index (resources_pois.db) and is skipped. One request at a time, 20 s apart
(Overpass usage policy); cells already cached for 24 h are skipped. Cache rows sync to Render with resources_cache.db."""
import os, sys, time
sys.path.insert(0, os.getcwd()); import resources as R
METROS = ["New York, NY", "Los Angeles, CA", "Chicago, IL", "Dallas, TX", "Houston, TX", "Washington, DC", "Philadelphia, PA", "Atlanta, GA",
 "Boston, MA", "Phoenix, AZ", "San Francisco, CA", "Riverside, CA", "Detroit, MI", "Seattle, WA", "Minneapolis, MN", "San Diego, CA", "Denver, CO",
 "Baltimore, MD", "St. Louis, MO", "Charlotte, NC", "San Antonio, TX", "Portland, OR", "Sacramento, CA", "Pittsburgh, PA", "Austin, TX", "Las Vegas, NV",
 "Cincinnati, OH", "Kansas City, MO", "Columbus, OH", "Indianapolis, IN", "Cleveland, OH", "San Jose, CA", "Nashville, TN", "Virginia Beach, VA",
 "Providence, RI", "Milwaukee, WI", "Raleigh, NC", "Memphis, TN", "Oklahoma City, OK", "Louisville, KY", "Richmond, VA", "New Orleans, LA",
 "Salt Lake City, UT", "Hartford, CT", "Buffalo, NY", "Birmingham, AL", "Rochester, NY", "Tucson, AZ", "Honolulu, HI", "Albuquerque, NM"]
for q in METROS:
    try:
        g, _ = R.geocode(q)
        if not g: print("no geocode", q); continue
        if R.local_pois(g["lat"], g["lon"])[0] is not None: print("offline", q); continue
        t = time.time(); els, cached, m = R.overpass(g["lat"], g["lon"])
        print(f"{q}: {len(els)} POIs {'cached' if cached else m} {time.time()-t:.1f}s", flush=True)
        if not cached: time.sleep(20)
    except Exception as ex: print(q, "failed:", ex, flush=True); time.sleep(20)
