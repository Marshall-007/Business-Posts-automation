"""captions: randomized Gwalava captions with brand, niche and viral tags."""

import random

from src.captions import (
    BRAND_TAGS,
    CAPTION_BODIES,
    MAX_CAPTION_CHARS,
    MAX_HASHTAGS,
    NICHE_TAGS,
    VIRAL_TAGS,
    CaptionPool,
    hashtag_block,
    random_caption,
    with_tags,
)


def test_caption_structure_and_instagram_limits():
    cap = random_caption(random.Random(1))
    assert len(cap) <= MAX_CAPTION_CHARS
    assert cap.count("#") <= MAX_HASHTAGS
    assert "#Gwalava" in cap                      # brand presence
    assert any(t in cap for t in NICHE_TAGS)      # furniture-fittings niche
    assert any(t in cap for t in VIRAL_TAGS)      # high-reach tags


def test_hashtag_block_mixes_all_pools():
    block = hashtag_block(random.Random(2))
    tags = block.split()
    assert len(tags) == 15
    assert len(tags) == len(set(tags))            # no duplicate tags
    assert sum(t in BRAND_TAGS for t in tags) == 3
    assert sum(t in NICHE_TAGS for t in tags) == 6
    assert sum(t in VIRAL_TAGS for t in tags) == 6


def test_pool_never_repeats_a_body_until_exhausted():
    pool = CaptionPool(random.Random(3))
    captions = [pool.next_caption() for _ in range(len(CAPTION_BODIES))]
    bodies = [c.split("\n\n")[0] for c in captions]
    assert len(set(bodies)) == len(CAPTION_BODIES)
    # and it keeps going after a reshuffle
    assert pool.next_caption()


def test_with_tags_appends_only_when_text_has_none():
    rng = random.Random(4)
    tagged = with_tags("Nice kitchen", rng)
    assert tagged.startswith("Nice kitchen")
    assert "#" in tagged

    own = with_tags("My words #handpicked", rng)
    assert own == "My words #handpicked"


def test_no_emoji_in_any_caption_material():
    text = " ".join(CAPTION_BODIES + BRAND_TAGS + NICHE_TAGS + VIRAL_TAGS)
    assert all(ord(ch) < 0x2600 for ch in text)
