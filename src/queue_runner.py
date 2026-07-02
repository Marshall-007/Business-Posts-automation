"""Post scheduled images from data/queue.json whose time has arrived, then
remove each posted image from the repo.

Runs in GitHub Actions on a short cron. Each queue item:
  id            unique id
  image_path    path in the repo (e.g. docs/uploads/<id>.jpg)
  image_url     public URL Instagram fetches (raw.githubusercontent, SHA-pinned)
  caption       caption text (posted verbatim)
  scheduled_at  ISO-8601 UTC time to post at
  status        pending | posted | error
  attempts      failed attempts so far

The workflow commits the updated queue.json and the image deletions.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import Credentials, load_business_config
from .platforms.base import PostError
from .platforms.instagram import Instagram

QUEUE_FILE = Path(__file__).resolve().parent.parent / "data" / "queue.json"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAX_ATTEMPTS = 3


def parse_ts(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def load_queue() -> dict:
    try:
        return json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"items": []}


def save_queue(data: dict) -> None:
    QUEUE_FILE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    data = load_queue()
    items = data.get("items", [])
    now = datetime.now(timezone.utc)

    creds = Credentials()
    business_config = load_business_config()

    due = [
        it for it in items
        if it.get("status") == "pending" and parse_ts(it["scheduled_at"]) <= now
    ]
    if not due:
        print("No posts are due.")
        return 0

    changed = False
    for item in due:
        ig = Instagram(creds, {**business_config, "image_urls": [item["image_url"]]})
        if not ig.is_configured():
            print("Instagram is not configured (missing secrets). Skipping.", file=sys.stderr)
            break
        try:
            post_id = ig.publish(item["caption"])
            item["status"] = "posted"
            item["post_id"] = post_id
            item["posted_at"] = now.isoformat(timespec="seconds")
            changed = True
            print(f"[ok] posted {item['id']} (post id {post_id})")

            # Remove the image from the repo now that it is published.
            img = PROJECT_ROOT / item.get("image_path", "")
            if item.get("image_path") and img.is_file():
                img.unlink()
                print(f"     removed {item['image_path']}")
        except (PostError, Exception) as exc:  # noqa: BLE001 - report and continue
            item["attempts"] = item.get("attempts", 0) + 1
            item["last_error"] = str(exc)
            if item["attempts"] >= MAX_ATTEMPTS:
                item["status"] = "error"
            changed = True
            print(f"[fail] {item['id']}: {exc}", file=sys.stderr)

    if changed:
        save_queue(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
