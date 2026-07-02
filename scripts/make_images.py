"""Generate branded 1080x1080 promotional images for Gwalava Boards.

Run:  python scripts/make_images.py
Outputs PNGs into assets/. Re-run after editing SLIDES to refresh them.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent / "assets"
FONT_DIR = "/usr/share/fonts/truetype/dejavu"
SIZE = 1080

BG_TOP = (24, 22, 30)       # deep charcoal
BG_BOTTOM = (46, 33, 22)    # warm wood-brown
ACCENT = (200, 137, 75)     # amber / wood accent
WHITE = (245, 242, 238)
MUTED = (196, 190, 182)

BRAND = "GWALAVA BOARDS"
SUB_BRAND = "& Furniture Fittings"

SLIDES = [
    {
        "file": "gwalava-01.png",
        "badge": "25 YEARS OF EXPERIENCE",
        "title": "Boards & Fittings\nDone Right",
        "bullets": [
            "Expertise in Color Boards",
            "Gloss Boards for a stylish finish",
            "Precision tops for every project",
        ],
    },
    {
        "file": "gwalava-02.png",
        "badge": "PRECISION SERVICES",
        "title": "Precision Cutting\n& Edge Banding",
        "bullets": [
            "Edge banding 0.4mm, 1mm & 2mm",
            "Clean, accurate cuts every time",
            "Finished to a professional standard",
        ],
    },
    {
        "file": "gwalava-03.png",
        "badge": "QUALITY HARDWARE",
        "title": "Top-Quality\nHardware Accessories",
        "bullets": [
            "Hinges, handles, runners & more",
            "Durable fittings that last",
            "Everything your project needs",
        ],
    },
]


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(f"{FONT_DIR}/{name}", size)


def gradient(w: int, h: int) -> Image.Image:
    base = Image.new("RGB", (w, h), BG_TOP)
    top, bottom = BG_TOP, BG_BOTTOM
    px = base.load()
    for y in range(h):
        t = y / h
        px_row = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        for x in range(w):
            px[x, y] = px_row
    return base


def center_x(draw, text, fnt, w):
    box = draw.textbbox((0, 0), text, font=fnt)
    return (w - (box[2] - box[0])) // 2


def make(slide: dict) -> Path:
    img = gradient(SIZE, SIZE)
    d = ImageDraw.Draw(img)

    # outer frame
    d.rectangle([28, 28, SIZE - 28, SIZE - 28], outline=ACCENT, width=3)

    f_brand = font("DejaVuSans-Bold.ttf", 46)
    f_subbrand = font("DejaVuSans.ttf", 30)
    f_badge = font("DejaVuSans-Bold.ttf", 26)
    f_title = font("DejaVuSans-Bold.ttf", 70)
    f_bullet = font("DejaVuSans.ttf", 34)
    f_footer = font("DejaVuSans.ttf", 26)

    # brand name (top)
    d.text((center_x(d, BRAND, f_brand, SIZE), 90), BRAND, font=f_brand, fill=WHITE)
    d.text((center_x(d, SUB_BRAND, f_subbrand, SIZE), 148), SUB_BRAND,
           font=f_subbrand, fill=ACCENT)

    # badge pill
    badge = slide["badge"]
    bb = d.textbbox((0, 0), badge, font=f_badge)
    bw, bh = bb[2] - bb[0], bb[3] - bb[1]
    px_pad, py_pad = 26, 14
    bx0 = (SIZE - (bw + px_pad * 2)) // 2
    by0 = 250
    d.rounded_rectangle([bx0, by0, bx0 + bw + px_pad * 2, by0 + bh + py_pad * 2],
                        radius=(bh + py_pad * 2) // 2, fill=ACCENT)
    d.text((bx0 + px_pad, by0 + py_pad - 2), badge, font=f_badge, fill=(20, 18, 24))

    # title (may be multi-line)
    y = 360
    for line in slide["title"].split("\n"):
        d.text((center_x(d, line, f_title, SIZE), y), line, font=f_title, fill=WHITE)
        y += 84

    # bullets
    y += 40
    for b in slide["bullets"]:
        dot_x = 150
        d.ellipse([dot_x, y + 14, dot_x + 14, y + 28], fill=ACCENT)
        d.text((dot_x + 34, y), b, font=f_bullet, fill=MUTED)
        y += 66

    # footer
    footer = "Visit us or send a message to learn more"
    d.text((center_x(d, footer, f_footer, SIZE), SIZE - 100), footer,
           font=f_footer, fill=MUTED)

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / slide["file"]
    img.save(path, "PNG")
    return path


if __name__ == "__main__":
    for s in SLIDES:
        print("wrote", make(s))
