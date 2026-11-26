# Voiceovers: rules and tools

Every Stackby video gets an ElevenLabs voiceover (model **Eleven v3**). Follow these rules for every new video.

## Rules
1. **"Stackby" is pronounced "Stack buy"** (never "Stack bee"). Scripts and captions keep the spelling
   *Stackby*; `voice.py` respells it as `Stackbuy` (one word: a hyphen makes the voice stumble on the web
   address) only in the text sent to the voice, and maps the word timings back so captions still read
   "Stackby". Add any other brand words to `SPOKEN` in `voice.py`.
2. **Every video ends with exactly: "Build on Stackby dot com for free today."**
3. Each video opens with a hook (a pain, a number or a bold question) in the first 3 to 6 seconds, then shows
   the real use case, then a clear call to action ("Start free at Stackby dot com").
4. Facts and prices come only from `data/captions.json` (the approved captions doc).
5. Scene timings come from ElevenLabs forced alignment, so visuals and captions land on the spoken word.
6. No overlapping on-screen text (each video is checked frame by frame before posting).

## Checks before a video is used (all must pass)
* `vo_gate.py`: generates the voiceover and keeps a take only if it reads the script word for word, ends with
  the full closing line, says the web address clearly ("stackby dot com") and passes the "Stack buy" check
  (up to 3 takes).
* `end_check.py`: run on every **finished video file**: the last line must be complete ("... for free today")
  and end before the video does.
* Audio mixing is done in separate passes (voice level, mix, final loudness): in a single ffmpeg filter graph
  the loudness filter's 3-second look-ahead tail is dropped and the last words get cut.
* `qa_vo.py`: speech-to-text of the voiceover matches the script word for word (numbers written as digits
  and US/UK spellings are fine).
* `pron_check.py`: acoustic check of every "Stackby": the vowel after the "b" must match the voice's own
  reference "Stack buy", not "Stack bee". (Speech-to-text cannot tell "buy" from "bee" for a brand name.)
* `tighten.py`: pauses longer than about half a second are shortened, and the timings shift with them.

## Tools
| File | What it does |
|---|---|
| `voice.py` | Pronunciation rules (`to_spoken`, `to_written`) |
| `tts.py` | Generates the voiceover (Eleven v3) and word timings (forced alignment) from a scripts JSON |
| `qa_vo.py` | Word-for-word check with ElevenLabs speech-to-text |
| `pron_check.py` | Acoustic "Stack buy" check |
| `tighten.py` | Shortens long pauses and shifts the timings |
| `vo_gate.py` | Generate + all voiceover checks, retrying bad takes |
| `place_vo.py` | Places each scene's line at its scene start in an existing video, never clipping a line |
| `end_check.py` | Checks the ending of finished video files |

Scripts JSON format: `{"<video-name>": {"voice": "<ElevenLabs voice id>", "scenes": [{"id": "hook", "vo": "[excited] ..."}]}}`.
Bracketed cues like `[excited]` steer the delivery and are not spoken. The ElevenLabs API key is never stored
in this repo.
