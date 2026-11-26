import json, re, sys, requests
from voice import to_spoken, to_written
import os; S = json.load(open(os.environ.get("SCRIPTS", "scripts.json")))
API = "https://api.elevenlabs.io/v1"
clean = lambda s: re.sub(r"\s+", " ", re.sub(r"\[[^\]]*\]", "", s)).strip()
for slug, v in S.items():
    if sys.argv[1:] and slug not in sys.argv[1:]: continue
    text = to_spoken(" ".join(s["vo"] for s in v["scenes"]))  # brand pronunciation (voice.py)
    r = requests.post(f"{API}/text-to-speech/{v['voice']}?output_format=mp3_44100_192",
                      json={"text": text, "model_id": "eleven_v3", "voice_settings": {"stability": 0.5, "similarity_boost": 0.8, "use_speaker_boost": True}}, timeout=600)
    if r.status_code != 200: print(slug, r.status_code, r.text[:300]); continue
    open(f"{slug}-vo.mp3", "wb").write(r.content)
    # forced alignment on the clean text
    ctext = to_spoken(" ".join(clean(s["vo"]) for s in v["scenes"]))
    fa = requests.post(f"{API}/forced-alignment", files={"file": (f"{slug}.mp3", r.content, "audio/mpeg")}, data={"text": ctext}, timeout=600).json()
    if "words" not in fa: print(slug, "alignment failed", fa); continue
    words = [{"w": to_written(w["text"].strip()), "s": w["start"], "e": w["end"]} for w in fa["words"] if w["text"].strip()]
    # scene boundaries by word counts
    scenes, i = [], 0
    for s in v["scenes"]:
        n = len(clean(s["vo"]).split())
        seg = words[i:i + n]
        scenes.append({"id": s["id"], "start": seg[0]["s"], "end": seg[-1]["e"]}); i += n
    dur = words[-1]["e"]
    json.dump({"scenes": scenes, "words": words, "duration": dur}, open(f"{slug}-timing.json", "w"), indent=1)
    print(slug, f"{dur:.1f}s", len(words), "words /", len(ctext.split()), [(x["id"], round(x["start"], 1)) for x in scenes])
