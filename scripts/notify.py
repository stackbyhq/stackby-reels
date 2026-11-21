"""Telegram housekeeping.
  python3 scripts/notify.py setup   -> find the chat that pressed Start, save ops/telegram_chat_id, say "bot connected"
  python3 scripts/notify.py digest  -> refresh stats, send the daily digest, sync the Google Sheet
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stats  # noqa: E402
import telegram  # noqa: E402
from common import CHANNEL, IST, POSTED, QUEUE, git_commit_push, ist, items, now, parse  # noqa: E402


def setup():
    chat = telegram.find_chat()
    if not chat:
        sys.exit("No chat found: open your bot in Telegram, press Start (send it any message), then push the trigger again.")
    with open(telegram.CHAT_FILE, "w") as f:
        f.write(str(chat))
    telegram.send(f"🤖 {CHANNEL} reels bot connected. You'll get a message after every post or failure, and a daily digest.")
    git_commit_push(["ops"], "telegram: link chat [skip ci]")


def digest():
    stats.collect()
    posted, queue = items(POSTED), items(QUEUE)
    t = now()
    day = dt.timedelta(days=1)
    last24 = [i for i in posted if any(p.get("posted_at") and t - parse(p["posted_at"]) < day for p in i["platforms"].values())]
    upcoming = sorted([i for i in queue if i.get("status") in ("queued", "partial") and i.get("at") and parse(i["at"]) - t < day], key=lambda i: i["at"])
    problems = [i for i in queue if i.get("status") in ("failed", "partial")]
    ig_views = sum(i.get("stats", {}).get("instagram", {}).get("views", 0) or 0 for i in posted)
    yt_views = sum((i.get("stats", {}).get(k, {}) or {}).get("views", 0) or 0 for i in posted for k in ("youtube_short", "youtube_long"))
    lines = [f"📊 {CHANNEL} daily digest · {t.astimezone(IST):%a %d %b}",
             f"Posted so far: {len(posted)} · Queued: {sum(1 for i in queue if i.get('status') == 'queued')} · On hold: {sum(1 for i in queue if i.get('status') == 'hold')}",
             f"Total views: Instagram {ig_views:,} · YouTube {yt_views:,}"]
    if last24:
        lines.append("\nLast 24h:\n" + "\n".join(f"• {i['title']}" for i in last24))
    if upcoming:
        lines.append("\nNext 24h:\n" + "\n".join(f"• {ist(i['at'])}: {i['title']}" for i in upcoming))
    if problems:
        lines.append("\n⚠️ Needs attention:\n" + "\n".join(f"• {i['title']} ({i['status']})" for i in problems))
    best = sorted(posted, key=lambda i: -(i.get("stats", {}).get("instagram", {}).get("views", 0) or 0))[:3]
    if best and ig_views:
        lines.append("\n🏆 Top reels:\n" + "\n".join(f"• {i['title']}: {i['stats']['instagram'].get('views', 0):,} views" for i in best))
    telegram.send("\n".join(lines))
    git_commit_push(["posted", "queue"], "stats: daily refresh [skip ci]")
    try:
        import sheet_sync
        sheet_sync.run()
    except Exception as e:
        print("sheet sync skipped:", e)


if __name__ == "__main__":
    {"setup": setup, "digest": digest}[sys.argv[1]]()
