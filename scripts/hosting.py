"""Temporary public hosting: Instagram can only fetch a video from a public URL, so each video is attached
to a short-lived release in the public MEDIA_REPO and the release is deleted right after publishing."""
import base64
import os

from common import gh, now


def ensure_initialized(repo):
    """GitHub can't create releases in a repo with no commits: give an empty media repo its first file."""
    try:
        gh("GET", f"/repos/{repo}/commits", params={"per_page": 1})
        return False
    except RuntimeError as e:
        if "409" not in str(e) and "empty" not in str(e).lower():
            raise
    readme = "# Stackby reels media\n\nTemporary public hosting for the reels robot: each video is attached to a short-lived release so Instagram can fetch it, then deleted.\n"
    gh("PUT", f"/repos/{repo}/contents/README.md", json={"message": "Initialize media repo", "content": base64.b64encode(readme.encode()).decode()})
    return True


def host(name, files):
    """files: {label: local path} -> (release_id, {label: public url})"""
    repo = os.environ["MEDIA_REPO"]
    ensure_initialized(repo)
    tag = f"tmp-{name}-{now().strftime('%Y%m%d%H%M%S')}"
    rel = gh("POST", f"/repos/{repo}/releases", json={"tag_name": tag, "name": tag, "body": "Temporary upload for Instagram. Deleted automatically.", "prerelease": True})
    urls = {}
    for label, path in files.items():
        ctype = "video/mp4" if path.endswith(".mp4") else "image/jpeg"
        with open(path, "rb") as f:
            asset = gh("POST", f"https://uploads.github.com/repos/{repo}/releases/{rel['id']}/assets?name={os.path.basename(path)}",
                       headers={"Content-Type": ctype}, data=f, timeout=600)
        urls[label] = asset["browser_download_url"]
    return rel["id"], urls, tag


def unhost(release_id, tag):
    repo = os.environ["MEDIA_REPO"]
    try:
        gh("DELETE", f"/repos/{repo}/releases/{release_id}")
        gh("DELETE", f"/repos/{repo}/git/refs/tags/{tag}")
    except RuntimeError as e:  # cleanup must never fail a post
        print("cleanup warning:", e)
