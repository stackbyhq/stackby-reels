"""Generate a voiceover and only keep it if it passes every check (up to 3 takes):
  1. speech-to-text matches the script (allowing digits, brand spelling and US/UK spellings)
  2. it ends with the full closing line "... for free today"
  3. every "Stackby" is acoustically "Stack buy"
usage (run inside the folder with tts3.py / voice.py / pron_check.py):  SCRIPTS=x.json python3 vo_gate.py SLUG"""
import difflib
import json
import os
import re
import subprocess
import sys

import requests

slug = sys.argv[1]
SPEC = os.environ["SCRIPTS"]
S = json.load(open(SPEC))
clean = lambda s: re.sub(r"\s+", " ", re.sub(r"\[[^\]]*\]", "", s)).strip()
NUM = {"zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10"}


def norm(t):
    t = re.sub(r"(\w)\.com\b", r"\1 dot com", t.lower())
    t = t.replace("stackby.com", "stackby dot com").replace("stackbuy", "stackby").replace("stack buy", "stackby").replace("stack-buy", "stackby")
    t = t.replace("organised", "organized").replace("metre", "meter")
    return re.sub(r"[^a-z0-9' ]", " ", t.replace("-", " ")).split()


def heard_text(path):
    d = requests.post("https://api.elevenlabs.io/v1/speech-to-text", files={"file": open(path, "rb")}, data={"model_id": "scribe_v1"}, timeout=600).json()
    return d.get("text", "")


CHECK_ONLY = "--check" in sys.argv
for take in range(1, 4):
    r = subprocess.run([sys.executable, "tts3.py", slug], capture_output=True, text=True) if not CHECK_ONLY else subprocess.CompletedProcess([], 0, "", "")
    if not os.path.exists(f"{slug}-vo.mp3") or "failed" in r.stdout:
        print(slug, "take", take, "generation failed:", r.stdout[-300:], r.stderr[-300:]); continue
    heard = heard_text(f"{slug}-vo.mp3")
    script = " ".join(clean(s["vo"]) for s in S[slug]["scenes"])
    a, b = norm(script), norm(heard)
    sm = difflib.SequenceMatcher(None, a, b)
    diffs = [(op, " ".join(a[i1:i2]), " ".join(b[j1:j2])) for op, i1, i2, j1, j2 in sm.get_opcodes() if op != "equal"]
    # digits for spelled numbers are fine
    real = [d for d in diffs if not (d[0] == "replace" and re.fullmatch(r"[\d ,.]+", d[2] or "x"))]
    # the web address must be heard clearly as "stackby dot com"
    url_ok = any(b[i:i + 3] == ["stackby", "dot", "com"] for i in range(len(b))) or "stackby" not in " ".join(a[-8:])
    ends_ok = b[-3:] == ["for", "free", "today"] and url_ok
    pc = subprocess.run([sys.executable, "pron_check.py", SPEC, slug, "--audio-suffix", "-vo.mp3"], capture_output=True, text=True)
    pron_ok = pc.returncode == 0
    ok = ends_ok and pron_ok and len(real) <= 1
    print(f"{slug} take {take}: {'PASS' if ok else 'reject'} | ending {'ok' if ends_ok else 'BROKEN: ' + ' '.join(b[-6:])} | "
          f"pronunciation {'ok' if pron_ok else 'BEE'} | text diffs {real[:4]}", flush=True)
    if ok or CHECK_ONLY:
        sys.exit(0 if ok else 1)
sys.exit(1)
