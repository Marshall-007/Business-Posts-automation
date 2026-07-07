"""captions: randomized Gwalava captions with brand, niche and viral tags."""

import random

from src.captions import (
    BRAND_TAGS,
    CAPTION_BODIES,
    CONTACT_PHONE,
    CONTACT_URL,
    MAX_CAPTION_CHARS,
    MAX_HASHTAGS,
    NICHE_TAGS,
    VIRAL_TAGS,
    CaptionPool,
    hashtag_block,
    random_caption,
    with_contact,
    with_tags,
)


def test_caption_structure_and_instagram_limits():
    cap = random_caption(random.Random(1))
    assert len(cap) <= MAX_CAPTION_CHARS
    assert cap.count("#") <= MAX_HASHTAGS
    assert "#Gwalava" in cap                      # brand presence
    assert any(t in cap for t in NICHE_TAGS)      # furniture-fittings niche
    assert any(t in cap for t in VIRAL_TAGS)      # high-reach tags
    assert CONTACT_PHONE in cap                   # contact number
    assert CONTACT_URL in cap                     # website


def test_every_random_caption_carries_contact_details():
    pool = CaptionPool(random.Random(7))
    for _ in range(len(CAPTION_BODIES) + 3):
        cap = pool.next_caption()
        assert CONTACT_PHONE in cap and CONTACT_URL in cap


def test_with_contact_is_idempotent():
    once = with_contact("Nice boards")
    assert CONTACT_PHONE in once and CONTACT_URL in once
    # A caption that already lists the number is left as-is (no duplicate).
    assert with_contact(once) == once
    assert once.count(CONTACT_PHONE) == 1


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


def test_with_tags_adds_contact_always_and_tags_only_when_missing():
    rng = random.Random(4)
    tagged = with_tags("Nice kitchen", rng)
    assert tagged.startswith("Nice kitchen")
    assert CONTACT_PHONE in tagged and CONTACT_URL in tagged
    assert "#" in tagged                         # tag block appended

    # Text that brought its own hashtags keeps them and gets no extra block,
    # but still receives the contact details.
    own = with_tags("My words #handpicked", rng)
    assert own.startswith("My words #handpicked")
    assert CONTACT_PHONE in own
    assert own.count("#") == 1                    # no auto tag block added


def test_no_emoji_in_any_caption_material():
    text = " ".join(CAPTION_BODIES + BRAND_TAGS + NICHE_TAGS + VIRAL_TAGS +
                     [CONTACT_PHONE, CONTACT_URL])
    assert all(ord(ch) < 0x2600 for ch in text)


def test_normalize_tags_from_string_and_list():
    from src.captions import normalize_tags
    # A free-typed string (spaces/commas, optional #) becomes clean #tags.
    assert normalize_tags("sale, #Winter  promo") == ["#sale", "#Winter", "#promo"]
    # A list is flattened and de-duplicated (case-insensitive), order preserved.
    assert normalize_tags(["#a", "b c", "#A"]) == ["#a", "#b", "#c"]
    assert normalize_tags("") == []
    assert normalize_tags(None) == []


def test_append_tags_adds_only_new_and_respects_cap():
    from src.captions import MAX_HASHTAGS, append_tags
    cap = append_tags("Nice #keep", ["#new", "#keep"])
    assert cap.startswith("Nice #keep")
    assert "#new" in cap
    assert cap.count("#keep") == 1                 # already present, not duplicated
    # Never exceeds Instagram's 30-hashtag ceiling.
    full = " ".join("#t%d" % i for i in range(MAX_HASHTAGS))
    out = append_tags(full, ["#extra"])
    assert "#extra" not in out                     # no room left
    assert out.count("#") == MAX_HASHTAGS
    # No custom tags -> caption returned unchanged.
    assert append_tags("Just words", []) == "Just words"
