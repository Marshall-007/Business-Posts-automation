"""Scan content/dayN folders and enqueue their media into data/queue.json.

Folder convention (dayN counts from the campaign start date in
data/campaign.json; day1 posts on the start date, day2 the next day, ...):

    content/day1/posts/    -> feed posts (images normalized to 1080x1080 JPEG)
    content/day1/stories/  -> stories   (images normalized to 1080x1920 JPEG)

Multiple files in one folder are spread across the day: the first goes out at
the folder's start time and the rest follow at an interval derived from the
file count -- 12 hours divided by the count, clamped between 3 and 6 hours.
So 2 files post 6h apart, 3 files 4h apart, 4+ files 3h apart.

Captions for feed posts come from, in order: a sidecar text file with the same
name (photo1.jpg -> photo1.txt), a caption.txt shared by the folder, or an
auto-generated caption. Stories have no caption (Instagram ignores them).

This runs after content_prepare (which converts .webp/.png to JPEG), so only
JPEG/MP4/MOV files are enqueued. The queue runner then posts each item at its
scheduled time and deletes the file. A path is never enqueued twice.
"""

import json
import re
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

from . import content_generator
from .config import Credentials, load_business_config
from .queue_runner import QUEUE_FILE, load_queue, save_queue

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR_NAME = "content"
CAMPAIGN_FILE_NAME = "campaign.json"

DAY_RE = re.compile(r"(?i)^day(\d+)$")
IMAGE_EXTS = {".jpg", ".jpeg"}
VIDEO_EXTS = {".mp4", ".mov"}

# Spread rule: 12h across the folder, each file 3-6h apart.
DAY_SPAN_MINUTES = 720
MIN_INTERVAL_MINUTES = 180
MAX_INTERVAL_MINUTES = 360

KINDS = (
    # (folder name, campaign time key, default UTC time, post_type)
    ("posts", "posts_time_utc", "07:00", "feed"),
    ("stories", "stories_time_utc", "10:00", "story"),
)


def campaign_path(root: Path) -> Path:
    return root / "data" / CAMPAIGN_FILE_NAME


def load_campaign(root: Path) -> dict:
    try:
        return json.loads(campaign_path(root).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def interval_minutes(count: int) -> int:
    """Minutes between posts in one folder, from how many files it holds."""
    if count <= 1:
        return 0
    return max(MIN_INTERVAL_MINUTES, min(MAX_INTERVAL_MINUTES, DAY_SPAN_MINUTES // count))


def parse_hhmm(value: str, fallback: str) -> time:
    for candidate in (value, fallback):
        try:
            return datetime.strptime((candidate or "").strip(), "%H:%M").time()
        except ValueError:
            continue
    return time(9, 0)


def raw_base_url(root: Path) -> str:
    """Base URL Instagram fetches media from (repo raw content at the branch)."""
    import os
    import subprocess

    explicit = os.environ.get("CONTENT_BASE_URL")
    if explicit:
        return explicit.rstrip("/") + "/"
    repo = os.environ.get("GITHUB_REPOSITORY", "Marshall-007/Business-Posts-automation")
    branch = os.environ.get("GITHUB_REF_NAME")
    if not branch:
        try:
            branch = subprocess.check_output(
                ["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"],
                text=True,
            ).strip()
        except Exception:
            branch = "main"
    return f"https://raw.githubusercontent.com/{repo}/{quote(branch, safe='')}/"


def media_files(folder: Path) -> list[Path]:
    files = []
    for f in sorted(folder.iterdir()):
        if not f.is_file() or f.name.startswith("."):
            continue
        if f.suffix.lower() in IMAGE_EXTS | VIDEO_EXTS:
            files.append(f)
    return files


def find_subdir(day_dir: Path, name: str) -> Path | None:
    for sub in day_dir.iterdir():
        if sub.is_dir() and sub.name.lower() == name:
            return sub
    return None


def resolve_caption(
    media: Path, folder: Path, business_config: dict, api_key: str | None, cache: dict
) -> str:
    sidecar = media.with_suffix(".txt")
    if sidecar.is_file():
        return sidecar.read_text(encoding="utf-8").strip()
    shared = folder / "caption.txt"
    if shared.is_file():
        return shared.read_text(encoding="utf-8").strip()
    if "generated" not in cache:
        _, posts = content_generator.generate_posts(business_config, api_key)
        cache["generated"] = posts.get("instagram", "")
    return cache["generated"]


def sync(
    root: Path | None = None,
    now: datetime | None = None,
    business_config: dict | None = None,
    queue_path: Path | None = None,
) -> list[dict]:
    """Enqueue any new folder media. Returns the newly added queue items."""
    root = root or PROJECT_ROOT
    queue_path = queue_path or QUEUE_FILE
    now = now or datetime.now(timezone.utc)

    campaign = load_campaign(root)
    if not campaign.get("enabled"):
        print("Content campaign is disabled; nothing to sync.")
        return []
    try:
        start = date.fromisoformat(campaign.get("start_date", ""))
    except ValueError:
        print("Content campaign has no valid start_date; nothing to sync.", file=sys.stderr)
        return []

    content_dir = root / CONTENT_DIR_NAME
    if not content_dir.is_dir():
        print("No content/ directory found.")
        return []

    if business_config is None:
        business_config = load_business_config()
    creds = Credentials()
    base_url = raw_base_url(root)

    data = load_queue(queue_path)
    items = data.get("items", [])
    known_paths = {it.get("media_path") for it in items if it.get("media_path")}

    day_dirs = []
    for d in content_dir.iterdir():
        m = DAY_RE.match(d.name) if d.is_dir() else None
        if m:
            day_dirs.append((int(m.group(1)), d))
    day_dirs.sort()

    caption_cache: dict = {}
    added: list[dict] = []

    for day_n, day_dir in day_dirs:
        day_date = start + timedelta(days=day_n - 1)
        for kind, time_key, default_time, post_type in KINDS:
            folder = find_subdir(day_dir, kind)
            if folder is None:
                continue
            files = media_files(folder)
            new_files = [
                f for f in files
                if str(f.relative_to(root)) not in known_paths
            ]
            if not new_files:
                continue

            rel_folder = str(folder.relative_to(root))
            existing = [
                it for it in items
                if (it.get("media_path") or "").startswith(rel_folder + "/")
            ]
            base_dt = datetime.combine(
                day_date,
                parse_hhmm(campaign.get(time_key, ""), default_time),
                tzinfo=timezone.utc,
            )
            step = timedelta(minutes=interval_minutes(len(existing) + len(new_files)))
            if existing:
                last = max(
                    datetime.fromisoformat(it["scheduled_at"].replace("Z", "+00:00"))
                    for it in existing
                )
                first_at = last + step
            else:
                first_at = base_dt

            for i, media in enumerate(new_files):
                rel = str(media.relative_to(root))
                scheduled = first_at + i * step
                caption = ""
                if post_type == "feed":
                    caption = resolve_caption(
                        media, folder, business_config,
                        creds.anthropic_api_key, caption_cache,
                    )
                item = {
                    "id": f"content_{day_dir.name.lower()}_{kind}_{media.stem}",
                    "source": "content",
                    "media_path": rel,
                    "media_url": base_url + quote(rel),
                    "post_type": post_type,
                    "is_video": media.suffix.lower() in VIDEO_EXTS,
                    "caption": caption,
                    "scheduled_at": scheduled.isoformat(timespec="seconds"),
                    "status": "pending",
                    "attempts": 0,
                }
                items.append(item)
                added.append(item)
                known_paths.add(rel)
                print(f"queued {rel} as {post_type} for {item['scheduled_at']}")

    if added:
        data["items"] = items
        save_queue(data, queue_path)
    else:
        print("No new content files to queue.")
    return added


def main() -> int:
    sync()
    return 0


if __name__ == "__main__":
    sys.exit(main())
