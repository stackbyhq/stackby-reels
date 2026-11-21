"""Turn the caption doc dump (data/doc_dump.json, read from the "Stackby Video Captions" Google Doc)
into data/captions.json: one entry per video with everything the robot posts, in posting order.
Run: python3 scripts/build_captions.py
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DUMP = os.path.join(ROOT, "data", "doc_dump.json")
OUT = os.path.join(ROOT, "data", "captions.json")
SIGNUP = "https://stackby.com/signup"
MCP_URL = "https://mcp.stackby.com/mcp"


def first_comment(slug, title):
    if "mcp" in slug:
        return f"🔌 Add the Stackby MCP connector: {MCP_URL}\nNew to Stackby? Start free → {SIGNUP}"
    if "-vs-" in slug:
        return f"💸 Compare plans and start free → {SIGNUP}\nPrices are public list prices, billed annually. Check each vendor's pricing page for current pricing."
    return f"🚀 Build yours free on Stackby → {SIGNUP}"


def yt_short_description(v):
    """Shorts description: the YouTube description without the chapter list (chapters do nothing on Shorts)."""
    d = v["sections"]["YouTube"]["Description"]
    d = re.sub(r"\nChapters\n(?:\d+:\d\d [^\n]*\n?)+", "\n", d)
    return re.sub(r"\n{3,}", "\n\n", d).strip()


def series(v):
    s = v["slug"]
    if "-vs-" in s or s == "07-google-sheets-to-stackby":
        return "Comparison"
    if v["group"].startswith(("Stackby + AI", "Batch 5")) and s[:2] in ("13", "14", "15", "16", "17", "25", "26"):
        return "Stackby + AI"
    if s == "10-instagram-sync-connectors":
        return "Sync connectors"
    return "Industry portal"


def order(videos):
    """Interleave the series so the feed alternates AI, comparisons and industry portals."""
    ai = [v for v in videos if v["slug"][:2] in ("13", "14", "15", "16", "17", "25", "26") and v["group"].startswith(("Stackby + AI", "Batch 5"))]
    vs = [v for v in videos if "-vs-" in v["slug"] or v["slug"] == "07-google-sheets-to-stackby"]
    rest_b5 = [v for v in videos if v["group"].startswith("Batch 5") and v not in ai and v not in vs]
    rest_b3 = [v for v in videos if v["group"].startswith("Batch 3") and v not in vs]
    ind = [v for v in videos if v["group"].startswith("Industry")]
    buckets = [ai, rest_b5 + rest_b3, vs, ind]
    out = []
    while any(buckets):
        for b in buckets:
            if b:
                out.append(b.pop(0))
    return out


def main():
    videos = json.load(open(DUMP))
    out = []
    for i, v in enumerate(order(videos), 1):
        s = v["sections"]
        slug = v["slug"]
        out.append({
            "order": i,
            "name": slug,
            "title": v["title"],
            "group": series(v),
            "files": {
                "vertical": f"stackby-{slug}-vertical.mp4",
                "landscape": f"stackby-{slug}-landscape.mp4",
                "cover": f"stackby-{slug}-cover-reels-1080x1920.jpg",
                "thumbnail": re.search(r"YouTube thumbnail: (\S+\.jpg)", v["thumbs"]).group(1),
            },
            "caption": s["Instagram Reels"]["_"],
            "first_comment": first_comment(slug, v["title"]),
            "yt_title": s["YouTube Shorts"]["Title"][:100],
            "yt_description": yt_short_description(v),
            "yt_long_title": s["YouTube"]["Title"][:100],
            "yt_long_description": s["YouTube"]["Description"],
            "yt_tags": [t.strip() for t in s["YouTube"]["Tags"].split(",") if t.strip()][:30],
        })
    json.dump(out, open(OUT, "w"), ensure_ascii=False, indent=1)
    print(f"wrote {OUT}: {len(out)} videos")


if __name__ == "__main__":
    main()
