# Voiceovers: rules and tools

Every Stackby video gets an ElevenLabs voiceover (model **Eleven v3**). Follow these rules for every new video.

## Rules
1. **"Stackby" is pronounced "Stack buy"** (never "Stack bee"). Scripts and captions keep the spelling
   *Stackby*; `voice.py` respells it as `Stack-buy` only in the text sent to the voice, and maps the word
   timings back so captions still read "Stackby". Add any other brand words to `SPOKEN` in `voice.py`.
2. Each video opens with a hook (a pain, a number or a bold question) in the first 3 to 6 seconds, then shows
   the real use case, then a clear call to action ("Start free at Stackby dot com").
3. Facts and prices come only from `data/captions.json` (the approved captions doc).
4. Scene timings come from ElevenLabs forced alignment, so visuals and captions land on the spoken word.
5. No overlapping on-screen text (each video is checked frame by frame before posting).

## Checks before a video is used (all must pass)
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

Scripts JSON format: `{"<video-name>": {"voice": "<ElevenLabs voice id>", "scenes": [{"id": "hook", "vo": "[excited] ..."}]}}`.
Bracketed cues like `[excited]` steer the delivery and are not spoken. The ElevenLabs API key is never stored
in this repo.
