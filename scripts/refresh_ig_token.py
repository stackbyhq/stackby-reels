"""Trade the Instagram long-lived token for a fresh 60-day one and save it back into the IG_ACCESS_TOKEN secret."""
import base64
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nacl import encoding, public  # noqa: E402

import post_instagram as IG  # noqa: E402
import telegram  # noqa: E402
from common import CHANNEL, gh, gh_repo  # noqa: E402


def save_secret(name, value):
    repo = gh_repo()
    key = gh("GET", f"/repos/{repo}/actions/secrets/public-key")
    box = public.SealedBox(public.PublicKey(key["key"].encode(), encoding.Base64Encoder()))
    enc = base64.b64encode(box.encrypt(value.encode())).decode()
    gh("PUT", f"/repos/{repo}/actions/secrets/{name}", json={"encrypted_value": enc, "key_id": key["key_id"]})


def main():
    try:
        token, expires = IG.refresh_token()
        save_secret("IG_ACCESS_TOKEN", token)
        days = int(expires or 0) // 86400
        print(f"Instagram token refreshed, valid {days} days")
        telegram.send(f"🔑 {CHANNEL}: Instagram token renewed (valid {days} days).")
    except Exception as e:
        telegram.send(f"❌ {CHANNEL}: Instagram token refresh failed: {e}\nGenerate a new token (README, Instagram step 4) and save it as IG_ACCESS_TOKEN.")
        raise


if __name__ == "__main__":
    main()
