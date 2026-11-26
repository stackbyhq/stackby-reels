"""Shorten pauses longer than MAXGAP to MAXGAP (cutting from the middle of the silence, with short crossfades),
and shift the word/scene timings to match."""
import json, subprocess, sys
import numpy as np
import os
SR, MAXGAP, XF = 44100, float(os.environ.get("MAXGAP", 0.5)), 0.012
for slug in sys.argv[1:]:
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", f"{slug}-vo.mp3", "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"], capture_output=True).stdout
    x = np.frombuffer(raw, np.float32).copy()
    t = json.load(open(f"{slug}-timing.json"))
    w = t["words"]
    cuts = []  # (start, end) seconds to remove
    for i in range(len(w) - 1):
        g = w[i + 1]["s"] - w[i]["e"]
        if g > MAXGAP:
            mid = (w[i]["e"] + w[i + 1]["s"]) / 2
            rm = g - MAXGAP
            cuts.append((mid - rm / 2, mid + rm / 2))
    out, pos = [], 0
    xf = int(XF * SR)
    for a, b in cuts:
        ia, ib = int(a * SR), int(b * SR)
        seg = x[pos:ia].copy()
        if out and len(seg) > xf:
            seg[:xf] *= np.linspace(0, 1, xf)
        if len(seg) > xf:
            seg[-xf:] *= np.linspace(1, 0, xf)
        out.append(seg); pos = ib
    tail = x[pos:].copy()
    if out and len(tail) > xf: tail[:xf] *= np.linspace(0, 1, xf)
    out.append(tail)
    y = np.concatenate(out)
    def shift(s):
        return s - sum(min(b, s) - a for a, b in cuts if s > a)
    for k in w: k["s"], k["e"] = shift(k["s"]), shift(k["e"])
    for sc in t["scenes"]: sc["start"], sc["end"] = shift(sc["start"]), shift(sc["end"])
    t["duration"] = w[-1]["e"]
    json.dump(t, open(f"{slug}-timing.json", "w"), indent=1)
    p = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "f32le", "-ac", "1", "-ar", str(SR), "-i", "-", "-c:a", "pcm_s16le", f"{slug}-vo.wav"], input=y.tobytes())
    print(slug, f"removed {sum(b - a for a, b in cuts):.1f}s in {len(cuts)} pauses -> {t['duration']:.1f}s", [(s['id'], round(s['start'], 1)) for s in t['scenes']])
