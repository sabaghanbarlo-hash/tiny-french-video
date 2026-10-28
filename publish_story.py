#!/usr/bin/env python3
"""Publish an APPROVED Story sequence to the Tiny French Instagram account as Stories, via Composio (official Graph API, media_type=STORIES).

  publish_story.py --check                     verify the Composio key + that the connected account is @tiny.french, post nothing
  publish_story.py --sequence ID [--dry-run]   publish one sequence now
  publish_story.py --due [--dry-run]           publish every approved sequence whose publish_at has passed (used by the hourly workflow)

Safety rules enforced here (not just in the UI):
  * the connected Instagram account must be the expected one (config expect_username, default tiny.french) or NOTHING is posted
  * only sequences that are approved (approved=true + reviewed_by in the sequence JSON) with zero QC errors are ever posted
  * a slide is only recorded as published when Instagram returns a media id for it; progress is saved after every slide
  * already-published slides are never posted twice (ig-stories/posted.json), so a retry resumes where it stopped
Instagram API limits: each slide is its own Story; no stickers, captions or native scheduling.
"""
import argparse, glob, json, os, sys, time, urllib.error, urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(ROOT, "ig-stories", "out")
POSTED = os.path.join(ROOT, "ig-stories", "posted.json")
CFG = json.load(open(os.path.join(ROOT, "ig-stories", "config.json"), encoding="utf-8"))
ACCOUNT = os.environ.get("IG_ACCOUNT") or CFG["ig_account"]
EXPECT = (os.environ.get("IG_EXPECT_USERNAME") or CFG.get("expect_username", "")).strip().lstrip("@").lower()
MCP_URL = "https://connect.composio.dev/mcp"
_s = {"id": None, "n": 0}


class IGError(Exception):
    pass


def _post(payload):
    key = os.environ.get("COMPOSIO_API_KEY", "").strip()
    if not key:
        raise IGError("COMPOSIO_API_KEY is not set (add it as a repository secret)")
    h = {"x-consumer-api-key": key, "Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    if _s["id"]:
        h["Mcp-Session-Id"] = _s["id"]
    req = urllib.request.Request(MCP_URL, data=json.dumps(payload).encode(), headers=h, method="POST")
    try:
        r = urllib.request.urlopen(req, timeout=400)
    except urllib.error.HTTPError as e:
        raise IGError(f"Composio MCP HTTP {e.code}: {e.read().decode()[:300]}")
    if r.headers.get("Mcp-Session-Id"):
        _s["id"] = r.headers.get("Mcp-Session-Id")
    raw = r.read().decode()
    if not raw.strip():
        return None
    if "data:" in raw and not raw.lstrip().startswith("{"):
        for m in reversed([l[5:].strip() for l in raw.splitlines() if l.startswith("data:")]):
            try:
                return json.loads(m)
            except ValueError:
                pass
        return None
    return json.loads(raw)


def _rpc(method, params=None, notify=False):
    msg = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        msg["params"] = params
    if not notify:
        _s["n"] += 1; msg["id"] = _s["n"]
    return _post(msg)


def start():
    r = _rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "tiny-french-stories", "version": "1.0"}})
    if not r or "error" in r:
        raise IGError(f"Composio MCP initialize failed: {str(r)[:300]}")
    _rpc("notifications/initialized", notify=True)


def call(slug, args):
    r = _rpc("tools/call", {"name": "COMPOSIO_MULTI_EXECUTE_TOOL", "arguments": {"tools": [
        {"tool_slug": slug, "account": ACCOUNT, "arguments": args}], "sync_response_to_workbench": False}})
    if not r or "error" in r:
        raise IGError(f"{slug}: {str(r)[:400]}")
    res = r.get("result", {})
    text = "".join(c.get("text", "") for c in res.get("content", []) if isinstance(c, dict))
    try:
        top = json.loads(text)
    except ValueError:
        raise IGError(f"{slug}: unreadable answer: {text[:300]}")
    items = (top.get("data") or {}).get("results") or []
    if res.get("isError") or not top.get("successful", True) or not items:
        raise IGError(f"{slug}: {str((items or [{}])[0].get('error') or top.get('error') or top)[:500]}")
    resp = items[0].get("response", {})
    if not resp.get("successful", True):
        raise IGError(f"{slug}: {str(resp.get('error') or resp)[:500]}")
    return resp


def confirm_account():
    """Refuse to post anywhere but the expected account (the Composio login also holds the Tiny Japanese account)."""
    info = call("INSTAGRAM_GET_USER_INFO", {"ig_user_id": "me", "fields": "id,username,account_type"})
    got = str((info.get("data") or {}).get("username", "")).lower()
    if EXPECT and got != EXPECT:
        raise IGError(f"Safety stop: the connected Instagram account is '{got}', expected '{EXPECT}'. Nothing was posted.")
    return info


def find_id(o):
    if isinstance(o, dict):
        if isinstance(o.get("id"), (str, int)):
            return str(o["id"])
        for v in o.values():
            f = find_id(v)
            if f:
                return f
    return None


def load_posted():
    return json.load(open(POSTED, encoding="utf-8")) if os.path.exists(POSTED) else {}


def save_posted(p):
    json.dump(p, open(POSTED, "w", encoding="utf-8"), indent=2)


def reachable(url, tries=60):
    for _ in range(tries):
        try:
            if urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=20).status == 200:
                return True
        except Exception:
            pass
        time.sleep(10)
    return False


def retry(fn, n=3):
    for i in range(n):
        try:
            return fn()
        except IGError as e:
            if i == n - 1:
                raise
            print(f"  retry {i + 1}/{n - 1} after error: {e}", flush=True); time.sleep(15 * (i + 1))


def load_manifests():
    """Rendered media + QC come from the manifest; approval and schedule are read fresh from the sequence JSON,
    so approving/scheduling a sequence never needs a re-render."""
    manifests = {}
    for p in glob.glob(os.path.join(OUT_DIR, "*", "manifest.json")):
        m = json.load(open(p, encoding="utf-8"))
        src = os.path.join(ROOT, m.get("source", ""))
        if os.path.exists(src):
            s = json.load(open(src, encoding="utf-8"))
            for k in ("approved", "reviewed_by", "publish_at"):
                m[k] = s.get(k, "" if k != "approved" else False)
        m["ready_to_publish"] = bool(m.get("approved")) and bool(str(m.get("reviewed_by", "")).strip()) and not m["qc"]["errors"]
        manifests[m["id"]] = m
    return manifests


def publish(m, base, dry):
    sid = m["id"]
    if not m.get("ready_to_publish"):
        raise IGError(f"{sid}: not ready. Needs approved=true, reviewed_by, and zero QC errors (QC status: {m['qc']['status']}).")
    posted = load_posted(); rec = posted.setdefault(sid, {"slides": {}})
    for sl in m["slides"]:
        n = str(sl["n"])
        if n in rec["slides"]:
            print(f"  slide {n}: already published ({rec['slides'][n]}), skipping"); continue
        url = f"{base}/story-media/{sid}/{sl['file']}"
        key = "video_url" if sl["kind"] == "video" else "image_url"
        if dry:
            print(f"  [dry-run] would publish slide {n} ({sl['type']}) from {url}"); continue
        if not reachable(url):
            raise IGError(f"slide {n}: media URL never became reachable: {url}")
        c = retry(lambda: call("INSTAGRAM_POST_IG_USER_MEDIA", {"ig_user_id": "me", "media_type": "STORIES", key: url}))
        cid = find_id(c.get("data"))
        if not cid:
            raise IGError(f"slide {n}: no container id returned")
        p = retry(lambda: call("INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH", {"ig_user_id": "me", "creation_id": cid, "max_wait_seconds": 300}))
        mid = find_id(p.get("data"))
        if not mid:
            raise IGError(f"slide {n}: Instagram returned no media id - NOT counted as published")
        rec["slides"][n] = mid; save_posted(posted)
        print(f"  slide {n}: published, media id {mid}", flush=True); time.sleep(5)
    if not dry and len(rec["slides"]) == len(m["slides"]):
        rec["complete"] = True; rec["time"] = datetime.now(timezone.utc).isoformat(); save_posted(posted)
        print(f"{sid}: all {len(m['slides'])} Stories published.")


def due(m, posted):
    if not m.get("ready_to_publish") or not m.get("publish_at") or posted.get(m["id"], {}).get("complete"):
        return False
    t = datetime.fromisoformat(m["publish_at"])
    if t.tzinfo is None:
        t = t.replace(tzinfo=ZoneInfo(CFG.get("timezone", "UTC")))
    return t <= datetime.now(timezone.utc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true"); ap.add_argument("--due", action="store_true")
    ap.add_argument("--sequence"); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    base = os.environ.get("PAGES_BASE", "").rstrip("/")
    try:
        if a.check:
            start()
            info = confirm_account()
            print("CHECK OK. Instagram account:", json.dumps(info.get("data"), ensure_ascii=False)); return
        manifests = load_manifests()
        if a.sequence:
            if a.sequence not in manifests:
                sys.exit(f"No rendered sequence '{a.sequence}'. Run Render Stories first.")
            todo = [manifests[a.sequence]]
        elif a.due:
            posted = load_posted()
            todo = sorted([m for m in manifests.values() if due(m, posted)], key=lambda m: (m["publish_at"], m.get("order", 0)))
        else:
            sys.exit("Use --check, --sequence ID or --due")
        if not todo:
            print("Nothing due."); return
        if not a.dry_run:
            start(); confirm_account()
        for m in todo:
            print(f"Publishing {m['id']} ({'dry run' if a.dry_run else 'LIVE'})")
            publish(m, base, a.dry_run)
    except IGError as e:
        print(f"::error::{e}"); sys.exit(1)


if __name__ == "__main__":
    main()
