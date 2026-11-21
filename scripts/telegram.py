"""Telegram alerts: a message (with the video when possible) after every post or failure."""
import os

import requests

from common import OPS

CHAT_FILE = os.path.join(OPS, "telegram_chat_id")


def _chat():
    tok = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not tok or not os.path.exists(CHAT_FILE):
        return None, None
    return tok, open(CHAT_FILE).read().strip()


def send(text, video=None):
    tok, chat = _chat()
    if not tok:
        print("[telegram skipped]", text)
        return
    try:
        if video and os.path.exists(video) and os.path.getsize(video) < 49 * 1024 * 1024:
            with open(video, "rb") as f:
                r = requests.post(f"https://api.telegram.org/bot{tok}/sendVideo", data={"chat_id": chat, "caption": text[:1024], "supports_streaming": "true"},
                                  files={"video": f}, timeout=300)
        else:
            r = requests.post(f"https://api.telegram.org/bot{tok}/sendMessage", data={"chat_id": chat, "text": text[:4000], "disable_web_page_preview": "true"}, timeout=60)
        if not r.ok:
            print("telegram error:", r.text[:300])
    except requests.RequestException as e:
        print("telegram error:", e)


def find_chat():
    tok = os.environ["TELEGRAM_BOT_TOKEN"]
    upd = requests.get(f"https://api.telegram.org/bot{tok}/getUpdates", timeout=60).json().get("result", [])
    chats = [u.get("message", u.get("my_chat_member", {})).get("chat", {}).get("id") for u in upd]
    chats = [c for c in chats if c]
    return chats[-1] if chats else None
