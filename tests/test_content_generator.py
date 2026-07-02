"""content_generator: template fallback, hashtags, X length clamp."""

import src.content_generator as cg
from src import history


def test_template_fallback_rotates_with_post_count(business_config, monkeypatch):
    seen = []
    for count in (0, 1, 2):
        monkeypatch.setattr(history, "post_count", lambda c=count: c)
        monkeypatch.setattr(history, "recent_topics", lambda limit=5: [])
        topic, posts = cg.generate_posts(business_config, api_key=None)
        seen.append(posts["telegram"])
        assert topic in business_config["topics"]
    assert seen[0] == "Template caption A"
    assert seen[1] == "Template caption B"
    assert seen[2] == "Template caption A"  # wraps around


def test_hashtags_only_on_hashtag_friendly_platforms(business_config):
    posts = cg.posts_from_caption(business_config, "Body text")
    assert posts["instagram"] == "Body text\n\n#one #two"
    assert posts["twitter"].startswith("Body text")
    assert "#one" in posts["twitter"]
    assert posts["facebook"] == "Body text"
    assert posts["telegram"] == "Body text"


def test_twitter_clamped_to_280_chars(business_config):
    long_caption = "x" * 400
    posts = cg.posts_from_caption(business_config, long_caption)
    assert len(posts["twitter"]) <= 280
    assert posts["twitter"].endswith("...")
    # other platforms keep the full text
    assert len(posts["facebook"]) == 400


def test_recent_topics_are_avoided(business_config, monkeypatch):
    monkeypatch.setattr(history, "recent_topics", lambda limit=5: ["topic x"])
    picks = {cg.pick_topic(business_config) for _ in range(20)}
    assert picks == {"topic y"}
