#!/usr/bin/env python3
"""Approve and schedule rendered Story sequences in one go (the 'review sign-off' + publish_at for many sequences).

  python schedule_stories.py --reviewer "Your name" --start 2026-10-29 [--time 14:00] [--per-day 1] [--dry-run]

Takes every sequence that is NOT yet approved, has zero QC errors in its rendered manifest, and is not already published,
puts them in `order` and gives them consecutive publish_at times (UTC) starting at --start. Sequences that already have
approved=true, are blocked, or have not been rendered yet are left alone. The hourly Publish Stories workflow then posts them.
"""
import argparse, glob, json, os, sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
SEQ_DIR = os.path.join(ROOT, "ig-stories", "sequences")
OUT_DIR = os.path.join(ROOT, "ig-stories", "out")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reviewer", required=True, help="name recorded as reviewed_by (the person who checked the French)")
    ap.add_argument("--start", required=True, help="first publish date, YYYY-MM-DD (UTC)")
    ap.add_argument("--time", default="14:00", help="UTC time of the first post each day, HH:MM")
    ap.add_argument("--per-day", type=int, default=1, help="sequences per day (extra ones are spaced 6 hours apart)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not a.reviewer.strip():
        sys.exit("--reviewer must not be empty")
    h, m = (int(x) for x in a.time.split(":"))
    day0 = datetime.strptime(a.start, "%Y-%m-%d").replace(hour=h, minute=m, tzinfo=timezone.utc)
    posted = json.load(open(os.path.join(ROOT, "ig-stories", "posted.json"), encoding="utf-8")) if os.path.exists(os.path.join(ROOT, "ig-stories", "posted.json")) else {}
    todo = []
    for p in sorted(glob.glob(os.path.join(SEQ_DIR, "*.json"))):
        s = json.load(open(p, encoding="utf-8"))
        mp = os.path.join(OUT_DIR, s["id"], "manifest.json")
        if s.get("approved") or posted.get(s["id"], {}).get("complete"):
            continue
        if not os.path.exists(mp):
            print(f"skip {s['id']}: not rendered yet"); continue
        if json.load(open(mp, encoding="utf-8"))["qc"]["errors"]:
            print(f"skip {s['id']}: has QC errors"); continue
        todo.append((s.get("order", 9999), s["id"], p, s))
    todo.sort(key=lambda x: (x[0], x[1]))
    for i, (_, sid, p, s) in enumerate(todo):
        when = day0 + timedelta(days=i // a.per_day, hours=6 * (i % a.per_day))
        s["approved"] = True; s["reviewed_by"] = a.reviewer.strip(); s["publish_at"] = when.strftime("%Y-%m-%dT%H:%M:%S+00:00")
        print(f"{'would schedule' if a.dry_run else 'scheduled'} {sid} -> {s['publish_at']}")
        if not a.dry_run:
            with open(p, "w", encoding="utf-8") as f:
                json.dump(s, f, ensure_ascii=False, indent=2); f.write("\n")
    if not todo:
        print("Nothing to schedule.")


if __name__ == "__main__":
    main()
