"""Normalize images under content/ so Instagram accepts them.

Instagram's API only accepts JPEG, so .webp/.png are converted. Any folder
named post/posts (feed) or story/stories (stories), at any nesting depth and in
any case, is processed:

    Feed  -> keep the photo's aspect ratio if Instagram allows it (0.8-1.91),
             capped at 1080 on the long edge; only pad to a 1080x1080 white
             square when the aspect is out of range.
    Story -> fit onto a 1080x1920 white canvas (9:16).

Videos and caption text files are left untouched. Idempotent: a JPEG already
within spec is skipped, so re-runs are no-ops until new files appear.
"""

import re
import sys
from pathlib import Path

from PIL import Image, ImageOps

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR_NAME = "content"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
POST_RE = re.compile(r"(?i)^posts?$")
STORY_RE = re.compile(r"(?i)^stor(?:y|ies)$")

FEED_MAX = 1080
FEED_MIN_AR = 0.8      # 4:5 portrait
FEED_MAX_AR = 1.91     # 1.91:1 landscape
STORY_SIZE = (1080, 1920)


def _load_rgb(src: Path) -> Image.Image:
    img = ImageOps.exif_transpose(Image.open(src))
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        flat = Image.new("RGB", img.size, (255, 255, 255))
        flat.paste(img, mask=img.getchannel("A"))
        return flat
    return img.convert("RGB")


def _pad_onto(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    canvas = Image.new("RGB", size, (255, 255, 255))
    scale = min(size[0] / img.width, size[1] / img.height)
    w, h = max(1, round(img.width * scale)), max(1, round(img.height * scale))
    canvas.paste(img.resize((w, h), Image.LANCZOS), ((size[0] - w) // 2, (size[1] - h) // 2))
    return canvas


def _target_path(src: Path) -> Path:
    candidate = src.with_suffix(".jpg")
    if candidate == src or not candidate.exists():
        return candidate
    i = 1
    while True:
        candidate = src.with_name(f"{src.stem}-{i}.jpg")
        if not candidate.exists():
            return candidate
        i += 1


def _feed_ok(src: Path, img: Image.Image) -> bool:
    ar = img.width / img.height
    return (
        src.suffix.lower() in (".jpg", ".jpeg")
        and max(img.width, img.height) <= FEED_MAX
        and FEED_MIN_AR <= ar <= FEED_MAX_AR
    )


def normalize_image(src: Path, kind: str) -> Path | None:
    """kind is 'feed' or 'story'. Returns the new path if changed, else None."""
    img = _load_rgb(src)

    if kind == "story":
        if src.suffix.lower() in (".jpg", ".jpeg") and img.size == STORY_SIZE:
            return None
        out = _pad_onto(img, STORY_SIZE)
    else:  # feed
        if _feed_ok(src, img):
            return None
        ar = img.width / img.height
        if FEED_MIN_AR <= ar <= FEED_MAX_AR:
            scale = min(1.0, FEED_MAX / max(img.width, img.height))
            out = img.resize(
                (max(1, round(img.width * scale)), max(1, round(img.height * scale))),
                Image.LANCZOS,
            )
        else:
            out = _pad_onto(img, (FEED_MAX, FEED_MAX))

    dest = _target_path(src)
    out.save(dest, "JPEG", quality=90)
    if dest != src:
        src.unlink()
    return dest


def folder_kind(name: str) -> str | None:
    if POST_RE.match(name):
        return "feed"
    if STORY_RE.match(name):
        return "story"
    return None


def prepare(root: Path | None = None) -> list[tuple[Path, Path]]:
    root = root or PROJECT_ROOT
    content = root / CONTENT_DIR_NAME
    changed: list[tuple[Path, Path]] = []
    if not content.is_dir():
        return changed

    for folder in content.rglob("*"):
        if not folder.is_dir():
            continue
        kind = folder_kind(folder.name)
        if kind is None:
            continue
        for f in sorted(folder.iterdir()):
            if not f.is_file() or f.name.startswith(".") or f.suffix.lower() not in IMAGE_EXTS:
                continue
            try:
                dest = normalize_image(f, kind)
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
