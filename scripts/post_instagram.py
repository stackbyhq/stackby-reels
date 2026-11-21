"""Instagram Reels via the Instagram API with Instagram Login (graph.instagram.com)."""
import os
import time

import requests

API = "https://graph.instagram.com/v21.0"


def _req(method, path, **params):
    params["access_token"] = os.environ["IG_ACCESS_TOKEN"]
    r = requests.request(method, f"{API}/{path}", params=params if method == "GET" else None, data=params if method != "GET" else None, timeout=120)
    j = r.json() if r.text else {}
    if r.status_code >= 400 or "error" in j:
        err = j.get("error", {})
        raise RuntimeError(f"Instagram {path}: {err.get('message', r.text[:300])} (code {err.get('code')}, sub {err.get('error_subcode')})")
    return j


def account():
    return _req("GET", "me", fields="user_id,username")


def publish_reel(video_url, caption, cover_url=None, first_comment=None, wait=600):
    """Create a REELS container, wait until Instagram has processed it, publish, then comment."""
    me = account()
    uid = me["user_id"]
    params = {"media_type": "REELS", "video_url": video_url, "caption": caption, "share_to_feed": "true"}
    if cover_url:
        params["cover_url"] = cover_url
    container = _req("POST", f"{uid}/media", **params)["id"]
    t0 = time.time()
    while True:
        st = _req("GET", container, fields="status_code,status")
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram container {st.get('status_code')}: {st.get('status', '')}")
        if time.time() - t0 > wait:
            raise RuntimeError("Instagram processing timed out")
        time.sleep(10)
    media_id = _req("POST", f"{uid}/media_publish", creation_id=container)["id"]
    info = _req("GET", media_id, fields="permalink,timestamp")
    comment_error = None
    if first_comment:
        try:
            _req("POST", f"{media_id}/comments", message=first_comment)
        except RuntimeError as e:  # the post is live; a failed comment is reported, not fatal
            comment_error = str(e)
    return {"id": media_id, "url": info.get("permalink"), "username": me.get("username"), "comment_error": comment_error}


def insights(media_id):
    """Views/likes/comments/shares/saves for one reel (missing metrics are skipped)."""
    out = {}
    for metric in ("views", "reach", "likes", "comments", "shares", "saved"):
        try:
            d = _req("GET", f"{media_id}/insights", metric=metric)
            out[metric] = d["data"][0]["values"][0]["value"]
        except (RuntimeError, KeyError, IndexError):
            pass
    return out


def refresh_token():
    r = requests.get("https://graph.instagram.com/refresh_access_token",
                     params={"grant_type": "ig_refresh_token", "access_token": os.environ["IG_ACCESS_TOKEN"]}, timeout=60)
    j = r.json()
    if "access_token" not in j:
        raise RuntimeError(f"Instagram token refresh failed: {j}")
    return j["access_token"], j.get("expires_in")
