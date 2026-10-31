#!/usr/bin/env python3
"""blackout.network offline translation sidecar (display-only).
Runs under /workspace/.translateenv (Argos Translate models + CTranslate2, CPU only) on 127.0.0.1:8788, localhost only.
No network calls at runtime: models were downloaded once into ~/.local/share/argos-translate.
Never reads or writes blackout.db; the dashboard add-on translate.py owns the cache (translate_cache.db) and calls this.
  GET  /langs                 -> {"langs": ["ar", ...]}
  POST /translate {to, texts} -> {"to":..., "out": [...], "ms": n}
"""
import json, os, re, threading, time, collections
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
os.environ.setdefault("ARGOS_DEVICE_TYPE", "cpu")
import ctranslate2
import argostranslate.package as P

PORT = int(os.environ.get("BN_TRANSLATE_PORT", "8788"))
MAX_LOADED = int(os.environ.get("BN_TRANSLATE_MAX_MODELS", "6"))     # LRU of loaded models (~100-250 MB RAM each)
THREADS = int(os.environ.get("BN_TRANSLATE_THREADS", "4"))            # leaves CPU for the scanner + stream watcher
PKGS = {p.to_code: p for p in P.get_installed_packages() if p.from_code == "en"}
SPLIT = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9"\u201c(])')
_loaded = collections.OrderedDict()
_lock = threading.Lock()          # one batch at a time: bounded CPU, no thread-safety surprises
stats = {"batches": 0, "texts": 0, "segments": 0, "ms": 0, "started": time.time()}

def _model(to):
    m = _loaded.get(to)
    if m is None:
        p = PKGS[to]
        m = (p, ctranslate2.Translator(str(p.package_path / "model"), device="cpu", inter_threads=1, intra_threads=THREADS, compute_type="auto"))
        _loaded[to] = m
        while len(_loaded) > MAX_LOADED: _loaded.popitem(last=False)
    _loaded.move_to_end(to)
    return m

CJK = {"zh", "zt", "ja", "ko"}
_REP = re.compile(r"(\S{1,12}?)(?:\s*\1){4,}")
def bad(src, out, to):
    """Guard against the small models' failure modes: runaway repetition and hallucinated filler on short inputs."""
    if not out.strip(): return True
    n, m = len(src), len(out)
    if m > (n * 1.3 + 8 if to in CJK else n * 2.5 + 15): return True
    if _REP.search(out) and not _REP.search(src): return True
    if re.search(r"\s{6,}", out) and not re.search(r"\s{6,}", src): return True
    return False

def _decode(p, r):
    v = p.tokenizer.decode(r.hypotheses[0])
    if p.target_prefix and v.startswith(p.target_prefix): v = v[len(p.target_prefix):]
    return re.sub(r"\s*<(?:blank|unk)>\s*", " ", v).strip()   # some models emit placeholder tokens

def translate(to, texts):
    with _lock:
        p, tr = _model(to)
        segs, own, sent = [], [], []
        for i, t in enumerate(texts):
            for s in SPLIT.split(t.strip()) or [""]:
                if s: segs.append(p.tokenizer.encode(s)); own.append(i); sent.append(s)
        out = [[] for _ in texts]
        if segs:
            tp = [[p.target_prefix]] * len(segs) if p.target_prefix else None
            res = tr.translate_batch(segs, target_prefix=tp, replace_unknowns=True, max_batch_size=2048, batch_type="tokens",
                                     beam_size=2, num_hypotheses=1, length_penalty=0.2, max_decoding_length=400)
            vals = [_decode(p, r) for r in res]
            badi = [k for k, v in enumerate(vals) if bad(sent[k], v, to)]
            if badi:   # retry the bad segments with a wider beam + repetition penalties, then fall back to the English source
                rs = [segs[k] for k in badi]
                res2 = tr.translate_batch(rs, target_prefix=[[p.target_prefix]] * len(rs) if p.target_prefix else None, replace_unknowns=True,
                                          beam_size=4, num_hypotheses=1, length_penalty=0.2, repetition_penalty=1.3, no_repeat_ngram_size=3,
                                          max_decoding_length=max(8, 3 * max(len(x) for x in rs)))
                for k, r in zip(badi, res2):
                    v = _decode(p, r)
                    if bad(sent[k], v, to): v = sent[k]; stats["fallback"] = stats.get("fallback", 0) + 1
                    else: stats["retried_ok"] = stats.get("retried_ok", 0) + 1
                    vals[k] = v
            for i, v in zip(own, vals): out[i].append(v)
        sep = "" if to in ("zh", "zt", "ja") else " "
        return [sep.join(o) for o in out]

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path == "/langs": return self._send(200, {"langs": sorted(PKGS)})
        if self.path == "/stats": return self._send(200, {**stats, "loaded": list(_loaded)})
        return self._send(404, {"error": "not found"})
    def do_POST(self):
        if self.path != "/translate": return self._send(404, {"error": "not found"})
        try:
            n = min(int(self.headers.get("Content-Length") or 0), 2_000_000)
            d = json.loads(self.rfile.read(n) or b"{}")
            to, texts = str(d.get("to", "")), d.get("texts") or []
            if to not in PKGS: return self._send(400, {"error": "unsupported language"})
            if not isinstance(texts, list) or len(texts) > 2000: return self._send(400, {"error": "texts must be a list (max 2000)"})
            texts = [str(t)[:2000] for t in texts]
            t0 = time.time(); out = translate(to, texts); ms = int((time.time() - t0) * 1000)
            stats["batches"] += 1; stats["texts"] += len(texts); stats["ms"] += ms
            return self._send(200, {"to": to, "out": out, "ms": ms})
        except Exception as ex:
            return self._send(500, {"error": str(ex)[:200]})

if __name__ == "__main__":
    print(f"translate sidecar on 127.0.0.1:{PORT} with {len(PKGS)} languages", flush=True)
    ThreadingHTTPServer.daemon_threads = True
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
