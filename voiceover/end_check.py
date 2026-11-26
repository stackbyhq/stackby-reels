"""Final-file check: the last line must be complete and end with "... for free today" well before the video ends."""
import subprocess, sys, requests, re
bad = 0
for f in sys.argv[1:]:
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f], capture_output=True, text=True).stdout)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(dur - 10), "-i", f, "-vn", "-ac", "1", "-ar", "16000", "_tail.wav"])
    d = requests.post("https://api.elevenlabs.io/v1/speech-to-text", files={"file": open("_tail.wav", "rb")}, data={"model_id": "scribe_v1", "timestamps_granularity": "word"}, timeout=300).json()
    words = [w for w in d.get("words", []) if w.get("type") == "word"]
    text = d.get("text", "")
    tail = re.sub(r"[^a-z ]", " ", text.lower()).split()[-7:]
    end_at = dur - 10 + words[-1]["end"] if words else 0
    ok = tail[-3:] == ["for", "free", "today"] and re.search(r"stackb(y|uy)", " ".join(tail)) and dur - end_at > 0.4
    bad += not ok
    print(f"{'OK  ' if ok else 'FAIL'} {f.split('/')[-1][:46]:46} ends: '...{text[-58:]}' at {end_at:.1f}s of {dur:.1f}s")
sys.exit(1 if bad else 0)
