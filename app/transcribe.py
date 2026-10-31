#!/usr/bin/env python3
"""Local CPU transcription for Live Broadcasts (run with /workspace/.whisperenv/bin/python). Prints JSON."""
import json, sys, wave
import numpy as np
from faster_whisper import WhisperModel
m = WhisperModel(sys.argv[2] if len(sys.argv) > 2 else "tiny.en", device="cpu", compute_type="int8", cpu_threads=2)
w = wave.open(sys.argv[1]); a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
segs, info = m.transcribe(a, beam_size=1, vad_filter=True, language="en")
print(json.dumps({"text": " ".join(s.text.strip() for s in segs).strip(), "duration": info.duration}))
