"""The posting robot (run by .github/workflows/post.yml).

For every queue item whose time has passed: fetch its files from the media branch, post the Reel to Instagram
(through a temporary public release), upload the Short (and the long-form video, if there is one) to YouTube,
add the first comment, then move the item to posted/ with the links, archive a permanent copy as a release,
send a Telegram alert and refresh the Google Sheets tracker. A platform that fails is retried on the next run
(up to MAX_ATTEMPTS); platforms that already succeeded are never posted twice.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import archive  # noqa: E402
import hosting  # noqa: E402
import post_instagram as IG  # noqa: E402
import post_youtube as YT  # noqa: E402
import telegram  # noqa: E402
from common import CHANNEL, MAX_ATTEMPTS, POSTED, QUEUE, git_commit_push, iso, items, media_files, now, parse, post_meta, write  # noqa: E402

PER_RUN = int(os.environ.get("POSTS_PER_RUN", "2"))  # keeps YouTube within its daily quota


def due():
    t = now()
    return [i for i in items(QUEUE) if i.get("status") in ("queued", "partial") and i.get("at") and parse(i["at"]) <= t and i.get("attempts", 0) < MAX_ATTEMPTS]


def post_one(item):
    name = item["name"]
    meta = post_meta(name)
    files = media_files(name)
    if "reel.mp4" not in files:
        raise RuntimeError(f"media/{name}/reel.mp4 not found on the media branch")
    p = item["platforms"]
    item["attempts"] = item.get("attempts", 0) + 1
    for plat, run in (("instagram", lambda: post_ig(name, files, meta)),
                      ("youtube_short", lambda: YT.upload(files["reel.mp4"], meta["yt_title"], meta.get("yt_description", meta["caption"]), meta.get("yt_tags"), short=True)),
                      ("youtube_long", lambda: YT.upload(files["landscape.mp4"], meta.get("yt_long_title", meta["yt_title"]), meta.get("yt_long_description", ""),
                                                         meta.get("yt_tags"), thumb=files.get("thumb.jpg"), short=False))):
        if plat not in p or p[plat].get("status") == "posted":
            continue
        try:
            res = run()
            p[plat] = {"status": "posted", "posted_at": iso(now()), **res}
        except Exception as e:  # keep going with the other platforms
            traceback.print_exc()
            p[plat] = {"status": "failed", "error": str(e)[:500], "failed_at": iso(now())}
    ok = all(v.get("status") == "posted" for v in p.values())
    item["status"] = "posted" if ok else ("failed" if item["attempts"] >= MAX_ATTEMPTS else "partial")
    item["updated_at"] = iso(now())
    return item, files


def post_ig(name, files, meta):
    rel_id, urls, tag = hosting.host(name, {k: v for k, v in (("video", files["reel.mp4"]), ("cover", files.get("cover.jpg"))) if v})
    try:
        return IG.publish_reel(urls["video"], meta["caption"], urls.get("cover"), meta.get("first_comment"))
    finally:
        hosting.unhost(rel_id, tag)


def summary(item):
    lines = []
    for plat, v in item["platforms"].items():
        label = {"instagram": "Instagram", "youtube_short": "YouTube Short", "youtube_long": "YouTube video"}[plat]
        if v.get("status") == "posted":
            extra = " (private: YouTube audit pending)" if v.get("privacy") == "private" else ""
            lines.append(f"✅ {label}: {v.get('url')}{extra}")
        else:
            lines.append(f"❌ {label}: {v.get('error', v.get('status'))}")
    return "\n".join(lines)


def main():
    todo = due()[:PER_RUN]
    if not todo:
        print("nothing due")
        return
    for item in todo:
        name = item["name"]
        files = {}
        try:
            item, files = post_one(item)
        except Exception as e:
            traceback.print_exc()
            item["attempts"] = item.get("attempts", 0) + 1
            item["status"] = "failed" if item["attempts"] >= MAX_ATTEMPTS else "partial"
            item["error"] = str(e)[:500]
        if item["status"] == "posted":
            try:
                item["archive"] = archive.archive(name, files)
            except Exception as e:
                print("archive warning:", e)
            write(os.path.join(POSTED, f"{name}.json"), item)
            os.remove(os.path.join(QUEUE, f"{name}.json"))
            telegram.send(f"✅ {CHANNEL} posted: {item['title']}\n\n{summary(item)}", video=files.get("reel.mp4"))
        else:
            write(os.path.join(QUEUE, f"{name}.json"), item)
            retry = "will retry on the next run" if item["status"] == "partial" else "gave up after 3 attempts, fix and re-queue"
            telegram.send(f"❌ {CHANNEL}: problem posting {item['title']} ({retry})\n\n{summary(item) if 'platforms' in item else item.get('error')}")
        git_commit_push(["queue", "posted"], f"posted: {name} ({item['status']}) [skip ci]")
    try:
        import sheet_sync
        sheet_sync.run()
    except Exception as e:
        print("sheet sync skipped:", e)


if __name__ == "__main__":
    main()
