"""Pronunciation rules for every Stackby voiceover.

Scripts and captions always use the brand spelling. Only the text sent to the voice is respelled, so it is
spoken the way the brand is said; the word timings are mapped back so captions still read "Stackby".

  Stackby  ->  "Stackbuy"  = said "Stack buy" (never "Stack bee"). One word, no hyphen: a hyphen makes the
  voice stumble on the web address ("stack-by dot com").
"""
import re

SPOKEN = [  # (written, spoken)
    ("Stackby", "Stackbuy"),
]


def to_spoken(text):
    for w, s in SPOKEN:
        text = re.sub(rf"\b{w}\b", s, text)
        text = re.sub(rf"\b{w.lower()}\b", s.lower(), text)
    return text


def to_written(word):
    for w, s in SPOKEN:
        word = re.sub(re.escape(s), w, word)
        word = re.sub(re.escape(s.lower()), w.lower(), word)
    return word


def pronunciation_problems(script_text, heard_text):
    """Every brand mention in the script must be heard the spoken way (e.g. 'Stack buy', not 'Stackby'/'Stack bee')."""
    out = []
    for w, s in SPOKEN:
        want = len(re.findall(rf"\b{w}\b", script_text, re.I))
        head, tail = s[:5], s[5:]
        good = len(re.findall(rf"\b{head}[\s-]?{tail}", heard_text, re.I))
        if good < want:
            out.append(f"'{w}' said {want}x in the script but heard as '{head} {tail}' only {good}x")
    return out
