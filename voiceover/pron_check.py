"""Acoustic check that every 'Stackby' in a voiceover ends in 'buy' (/baɪ/) and not 'bee' (/biː/).

For each voice, reference clips 'Stack buy' and 'Stack bee' are synthesised. ElevenLabs forced alignment gives
character times; the vowel after the 'b' is cut out and its first formant (F1, mouth openness) is measured with
LPC over the first half of the vowel: /aɪ/ starts open (high F1), /iː/ is closed (low F1). Each mention is
classified by whichever reference it is closer to.
usage: python3 pron_check.py SPEC.json SLUG [SLUG...] [--audio-suffix -vo.wav]
"""
import json
import os
import re
import subprocess
import sys

import numpy as np
import requests

API = "https://api.elevenlabs.io/v1"
SR = 16000


def load(path):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.float32)


def align(path, text):
    with open(path, "rb") as f:
        r = requests.post(f"{API}/forced-alignment", files={"file": (os.path.basename(path), f, "audio/mpeg")}, data={"text": text}, timeout=600).json()
    return r["characters"]


def f1_track(x):
    """F1 (Hz) per 20 ms frame via LPC."""
    x = np.append(x[0], x[1:] - 0.97 * x[:-1])
    n, hop, order = int(.025 * SR), int(.01 * SR), 16
    out = []
    for i in range(0, max(1, len(x) - n), hop):
        fr = x[i:i + n] * np.hamming(n)
        if np.abs(fr).max() < 1e-3:
            continue
        r = np.correlate(fr, fr, "full")[n - 1:n + order]
        R = np.array([[r[abs(a - b)] for b in range(order)] for a in range(order)]) + np.eye(order) * 1e-9
        a = np.linalg.solve(R, r[1:order + 1])
        roots = [z for z in np.roots(np.concatenate([[1], -a])) if np.imag(z) > 0]
        fs = sorted((np.angle(z) * SR / (2 * np.pi), -np.log(abs(z)) * SR / np.pi) for z in roots)
        fs = [f for f, bw in fs if 200 < f < 1300 and bw < 500]
        if fs:
            out.append(fs[0])
    return out


def vowel_f1(x, chars, start_idx):
    """chars[start_idx] is the 'b' of 'buy'/'bee': measure the vowel that follows (first half)."""
    v0 = chars[start_idx + 1]["start"]
    v1 = chars[start_idx + 2]["end"]
    seg = x[int(v0 * SR): int((v0 + max(.06, (v1 - v0) * .5)) * SR)]
    tr = f1_track(seg)
    return float(np.median(tr)) if tr else None


def mentions(chars, word=None):
    """Index of the 'b' in every spoken brand word (e.g. Stack|b|uy)."""
    from voice import SPOKEN
    word = word or SPOKEN[0][1]
    text = "".join(c["text"] for c in chars)
    return [m.start() + len(word) - 3 for m in re.finditer(re.escape(word), text, re.I)]


def reference(voice):
    path = f"ref-{voice}.mp3"
    text = "Stack bee. Stack buy. Stack bee. Stack buy."
    if not os.path.exists(path):
        a = requests.post(f"{API}/text-to-speech/{voice}?output_format=mp3_44100_128", json={"text": text, "model_id": "eleven_v3", "voice_settings": {"stability": 0.5, "similarity_boost": 0.8}}, timeout=300).content
        open(path, "wb").write(a)
    chars = align(path, text)
    x = load(path)
    t = "".join(c["text"] for c in chars)
    bee = [vowel_f1(x, chars, m.start() + 6) for m in re.finditer("Stack bee", t)]
    buy = [vowel_f1(x, chars, m.start() + 6) for m in re.finditer("Stack buy", t)]
    return float(np.nanmean([v for v in bee if v])), float(np.nanmean([v for v in buy if v]))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    suffix = sys.argv[sys.argv.index("--audio-suffix") + 1] if "--audio-suffix" in sys.argv else "-vo.wav"
    if "--audio-suffix" in sys.argv:
        args.remove(suffix)
    spec = json.load(open(args[0]))
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from voice import to_spoken
    clean = lambda s: re.sub(r"\s+", " ", re.sub(r"\[[^\]]*\]", "", s)).strip()
    bad = 0
    for slug in args[1:]:
        v = spec[slug]
        bee, buy = reference(v["voice"])
        text = to_spoken(" ".join(clean(s["vo"]) for s in v["scenes"]))
        path = slug + suffix
        chars = align(path, text)
        x = load(path)
        res = []
        for idx in mentions(chars):
            f1 = vowel_f1(x, chars, idx)
            res.append(("buy" if f1 is not None and abs(f1 - buy) < abs(f1 - bee) else "BEE", round(f1 or 0)))
        ok = all(r[0] == "buy" for r in res)
        bad += not ok
        print(f"{slug}: refs F1 bee≈{bee:.0f}Hz buy≈{buy:.0f}Hz -> {'OK' if ok else 'PROBLEM'} {res}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
