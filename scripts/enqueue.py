"""Queue one video.  python3 scripts/enqueue.py my-video [--at 2026-11-25T07:00:00Z | --now | --hold] [--push]

Needs out/my-video/reel.mp4 (9:16), optional out/my-video/cover.jpg, out/my-video/landscape.mp4 + thumb.jpg
(16:9 long-form for YouTube) and reels/my-video/post.json. Video files are stored on the `media` branch,
the queue item in queue/my-video.json. Without --at the video takes the next free daily slot (SLOTS, IST).
"""
import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import IST, OUTDIR, PLATFORMS, QUEUE, REELS, ROOT, items, iso, now, parse, sh, write  # noqa: E402

SLOTS = ["12:30"]  # daily posting slots, IST (12:30 IST = 07:00 UTC). Add "19:00" for two posts a day.
MEDIA_WT = os.path.join(ROOT, ".media")
FILES = ("reel.mp4", "cover.jpg", "landscape.mp4", "thumb.jpg")


def probe(path):
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height:format=duration",
                              "-of", "json", path], capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    j = json.loads(out)
    v = next((s for s in j["streams"] if s["codec_type"] == "video"), {})
    a = next((s for s in j["streams"] if s["codec_type"] == "audio"), {})
    return {"w": v.get("width"), "h": v.get("height"), "vcodec": v.get("codec_name"), "acodec": a.get("codec_name"), "dur": float(j["format"].get("duration", 0))}


def check(name):
    """Return a list of problems (empty = OK) for one prepared video."""
    d = os.path.join(OUTDIR, name)
    errs = []
    reel = os.path.join(d, "reel.mp4")
    if not os.path.exists(reel):
        return [f"missing {reel}"]
    mb = os.path.getsize(reel) / 1e6
    if mb > 95:
        errs.append(f"reel.mp4 is {mb:.0f} MB (max 95)")
    p = probe(reel)
    if p:
        if (p["w"], p["h"]) != (1080, 1920):
            errs.append(f"reel.mp4 is {p['w']}x{p['h']}, expected 1080x1920")
        if p["vcodec"] != "h264" or p["acodec"] != "aac":
            errs.append(f"reel.mp4 codecs {p['vcodec']}/{p['acodec']}, expected h264/aac")
        if p["dur"] > 90:
            errs.append(f"reel.mp4 is {p['dur']:.0f}s (Reels via API: keep under 90s)")
    pj = os.path.join(REELS, name, "post.json")
    if not os.path.exists(pj):
        errs.append(f"missing {pj}")
    else:
        meta = json.load(open(pj))
        if len(meta.get("caption", "")) > 2200:
            errs.append("caption longer than 2200 characters")
        if meta.get("caption", "").count("#") > 30:
            errs.append("more than 30 hashtags")
        if len(meta.get("yt_title", "")) > 100:
            errs.append("yt_title longer than 100 characters")
    return errs


def taken():
    return {i["at"] for i in items(QUEUE) if i.get("status") != "hold" and i.get("at")}


def next_slot(after=None, used=None):
    used = set(used or taken())
    t = (after or now() + dt.timedelta(minutes=20)).astimezone(IST)
    day = t.date()
    for _ in range(400):
        for s in SLOTS:
            hh, mm = map(int, s.split(":"))
            cand = dt.datetime(day.year, day.month, day.day, hh, mm, tzinfo=IST)
            if cand > t and iso(cand) not in used:
                return iso(cand)
        day += dt.timedelta(days=1)
    raise RuntimeError("no free slot found")


def media_worktree():
    """A worktree of the `media` branch in .media/ (created as an orphan branch the first time)."""
    if os.path.isdir(os.path.join(MEDIA_WT, ".git")) or os.path.isfile(os.path.join(MEDIA_WT, ".git")):
        sh("git", "pull", "--ff-only", "origin", "media", cwd=MEDIA_WT, check=False)
        return MEDIA_WT
    remote = subprocess.run(["git", "ls-remote", "--heads", "origin", "media"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    if remote:
        sh("git", "fetch", "origin", "media:media", check=False)
        sh("git", "worktree", "add", MEDIA_WT, "media")
    else:
        sh("git", "worktree", "add", "--detach", MEDIA_WT)
        sh("git", "checkout", "--orphan", "media", cwd=MEDIA_WT)
        sh("git", "rm", "-rf", "--quiet", ".", cwd=MEDIA_WT, check=False)
        with open(os.path.join(MEDIA_WT, "README.md"), "w") as f:
            f.write("Video files for the posting queue. Managed by scripts/enqueue.py.\n")
    return MEDIA_WT


def store_media(names, push=True):
    wt = media_worktree()
    for name in names:
        dest = os.path.join(wt, "media", name)
        os.makedirs(dest, exist_ok=True)
        for f in FILES:
            src = os.path.join(OUTDIR, name, f)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(dest, f))
    sh("git", "add", "-A", cwd=wt)
    if sh("git", "status", "--porcelain", cwd=wt):
        sh("git", "commit", "-m", f"media: {', '.join(names)[:200]}", cwd=wt)
    if push:
        sh("git", "push", "-u", "origin", "media", cwd=wt, capture=False)


def make_item(name, at=None, hold=False, title=None):
    has_long = os.path.exists(os.path.join(OUTDIR, name, "landscape.mp4"))
    platforms = [p for p in PLATFORMS if p != "youtube_long" or has_long]
    return {"name": name, "title": title or name, "at": at, "status": "hold" if hold else "queued", "queued_at": iso(now()),
            "attempts": 0, "platforms": {p: {"status": "pending"} for p in platforms}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--at", help="UTC time, e.g. 2026-11-25T07:00:00Z")
    g.add_argument("--now", action="store_true", help="post within minutes")
    g.add_argument("--hold", action="store_true", help="park without posting")
    ap.add_argument("--push", action="store_true", help="also commit and push the queue item")
    a = ap.parse_args()
    errs = check(a.name)
    if errs:
        sys.exit("Not queued:\n  " + "\n  ".join(errs))
    at = iso(parse(a.at)) if a.at else iso(now()) if a.now else None if a.hold else next_slot()
    title = json.load(open(os.path.join(REELS, a.name, "script.json"))).get("title") if os.path.exists(os.path.join(REELS, a.name, "script.json")) else a.name
    store_media([a.name])
    item = make_item(a.name, at, a.hold, title)
    write(os.path.join(QUEUE, f"{a.name}.json"), item)
    print(f"queued {a.name} for {at or 'HOLD'} -> {', '.join(item['platforms'])}")
    if a.push:
        sh("git", "add", "queue", "reels")
        sh("git", "commit", "-m", f"queue {a.name}")
        sh("git", "pull", "--rebase")
        sh("git", "push", capture=False)
    else:
        print('next: git add queue reels && git commit -m "queue %s" && git pull --rebase && git push' % a.name)


if __name__ == "__main__":
    main()
