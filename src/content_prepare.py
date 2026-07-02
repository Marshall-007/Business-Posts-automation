"""Normalize images under content/ so Instagram accepts them.

Instagram's API only accepts JPEG images, so anything else (.webp, .png) is
converted. Images are padded onto a white canvas at the right shape:

    content/dayN/posts/    -> 1080x1080 (square feed post)
    content/dayN/stories/  -> 1080x1920 (9:16 story)

Videos (.mp4/.mov) and caption text files are left untouched. The step is
idempotent: a JPEG already at the target size is skipped, so re-runs are
no-ops until new files appear.
"""

import re
import sys
from pathlib import Path

from PIL import Image, ImageOps

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR_NAME = "content"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
POSTS_SIZE = (1080, 1080)
STORIES_SIZE = (1080, 1920)
DAY_RE = re.compile(r"(?i)^day(\d+)$")


def _target_path(src: Path) -> Path:
    """Pick a .jpg path for the normalized file, avoiding collisions."""
    candidate = src.with_suffix(".jpg")
    if candidate == src or not candidate.exists():
        return candidate
    i = 1
    while True:
        candidate = src.with_name(f"{src.stem}-{i}.jpg")
        if not candidate.exists():
            return candidate
        i += 1


def normalize_image(src: Path, size: tuple[int, int]) -> Path | None:
    """Convert/pad one image to a JPEG of `size`. Returns the new path if the
    file changed, or None if it was already correct."""
    img = Image.open(src)
    img = ImageOps.exif_transpose(img)

    if src.suffix.lower() in (".jpg", ".jpeg") and img.size == size:
        return None

    # Flatten transparency onto white, then pad-center onto the target canvas.
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        flat = Image.new("RGB", img.size, (255, 255, 255))
        flat.paste(img, mask=img.getchannel("A"))
        img = flat
    else:
        img = img.convert("RGB")

    canvas = Image.new("RGB", size, (255, 255, 255))
    scale = min(size[0] / img.width, size[1] / img.height)
    w, h = max(1, round(img.width * scale)), max(1, round(img.height * scale))
    resized = img.resize((w, h), Image.LANCZOS)
    canvas.paste(resized, ((size[0] - w) // 2, (size[1] - h) // 2))

    dest = _target_path(src)
    canvas.save(dest, "JPEG", quality=90)
    if dest != src:
        src.unlink()
    return dest


def prepare(root: Path | None = None) -> list[tuple[Path, Path]]:
    """Normalize every image under content/. Returns [(old, new), ...]."""
    root = root or PROJECT_ROOT
    content = root / CONTENT_DIR_NAME
    changed: list[tuple[Path, Path]] = []
    if not content.is_dir():
        return changed

    for day_dir in sorted(content.iterdir()):
        if not day_dir.is_dir() or not DAY_RE.match(day_dir.name):
            continue
        for sub in day_dir.iterdir():
            if not sub.is_dir():
                continue
            kind = sub.name.lower()
            if kind == "posts":
                size = POSTS_SIZE
            elif kind == "stories":
                size = STORIES_SIZE
            else:
                continue
            for f in sorted(sub.iterdir()):
                if not f.is_file() or f.name.startswith("."):
                    continue
                if f.suffix.lower() not in IMAGE_EXTS:
                    continue
                try:
                    dest = normalize_image(f, size)
                except Exception as exc:  # corrupt/unreadable image
                    print(f"[warn] could not normalize {f}: {exc}", file=sys.stderr)
                    continue
                if dest is not None:
                    changed.append((f, dest))
                    print(f"normalized {f.relative_to(root)} -> {dest.name}")
    return changed


def main() -> int:
    changed = prepare()
    print(f"{len(changed)} file(s) normalized.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
