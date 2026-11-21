"""Instagram Reels through either Meta login type, picked from the token itself:
  IGAA… token -> Instagram API with Instagram Login   (graph.instagram.com)
  EAA…  token -> Instagram API with Facebook Login    (graph.facebook.com; the Instagram professional account
                 must be linked to a Facebook Page the token can see, or set IG_USER_ID)
The container -> publish -> comment flow is the same on both."""
import os
import time

import requests


def fb_login():
    return not os.environ.get("IG_ACCESS_TOKEN", "").startswith("IG")


def api():
    return "https://graph.facebook.com/v21.0" if fb_login() else "https://graph.instagram.com/v21.0"


def _req(method, path, **params):
    params["access_token"] = os.environ["IG_ACCESS_TOKEN"]
    r = requests.request(method, f"{api()}/{path}", params=params if method == "GET" else None, data=params if method != "GET" else None, timeout=120)
    j = r.json() if r.text else {}
    if r.status_code >= 400 or "error" in j:
        err = j.get("error", {})
        raise RuntimeError(f"Instagram {path}: {err.get('message', r.text[:300])} (code {err.get('code')}, sub {err.get('error_subcode')})")
    return j


def account():
    """-> {"user_id": Instagram professional account id, "username": …}"""
    if not fb_login():
        return _req("GET", "me", fields="user_id,username")
    if os.environ.get("IG_USER_ID"):
        me = _req("GET", os.environ["IG_USER_ID"], fields="id,username")
        return {"user_id": me["id"], "username": me.get("username")}
    pages = _req("GET", "me/accounts", fields="name,instagram_business_account{id,username}").get("data", [])
    for pg in pages:
        ig = pg.get("instagram_business_account")
        if ig:
            return {"user_id": ig["id"], "username": ig.get("username"), "page": pg.get("name")}
    raise RuntimeError("No Instagram professional account found: link the Stackby Instagram to a Facebook Page and give the token "
                       "instagram_basic, instagram_content_publish, pages_show_list and pages_read_engagement (or set the IG_USER_ID secret)")


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
    """Fresh 60-day token. Facebook Login tokens need the app's ID and secret (FB_APP_ID, FB_APP_SECRET)."""
    tok = os.environ["IG_ACCESS_TOKEN"]
    if fb_login():
        if not (os.environ.get("FB_APP_ID") and os.environ.get("FB_APP_SECRET")):
            raise RuntimeError("Facebook-login token: add the FB_APP_ID and FB_APP_SECRET secrets (Meta app → App settings → Basic) so it can be renewed")
        r = requests.get("https://graph.facebook.com/v21.0/oauth/access_token", params={"grant_type": "fb_exchange_token", "client_id": os.environ["FB_APP_ID"],
                         "client_secret": os.environ["FB_APP_SECRET"], "fb_exchange_token": tok}, timeout=60)
    else:
        r = requests.get("https://graph.instagram.com/refresh_access_token", params={"grant_type": "ig_refresh_token", "access_token": tok}, timeout=60)
    j = r.json()
    if "access_token" not in j:
        raise RuntimeError(f"Instagram token refresh failed: {j}")
    return j["access_token"], j.get("expires_in")
