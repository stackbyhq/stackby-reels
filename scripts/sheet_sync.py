"""Write the live tracker to Google Sheets: which video is scheduled, posted where, links and stats.
Runs daily (sheet-sync.yml), after every posting run and after the daily digest.
Needs: secret GOOGLE_SERVICE_ACCOUNT_JSON (service account key) and variable SHEET_ID; share the sheet with
the service account's email as Editor.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import IST, POSTED, QUEUE, captions, ist, items, now  # noqa: E402

HEAD = ["#", "Video", "Series", "Scheduled (IST)", "Status", "Instagram Reel", "IG posted (IST)", "IG views", "IG likes", "IG comments",
        "YouTube Short", "Short views", "YouTube video", "Video views", "YouTube visibility", "Notes", "Last updated (IST)"]
LABEL = {"queued": "Scheduled", "hold": "On hold", "posted": "Posted", "partial": "Partly posted · retrying", "failed": "Failed · needs attention"}


def link(url, text):
    return f'=HYPERLINK("{url}","{text}")' if url else ""


def rows():
    caps = captions()
    state = {i["name"]: i for i in items(QUEUE)} | {i["name"]: i for i in items(POSTED)}
    names = list(caps) + [n for n in state if n not in caps]
    stamp = now().astimezone(IST).strftime("%d %b %Y %H:%M")
    out = []
    for n in names:
        c, i = caps.get(n, {}), state.get(n)
        if not i:
            out.append([c.get("order", ""), c.get("title", n), c.get("group", ""), "", "Not queued · add video", "", "", "", "", "", "", "", "", "", "", "", stamp])
            continue
        p, st = i.get("platforms", {}), i.get("stats", {})
        ig, ys, yl = p.get("instagram", {}), p.get("youtube_short", {}), p.get("youtube_long", {})
        notes = "; ".join(f"{k}: {v['error']}" for k, v in p.items() if v.get("error"))[:300] or i.get("error", "")
        vis = ys.get("privacy") or yl.get("privacy") or ""
        if vis == "private":
            notes = (notes + "; " if notes else "") + "YouTube private until the API audit is approved (make public in YouTube Studio)"
        out.append([c.get("order", ""), i.get("title", n), c.get("group", ""), ist(i.get("at")) if i.get("at") else "—", LABEL.get(i.get("status"), i.get("status")),
                    link(ig.get("url"), "Open reel"), ist(ig.get("posted_at")), st.get("instagram", {}).get("views", ""), st.get("instagram", {}).get("likes", ""),
                    st.get("instagram", {}).get("comments", ""), link(ys.get("url"), "Open short"), (st.get("youtube_short") or {}).get("views", ""),
                    link(yl.get("url"), "Open video"), (st.get("youtube_long") or {}).get("views", ""), vis, notes, stamp])
    out.sort(key=lambda r: (r[0] == "", r[0]))
    return out


def summary(data):
    total = len(data)
    by = {k: sum(1 for r in data if r[4] == v) for k, v in LABEL.items()}
    num = lambda col: sum(r[col] for r in data if isinstance(r[col], (int, float)))  # noqa: E731
    return [["Stackby video tracker", ""], ["Last sync (IST)", now().astimezone(IST).strftime("%d %b %Y %H:%M")], ["", ""],
            ["Videos in the library", total], ["Posted", by["posted"]], ["Scheduled", by["queued"]], ["On hold", by["hold"]],
            ["Partly posted (retrying)", by["partial"]], ["Failed", by["failed"]], ["Not queued yet", sum(1 for r in data if r[4].startswith("Not queued"))], ["", ""],
            ["Instagram views", num(7)], ["Instagram likes", num(8)], ["YouTube Short views", num(11)], ["YouTube video views", num(13)]]


def run():
    sa, sheet = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON"), os.environ.get("SHEET_ID")
    if not sa or not sheet:
        print("sheet sync skipped: GOOGLE_SERVICE_ACCOUNT_JSON / SHEET_ID not set")
        return
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2 import service_account
    creds = service_account.Credentials.from_service_account_info(json.loads(sa), scopes=["https://www.googleapis.com/auth/spreadsheets"])
    s = AuthorizedSession(creds)
    base = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet}"
    data = rows()
    tabs = {t["properties"]["title"] for t in s.get(base, params={"fields": "sheets.properties.title"}).json().get("sheets", [])}
    missing = [t for t in ("Tracker", "Summary") if t not in tabs]
    if missing:
        s.post(f"{base}:batchUpdate", json={"requests": [{"addSheet": {"properties": {"title": t}}} for t in missing]}).raise_for_status()
    s.post(f"{base}/values:batchClear", json={"ranges": ["Tracker!A2:Q1000", "Summary!A1:B40"]}).raise_for_status()
    r = s.post(f"{base}/values:batchUpdate", json={"valueInputOption": "USER_ENTERED", "data": [
        {"range": "Tracker!A1", "values": [HEAD] + data}, {"range": "Summary!A1", "values": summary(data)}]})
    r.raise_for_status()
    print(f"sheet synced: {len(data)} videos")


if __name__ == "__main__":
    run()
