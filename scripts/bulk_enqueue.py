"""Queue every video in one go from the folder of files you already have.

  python3 scripts/bulk_enqueue.py --from ~/Downloads/stackby-videos [--start 2026-11-25] [--only 13-ai-fields-data-entry ...] [--check]

The folder may contain sub-folders (e.g. the unzipped thumbnails zip). Files are matched by name:
  stackby-<name>-vertical.mp4            -> Instagram Reel + YouTube Short   (required)
  stackby-<name>-cover-reels-1080x1920.jpg -> Reel cover                    (optional)
  stackby-<name>-landscape.mp4           -> long-form YouTube video          (optional)
  stackby-<name>-thumbnail*.jpg          -> long-form YouTube thumbnail      (optional)
Captions, titles, tags and first comments come from data/captions.json (built from the captions Google Doc).
Videos are scheduled one per slot (SLOTS in enqueue.py) in the order of data/captions.json.
"""
import argparse
import datetime as dt
import glob
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import enqueue as E  # noqa: E402
from common import CAPTIONS, IST, OUTDIR, QUEUE, REELS, ist, now, read, sh, write  # noqa: E402


def find(folder, pattern):
    hits = sorted(glob.glob(os.path.join(folder, "**", pattern), recursive=True), key=lambda p: (-os.path.getmtime(p), p))
    return hits[0] if hits else None


def prepare(c, folder):
    name = c["name"]
    src = {"reel.mp4": find(folder, c["files"]["vertical"]), "cover.jpg": find(folder, c["files"]["cover"]),
           "landscape.mp4": find(folder, c["files"]["landscape"]), "thumb.jpg": find(folder, f"stackby-{name}-thumbnail*.jpg")}
    if not src["reel.mp4"]:
        return None
    d = os.path.join(OUTDIR, name)
    os.makedirs(d, exist_ok=True)
    for dst, s in src.items():
        if s:
            shutil.copy2(s, os.path.join(d, dst))
    write(os.path.join(REELS, name, "script.json"), {"title": c["title"]})
    write(os.path.join(REELS, name, "post.json"), {k: c[k] for k in ("caption", "first_comment", "yt_title", "yt_description", "yt_long_title", "yt_long_description", "yt_tags")})
    return [k for k, v in src.items() if v]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="folder", required=True)
    ap.add_argument("--start", help="first posting date (IST), default tomorrow")
    ap.add_argument("--only", nargs="*", help="queue only these names")
    ap.add_argument("--check", action="store_true", help="validate files and print the schedule without queuing")
    ap.add_argument("--no-push", action="store_true")
    a = ap.parse_args()
    folder = os.path.expanduser(a.folder)
    caps = read(CAPTIONS)
    already = {os.path.basename(p)[:-5] for p in glob.glob(os.path.join(QUEUE, "*.json"))} | {os.path.basename(p)[:-5] for p in glob.glob(os.path.join(os.path.dirname(QUEUE), "posted", "*.json"))}
    start = dt.datetime.fromisoformat(a.start).replace(tzinfo=IST) if a.start else (now().astimezone(IST) + dt.timedelta(days=1)).replace(hour=0, minute=0)
    after, used = start - dt.timedelta(minutes=1), E.taken()
    ready, missing, problems = [], [], []
    for c in caps:
        if (a.only and c["name"] not in a.only) or c["name"] in already:
            continue
        got = prepare(c, folder)
        if got is None:
            missing.append(c["files"]["vertical"])
            continue
        errs = E.check(c["name"])
        if errs:
            problems.append((c["name"], errs))
            continue
        at = E.next_slot(after, used)
        used.add(at)
        after = dt.datetime.fromisoformat(at.replace("Z", "+00:00"))
        ready.append((c, at, got))
    for c, at, got in ready:
        print(f"{c['order']:>2}. {ist(at)}  {c['name']:<34} {', '.join(got)}")
    for n, errs in problems:
        print(f"!! {n}: {'; '.join(errs)}")
    if missing:
        print(f"-- {len(missing)} videos not found in {folder} (skipped): {', '.join(missing[:6])}{' …' if len(missing) > 6 else ''}")
    if a.check or not ready:
        print("check only, nothing queued" if a.check else "nothing to queue")
        return
    names = [c["name"] for c, _, _ in ready]
    print(f"storing {len(names)} videos on the media branch (one-time upload, this can take a while)…")
    E.store_media(names, push=not a.no_push)
    for c, at, _ in ready:
        write(os.path.join(QUEUE, f"{c['name']}.json"), E.make_item(c["name"], at, title=c["title"]))
    if not a.no_push:
        sh("git", "add", "queue", "reels")
        sh("git", "commit", "-m", f"queue {len(names)} videos")
        sh("git", "pull", "--rebase")
        sh("git", "push", capture=False)
    print(f"queued {len(names)} videos: first {ready[0][1]}, last {ready[-1][1]} (UTC)")


if __name__ == "__main__":
    main()
