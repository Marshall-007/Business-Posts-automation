"""Pull post performance (likes, comments, reach) back into a client report.

For every item that was published (status "posted", carrying an ig_post_id
and/or fb_post_id), this asks the platform for a few engagement numbers and
writes them to data/report.json -- a compact, per-post-plus-totals summary the
dashboard shows and docs/report.html renders as a shareable client report.

Design: the network is isolated in two small fetchers so build_report() stays
pure and fully testable with fake fetchers. Everything is best effort -- a
metric the API will not give (stories expose different numbers than feed posts,
tokens may lack a scope) is simply left out; it never raises.

Metrics collected where available:
  Instagram: likes, comments, reach
  Facebook:  likes, comments, shares
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

from .config import Credentials

PROJECT_ROOT = Path(__file__).resolve().parent.parent
QUEUE_FILE = PROJECT_ROOT / "data" / "queue.json"
REPORT_FILE = PROJECT_ROOT / "data" / "report.json"

IG_GRAPH = "https://graph.instagram.com/v21.0"
FB_GRAPH = "https://graph.facebook.com/v21.0"

# The engagement numbers we surface, in display order, per platform.
IG_METRICS = ("likes", "comments", "reach")
FB_METRICS = ("likes", "comments", "shares")


def fetch_instagram_metrics(media_id: str, token: str) -> dict:
    """likes/comments from the media fields, reach from insights. Best effort."""
    out: dict = {}
    try:
        resp = requests.get(
            f"{IG_GRAPH}/{media_id}",
            params={"fields": "like_count,comments_count", "access_token": token},
            timeout=30,
        )
        data = resp.json()
        if isinstance(data.get("like_count"), int):
            out["likes"] = data["like_count"]
        if isinstance(data.get("comments_count"), int):
            out["comments"] = data["comments_count"]
    except (requests.RequestException, ValueError):
        pass
    try:
        resp = requests.get(
            f"{IG_GRAPH}/{media_id}/insights",
            params={"metric": "reach", "access_token": token},
            timeout=30,
        )
        for row in resp.json().get("data", []):
            values = row.get("values") or [{}]
            if isinstance(values[0].get("value"), int):
                out[row.get("name", "reach")] = values[0]["value"]
    except (requests.RequestException, ValueError, KeyError, IndexError):
        pass
    return out


def fetch_facebook_metrics(post_id: str, token: str) -> dict:
    """likes/comments/shares from the post's summary counts. Best effort."""
    out: dict = {}
    try:
        resp = requests.get(
            f"{FB_GRAPH}/{post_id}",
            params={
                "fields": "likes.summary(true).limit(0),"
                          "comments.summary(true).limit(0),shares",
                "access_token": token,
            },
            timeout=30,
        )
        data = resp.json()
        likes = (data.get("likes") or {}).get("summary", {}).get("total_count")
        comments = (data.get("comments") or {}).get("summary", {}).get("total_count")
        shares = (data.get("shares") or {}).get("count")
        if isinstance(likes, int):
            out["likes"] = likes
        if isinstance(comments, int):
            out["comments"] = comments
        if isinstance(shares, int):
            out["shares"] = shares
    except (requests.RequestException, ValueError):
        pass
    return out


def _add(totals: dict, metrics: dict) -> None:
    for key, value in metrics.items():
        if isinstance(value, int):
            totals[key] = totals.get(key, 0) + value


def build_report(items, ig_fetch, fb_fetch, now=None) -> dict:
    """Pure report builder: iterate posted items, ask the fetchers for numbers,
    and aggregate. ig_fetch(media_id) / fb_fetch(post_id) return metric dicts."""
    now = now or datetime.now(timezone.utc)
    rows = []
    totals = {"posts": 0, "instagram": {}, "facebook": {}}
    for it in items:
        if it.get("status") != "posted":
            continue
        ig_id = it.get("ig_post_id")
        fb_id = it.get("fb_post_id")
        if not (ig_id or fb_id):
            continue
        row = {
            "id": it.get("id"),
            "campaign": it.get("campaign", ""),
            "post_type": it.get("post_type", "feed"),
            "posted_at": it.get("posted_at", ""),
            "caption": (it.get("caption") or "")[:140],
        }
        if ig_id:
            m = ig_fetch(ig_id)
            row["instagram"] = {"post_id": ig_id, **m}
            _add(totals["instagram"], m)
        if fb_id:
            m = fb_fetch(fb_id)
            row["facebook"] = {"post_id": fb_id, **m}
            _add(totals["facebook"], m)
        totals["posts"] += 1
        rows.append(row)
    rows.sort(key=lambda r: r.get("posted_at", ""), reverse=True)
    return {"generated_at": now.isoformat(timespec="seconds"),
            "totals": totals, "items": rows}


def load_items(queue_path: Path) -> list:
    try:
        return json.loads(queue_path.read_text(encoding="utf-8")).get("items", [])
    except (json.JSONDecodeError, OSError):
        return []


def generate(root: Path | None = None, now=None) -> dict:
    """Read the queue, fetch live metrics with the configured tokens, and write
    data/report.json. Returns the report dict."""
    root = root or PROJECT_ROOT
    queue_path = root / "data" / "queue.json"
    report_path = root / "data" / "report.json"

    creds = Credentials()
    ig_token = creds.instagram_access_token or ""
    fb_token = creds.facebook_page_access_token or ""

    def ig_fetch(media_id: str) -> dict:
        return fetch_instagram_metrics(media_id, ig_token) if ig_token else {}

    def fb_fetch(post_id: str) -> dict:
        return fetch_facebook_metrics(post_id, fb_token) if fb_token else {}

    report = build_report(load_items(queue_path), ig_fetch, fb_fetch, now)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {report_path} ({report['totals']['posts']} post(s)).")
    return report


def main() -> int:
    generate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
