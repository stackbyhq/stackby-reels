"""Dry run: everything except publishing.  Triggered by writing a video name into ops/dryrun.trigger.
Checks every token, the media repo, Telegram, and for each named video its queue item, files on the media
branch, specs and caption limits. Writes ops/status/dry-run.log and sends the result to Telegram."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import enqueue as E  # noqa: E402
import post_instagram as IG  # noqa: E402
import post_youtube as YT  # noqa: E402
import telegram  # noqa: E402
from common import CHANNEL, OPS, QUEUE, STATUS, gh, git_commit_push, iso, media_files, now  # noqa: E402


def media_repo():
    r = gh("GET", f"/repos/{os.environ['MEDIA_REPO']}")
    if r["private"]:
        raise RuntimeError(f"{r['full_name']} is private: Instagram cannot fetch videos from it")
    return f"{r['full_name']} (public)"


def telegram_linked():
    if not os.path.exists(telegram.CHAT_FILE):
        raise RuntimeError("chat not linked (README, Telegram step 4)")
    return "linked"


def video(name):
    if not os.path.exists(os.path.join(QUEUE, f"{name}.json")):
        raise RuntimeError("no queue item")
    files = media_files(name)
    errs = E.check(name)
    if errs:
        raise RuntimeError("; ".join(errs))
    return "files: " + ", ".join(files)


def main():
    names = open(os.path.join(OPS, "dryrun.trigger")).read().split()
    log = [f"Dry run {iso(now())}"]
    checks = [("Instagram token", lambda: "@" + IG.account().get("username", "?")), ("YouTube token", YT.channel),
              ("Media repo", media_repo), ("Telegram", telegram_linked)] + [(f"Video {n}", lambda n=n: video(n)) for n in names]
    for label, fn in checks:
        try:
            log.append(f"OK   {label}: {fn()}")
        except Exception as e:
            log.append(f"FAIL {label}: {e}")
    text = "\n".join(log)
    os.makedirs(STATUS, exist_ok=True)
    with open(os.path.join(STATUS, "dry-run.log"), "w") as f:
        f.write(text + "\n")
    print(text)
    telegram.send(("✅" if "FAIL" not in text else "⚠️") + f" {CHANNEL} dry run\n\n" + text)
    git_commit_push(["ops/status"], "dry run result [skip ci]")


if __name__ == "__main__":
    main()
