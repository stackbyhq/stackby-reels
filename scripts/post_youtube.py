"""YouTube uploads (Shorts and long-form) with the Data API v3, authorised by a stored refresh token."""
import json
import os

import requests

TOKEN_URL = "https://oauth2.googleapis.com/token"


def access_token():
    r = requests.post(TOKEN_URL, data={"client_id": os.environ["YT_CLIENT_ID"], "client_secret": os.environ["YT_CLIENT_SECRET"],
                                       "refresh_token": os.environ["YT_REFRESH_TOKEN"], "grant_type": "refresh_token"}, timeout=60)
    j = r.json()
    if "access_token" not in j:
        raise RuntimeError(f"YouTube auth failed: {j.get('error')} {j.get('error_description', '')}")
    return j["access_token"]


def _api(method, url, tok, **kw):
    r = requests.request(method, url, headers={"Authorization": f"Bearer {tok}", **kw.pop("headers", {})}, timeout=kw.pop("timeout", 120), **kw)
    if r.status_code >= 400:
        raise RuntimeError(f"YouTube {url.split('?')[0].rsplit('/', 1)[-1]} -> {r.status_code}: {r.text[:400]}")
    return r


def upload(path, title, description, tags=None, thumb=None, short=True, privacy="public"):
    tok = access_token()
    meta = {"snippet": {"title": title[:100], "description": description[:4900], "tags": tags or [], "categoryId": "28"},
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False, "embeddable": True}}
    size = os.path.getsize(path)
    start = _api("POST", "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status", tok,
                 headers={"Content-Type": "application/json; charset=UTF-8", "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)},
                 data=json.dumps(meta))
    with open(path, "rb") as f:
        res = _api("PUT", start.headers["Location"], tok, headers={"Content-Type": "video/mp4", "Content-Length": str(size)}, data=f, timeout=1800).json()
    vid = res["id"]
    thumb_error = None
    if thumb and not short:  # custom thumbnails apply to long-form videos (needs a verified channel)
        try:
            with open(thumb, "rb") as f:
                _api("POST", f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid}", tok, headers={"Content-Type": "image/jpeg"}, data=f)
        except RuntimeError as e:
            thumb_error = str(e)
    privacy_now = res.get("status", {}).get("privacyStatus", privacy)
    url = f"https://youtube.com/shorts/{vid}" if short else f"https://youtu.be/{vid}"
    return {"id": vid, "url": url, "privacy": privacy_now, "thumb_error": thumb_error}


def stats(video_ids):
    if not video_ids:
        return {}
    tok = access_token()
    out = {}
    for i in range(0, len(video_ids), 50):
        r = _api("GET", "https://www.googleapis.com/youtube/v3/videos", tok, params={"part": "statistics,status", "id": ",".join(video_ids[i:i + 50])}).json()
        for v in r.get("items", []):
            s = v.get("statistics", {})
            out[v["id"]] = {"views": int(s.get("viewCount", 0)), "likes": int(s.get("likeCount", 0)), "comments": int(s.get("commentCount", 0)),
                            "privacy": v.get("status", {}).get("privacyStatus")}
    return out


def channel():
    tok = access_token()
    r = _api("GET", "https://www.googleapis.com/youtube/v3/channels", tok, params={"part": "snippet", "mine": "true"}).json()
    return r["items"][0]["snippet"]["title"] if r.get("items") else None
