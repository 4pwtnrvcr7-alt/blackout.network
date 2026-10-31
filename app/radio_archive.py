#!/usr/bin/env python3
"""blackout.network Radio recorder (separate process; launched by radio.py ensure_worker() and by start.sh).
 - Records the DIRECT streams marked archive=True into rolling 15-min MP3s (16 kbps mono) under archive/radio/<id>/<YYYYMMDD>/<HHMMSS>.mp3 (UTC).
 - Relays 2 shortwave channels from a public KiwiSDR (over HTTPS/wss): UVB-76 4625 kHz continuously, and HFGCS 8992 kHz,
   switching that second slot to Priyom-scheduled number-station transmissions when one is due. Each relay feeds a short
   live HLS window (archive/radio_live/<id>/) for the Radio tab and the same archive format.
 - Retention: RETAIN_DAYS or RETAIN_BYTES total (whichever first), oldest deleted first; stops recording if free disk < MIN_FREE_BYTES.
Receive-only monitoring. Never touches scanner.py, scoring, push.py, jets.py, config.json or blackout.db."""
import os, sys, json, time, signal, shutil, subprocess, fcntl, re, urllib.request, traceback
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radio_common as RC

LOG = os.path.join(RC.BASE, "logs", "radio_archive.log")
EVENTS = os.path.join(RC.BASE, "logs", "priyom_events.json")
SKIP_DIGITAL = ("XPA", "F06", "F01", "F11", "XPH")      # data-only Russian digital stations: skipped for the voice/CW slot
UA = {"User-Agent": "blackout.network radio monitor (receive-only)"}
ENV = {**os.environ, "TZ": "UTC"}
ST = {"started": None, "streams": {}, "retention": {}, "kiwi": {}}
procs = {}       # id -> dict(p=[Popen...], since, restarts, next_try, tune)

def log(*a):
    with open(LOG, "a") as f: f.write(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ ") + " ".join(map(str, a)) + "\n")
def now(): return datetime.now(timezone.utc)
def iso(d=None): return (d or now()).strftime("%Y-%m-%dT%H:%M:%SZ")

def prep_dirs(sid):
    for d in (now(), now() + timedelta(hours=1), now() + timedelta(days=1)):
        os.makedirs(os.path.join(RC.ARCHIVE, sid, d.strftime("%Y%m%d")), exist_ok=True)

def seg_args(sid, sr=22050):
    return ["-ac", "1", "-ar", str(sr), "-c:a", "libmp3lame", "-b:a", f"{RC.ARCHIVE_KBPS}k", "-f", "segment", "-segment_time", str(RC.SEGMENT_S),
            "-segment_atclocktime", "1", "-strftime", "1", "-reset_timestamps", "1", os.path.join(RC.ARCHIVE, sid, "%Y%m%d", "%H%M%S.mp3")]

def disk_ok(): return shutil.disk_usage(RC.BASE).free > RC.MIN_FREE_BYTES

# ---------------- direct streams ----------------
def start_direct(s):
    prep_dirs(s["id"])
    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "30",
           "-rw_timeout", "30000000", "-user_agent", UA["User-Agent"], "-i", s["url"], "-vn", *seg_args(s["id"])]
    lf = open(LOG, "a")
    return [subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=lf, stderr=lf, env=ENV, start_new_session=True)]

# ---------------- KiwiSDR relays ----------------
def kiwi_status(host):
    try:
        t = urllib.request.urlopen(urllib.request.Request(f"https://{host}/status", headers=UA), timeout=8).read().decode("utf-8", "ignore")
        kv = dict(l.split("=", 1) for l in t.splitlines() if "=" in l)
        return {"ok": kv.get("status") == "active" and kv.get("offline") == "no", "users": int(kv.get("users", 99)), "max": int(kv.get("users_max", 0))}
    except Exception as ex: return {"ok": False, "err": str(ex)[:80]}

def pick_kiwi(avoid):
    hosts = sorted(RC.KIWIS, key=lambda k: k["host"] in avoid)
    for k in hosts:
        s = kiwi_status(k["host"]); ST["kiwi"][k["host"]] = {**s, "checked": iso()}
        if s.get("ok") and s["max"] - s["users"] >= RC.KIWI_FREE_SLOTS_MIN: return k
    return None

def start_relay(rid, tune, kiwi):
    out_id = tune.get("archive_id", rid)
    prep_dirs(out_id)
    live = os.path.join(RC.LIVE, rid); shutil.rmtree(live, ignore_errors=True); os.makedirs(live, exist_ok=True)
    mode = tune["mode"]; lo, hi = {"usb": (300, 2700), "lsb": (-2700, -300), "am": (-4500, 4500), "cw": (300, 700)}.get(mode, (300, 2700))
    kcmd = [sys.executable, RC.KIWI_TLS, "-s", kiwi["host"], "-p", "443", "-f", str(tune["khz"]), "-m", mode, "-L", str(lo), "-H", str(hi),
            "--nc", "--nc-wav", "--user", "blackout.network", "--quiet"]
    fcmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-f", "wav", "-i", "-",
            "-map", "0:a", "-c:a", "aac", "-b:a", "32k", "-ac", "1", "-f", "hls", "-hls_time", "4", "-hls_list_size", "8",
            "-hls_flags", "delete_segments+omit_endlist", "-hls_segment_filename", os.path.join(live, "s%06d.ts"), os.path.join(live, "index.m3u8"),
            "-map", "0:a", *seg_args(out_id, 12000)]
    lf = open(LOG, "a")
    k = subprocess.Popen(kcmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=lf, cwd=os.path.dirname(RC.KIWI_TLS), start_new_session=True)
    f = subprocess.Popen(fcmd, stdin=k.stdout, stdout=lf, stderr=lf, env=ENV, start_new_session=True)
    k.stdout.close()
    log(f"relay {rid}: {tune['label']} {tune['khz']} kHz {mode} via {kiwi['host']}")
    return [k, f]

# ---------------- Priyom schedule (public calendar used by priyom.org) ----------------
def load_events():
    try:
        st = os.stat(EVENTS)
        if time.time() - st.st_mtime < 1800: return json.load(open(EVENTS))
    except Exception: pass
    try:
        u = "https://calendar2.priyom.org/events?timeMin=" + iso(now() - timedelta(hours=1)) + "&maxResults=250"
        d = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=15).read())
        ev = []
        for e in d.get("items", []):
            m = re.match(r"^([\w /-]+?) (\d+) ?kHz(?: ([A-Z/]+))?", e.get("summary", ""))
            if not m: continue
            ev.append({"station": m.group(1), "khz": int(m.group(2)), "mode": (m.group(3) or "USB"), "start": e["start"]["dateTime"], "summary": e["summary"]})
        tmp = EVENTS + ".tmp"; json.dump(ev, open(tmp, "w")); os.replace(tmp, EVENTS); return ev
    except Exception as ex:
        log("priyom calendar:", ex)
        try: return json.load(open(EVENTS))
        except Exception: return []

def due_event():
    t = now()
    for e in load_events():
        if e["station"].upper().startswith(SKIP_DIGITAL) or e["khz"] > 30000: continue
        s = datetime.fromisoformat(e["start"].replace("Z", "+00:00"))
        if s - timedelta(minutes=1) <= t <= s + timedelta(minutes=12):
            m = e["mode"].split("/")[0].lower(); m = m if m in ("usb", "lsb", "am", "cw") else "usb"
            return {"khz": e["khz"], "mode": m, "label": f"{e['station']} {e['khz']} kHz (Priyom schedule {s.strftime('%H:%MZ')})",
                    "archive_id": "priyom", "event": e, "until": iso(s + timedelta(minutes=12))}
    return None

def relay_tune(r):
    if r["id"] == "hfgcs":
        ev = due_event()
        if ev: return ev
    return {"khz": r["freq_khz"], "mode": r["mode"], "label": r["name"], "archive_id": r["id"]}

# ---------------- retention ----------------
def retention():
    files = []
    for dp, dn, fn in os.walk(RC.ARCHIVE):
        for f in fn:
            p = os.path.join(dp, f)
            try: st = os.stat(p)
            except FileNotFoundError: continue
            files.append((st.st_mtime, st.st_size, p))
    files.sort(); total = sum(f[1] for f in files); cut = time.time() - RC.RETAIN_DAYS * 86400; deleted = 0
    for mt, sz, p in files:
        if mt < cut or total > RC.RETAIN_BYTES:
            try: os.remove(p); total -= sz; deleted += 1
            except Exception: pass
    for dp, dn, fn in sorted(os.walk(RC.ARCHIVE), key=lambda x: -len(x[0])):
        if dp != RC.ARCHIVE and not os.listdir(dp) and os.path.basename(dp) < (now() - timedelta(days=1)).strftime("%Y%m%d"):
            try: os.rmdir(dp)
            except Exception: pass
    du = shutil.disk_usage(RC.BASE)
    ST["retention"] = {"total_bytes": total, "files": len(files) - deleted, "deleted_last": deleted, "cap_bytes": RC.RETAIN_BYTES,
                       "retain_days": RC.RETAIN_DAYS, "disk_free_bytes": du.free, "min_free_bytes": RC.MIN_FREE_BYTES, "checked": iso()}

# ---------------- supervisor ----------------
def alive(ps): return all(p.poll() is None for p in ps)
def stop(ps):
    for p in ps:
        try: os.killpg(p.pid, signal.SIGTERM)
        except Exception: pass
    for p in ps:
        try: p.wait(5)
        except Exception:
            try: os.killpg(p.pid, signal.SIGKILL)
            except Exception: pass

def write_status():
    ST["updated"] = iso(); tmp = RC.STATUS + ".tmp"
    json.dump(ST, open(tmp, "w"), default=str); os.replace(tmp, RC.STATUS)

def supervise():
    ok_disk = disk_ok()
    for s in [x for x in RC.DIRECT if x.get("archive")]:
        e = procs.setdefault(s["id"], {"p": [], "restarts": 0, "next_try": 0, "since": None})
        prep_dirs(s["id"])
        if e["p"] and alive(e["p"]) and ok_disk: pass
        else:
            if e["p"]: stop(e["p"]); e["p"] = []; e["restarts"] += 1; e["next_try"] = time.time() + min(600, 15 * 2 ** min(e["restarts"], 5))
            if ok_disk and time.time() >= e["next_try"]: e["p"] = start_direct(s); e["since"] = iso()
        ST["streams"][s["id"]] = {"type": "direct", "running": bool(e["p"]) and alive(e["p"]), "since": e["since"], "restarts": e["restarts"], "disk_ok": ok_disk}
    used = set()
    for r in RC.RELAYS:
        e = procs.setdefault(r["id"], {"p": [], "restarts": 0, "next_try": 0, "since": None, "tune": None, "kiwi": None})
        want = relay_tune(r)
        if e["tune"] and e["p"] and alive(e["p"]) and (want["khz"], want["mode"]) != (e["tune"]["khz"], e["tune"]["mode"]):
            stop(e["p"]); e["p"] = []; e["next_try"] = 0          # retune (scheduled event started/ended): not a failure
        if e["p"] and alive(e["p"]) and ok_disk:
            used.add(e["kiwi"]["host"]); e["fails"] = 0
            if time.time() - e.get("ok_since", time.time()) > 600: e["restarts"] = 0
        else:
            if e["p"]:
                stop(e["p"]); e["p"] = []; e["restarts"] += 1
                e["next_try"] = time.time() + min(900, 20 * 2 ** min(e["restarts"], 6))
                log(f"relay {r['id']} stopped (restart #{e['restarts']}), next try in {int(e['next_try'] - time.time())}s")
            if ok_disk and time.time() >= e["next_try"]:
                k = pick_kiwi(used)
                if k: e["p"] = start_relay(r["id"], want, k); e["tune"] = want; e["kiwi"] = k; e["since"] = iso(); e["ok_since"] = time.time(); used.add(k["host"])
                else: e["next_try"] = time.time() + 300; log(f"relay {r['id']}: no KiwiSDR with {RC.KIWI_FREE_SLOTS_MIN}+ free slots; retry in 5 min")
        running = bool(e["p"]) and alive(e["p"])
        ST["streams"][r["id"]] = {"type": "relay", "running": running, "since": e["since"], "restarts": e["restarts"],
                                  "tuned": e["tune"] and {k: e["tune"][k] for k in ("khz", "mode", "label", "archive_id") if k in e["tune"]},
                                  "until": (e["tune"] or {}).get("until"), "receiver": e["kiwi"], "next_try": iso(datetime.fromtimestamp(e["next_try"], timezone.utc)) if not running else None,
                                  "disk_ok": ok_disk}

def main():
    os.makedirs(os.path.dirname(RC.STATUS), exist_ok=True); os.makedirs(RC.ARCHIVE, exist_ok=True); os.makedirs(RC.LIVE, exist_ok=True)
    lk = open(os.path.join(RC.BASE, "logs", "radio_archive.lock"), "w")
    try: fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError: print("radio_archive already running"); return
    open(RC.PIDF, "w").write(str(os.getpid()))
    def bye(*_):
        for e in procs.values(): stop(e["p"])
        sys.exit(0)
    signal.signal(signal.SIGTERM, bye); signal.signal(signal.SIGINT, bye)
    ST["started"] = iso(); log("radio_archive started")
    os.environ["BN_LIVE_ARCHIVE_POLLER"] = "1"      # this process also keeps the Live Archive log (live_archive.py, every 5 min)
    try: import radio  # noqa: F401  (5-min live/offline checks of the direct streams -> logs/radio_check.json)
    except Exception: log("radio checks:", traceback.format_exc())
    try: import live_archive  # noqa: F401  (starts its poll thread)
    except Exception: log("live_archive:", traceback.format_exc())
    last_ret = 0
    while True:
        try:
            if time.time() - last_ret > 300: retention(); last_ret = time.time()
            supervise(); write_status()
        except Exception: log(traceback.format_exc())
        time.sleep(10)

if __name__ == "__main__": main()
