"""Scan content campaigns and enqueue their media into data/queue.json.

A *campaign* is a named folder under content/ (e.g. "William Collins Ghost 1").
Each campaign has its own start date, set in the dashboard and stored in
data/campaigns.json. Inside a campaign, day folders drive the schedule:

    content/<Campaign>/day1/posts/     -> feed posts on the start date
    content/<Campaign>/day1/stories/   -> stories on the start date
    content/<Campaign>/day2/...        -> the next day, and so on

A campaign with no dayN folders but posts/stories directly is treated as day1.
For backwards compatibility, day folders placed directly under content/
(content/dayN/...) form the default campaign, keyed "" in campaigns.json (or
the legacy data/campaign.json).

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
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

from . import content_generator
from .config import Credentials, load_business_config
from .queue_runner import QUEUE_FILE, load_queue, save_queue

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR_NAME = "content"
CAMPAIGNS_FILE_NAME = "campaigns.json"
LEGACY_CAMPAIGN_FILE_NAME = "campaign.json"

DAY_RE = re.compile(r"(?i)^day(\d+)$")
IMAGE_EXTS = {".jpg", ".jpeg"}
VIDEO_EXTS = {".mp4", ".mov"}

DAY_SPAN_MINUTES = 720
MIN_INTERVAL_MINUTES = 180
MAX_INTERVAL_MINUTES = 360

KINDS = (
    # (folder name, campaign time key, default UTC time, post_type)
    ("posts", "posts_time_utc", "07:00", "feed"),
    ("stories", "stories_time_utc", "10:00", "story"),
)

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
    for f in sorted(folder.iterdir()):
        if not f.is_file() or f.name.startswith("."):
            continue
        if f.suffix.lower() in IMAGE_EXTS | VIDEO_EXTS:
            files.append(f)
    return files


def find_subdir(parent: Path, name: str) -> Path | None:
    for sub in parent.iterdir():
        if sub.is_dir() and sub.name.lower() == name:
            return sub
    return None


def campaign_days(campaign_dir: Path) -> list[tuple[int, Path]]:
    """Return [(day_number, day_dir)]. A campaign with no dayN folders but
    posts/stories directly is treated as a single day1."""
    days = []
    for d in campaign_dir.iterdir():
        m = DAY_RE.match(d.name) if d.is_dir() else None
        if m:
            days.append((int(m.group(1)), d))
    if days:
        return sorted(days)
    if find_subdir(campaign_dir, "posts") or find_subdir(campaign_dir, "stories"):
        return [(1, campaign_dir)]
    return []


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
    folder, post_type, time_key, default_time, campaign_dir, campaign_name,
    day_date, config, items, known_paths, root, base_url, business_config, creds, cache,
):
    files = media_files(folder)
    rel_folder = str(folder.relative_to(root))
    new_files = [f for f in files if str(f.relative_to(root)) not in known_paths]
    if not new_files:
        return []

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
            "id": f"content_{slug(campaign_name)}_{campaign_dir.name.lower()}"
                  f"_{post_type}_{media.stem}",
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

    # Enumerate campaigns: the default "" (content/dayN) plus each named folder.
    campaigns: list[tuple[str, Path]] = []
    if campaign_days(content_dir):
        campaigns.append(("", content_dir))
    for d in sorted(content_dir.iterdir()):
        if d.is_dir() and not DAY_RE.match(d.name) and d.name.lower() not in ("posts", "stories"):
            campaigns.append((d.name, d))

    cache: dict = {}
    added: list[dict] = []

    for name, campaign_dir in campaigns:
        config = {**DEFAULTS, **configs.get(name, {})}
        if not config.get("enabled"):
            continue
        try:
            start = date.fromisoformat(config.get("start_date", ""))
        except ValueError:
            print(f"Campaign {name or '(default)'} has no valid start_date; skipping.",
                  file=sys.stderr)
            continue

        for day_n, day_dir in campaign_days(campaign_dir):
            day_date = start + timedelta(days=day_n - 1)
            for kind, time_key, default_time, post_type in KINDS:
                folder = find_subdir(day_dir, kind)
                if folder is None:
                    continue
                added += _enqueue_folder(
                    folder, post_type, time_key, default_time, day_dir, name,
                    day_date, config, items, known_paths, root, base_url,
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
