"""Randomized Instagram captions for Gwalava Boards and Furniture Fittings.

Every auto-posted feed photo gets a unique caption assembled from a pool of
Gwalava-specific bodies, a rotating call to action, and a randomized hashtag
block: brand tags + furniture/fittings niche tags + high-reach "viral" tags.

Bodies are drawn without replacement (reshuffled once the pool runs out), so
back-to-back posts never share a caption -- Instagram down-ranks and can flag
duplicated captions. Output respects Instagram's hard limits: max 2,200
characters and max 30 hashtags.
"""

import random

MAX_CAPTION_CHARS = 2200
MAX_HASHTAGS = 30

CAPTION_BODIES = [
    "A kitchen this clean starts below the surface: quality boards, precise "
    "cuts and fittings that hold their line for years. That is what we supply, "
    "every single day.",

    "Gloss boards, colour boards and precision tops. Pick the finish, we make "
    "sure it arrives cut to size and edged to perfection.",

    "25 years in boards and fittings taught us one thing: the finish you "
    "admire is only as good as the hardware behind it.",

    "Edge banding at 0.4mm, 1mm or 2mm. Small numbers, huge difference. Clean "
    "edges are what separate a professional build from a weekend job.",

    "Soft-close hinges, smooth runners, handles that feel right in the hand. "
    "The details you touch every day deserve the best fittings.",

    "Building a kitchen, a wardrobe or a full shop fit? Start with boards cut "
    "right the first time. Precision cutting is our specialty.",

    "The difference between good and great furniture is measured in "
    "millimetres. We cut, edge and supply to exact measurements.",

    "Your design, our boards. From high-gloss modern to warm woodgrain, we "
    "stock the colours and finishes that bring ideas to life.",

    "Furniture makers, carpenters, contractors: bring us your cutting list "
    "and walk out project-ready. Boards, tops, edging and hardware in one stop.",

    "A great finish starts with great fittings. Durable hinges, reliable "
    "runners and top-quality handles, all under one roof.",

    "Strong boards. Clean edges. Hardware that lasts. Everything your next "
    "project needs, backed by 25 years of experience.",

    "Dream kitchens are built one precise cut at a time. We handle the "
    "cutting and edge banding so your build goes together perfectly.",

    "From a single shelf to a full kitchen fit-out, the recipe never "
    "changes: quality boards, accurate cuts, dependable fittings.",

    "Colour boards for personality. Gloss boards for shine. Precision tops "
    "for the perfect work surface. What are you building next?",

    "Cabinets that close softly, drawers that glide, doors that line up "
    "perfectly. It all comes down to the fittings you choose.",

    "Quality boards and fittings are not an expense, they are a saving. "
    "Build it right once and it serves you for decades.",
]

CTAS = [
    "Visit us or send us a message to get started.",
    "DM us your cutting list for a quote.",
    "Send us a message and let's plan your project.",
    "Visit our store or message us to see the full range.",
    "Get in touch today, we are happy to advise.",
    "Message us for prices and availability.",
    "Come see the range for yourself, or send us a DM.",
]

BRAND_TAGS = [
    "#GwalavaBoards",
    "#Gwalava",
    "#GwalavaFurnitureFittings",
    "#BoardsAndFittings",
]

NICHE_TAGS = [
    "#FurnitureFittings",
    "#FurnitureHardware",
    "#KitchenFittings",
    "#CabinetHardware",
    "#EdgeBanding",
    "#PrecisionCutting",
    "#GlossBoards",
    "#ColourBoards",
    "#MelamineBoards",
    "#BoardCutting",
    "#KitchenCabinets",
    "#CustomFurniture",
    "#FurnitureMakers",
    "#Carpentry",
    "#Woodwork",
    "#CabinetMaking",
    "#Worktops",
    "#SoftCloseHinges",
    "#DrawerRunners",
    "#ShopFitting",
]

VIRAL_TAGS = [
    "#InteriorDesign",
    "#HomeDecor",
    "#HomeDesign",
    "#KitchenDesign",
    "#DreamKitchen",
    "#KitchenGoals",
    "#KitchenInspo",
    "#HomeInspo",
    "#ModernKitchen",
    "#ModernHome",
    "#HomeImprovement",
    "#Renovation",
    "#HouseGoals",
    "#FurnitureDesign",
    "#DesignInspiration",
    "#InstaHome",
    "#Explore",
    "#ExplorePage",
    "#Viral",
    "#Trending",
]


def hashtag_block(rng: random.Random | None = None) -> str:
    """A randomized tag block: brand + niche + viral, capped at MAX_HASHTAGS."""
    rng = rng or random.Random()
    tags = rng.sample(BRAND_TAGS, 3)
    tags += rng.sample(NICHE_TAGS, 6)
    tags += rng.sample(VIRAL_TAGS, 6)
    return " ".join(tags[:MAX_HASHTAGS])


def with_tags(text: str, rng: random.Random | None = None) -> str:
    """Append a randomized tag block to user-written text that has no tags."""
    text = (text or "").strip()
    if "#" in text:
        return text[:MAX_CAPTION_CHARS]
    return f"{text}\n\n{hashtag_block(rng)}"[:MAX_CAPTION_CHARS].strip()


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
        caption = (
            f"{self._next_body()}\n\n"
            f"{self.rng.choice(CTAS)}\n\n"
            f"{hashtag_block(self.rng)}"
        )
        return caption[:MAX_CAPTION_CHARS]


def random_caption(rng: random.Random | None = None) -> str:
    """One-off randomized caption (body + CTA + tags)."""
    return CaptionPool(rng).next_caption()
