"""Scan content campaigns and enqueue their media into data/queue.json.

A *campaign* is a named folder under content/ (e.g. "William Collins Ghost 1").
Each campaign has its own start date, set in the dashboard and stored in
data/campaigns.json.

A *day* is any folder that directly contains a Post/Posts or Story/Stories
subfolder, at any nesting depth. This means every layout works:

    content/<Campaign>/Day 1/Post/            -> feed posts
    content/<Campaign>/Day 1/Story/           -> stories
    content/<Campaign>/Month 1/Day 1/Post/    -> nested months are fine too
    content/day1/posts/                        -> the default campaign ("")

Day folders are ordered by a natural sort of their path ("Day 2" before
"Day 10", "Month 1" before "Month 2") and each is assigned a consecutive
calendar date starting from the campaign's start date -- the first day in
order posts on the start date, the next on the following day, and so on.

Multiple files in one folder are spread across the day: the first at the
folder's start time, the rest at an interval of 12h / file-count, clamped
between 3 and 6 hours. So 2 files post 6h apart, 3 files 4h apart, 4+ 3h apart.

Captions for feed posts: a sidecar text file (photo1.jpg -> photo1.txt), a
folder caption.txt, or an auto-generated caption. Stories ignore captions.

Runs after content_prepare (which converts .webp/.png to JPEG), so only
JPEG/MP4/MOV files are enqueued. A path is never enqueued twice.
"""

import json
import re
import sys
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

from . import content_generator
from .config import Credentials, load_business_config
from .content_prepare import folder_kind
from .queue_runner import QUEUE_FILE, load_queue, save_queue

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR_NAME = "content"
CAMPAIGNS_FILE_NAME = "campaigns.json"
LEGACY_CAMPAIGN_FILE_NAME = "campaign.json"

IMAGE_EXTS = {".jpg", ".jpeg"}
VIDEO_EXTS = {".mp4", ".mov"}

# A top-level content/dayN folder belongs to the default campaign ("").
DAY_RE = re.compile(r"(?i)^day\s*\d+$")

DAY_SPAN_MINUTES = 720
MIN_INTERVAL_MINUTES = 180
MAX_INTERVAL_MINUTES = 360

# (post_type, campaign time key, default UTC time)
KIND_SETTINGS = {
    "feed": ("posts_time_utc", "07:00"),
    "story": ("stories_time_utc", "10:00"),
}

DEFAULTS = {
    "enabled": False,
    "start_date": "",
    "posts_time_utc": "07:00",
    "stories_time_utc": "10:00",
}


def load_campaign_configs(root: Path) -> dict:
    """Return {campaign_name: config}. "" is the default (content/dayN)."""
    data_dir = root / "data"
    configs: dict = {}
    campaigns_path = data_dir / CAMPAIGNS_FILE_NAME
    if campaigns_path.is_file():
        try:
            configs = json.loads(campaigns_path.read_text(encoding="utf-8")).get("campaigns", {})
        except (json.JSONDecodeError, OSError):
            configs = {}
    # Legacy single-campaign file seeds the default campaign if not already set.
    legacy = data_dir / LEGACY_CAMPAIGN_FILE_NAME
    if "" not in configs and legacy.is_file():
        try:
            configs[""] = json.loads(legacy.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return configs


def interval_minutes(count: int) -> int:
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
    for f in sorted(folder.iterdir(), key=lambda p: natural_key(p.name)):
        if not f.is_file() or f.name.startswith("."):
            continue
        if f.suffix.lower() in IMAGE_EXTS | VIDEO_EXTS:
            files.append(f)
    return files


def natural_key(text: str) -> list:
    """Split into text/number tokens so 'Day 2' sorts before 'Day 10'."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", text)]


def find_day_dirs(content_dir: Path) -> dict[str, list[Path]]:
    """Group day folders by campaign.

    A day folder is any directory that directly contains a Post/Story subfolder.
    The campaign is the first path component under content/; a day folder that is
    itself a direct child of content/ belongs to the default campaign ("").
    """
    by_campaign: dict[str, set] = defaultdict(set)
    for sub in content_dir.rglob("*"):
        if sub.is_dir() and folder_kind(sub.name) is not None:
            day_dir = sub.parent
            rel = day_dir.relative_to(content_dir).parts
            # A direct content/dayN child is the default campaign (""); any other
            # top-level folder is a named campaign, even if it holds posts/stories
            # directly (then the campaign folder itself is its single day).
            if len(rel) == 1 and DAY_RE.match(rel[0]):
                name = ""
            else:
                name = rel[0]
            by_campaign[name].add(day_dir)
    return {
        name: sorted(dirs, key=lambda d: natural_key(str(d.relative_to(content_dir))))
        for name, dirs in by_campaign.items()
    }


def day_subfolders(day_dir: Path) -> list[tuple[str, Path]]:
    """Return [(post_type, folder)] for the Post/Story folders inside a day."""
    found = []
    for child in sorted(day_dir.iterdir(), key=lambda p: natural_key(p.name)):
        if not child.is_dir():
            continue
        kind = folder_kind(child.name)
        if kind == "feed":
            found.append(("feed", child))
        elif kind == "story":
            found.append(("story", child))
    return found


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "default"


def resolve_caption(media, folder, business_config, api_key, cache) -> str:
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


def _enqueue_folder(
    folder, post_type, campaign_name, day_slug, day_date, config,
    items, known_paths, root, base_url, business_config, creds, cache,
):
    files = media_files(folder)
    rel_folder = str(folder.relative_to(root))
    new_files = [f for f in files if str(f.relative_to(root)) not in known_paths]
    if not new_files:
        return []

    time_key, default_time = KIND_SETTINGS[post_type]
    existing = [
        it for it in items
        if (it.get("media_path") or "").startswith(rel_folder + "/")
    ]
    base_dt = datetime.combine(
        day_date, parse_hhmm(config.get(time_key, ""), default_time), tzinfo=timezone.utc
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

    added = []
    for i, media in enumerate(new_files):
        rel = str(media.relative_to(root))
        caption = ""
        if post_type == "feed":
            caption = resolve_caption(media, folder, business_config, creds.anthropic_api_key, cache)
        item = {
            "id": f"content_{slug(campaign_name)}_{day_slug}_{post_type}_{slug(media.stem)}",
            "source": "content",
            "campaign": campaign_name,
            "media_path": rel,
            "media_url": base_url + quote(rel),
            "post_type": post_type,
            "is_video": media.suffix.lower() in VIDEO_EXTS,
            "caption": caption,
            "scheduled_at": (first_at + i * step).isoformat(timespec="seconds"),
            "status": "pending",
            "attempts": 0,
        }
        items.append(item)
        added.append(item)
        known_paths.add(rel)
        print(f"queued {rel} as {post_type} for {item['scheduled_at']}")
    return added


def sync(root=None, now=None, business_config=None, queue_path=None) -> list[dict]:
    """Enqueue new media from every enabled campaign. Returns added items."""
    root = root or PROJECT_ROOT
    queue_path = queue_path or QUEUE_FILE
    now = now or datetime.now(timezone.utc)

    content_dir = root / CONTENT_DIR_NAME
    if not content_dir.is_dir():
        print("No content/ directory found.")
        return []

    configs = load_campaign_configs(root)
    if business_config is None:
        business_config = load_business_config()
    creds = Credentials()
    base_url = raw_base_url(root)

    data = load_queue(queue_path)
    items = data.get("items", [])
    known_paths = {it.get("media_path") for it in items if it.get("media_path")}

    campaigns = find_day_dirs(content_dir)
    cache: dict = {}
    added: list[dict] = []

    for name, day_dirs in campaigns.items():
        config = {**DEFAULTS, **configs.get(name, {})}
        if not config.get("enabled"):
            continue
        try:
            start = date.fromisoformat(config.get("start_date", ""))
        except ValueError:
            print(f"Campaign {name or '(default)'} has no valid start_date; skipping.",
                  file=sys.stderr)
            continue

        for index, day_dir in enumerate(day_dirs):
            day_date = start + timedelta(days=index)
            day_slug = slug(str(day_dir.relative_to(content_dir / name if name else content_dir)))
            for post_type, folder in day_subfolders(day_dir):
                added += _enqueue_folder(
                    folder, post_type, name, day_slug, day_date, config,
                    items, known_paths, root, base_url,
                    business_config, creds, cache,
                )

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
