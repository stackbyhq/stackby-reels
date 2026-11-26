import json, re, sys, requests, difflib
from voice import to_spoken, pronunciation_problems
import os; S = json.load(open(os.environ.get("SCRIPTS", "scripts.json")))
clean = lambda s: re.sub(r"\s+", " ", re.sub(r"\[[^\]]*\]", "", s)).strip()
norm = lambda s: re.sub(r"[^a-z0-9' ]", " ", s.lower().replace("-", " ")).split()
for slug, v in S.items():
    if sys.argv[1:] and slug not in sys.argv[1:]: continue
    t = json.load(open(f"{slug}-timing.json"))
    w = t["words"]
    gaps = [(round(w[i]["e"], 1), round(w[i + 1]["s"] - w[i]["e"], 2), w[i]["w"], w[i + 1]["w"]) for i in range(len(w) - 1) if w[i + 1]["s"] - w[i]["e"] > 0.8]
    stt = requests.post("https://api.elevenlabs.io/v1/speech-to-text", files={"file": open(f"{slug}-vo.mp3", "rb")}, data={"model_id": "scribe_v1", "tag_audio_events": "true"}, timeout=600).json()
    heard = stt.get("text", str(stt))
    script = " ".join(clean(s["vo"]) for s in v["scenes"])
    a, b = norm(to_spoken(script)), norm(heard)
    sm = difflib.SequenceMatcher(None, a, b)
    diffs = [(op, " ".join(a[i1:i2]), " ".join(b[j1:j2])) for op, i1, i2, j1, j2 in sm.get_opcodes() if op != "equal"]
    print(f"== {slug}  dur {t['duration']:.1f}s  match {sm.ratio():.3f}")
    print("   long gaps:", gaps)
    print("   diffs:", diffs[:12])
    events = re.findall(r"\([^)]*\)", heard)
    print("   audio events heard:", events)
    pp = pronunciation_problems(script, heard)
    print("   pronunciation:", "OK (Stackby heard as Stack buy every time)" if not pp else "PROBLEM: " + "; ".join(pp))
