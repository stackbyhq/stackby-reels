"""Telegram housekeeping.
  python3 scripts/notify.py setup   -> find the chat that pressed Start, save ops/telegram_chat_id, say "bot connected"
  python3 scripts/notify.py digest  -> the daily insights digest (scripts/digest.py), once per IST day
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import telegram  # noqa: E402
from common import CHANNEL, git_commit_push  # noqa: E402


def setup():
    chat = telegram.find_chat()
    if not chat:
        sys.exit("No chat found: open your bot in Telegram, press Start (send it any message), then push the trigger again.")
    with open(telegram.CHAT_FILE, "w") as f:
        f.write(str(chat))
    telegram.send(f"🤖 {CHANNEL} reels bot connected. You'll get a message after every post or failure, and a daily digest.")
    git_commit_push(["ops"], "telegram: link chat [skip ci]")


def digest():
    import digest as D  # the daily insights digest
    D.main()


if __name__ == "__main__":
    {"setup": setup, "digest": digest}[sys.argv[1]]()
