"""Collect views/likes/comments for every posted video and store them in posted/<name>.json (stats)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import post_instagram as IG  # noqa: E402
import post_youtube as YT  # noqa: E402
from common import POSTED, QUEUE, items, iso, now, write  # noqa: E402


def collect():
    rows = [(POSTED, i) for i in items(POSTED)] + [(QUEUE, i) for i in items(QUEUE) if i.get("status") == "partial"]
    yt_ids = [p["id"] for _, i in rows for k, p in i["platforms"].items() if k.startswith("youtube") and p.get("status") == "posted"]
    yt = {}
    if yt_ids and os.environ.get("YT_REFRESH_TOKEN"):
        try:
            yt = YT.stats(yt_ids)
        except Exception as e:
            print("YouTube stats skipped:", e)
    for folder, i in rows:
        st = i.setdefault("stats", {})
        for k, p in i["platforms"].items():
            if p.get("status") != "posted":
                continue
            if k == "instagram" and os.environ.get("IG_ACCESS_TOKEN"):
                try:
                    st[k] = IG.insights(p["id"])
                except Exception as e:
                    print("IG insights skipped:", e)
            elif k.startswith("youtube") and p["id"] in yt:
                st[k] = yt[p["id"]]
                p["privacy"] = yt[p["id"]].get("privacy", p.get("privacy"))
        i["stats_updated_at"] = iso(now())
        write(os.path.join(folder, f"{i['name']}.json"), i)
    return rows


if __name__ == "__main__":
    print(len(collect()), "items updated")
