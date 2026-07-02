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
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import Credentials, load_business_config
from .platforms.instagram import Instagram

QUEUE_FILE = Path(__file__).resolve().parent.parent / "data" / "queue.json"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAX_ATTEMPTS = 3


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

    due = [
        it for it in items
        if it.get("status") == "pending" and parse_ts(it["scheduled_at"]) <= now
    ]
    if not due:
        print("No posts are due.")
        return items

    creds = Credentials()
    business_config = load_business_config()
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
