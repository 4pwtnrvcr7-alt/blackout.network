#!/usr/bin/env python3
"""Runs the UNMODIFIED /workspace/blackout/webpush_notifier.py against the live feed (bn_webpush_feed.py). Overrides only module paths:
subscriptions -> render_subs.db, stories -> live_clusters.db, config copy / dead list / log -> /workspace/webpush_box. Box only; VAPID key
stays in /workspace/.credentials. Usage: bn_webpush_run.py loop | once | status | list | testreqs"""
import os, sys, shutil
sys.dont_write_bytecode = True
sys.path.insert(0, "/workspace/blackout")
import webpush_notifier as N
D = "/workspace/webpush_box"
CONF = os.path.join(D, "webpush_config.json")
try:
    if os.path.exists("/workspace/blackout/webpush_config.json"): shutil.copyfile("/workspace/blackout/webpush_config.json", CONF)   # read-only copy; holds no secrets
except Exception: pass
N.CONF_F = CONF; N.DEAD_F = os.path.join(D, "webpush_dead.json"); N.LOG_F = os.path.join(D, "webpush.log")
N.SUB_DBS = [os.path.join(D, "render_subs.db")]; N.SRC_DB = os.path.join(D, "live_clusters.db")
if __name__ == "__main__": sys.exit(N.main())
