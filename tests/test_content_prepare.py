"""content_prepare: converts/resizes images for Instagram, idempotently."""

from pathlib import Path

from PIL import Image

from src.content_prepare import prepare


def make_image(path: Path, size, mode="RGB", fmt=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    color = (200, 30, 30, 255) if mode == "RGBA" else (200, 30, 30)
    Image.new(mode, size, color).save(path, fmt or path.suffix.lstrip(".").upper().replace("JPG", "JPEG"))


def test_webp_post_keeps_aspect_ratio_as_jpeg(tmp_path):
    # A feed image within Instagram's allowed aspect range (0.8-1.91) keeps its
    # shape; it is only converted to JPEG (and capped at 1080 on the long edge).
    src = tmp_path / "content/day1/posts/photo.webp"
    make_image(src, (800, 600), fmt="WEBP")

    changed = prepare(tmp_path)

    out = tmp_path / "content/day1/posts/photo.jpg"
    assert [(a.name, b.name) for a, b in changed] == [("photo.webp", "photo.jpg")]
    assert not src.exists()
    assert Image.open(out).size == (800, 600)


def test_out_of_range_feed_image_is_padded_to_square(tmp_path):
    # A too-wide panorama (aspect > 1.91) is padded onto a 1080x1080 white square.
    src = tmp_path / "content/day1/posts/pano.webp"
    make_image(src, (2000, 500), fmt="WEBP")

    prepare(tmp_path)

    out = tmp_path / "content/day1/posts/pano.jpg"
    assert Image.open(out).size == (1080, 1080)


def test_large_in_range_feed_image_is_capped_to_1080(tmp_path):
    src = tmp_path / "content/day1/posts/big.webp"
    make_image(src, (2160, 2160), fmt="WEBP")

    prepare(tmp_path)

    out = tmp_path / "content/day1/posts/big.jpg"
    assert Image.open(out).size == (1080, 1080)


def test_png_with_alpha_story_becomes_portrait_jpeg(tmp_path):
    src = tmp_path / "content/day2/stories/promo.png"
    make_image(src, (500, 500), mode="RGBA", fmt="PNG")

    prepare(tmp_path)

    out = tmp_path / "content/day2/stories/promo.jpg"
    assert not src.exists()
    img = Image.open(out)
    assert img.size == (1080, 1920)
    assert img.mode == "RGB"


def test_correct_jpeg_is_untouched_and_prepare_is_idempotent(tmp_path):
    ok = tmp_path / "content/day1/posts/ready.jpg"
    make_image(ok, (1080, 1080))
    before = ok.read_bytes()

    assert prepare(tmp_path) == []
    assert ok.read_bytes() == before

    # A wrong-sized jpeg gets fixed once, then later runs are no-ops.
    wrong = tmp_path / "content/day1/posts/big.jpg"
    make_image(wrong, (2000, 1000))
    assert len(prepare(tmp_path)) == 1
    assert Image.open(wrong).size == (1080, 1080)
    assert prepare(tmp_path) == []


def test_videos_captions_and_dotfiles_are_ignored(tmp_path):
    posts = tmp_path / "content/day1/posts"
    posts.mkdir(parents=True)
    (posts / "clip.mp4").write_bytes(b"not-really-video")
    (posts / "caption.txt").write_text("hello")
    (posts / ".gitkeep").write_text("")

    assert prepare(tmp_path) == []
    assert (posts / "clip.mp4").read_bytes() == b"not-really-video"


def test_posts_folder_at_any_depth_is_normalized(tmp_path):
    # A campaign posts folder (content/<campaign>/dayN/posts) is normalized.
    deep = tmp_path / "content/William Collins Ghost 1/day1/posts/x.webp"
    make_image(deep, (300, 300), fmt="WEBP")
    changed = prepare(tmp_path)
    assert [b.name for _, b in changed] == ["x.jpg"]


def test_images_outside_posts_or_stories_are_ignored(tmp_path):
    # Images not inside a posts/ or stories/ folder are left untouched.
    stray = tmp_path / "content/Campaign/day1/x.webp"
    make_image(stray, (300, 300), fmt="WEBP")
    assert prepare(tmp_path) == []
    assert stray.exists()
