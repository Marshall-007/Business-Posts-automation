"""Generate post text for each platform.

Uses the Claude API when ANTHROPIC_API_KEY is configured; otherwise falls back
to rotating through the template posts in config.yaml.
"""

import json
import random

from . import history

PLATFORM_RULES = {
    "twitter": "Maximum 270 characters including hashtags. Punchy and direct.",
    "facebook": "2-4 short paragraphs. Conversational. End with the call to action.",
    "instagram": "Engaging caption, 2-3 short paragraphs, emoji welcome, hashtags at the end.",
    "linkedin": "Professional tone, 2-4 short paragraphs, minimal emoji, 3-5 hashtags at the end.",
    "telegram": "1-2 short paragraphs, plain text, friendly and informative.",
}

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        platform: {"type": "string"} for platform in PLATFORM_RULES
    },
    "required": list(PLATFORM_RULES),
    "additionalProperties": False,
}


def pick_topic(business_config: dict) -> str:
    topics = business_config.get("topics") or ["a general update about the business"]
    recent = set(history.recent_topics(limit=min(len(topics) - 1, 5)))
    candidates = [t for t in topics if t not in recent] or topics
    return random.choice(candidates)


def generate_posts(business_config: dict, api_key: str | None) -> tuple[str, dict[str, str]]:
    """Return (topic, {platform: post_text}) for every known platform."""
    topic = pick_topic(business_config)
    if api_key:
        return topic, _generate_with_claude(business_config, topic)
    return topic, _generate_from_templates(business_config)


def _generate_with_claude(business_config: dict, topic: str) -> dict[str, str]:
    import anthropic

    business = business_config.get("business", {})
    hashtags = " ".join(business_config.get("hashtags", []))
    rules = "\n".join(f"- {name}: {rule}" for name, rule in PLATFORM_RULES.items())

    prompt = f"""Write one social media post for each platform below, promoting this business.

Business name: {business.get('name')}
Description: {business.get('description')}
Website: {business.get('website')}
Tone: {business.get('tone')}
Target audience: {business.get('audience')}
Call to action: {business.get('call_to_action')}
Preferred hashtags: {hashtags or 'none'}

Today's post theme: {topic}

Platform requirements:
{rules}

Each post must stand on its own, sound human (not like an ad template), and vary
in structure from the others. Do not invent specific facts, prices, statistics,
or customer names."""

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=2048,
        thinking={"type": "adaptive"},
        output_config={"format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
        messages=[{"role": "user", "content": prompt}],
    )
    text = next(block.text for block in response.content if block.type == "text")
    posts = json.loads(text)
    # Hard safety net for the X character limit.
    if len(posts.get("twitter", "")) > 280:
        posts["twitter"] = posts["twitter"][:277] + "..."
    return posts


def _generate_from_templates(business_config: dict) -> dict[str, str]:
    templates = business_config.get("template_posts") or [
        "Thanks for following us — more updates coming soon!"
    ]
    text = templates[history.post_count() % len(templates)]
    return posts_from_caption(business_config, text)


def posts_from_caption(business_config: dict, text: str) -> dict[str, str]:
    """Build a per-platform post dict from one caption, applying hashtags where
    useful and enforcing the X character limit."""
    hashtags = " ".join(business_config.get("hashtags", []))
    posts = {}
    for platform in PLATFORM_RULES:
        post = text
        if hashtags and platform in ("instagram", "linkedin", "twitter"):
            post = f"{text}\n\n{hashtags}"
        if platform == "twitter" and len(post) > 280:
            post = text[:277] + "..."
        posts[platform] = post
    return posts
