"""Permanent copy of every posted video as a release in this (private) repo."""
import os

from common import gh, gh_repo


def archive(name, files):
    repo = gh_repo()
    tag = f"posted-{name}"
    try:
        rel = gh("POST", f"/repos/{repo}/releases", json={"tag_name": tag, "name": f"Posted: {name}", "body": "Archived copy of the posted video."})
    except RuntimeError as e:
        if "already_exists" in str(e):
            return f"https://github.com/{repo}/releases/tag/{tag}"
        raise
    for label in ("reel.mp4", "landscape.mp4", "cover.jpg", "thumb.jpg"):
        path = files.get(label)
        if path and os.path.exists(path):
            with open(path, "rb") as f:
                gh("POST", f"https://uploads.github.com/repos/{repo}/releases/{rel['id']}/assets?name={label}",
                   headers={"Content-Type": "application/octet-stream"}, data=f, timeout=900)
    return rel["html_url"]
