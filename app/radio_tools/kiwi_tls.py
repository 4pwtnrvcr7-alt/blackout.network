#!/usr/bin/env python3
"""Run kiwiclient's kiwirecorder.py over TLS (wss://host:443) for public KiwiSDRs behind HTTPS.
The box egress only allows HTTPS, so plain ws://host:8073 receivers are skipped; this only adds TLS, nothing else.
Usage: kiwi_tls.py <kiwirecorder args...>  (kiwiclient lives in /workspace/tools/kiwiclient)"""
import os, sys, socket, ssl
KC = os.environ.get("BN_KIWICLIENT", "/workspace/tools/kiwiclient")
sys.path.insert(0, KC)
_orig = socket.create_connection
_ctx = ssl.create_default_context()
def _tls(address, *a, **k):
    s = _orig(address, *a, **k)
    if int(address[1]) == 443: s = _ctx.wrap_socket(s, server_hostname=address[0])
    return s
import kiwi.client as kc
kc.socket.create_connection = _tls
sys.argv[0] = os.path.join(KC, "kiwirecorder.py")
os.chdir(KC)
import runpy
runpy.run_path(sys.argv[0], run_name="__main__")
