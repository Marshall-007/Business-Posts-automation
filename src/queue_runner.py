"""Post scheduled images/videos from data/queue.json whose time has arrived,
then remove each posted file from the repo.

Runs in GitHub Actions on a short cron. Each queue item:
  id            unique id
  media_path    path in the repo (e.g. docs/uploads/<id>.jpg, content/day1/posts/a.jpg)
  media_url     public URL Instagram fetches (raw.githubusercontent)
  post_type     "feed" or "story"
  is_video      True for MP4/MOV, False for images
  caption       caption text (ignored by Instagram for stories)
  scheduled_at  ISO-8601 time to post at
  status        pending | posted | error
  attempts      failed attempts so far

The workflow commits the updated queue.json and the media deletions.

Safety valve: Instagram's API allows roughly 25 published posts per account
per 24 hours. At most DAILY_CAP items (default 20, override with the
IG_DAILY_CAP env var) are posted in any rolling 24-hour window; anything
beyond that stays pending and goes out on later runs.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import Credentials, load_business_config
from .platforms.base import PostError
from .platforms.facebook import Facebook
from .platforms.instagram import Instagram

QUEUE_FILE = Path(__file__).resolve().parent.parent / "data" / "queue.json"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAX_ATTEMPTS = 3
DAILY_CAP_DEFAULT = 20


def daily_cap() -> int:
    try:
        return max(1, int(os.environ.get("IG_DAILY_CAP", DAILY_CAP_DEFAULT)))
    except ValueError:
        return DAILY_CAP_DEFAULT


def posted_in_last_24h(items: list[dict], now: datetime) -> int:
    count = 0
    for it in items:
        if it.get("status") != "posted" or not it.get("posted_at"):
            continue
        try:
            if parse_ts(it["posted_at"]) > now - timedelta(hours=24):
                count += 1
        except ValueError:
            continue
    return count


def parse_ts(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def load_queue(path: Path | None = None) -> dict:
    path = path or QUEUE_FILE
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"items": []}


def save_queue(data: dict, path: Path | None = None) -> None:
    path = path or QUEUE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def process_due(
    now: datetime | None = None,
    root: Path | None = None,
    queue_path: Path | None = None,
) -> list[dict]:
    """Post every pending queue item whose scheduled_at has passed.

    Returns the full (mutated in place) items list, so callers/tests can
    inspect status/post_id/attempts after the run.
    """
    root = root or PROJECT_ROOT
    queue_path = queue_path or QUEUE_FILE
    now = now or datetime.now(timezone.utc)

    data = load_queue(queue_path)
    items = data.get("items", [])

    due = sorted(
        (
            it for it in items
            if it.get("status") == "pending" and parse_ts(it["scheduled_at"]) <= now
        ),
        key=lambda it: parse_ts(it["scheduled_at"]),
    )
    if not due:
        print("No posts are due.")
        return items

    # Stay under Instagram's daily publishing limit (rolling 24h window).
    cap = daily_cap()
    room = cap - posted_in_last_24h(items, now)
    if room <= 0:
        print(f"Daily cap of {cap} posts reached; {len(due)} due item(s) wait "
              "for the next window.")
        return items
    if len(due) > room:
        print(f"Daily cap: posting {room} of {len(due)} due item(s); the rest "
              "go out on later runs.")
        due = due[:room]

    creds = Credentials()
    business_config = load_business_config()
    facebook = Facebook(creds, business_config)
    fb_ready = facebook.is_configured()
    changed = False

    for item in due:
        media_url = item.get("media_url") or item.get("image_url")
        media_path = item.get("media_path") or item.get("image_path")
        # post_type: "feed" or "story"; is_video: True for MP4/MOV.
        post_type = item.get("post_type")
        is_video = item.get("is_video")
        if post_type is None:  # legacy items used media_type IMAGE/REELS
            post_type = "feed"
        if is_video is None:
            is_video = item.get("media_type") == "REELS"

        # is_configured() checks for image_urls; give it the item's URL.
        ig = Instagram(creds, {**business_config, "image_urls": [media_url]})
        if not ig.is_configured():
            print("Instagram is not configured (missing secrets). Skipping.", file=sys.stderr)
            break
        try:
            post_id = ig.publish_media(item.get("caption", ""), media_url, post_type, is_video)
            item["status"] = "posted"
            item["post_id"] = post_id
            item["posted_at"] = now.isoformat(timespec="seconds")
            changed = True
            kind = "story" if post_type == "story" else ("reel" if is_video else "image")
            print(f"[ok] posted {item['id']} ({kind}, post id {post_id})")

            # Cross-post the same media to the Facebook Page (best effort: a
            # Facebook failure must not block Instagram or re-trigger a retry,
            # since Instagram already succeeded). Done before the file is
            # deleted so Facebook can still fetch it from the public URL.
            if fb_ready:
                try:
                    fb_id = facebook.publish_media(
                        item.get("caption", ""), media_url, post_type, is_video
                    )
                    item["fb_post_id"] = fb_id
                    item.pop("fb_error", None)
                    print(f"     cross-posted to Facebook (post id {fb_id})")
                except (PostError, Exception) as fb_exc:  # noqa: BLE001
                    item["fb_error"] = str(fb_exc)
                    print(f"     [warn] Facebook cross-post failed: {fb_exc}",
                          file=sys.stderr)

            # Remove the media from the repo now that it is published.
            media = root / media_path if media_path else None
            if media and media.is_file():
                media.unlink()
                print(f"     removed {media_path}")
        except Exception as exc:  # noqa: BLE001 - report and continue
            item["attempts"] = item.get("attempts", 0) + 1
            item["last_error"] = str(exc)
            if item["attempts"] >= MAX_ATTEMPTS:
                item["status"] = "error"
            changed = True
            print(f"[fail] {item['id']}: {exc}", file=sys.stderr)

    if changed:
        save_queue(data, queue_path)
    return items


def main() -> int:
    process_due()
    return 0


if __name__ == "__main__":
    sys.exit(main())
