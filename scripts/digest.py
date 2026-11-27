"""Daily insights digest for Telegram (09:00 IST): how every reel and video is doing.

  python3 scripts/digest.py          -> refresh stats, send the digest (once per IST day), save a snapshot
  python3 scripts/digest.py --dry    -> print the digest instead of sending it

Each run stores a snapshot of every video's numbers in ops/stats-history.json, so the digest can show what
changed in the last 24 hours.
"""
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stats  # noqa: E402
import telegram  # noqa: E402
from common import CHANNEL, IST, OPS, POSTED, QUEUE, git_commit_push, ist, items, now, parse  # noqa: E402

HISTORY = os.path.join(OPS, "stats-history.json")
SENT = os.path.join(OPS, "digest-last-sent.txt")
PLAT = {"instagram": "IG", "youtube_short": "Short", "youtube_long": "YouTube"}
METRICS = ("views", "reach", "likes", "comments", "shares", "saved")


def n(x):
    x = x or 0
    return f"{x / 1000:.1f}k" if x >= 10000 else f"{x:,}"


def numbers(i):
    """{platform: {metric: value}} for one posted item."""
    st = i.get("stats", {}) or {}
    return {p: {m: (st.get(p) or {}).get(m) or 0 for m in METRICS} for p in i.get("platforms", {}) if i["platforms"][p].get("status") == "posted"}


def total_views(nums):
    return sum(v.get("views", 0) for v in nums.values())


def engagement(ig):
    """Instagram engagement rate: interactions / reach."""
    inter = sum(ig.get(k, 0) for k in ("likes", "comments", "shares", "saved"))
    base = ig.get("reach") or ig.get("views")
    return 100 * inter / base if base else None


def build(posted, queue, prev, t):
    today = t.astimezone(IST)
    lines = [f"📊 {CHANNEL} daily insights · {today:%a %d %b}"]
    nums = {i["name"]: numbers(i) for i in posted}

    # 1. what changed in the last 24 h (vs yesterday's snapshot)
    delta = {p: {"views": 0, "likes": 0, "comments": 0} for p in PLAT}
    grow = []
    for name, by_p in nums.items():
        before = prev.get(name, {})
        g = 0
        for p, m in by_p.items():
            for k in ("views", "likes", "comments"):
                d = max(0, m.get(k, 0) - (before.get(p, {}) or {}).get(k, 0))
                delta[p][k] += d
                if k == "views":
                    g += d
        grow.append((g, name))
    if prev:
        lines.append("\n📈 Last 24 hours")
        for p, lab in PLAT.items():
            d = delta[p]
            lines.append(f"• {lab}: +{n(d['views'])} views · +{n(d['likes'])} likes · +{n(d['comments'])} comments")

    # 2. posts that went out in the last 24 h, with their numbers
    fresh = [i for i in posted if any(v.get("posted_at") and t - parse(v["posted_at"]) < dt.timedelta(hours=26) for v in i["platforms"].values())]
    for i in fresh:
        m = nums[i["name"]]
        lines.append(f"\n🆕 Posted: {i['title']}")
        if "instagram" in m:
            ig = m["instagram"]
            er = engagement(ig)
            lines.append(f"• IG reel: {n(ig['views'])} views · {n(ig['reach'])} reach · {n(ig['likes'])} likes · {n(ig['comments'])} comments · "
                         f"{n(ig['shares'])} shares · {n(ig['saved'])} saves" + (f" · {er:.1f}% engagement" if er is not None else ""))
        for p in ("youtube_short", "youtube_long"):
            if p in m:
                y = m[p]
                priv = i["platforms"][p].get("privacy")
                lines.append(f"• {PLAT[p]}: {n(y['views'])} views · {n(y['likes'])} likes · {n(y['comments'])} comments" + (" (private)" if priv == "private" else ""))
        links = [i["platforms"][p].get("url") for p in PLAT if i["platforms"].get(p, {}).get("url")]
        if links:
            lines.append("  " + " · ".join(links))

    # 3. running totals
    tot = {p: {k: sum(nums[x].get(p, {}).get(k, 0) for x in nums) for k in ("views", "likes", "comments")} for p in PLAT}
    all_views = sum(tot[p]["views"] for p in PLAT)
    lines.append(f"\n📦 Totals ({len(posted)} videos posted): {n(all_views)} views")
    for p, lab in PLAT.items():
        lines.append(f"• {lab}: {n(tot[p]['views'])} views · {n(tot[p]['likes'])} likes · {n(tot[p]['comments'])} comments")

    # 4. leaders
    by_title = {i["name"]: i["title"] for i in posted}
    top = sorted(nums, key=lambda x: -total_views(nums[x]))[:3]
    if all_views:
        lines.append("\n🏆 Top videos (all platforms)")
        for k, x in enumerate(top, 1):
            lines.append(f"{k}. {by_title[x]}: {n(total_views(nums[x]))} views")
        g, x = max(grow) if grow else (0, None)
        if prev and g:
            lines.append(f"🚀 Fastest growing today: {by_title[x]} (+{n(g)} views)")
        igs = [(engagement(nums[x]["instagram"]), x) for x in nums if "instagram" in nums[x] and (nums[x]["instagram"].get("reach") or 0) >= 50]
        igs = [e for e in igs if e[0] is not None]
        if igs:
            e, x = max(igs)
            lines.append(f"💬 Most engaging reel: {by_title[x]} ({e:.1f}%)")

    # 5. what's next
    upcoming = sorted([i for i in queue if i.get("status") in ("queued", "partial") and i.get("at")], key=lambda i: i["at"])[:3]
    if upcoming:
        lines.append("\n🗓 Coming up")
        for i in upcoming:
            lines.append(f"• {ist(i['at'])}: {i['title']}")
        lines.append(f"{sum(1 for i in queue if i.get('status') in ('queued', 'partial'))} videos scheduled")

    # 6. anything that needs a human
    problems = [f"{i['title']} ({i['status']})" for i in queue if i.get("status") in ("failed", "partial")]
    problems += [f"{i['title']}: {PLAT[p]} is private" for i in posted for p in ("youtube_short", "youtube_long")
                 if i["platforms"].get(p, {}).get("privacy") == "private"]
    overdue = [i["title"] for i in queue if i.get("status") == "queued" and i.get("at") and t - parse(i["at"]) > dt.timedelta(hours=3)]
    problems += [f"{x}: overdue, not posted yet" for x in overdue]
    if problems:
        lines.append("\n⚠️ Needs attention\n" + "\n".join(f"• {x}" for x in problems))
    return "\n".join(lines), nums


def main():
    dry = "--dry" in sys.argv
    t = now()
    day = t.astimezone(IST).strftime("%Y-%m-%d")
    if not dry and os.path.exists(SENT) and open(SENT).read().strip() == day:
        print("digest already sent today")
        return
    stats.collect()
    posted, queue = items(POSTED), items(QUEUE)
    hist = json.load(open(HISTORY)) if os.path.exists(HISTORY) else {}
    prev_days = sorted(d for d in hist if d < day)
    prev = hist[prev_days[-1]] if prev_days else {}
    text, nums = build(posted, queue, prev, t)
    if dry:
        print(text)
        return
    telegram.send(text)
    hist[day] = nums
    for d in sorted(hist)[:-45]:  # keep 45 days
        del hist[d]
    json.dump(hist, open(HISTORY, "w"), indent=1)
    open(SENT, "w").write(day)
    git_commit_push(["posted", "queue", "ops"], "digest: daily insights [skip ci]")
    try:
        import sheet_sync
        sheet_sync.run()
    except Exception as e:
        print("sheet sync skipped:", e)


if __name__ == "__main__":
    main()
