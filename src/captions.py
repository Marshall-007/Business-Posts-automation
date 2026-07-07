"""Randomized captions with brand, niche and viral hashtags.

Every auto-posted feed photo gets a caption. In *auto* mode it is assembled
from a pool of caption bodies, a rotating call to action, contact details and a
randomized hashtag block (brand + niche + viral). In *fixed* mode the operator
supplies one caption that is reused on every post. Either way, a per-campaign
set of custom hashtags can be appended on top, and a per-campaign list of
comments can be rotated onto the posts (handled by content_sync/queue_runner).

Bodies are drawn without replacement (reshuffled once the pool runs out) so
back-to-back auto posts never share a caption -- Instagram down-ranks and can
flag duplicated captions. Output respects Instagram's hard limits: max 2,200
characters and max 30 hashtags.

Multi-company: the built-in defaults below are deliberately GENERIC and derive
the brand hashtag from the business name, so a brand-new company never inherits
another company's wording. A business tunes any of it in config.yaml under a
`captions:` section (this is where Gwalava's own board-specific copy lives):

    captions:
      contact_phone: "0813471724"
      contact_url: "https://example.com/"
      bodies: [ ... ]        # caption texts
      ctas: [ ... ]          # calls to action
      brand_tags: [ ... ]    # e.g. "#YourBrand"
      niche_tags: [ ... ]
      viral_tags: [ ... ]
"""

import random
import re

MAX_CAPTION_CHARS = 2200
MAX_HASHTAGS = 30


def _business_config() -> dict:
    try:
        from .config import load_business_config
        return load_business_config() or {}
    except Exception:
        return {}


_CFG = _business_config()
_OV = _CFG.get("captions") or {}
_BIZ = _CFG.get("business") or {}
_BIZ_NAME = (_BIZ.get("name") or "").strip()


def _default_brand_tags() -> list:
    """Brand tags derived from the business name (never hard-coded to one company)."""
    tags: list[str] = []
    full = re.sub(r"[^A-Za-z0-9]+", "", _BIZ_NAME)
    if full:
        tags.append("#" + full)
    first = re.sub(r"[^A-Za-z0-9]+", "", (_BIZ_NAME.split() or [""])[0])
    if first and ("#" + first) not in tags:
        tags.append("#" + first)
    for extra in ("#SmallBusiness", "#LocalBusiness", "#QualityService"):
        if extra not in tags:
            tags.append(extra)
    return tags[:6]


# Generic, business-neutral defaults. Any company can override these in
# config.yaml; the template repo (Gwalava) does exactly that.
GENERIC_BODIES = [
    "Quality you can count on, every single day. That is the standard we hold "
    "ourselves to on every job.",
    "Great results start with great attention to detail -- and detail is what "
    "we do best.",
    "Years of experience behind everything we do. Let us put that experience to "
    "work for you.",
    "We take pride in doing things properly the first time, so you get a result "
    "that lasts.",
    "From the first conversation to the final result, we are with you every "
    "step of the way.",
    "Big or small, every project gets the same care and the same commitment to "
    "getting it right.",
    "Reliable, professional and always ready to help. Get in touch and let us "
    "show you what we can do.",
    "Your goals, our craft. Tell us what you have in mind and we will make it "
    "happen.",
]

GENERIC_CTAS = [
    "Visit us or send us a message to get started.",
    "DM us today for a quote.",
    "Send us a message and let's plan your project.",
    "Get in touch today, we are happy to help.",
    "Message us for prices and availability.",
    "Come see us, or send a DM to learn more.",
]

GENERIC_NICHE_TAGS = [
    "#SmallBusiness",
    "#LocalBusiness",
    "#SupportLocal",
    "#QualityService",
    "#CustomerService",
    "#MadeWithCare",
    "#Professional",
    "#ShopLocal",
]

GENERIC_VIRAL_TAGS = [
    "#Explore",
    "#ExplorePage",
    "#InstaGood",
    "#Trending",
    "#Viral",
    "#InstaDaily",
    "#PhotoOfTheDay",
    "#Community",
    "#Inspiration",
    "#Motivation",
]


# Per-business overrides from config.yaml (captions: section).
CAPTION_BODIES = list(_OV.get("bodies") or GENERIC_BODIES)
CTAS = list(_OV.get("ctas") or GENERIC_CTAS)
BRAND_TAGS = list(_OV.get("brand_tags") or _default_brand_tags())
NICHE_TAGS = list(_OV.get("niche_tags") or GENERIC_NICHE_TAGS)
VIRAL_TAGS = list(_OV.get("viral_tags") or GENERIC_VIRAL_TAGS)

# Contact details appended to every caption when present (blank by default so a
# new company never posts another company's number/site).
CONTACT_PHONE = (_OV.get("contact_phone") or "").strip()
CONTACT_URL = (_OV.get("contact_url") or "").strip()
_contact_parts = []
if CONTACT_PHONE:
    _contact_parts.append(f"Call us on {CONTACT_PHONE}")
if CONTACT_URL:
    _contact_parts.append(CONTACT_URL)
CONTACT_LINE = "\n".join(_contact_parts)


def _sample(rng: random.Random, pool: list, n: int) -> list:
    return rng.sample(pool, min(n, len(pool)))


def hashtag_block(rng: random.Random | None = None) -> str:
    """A randomized tag block: brand + niche + viral, capped at MAX_HASHTAGS."""
    rng = rng or random.Random()
    tags = _sample(rng, BRAND_TAGS, 3)
    tags += _sample(rng, NICHE_TAGS, 6)
    tags += _sample(rng, VIRAL_TAGS, 6)
    return " ".join(tags[:MAX_HASHTAGS])


def with_contact(text: str) -> str:
    """Append the contact line to text unless it already lists the number."""
    text = (text or "").strip()
    if not CONTACT_LINE:
        return text
    if CONTACT_PHONE and CONTACT_PHONE in text:
        return text
    return f"{text}\n\n{CONTACT_LINE}".strip() if text else CONTACT_LINE


def with_tags(text: str, rng: random.Random | None = None) -> str:
    """Add the contact line, then a randomized tag block if the text has none."""
    original = (text or "").strip()
    body = with_contact(original)
    if "#" in original:
        return body[:MAX_CAPTION_CHARS]
    block = hashtag_block(rng)
    return (f"{body}\n\n{block}".strip() if body else block)[:MAX_CAPTION_CHARS]


def normalize_tags(tags) -> list[str]:
    """Turn a string ('#a b, c') or list into a clean, deduped list of #tags."""
    if not tags:
        return []
    raw: list[str] = []
    if isinstance(tags, str):
        raw = re.split(r"[\s,]+", tags)
    else:
        for t in tags:
            raw += re.split(r"[\s,]+", str(t))
    out: list[str] = []
    seen: set[str] = set()
    for p in raw:
        p = p.strip()
        if not p:
            continue
        p = "#" + re.sub(r"^#+", "", p)
        if p == "#":
            continue
        key = p.lower()
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def append_tags(caption: str, custom_tags) -> str:
    """Append the operator's custom hashtags to a caption.

    Skips any tag already present, respects the 30-hashtag ceiling, and stays
    within the character limit. Returns the caption unchanged when there are no
    new tags to add.
    """
    caption = (caption or "").strip()
    tags = normalize_tags(custom_tags)
    if not tags:
        return caption[:MAX_CAPTION_CHARS]
    have = {t.lower() for t in re.findall(r"#\w+", caption)}
    room = MAX_HASHTAGS - len(have)
    add = [t for t in tags if t.lower() not in have][: max(0, room)]
    if not add:
        return caption[:MAX_CAPTION_CHARS]
    joined = f"{caption}\n\n{' '.join(add)}".strip() if caption else " ".join(add)
    return joined[:MAX_CAPTION_CHARS]


class CaptionPool:
    """Hands out unique randomized captions; bodies never repeat until the
    whole pool has been used, then it reshuffles."""

    def __init__(self, rng: random.Random | None = None):
        self.rng = rng or random.Random()
        self._bodies: list[str] = []

    def _next_body(self) -> str:
        if not self._bodies:
            self._bodies = CAPTION_BODIES[:]
            self.rng.shuffle(self._bodies)
        return self._bodies.pop()

    def next_caption(self) -> str:
        parts = [self._next_body(), self.rng.choice(CTAS)]
        if CONTACT_LINE:
            parts.append(CONTACT_LINE)
        parts.append(hashtag_block(self.rng))
        return "\n\n".join(parts)[:MAX_CAPTION_CHARS]


def random_caption(rng: random.Random | None = None) -> str:
    """One-off randomized caption (body + CTA + tags)."""
    return CaptionPool(rng).next_caption()
