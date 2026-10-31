#!/usr/bin/env python3
"""blackout.network newsletter scheduler (stdlib only, ~0% CPU: wakes every 30 s). Launched by newsletter.ensure_worker() from the
dashboard server (startup + any newsletter request), the same way streams_worker / video_subs_worker are launched, under nice 10.
Single instance via flock. Calls newsletter.run_due(), which is idempotent per slot, so restarts never double-send.
Hot-reloads newsletter.py when it changes. Writes only newsletter.db, newsletter_outbox/ and logs/."""
import fcntl, importlib, os, sys, time, traceback
BASE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, BASE)
os.makedirs(os.path.join(BASE, "logs"), exist_ok=True)
_lk = open(os.path.join(BASE, "logs", "newsletter_worker.lock"), "w")
try: fcntl.flock(_lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError: sys.exit(0)                       # another worker is already running
open(os.path.join(BASE, "logs", "newsletter_worker.pid"), "w").write(str(os.getpid()))
import newsletter as NL
mt = os.path.getmtime(NL.__file__); last_clean = 0
NL.log(f"worker started (pid {os.getpid()})", "worker")
while True:
    try:
        m = os.path.getmtime(NL.__file__)
        if m != mt: NL = importlib.reload(NL); mt = m; NL.log("worker reloaded newsletter.py", "worker")
        for key, st in NL.run_due(): print(f"{NL.iso(NL.now())} slot {key}: {st}", flush=True)
        if time.time() - last_clean > 6 * 3600:
            n = NL.cleanup_outbox(); last_clean = time.time()
            if n: NL.log(f"outbox retention: removed {n} old file(s)", "worker")
    except Exception: traceback.print_exc()
    time.sleep(30)
