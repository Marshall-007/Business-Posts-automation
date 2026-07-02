"""Generate branded 1080x1920 story images for Gwalava Boards.

Run:  python scripts/make_story_images.py [output_dir]
Defaults to content/day1/stories/. Re-run after editing SLIDES.
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
W, H = 1080, 1920

BG_TOP = (24, 22, 30)
BG_BOTTOM = (46, 33, 22)
ACCENT = (200, 137, 75)
WHITE = (245, 242, 238)
MUTED = (196, 190, 182)

BRAND = "GWALAVA BOARDS"
SUB_BRAND = "& Furniture Fittings"

SLIDES = [
    {
        "file": "story-01.jpg",
        "big": "25 YEARS",
        "title": "of getting\nboards right",
        "footer": "Colour boards, gloss boards, precision tops",
    },
    {
        "file": "story-02.jpg",
        "big": "0.4 / 1 / 2mm",
        "title": "Edge banding\ndone clean",
        "footer": "Precision cutting for every project",
    },
    {
        "file": "story-03.jpg",
        "big": "HARDWARE",
        "title": "Fittings that\nlast for years",
        "footer": "Hinges, handles, runners and more",
    },
]


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(f"{FONT_DIR}/{name}", size)


def gradient() -> Image.Image:
    base = Image.new("RGB", (W, H), BG_TOP)
    px = base.load()
    for y in range(H):
        t = y / H
        row = tuple(int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3))
        for x in range(W):
            px[x, y] = row
    return base


def center_x(draw, text, fnt) -> int:
    box = draw.textbbox((0, 0), text, font=fnt)
    return (W - (box[2] - box[0])) // 2


def make(slide: dict, out_dir: Path) -> Path:
    img = gradient()
    d = ImageDraw.Draw(img)
    d.rectangle([40, 40, W - 40, H - 40], outline=ACCENT, width=4)

    f_brand = font("DejaVuSans-Bold.ttf", 54)
    f_sub = font("DejaVuSans.ttf", 34)
    f_big = font("DejaVuSans-Bold.ttf", 110)
    f_title = font("DejaVuSans-Bold.ttf", 76)
    f_footer = font("DejaVuSans.ttf", 34)

    d.text((center_x(d, BRAND, f_brand), 180), BRAND, font=f_brand, fill=WHITE)
    d.text((center_x(d, SUB_BRAND, f_sub), 250), SUB_BRAND, font=f_sub, fill=ACCENT)

    d.text((center_x(d, slide["big"], f_big), 640), slide["big"], font=f_big, fill=ACCENT)

    y = 820
    for line in slide["title"].split("\n"):
        d.text((center_x(d, line, f_title), y), line, font=f_title, fill=WHITE)
        y += 92

    d.text((center_x(d, slide["footer"], f_footer), H - 260), slide["footer"],
           font=f_footer, fill=MUTED)

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / slide["file"]
    img.save(path, "JPEG", quality=90)
    return path


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        Path(__file__).resolve().parent.parent / "content" / "day1" / "stories"
    )
    for s in SLIDES:
        print("wrote", make(s, out))
