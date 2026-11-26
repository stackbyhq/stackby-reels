"""Cut each scene's line out of the single voiceover take and place it at that scene's start in the 60 s video.
Lines longer than their window are sped up (max MAX_TEMPO); anything needing more is reported as a problem.
usage: python3 place_vo.py SLUG [SLUG...]  -> SLUG-vo-placed.wav + SLUG-placement.json"""
import json
import subprocess
import sys

import numpy as np

SR, LEAD, PAD, MAX_TEMPO, TOTAL = 44100, 0.12, 0.15, 1.18, 60.0
import os; S = json.load(open(os.environ.get("SCRIPTS", "ind_scripts.json")))


def load(path):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def tempo(x, f):
    if abs(f - 1) < 1e-3:
        return x
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "f32le", "-ac", "1", "-ar", str(SR), "-i", "-", "-af", f"atempo={f:.4f}", "-f", "f32le", "-"],
                       input=x.tobytes(), capture_output=True).stdout
    return np.frombuffer(r, np.float32).copy()


bad = 0
for slug in sys.argv[1:]:
    spec, t = S[slug], json.load(open(f"{slug}-timing.json"))
    x = load(f"{slug}-vo.wav" if os.path.exists(f"{slug}-vo.wav") else f"{slug}-vo.mp3")
    out = np.zeros(int(TOTAL * SR), np.float32)
    rep = []
    sc = t["scenes"]
    for i, s in enumerate(sc):
        w0, w1 = spec["windows"][s["id"]]
        a = max(0, s["start"] - 0.06)
        # never clip a line: run to just before the next line starts, or to the end of the take
        b = sc[i + 1]["start"] - 0.04 if i + 1 < len(sc) else len(x) / SR
        seg = x[int(a * SR):int(b * SR)]
        # drop trailing silence (keep 120 ms of tail so word endings are never cut)
        env = np.convolve(np.abs(seg), np.ones(441) / 441, "same")
        loud = np.where(env > 0.01)[0]
        if len(loud):
            seg = seg[:min(len(seg), loud[-1] + int(.12 * SR))]
        n = min(len(seg), int(.008 * SR)); seg[:n] *= np.linspace(0, 1, n); seg[-n:] *= np.linspace(1, 0, n)
        avail = (w1 - w0) - LEAD - PAD
        f = max(1.0, len(seg) / SR / avail)
        ok = f <= MAX_TEMPO
        bad += not ok
        seg = tempo(seg, min(f, MAX_TEMPO))
        i0 = int((w0 + LEAD) * SR)
        out[i0:i0 + len(seg)] += seg[:len(out) - i0]
        rep.append({"scene": s["id"], "at": round(w0 + LEAD, 2), "len": round(len(seg) / SR, 2), "window": round(w1 - w0, 2), "speedup": round(f, 3), "ok": ok})
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "f32le", "-ac", "1", "-ar", str(SR), "-i", "-", "-ac", "2", "-c:a", "pcm_s16le", f"{slug}-vo-placed.wav"], input=out.tobytes(), check=True)
    json.dump(rep, open(f"{slug}-placement.json", "w"), indent=1)
    worst = max(rep, key=lambda r: r["speedup"])
    flags = [r["scene"] for r in rep if not r["ok"]]
    print(f"{slug}: max speed-up {worst['speedup']:.2f}x ({worst['scene']})" + (f"  PROBLEM: too long for window: {flags}" if flags else "  OK"))
sys.exit(1 if bad else 0)
