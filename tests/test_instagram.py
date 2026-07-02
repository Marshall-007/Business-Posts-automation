"""Instagram publisher: correct Graph API parameters per post kind."""

import pytest

import src.platforms.instagram as ig_mod
from src.config import Credentials
from src.platforms.base import PostError
from src.platforms.instagram import Instagram


class FakeResponse:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


class FakeRequests:
    """Stands in for the requests module inside the instagram platform."""

    def __init__(self, container_error=None):
        self.posts = []
        self.container_error = container_error

    def post(self, url, data=None, timeout=None):
        self.posts.append((url, dict(data or {})))
        if url.endswith("/media_publish"):
            return FakeResponse({"id": "published_1"})
        if self.container_error:
            return FakeResponse({"error": {"message": self.container_error}})
        return FakeResponse({"id": "container_1"})

    def get(self, url, params=None, timeout=None):
        if "access_token" in url or "refresh_access_token" in url:
            return FakeResponse({})  # no refresh available; keep original token
        return FakeResponse({"status_code": "FINISHED"})


@pytest.fixture
def fake_requests(monkeypatch, ig_env):
    fake = FakeRequests()
    monkeypatch.setattr(ig_mod, "requests", fake)
    return fake


def make_ig(image_urls=("https://x/img.jpg",)):
    return Instagram(Credentials(), {"image_urls": list(image_urls)})


def container_params(fake):
    url, params = fake.posts[0]
    assert url.endswith("/12345/media")
    return params


def test_feed_image_container(fake_requests):
    post_id = make_ig().publish_media("Hello", "https://x/img.jpg", "feed", False)

    params = container_params(fake_requests)
    assert params["image_url"] == "https://x/img.jpg"
    assert params["caption"] == "Hello"
    assert "media_type" not in params
    assert post_id == "published_1"
    # container then publish
    assert fake_requests.posts[1][0].endswith("/media_publish")
    assert fake_requests.posts[1][1]["creation_id"] == "container_1"


def test_feed_video_becomes_reel(fake_requests):
    make_ig().publish_media("Reel cap", "https://x/v.mp4", "feed", True)

    params = container_params(fake_requests)
    assert params["media_type"] == "REELS"
    assert params["video_url"] == "https://x/v.mp4"
    assert params["share_to_feed"] == "true"
    assert params["caption"] == "Reel cap"


def test_story_image_and_video_use_stories_container(fake_requests):
    make_ig().publish_media("ignored", "https://x/s.jpg", "story", False)
    params = container_params(fake_requests)
    assert params["media_type"] == "STORIES"
    assert params["image_url"] == "https://x/s.jpg"
    assert "caption" not in params

    fake_requests.posts.clear()
    make_ig().publish_media("ignored", "https://x/s.mp4", "story", True)
    params = container_params(fake_requests)
    assert params["media_type"] == "STORIES"
    assert params["video_url"] == "https://x/s.mp4"


def test_container_error_raises_posterror(monkeypatch, ig_env):
    fake = FakeRequests(container_error="Invalid image")
    monkeypatch.setattr(ig_mod, "requests", fake)

    with pytest.raises(PostError, match="Invalid image"):
        make_ig().publish_media("c", "https://x/bad.jpg", "feed", False)


def test_is_configured_requires_creds_and_media(ig_env, monkeypatch):
    assert make_ig().is_configured() is True
    assert make_ig(image_urls=()).is_configured() is False
    monkeypatch.delenv("INSTAGRAM_ACCESS_TOKEN")
    assert make_ig().is_configured() is False
