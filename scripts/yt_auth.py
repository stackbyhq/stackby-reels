"""One-time: get the YouTube refresh token.  Run on your own computer:  python3 scripts/yt_auth.py
Paste the OAuth client ID and secret (Desktop app), log in with the Google account that owns the channel,
allow access, and copy the printed refresh token into the GitHub secret YT_REFRESH_TOKEN. Standard library only."""
import http.server
import json
import secrets
import socketserver
import threading
import urllib.parse
import urllib.request
import webbrowser

SCOPES = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly"


def main():
    cid = input("YT client ID: ").strip()
    csec = input("YT client secret: ").strip()
    state = secrets.token_urlsafe(16)
    got = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if q.get("state", [""])[0] == state and "code" in q:
                got["code"] = q["code"][0]
                msg = "Done. You can close this tab and go back to the terminal."
            else:
                msg = "Something went wrong; try again."
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(msg.encode())

        def log_message(self, *a):
            pass

    with socketserver.TCPServer(("127.0.0.1", 0), H) as srv:
        redirect = f"http://127.0.0.1:{srv.server_address[1]}"
        url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
            "client_id": cid, "redirect_uri": redirect, "response_type": "code", "scope": SCOPES,
            "access_type": "offline", "prompt": "consent", "state": state})
        print("\nOpening your browser. If it doesn't open, visit:\n" + url + "\n")
        webbrowser.open(url)
        t = threading.Thread(target=lambda: [srv.handle_request() for _ in range(3) if "code" not in got])
        t.start()
        t.join(timeout=600)
    if "code" not in got:
        raise SystemExit("No authorisation code received.")
    data = urllib.parse.urlencode({"code": got["code"], "client_id": cid, "client_secret": csec, "redirect_uri": redirect, "grant_type": "authorization_code"}).encode()
    res = json.load(urllib.request.urlopen("https://oauth2.googleapis.com/token", data=data))
    if "refresh_token" not in res:
        raise SystemExit(f"No refresh token returned: {res}")
    print("\nYT_REFRESH_TOKEN (save it as a GitHub secret, never share it):\n\n" + res["refresh_token"] + "\n")


if __name__ == "__main__":
    main()
