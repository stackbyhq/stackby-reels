# Stackby reels automation

Every Stackby video goes live automatically: **Instagram Reel + YouTube Short** (vertical file) and a
**long-form YouTube video** (landscape file, with its custom thumbnail), with the caption, title, tags and a
first comment, at its scheduled time. A Telegram message arrives after every post or failure, a daily digest
at 09:00 IST, and the **Google Sheets tracker** updates every day and after every posting run.

Built to the "Reels Automation: Full Setup Guide (Instagram + YouTube)": one queue in GitHub, GitHub Actions
robots that post through the official Instagram and YouTube APIs, tokens stored only as GitHub secrets.

```
you (once)                 GitHub repo stackby-reels                  outputs
bulk_enqueue.py ──► queue/<video>.json + media branch ──► post-reel robot ──► Instagram Reel + first comment
(all 39 videos)            (one file per video)          (GitHub Actions) ──► YouTube Short
                                                                          ──► YouTube video (+ thumbnail)
                                                                          ──► Telegram ✅ / ❌
                                                                          ──► Google Sheet tracker
```

Tracker: [Stackby Video Posting Tracker](https://docs.google.com/spreadsheets/d/1OTJRHzf1OUDkENIs_dq3IPuvicJAN7nk29tSMHI6hV8/edit)

## What's already done

* All 39 videos' captions, Shorts titles, YouTube titles/descriptions/tags and first comments are in
  `data/captions.json` (built from the "Stackby Video Captions" Google Doc by `scripts/build_captions.py`),
  in a posting order that alternates Stackby + AI, comparisons and industry portals.
* The robots: `post.yml` (posting), `refresh-token.yml` (Instagram token renewal on the 1st and 15th),
  `notify.yml` (Telegram link + daily digest), `dry-run.yml` (full check without publishing),
  `sheet-sync.yml` (daily tracker refresh).
* The tracker sheet with Tracker, Summary and How-it-works tabs.

## One-time setup (about half a day)

### 1 · GitHub (5 min)
1. Create two repos in the stackbyhq org: **`stackby-reels`** (private, empty) and **`stackby-reels-media`**
   (**public**, empty: Instagram can only fetch videos from a public link; each video sits there a few
   minutes as a temporary release, then is deleted).
2. Push this folder to `stackby-reels` (or ask Claude to push it once the repo exists).
3. `stackby-reels` → Settings → Actions → General → Workflow permissions → **Read and write** → Save.
4. Fine-grained personal access token (avatar → Settings → Developer settings → Fine-grained tokens):
   repository access **only the two repos**; permissions **Contents: Read and write, Actions: Read and
   write, Secrets: Read and write** (Metadata is added automatically); longest expiry, set a reminder.
   Save it as secret **`BOT_PAT`**.
5. Nothing else: `MEDIA_REPO` (`stackbyhq/stackby-reels-media`) and `SHEET_ID` (the tracker) are built into the
   workflows. Override them under Settings → Secrets and variables → Actions → Variables only if they change.
   Every workflow starts with `setup_check.py`, which lists any secret that is still missing.

### 2 · Instagram (15 min)
1. The Stackby Instagram must be a **Business or Creator** account, and public.
2. developers.facebook.com/apps → Create App → use case **Other** → type **Business**.
3. Add the **Instagram** product → Set up (API setup with Instagram login) → add the Stackby account →
   **Generate token**. Permissions: `instagram_business_basic`, `instagram_business_content_publish`,
   `instagram_business_manage_comments`, `instagram_business_manage_insights` (not manage_messages).
4. Save it as secret **`IG_ACCESS_TOKEN`**. The app can stay in development mode for your own account.
   Both Meta token types work: **`IGAA…`** (Instagram Login, renews itself) or **`EAA…`** (Facebook Login: the
   Stackby Instagram must be linked to a Facebook Page; token permissions `instagram_basic`,
   `instagram_content_publish`, `instagram_manage_comments`, `instagram_manage_insights`, `pages_show_list`,
   `pages_read_engagement`; also add **`FB_APP_ID`** and **`FB_APP_SECRET`** from App settings → Basic so the
   robot can renew it, and exchange a short-lived token for a 60-day one first, see below).
   `refresh-token.yml` renews it every 1st and 15th; if the robot is off for 60 days, generate a new one.

### 3 · YouTube (20 min)
1. console.cloud.google.com → new project → APIs & Services → Library → enable **YouTube Data API v3**
   (and **Google Sheets API**, used by the tracker in step 5).
2. Google Auth Platform → Get started → External → add your Google account as a test user →
   **Publish app** (in "Testing", refresh tokens die after 7 days).
3. Clients → Create client → **Desktop app** → save the ID and secret as **`YT_CLIENT_ID`** and **`YT_CLIENT_SECRET`**.
4. On your computer: `python3 scripts/yt_auth.py`, log in with the account that owns the Stackby channel,
   save the printed token as **`YT_REFRESH_TOKEN`**.
5. **Day one:** apply for the "YouTube API Services: Audit and Quota Extension". Until it's approved, YouTube
   keeps API uploads **private**; the tracker flags them and you can make them public in YouTube Studio.
   Quota: each upload costs ~1,600 of the 10,000 daily units, so one video a day (Short + long-form) fits easily.

### 4 · Telegram (5 min)
1. @BotFather → `/newbot` → save the token as **`TELEGRAM_BOT_TOKEN`**.
2. Open the bot, press **Start**.
3. Write anything into `ops/telegram-setup.trigger`, commit, push. The bot replies "bot connected".

### 5 · Google Sheets tracker (5 min)
1. Same Google Cloud project → IAM & Admin → Service accounts → Create → no roles needed → Keys → Add key →
   JSON. Save the whole JSON file content as secret **`GOOGLE_SERVICE_ACCOUNT_JSON`**.
2. Open the tracker sheet → Share → add the service account's email (…@….iam.gserviceaccount.com) as **Editor**.

### 6 · Queue all the videos (one command)
Put the files you already have in one folder (sub-folders are fine, e.g. the unzipped thumbnails zip):
`stackby-<name>-vertical.mp4`, `stackby-<name>-landscape.mp4`, `stackby-<name>-cover-reels-1080x1920.jpg`,
`stackby-<name>-thumbnail…jpg`. Then, in the repo folder:

```bash
pip install -r requirements.txt
python3 scripts/bulk_enqueue.py --from ~/Downloads/stackby-videos --check        # shows the schedule, queues nothing
python3 scripts/bulk_enqueue.py --from ~/Downloads/stackby-videos --start 2026-11-25
```

It copies each video, writes its captions (`reels/<name>/post.json`), stores the files on the `media` branch,
schedules one video a day at 12:30 IST in the order of `data/captions.json`, and pushes. Missing files are
skipped and listed; run it again later and it only queues what's new.

### 7 · Dry run before the first real post
Write a video name (e.g. `13-ai-fields-data-entry`) into `ops/dryrun.trigger` and push. The dry run checks every
token, the media repo, Telegram, the files and the captions, without publishing, and reports to Telegram and
`ops/status/dry-run.log`.

## Day to day

| Want to… | Do |
|---|---|
| See what's posted where | The tracker sheet (updates daily + after every post) or the Telegram digest |
| Post a video now | `python3 scripts/enqueue.py <name> --now --push` (files in `out/<name>/`) |
| Move a video | edit `"at"` in `queue/<name>.json` (UTC) and push |
| Park a video | set `"status": "hold"` in its queue file |
| Two posts a day | add `"19:00"` to `SLOTS` in `scripts/enqueue.py` and add a cron near 13:30 UTC in `post.yml` |
| Skip long-form YouTube | delete `"youtube_long"` from the item's `platforms` |
| Add new videos | add their captions to `data/captions.json` (or the Google Doc, then `build_captions.py`) and rerun `bulk_enqueue.py` |
| Post right away if a scheduled run was skipped | Actions → post-reel → Run workflow |

After a post the item moves from `queue/` to `posted/` with every link, a permanent copy is archived as a
release, Telegram gets ✅ with the video, and the sheet updates. If one platform fails, only that platform is
retried on the next run (up to 3 tries); nothing is ever posted twice.

## Secrets and variables

| Name | Kind | From | Expires |
|---|---|---|---|
| `BOT_PAT` | secret | GitHub step 4 | when you chose |
| `IG_ACCESS_TOKEN` | secret | Instagram step 3 | 60 days, renewed automatically |
| `FB_APP_ID`, `FB_APP_SECRET` | secrets, only for `EAA…` tokens | Meta app → App settings → Basic | never |
| `IG_USER_ID` | optional secret | Instagram account id, if the token can't find it via your Pages | never |
| `YT_CLIENT_ID`, `YT_CLIENT_SECRET` | secret | YouTube step 3 | never |
| `YT_REFRESH_TOKEN` | secret | `yt_auth.py` | not while the app is in production |
| `TELEGRAM_BOT_TOKEN` | secret | BotFather | never |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | secret | Tracker step 1 | never (delete the key to revoke) |
| `MEDIA_REPO`, `SHEET_ID` | optional variables | built in | — |

Never paste a token into a chat, email or file in the repo. If one leaks, revoke it and save a new one.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Instagram "token"/"session expired" | Generate a new token (Instagram step 3), save `IG_ACCESS_TOKEN` |
| Instagram `container ERROR` on one video | Re-export as H.264/AAC 1080×1920 and re-queue |
| YouTube `invalid_grant` | Publish the OAuth app to production, rerun `yt_auth.py` |
| YouTube video private | Audit pending: make it public in YouTube Studio |
| Nothing posted at the slot | GitHub skipped the scheduled run: Actions → post-reel → Run workflow |
| No Telegram messages | Repeat Telegram step 3 |
| Sheet not updating | Check `GOOGLE_SERVICE_ACCOUNT_JSON`, `SHEET_ID`, and that the sheet is shared with the service account |
