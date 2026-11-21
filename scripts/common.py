"""Shared helpers: paths, queue items, time, GitHub API, media download."""
import datetime as dt
import glob
import json
import os
import subprocess

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEUE = os.path.join(ROOT, "queue")
POSTED = os.path.join(ROOT, "posted")
REELS = os.path.join(ROOT, "reels")
OUTDIR = os.path.join(ROOT, "out")
OPS = os.path.join(ROOT, "ops")
STATUS = os.path.join(OPS, "status")
CAPTIONS = os.path.join(ROOT, "data", "captions.json")
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
CHANNEL = os.environ.get("CHANNEL_NAME", "Stackby")
PLATFORMS = ("instagram", "youtube_short", "youtube_long")
MAX_ATTEMPTS = 3


def now():
    return dt.datetime.now(dt.timezone.utc)


def iso(t):
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def ist(s):
    return parse(s).astimezone(IST).strftime("%a %d %b %Y, %I:%M %p IST") if s else ""


def read(path):
    with open(path) as f:
        return json.load(f)


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")


def items(folder):
    return [read(p) for p in sorted(glob.glob(os.path.join(folder, "*.json")))]


def captions():
    return {c["name"]: c for c in read(CAPTIONS)} if os.path.exists(CAPTIONS) else {}


def post_meta(name):
    """post.json written at enqueue time (caption, titles, tags, first comment)."""
    return read(os.path.join(REELS, name, "post.json"))


def sh(*cmd, check=True, cwd=ROOT, capture=True):
    r = subprocess.run(cmd, cwd=cwd, check=False, text=True, capture_output=capture)
    if check and r.returncode:
        raise RuntimeError(f"{' '.join(cmd)} failed: {(r.stderr or r.stdout or '').strip()[-600:]}")
    return (r.stdout or "").strip()


# ------------------------------------------------------------------ GitHub
def gh_repo():
    return os.environ.get("GITHUB_REPOSITORY") or sh("git", "config", "--get", "remote.origin.url").split("github.com")[-1].lstrip(":/").removesuffix(".git")


def gh(method, url, token=None, **kw):
    token = token or os.environ["BOT_PAT"]
    if not url.startswith("http"):
        url = "https://api.github.com" + url
    h = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    h.update(kw.pop("headers", {}))
    r = requests.request(method, url, headers=h, timeout=kw.pop("timeout", 120), **kw)
    if r.status_code >= 400:
        raise RuntimeError(f"GitHub {method} {url} -> {r.status_code}: {r.text[:400]}")
    return r.json() if r.text and "json" in r.headers.get("content-type", "") else r


def media_files(name):
    """Fetch only this video's files from the `media` branch (partial clone keeps runs fast)."""
    dest = os.path.join(OUTDIR, name)
    os.makedirs(dest, exist_ok=True)
    sh("git", "fetch", "--depth=1", "--filter=blob:none", "origin", "media")
    found = {}
    for f in ("reel.mp4", "cover.jpg", "landscape.mp4", "thumb.jpg"):
        path = f"media/{name}/{f}"
        if subprocess.run(["git", "cat-file", "-e", f"FETCH_HEAD:{path}"], cwd=ROOT, capture_output=True).returncode == 0:
            with open(os.path.join(dest, f), "wb") as out:
                subprocess.run(["git", "show", f"FETCH_HEAD:{path}"], cwd=ROOT, check=True, stdout=out)
            found[f] = os.path.join(dest, f)
    return found


def git_commit_push(paths, message):
    """Commit queue/posted/ops changes back to the repo (retrying on races with other runs)."""
    sh("git", "config", "user.name", f"{CHANNEL} reels bot")
    sh("git", "config", "user.email", "reels-bot@users.noreply.github.com")
    sh("git", "add", "-A", *paths)
    if not sh("git", "status", "--porcelain", *paths):
        return False
    sh("git", "commit", "-m", message)
    for _ in range(4):
        if subprocess.run(["git", "push"], cwd=ROOT).returncode == 0:
            return True
        sh("git", "pull", "--rebase", "--autostash")
    raise RuntimeError("git push failed after retries")
