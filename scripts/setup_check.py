"""Print which secrets/settings are in place (never their values). Runs at the start of every workflow."""
import os

NEEDED = [("BOT_PAT", "GitHub token so the robots can push and manage releases (README 1.4)"),
          ("IG_ACCESS_TOKEN", "Instagram posting token (README 2)"),
          ("YT_CLIENT_ID", "YouTube OAuth client ID (README 3)"),
          ("YT_CLIENT_SECRET", "YouTube OAuth client secret (README 3)"),
          ("YT_REFRESH_TOKEN", "YouTube upload permission from yt_auth.py (README 3)"),
          ("TELEGRAM_BOT_TOKEN", "Telegram alerts (README 4, optional)"),
          ("GOOGLE_SERVICE_ACCOUNT_JSON", "Google Sheets tracker (README 5)")]


def missing():
    return [(k, why) for k, why in NEEDED if not os.environ.get(k)]


if __name__ == "__main__":
    miss = missing()
    for k, why in NEEDED:
        print(f"{'OK     ' if os.environ.get(k) else 'MISSING'} {k:<28} {why}")
    tok = os.environ.get("IG_ACCESS_TOKEN", "")
    if tok and not tok.startswith("IG"):
        print("Instagram token type: Facebook Login (EAA…). Needs the Instagram account linked to a Facebook Page.")
        for k in ("FB_APP_ID", "FB_APP_SECRET"):
            print(f"{'OK     ' if os.environ.get(k) else 'MISSING'} {k:<28} needed to renew a Facebook-login token every 60 days")
    elif tok:
        print("Instagram token type: Instagram Login (IGAA…), renews itself")
    print(f"MEDIA_REPO={os.environ.get('MEDIA_REPO')}  SHEET_ID={os.environ.get('SHEET_ID')}")
    if miss:
        print(f"::warning::{len(miss)} secret(s) missing: {', '.join(k for k, _ in miss)}. Add them in Settings → Secrets and variables → Actions.")
