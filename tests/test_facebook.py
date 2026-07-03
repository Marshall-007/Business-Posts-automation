"""facebook: Page photo/video/text publishing and error handling."""

import pytest

from src.config import Credentials
from src.platforms.base import PostError
from src.platforms.facebook import Facebook


@pytest.fixture
def fb_env(monkeypatch):
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "PAGE123")
    monkeypatch.setenv("FACEBOOK_PAGE_ACCESS_TOKEN", "EAAtoken")


def make_fb():
    return Facebook(Credentials(), {"business": {"name": "Gwalava"}})


class FakeResp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def test_not_configured_without_credentials(monkeypatch):
    monkeypatch.delenv("FACEBOOK_PAGE_ID", raising=False)
    monkeypatch.delenv("FACEBOOK_PAGE_ACCESS_TOKEN", raising=False)
    assert make_fb().is_configured() is False


def test_photo_post_hits_photos_endpoint_and_returns_post_id(fb_env, monkeypatch):
    calls = {}

    def fake_post(url, data=None, timeout=None):
        calls["url"] = url
        calls["data"] = data
        return FakeResp({"id": "photo_1", "post_id": "PAGE123_9"})

    monkeypatch.setattr("src.platforms.facebook.requests.post", fake_post)
    fb = make_fb()

    pid = fb.publish_media("A caption", "https://raw/x.jpg", "feed", False)

    assert pid == "PAGE123_9"                       # prefers post_id
    assert calls["url"].endswith("/PAGE123/photos")
    assert calls["data"]["url"] == "https://raw/x.jpg"
    assert calls["data"]["caption"] == "A caption"
    assert calls["data"]["access_token"] == "EAAtoken"


def test_video_post_hits_videos_endpoint(fb_env, monkeypatch):
    calls = {}

    def fake_post(url, data=None, timeout=None):
        calls["url"] = url
        calls["data"] = data
        return FakeResp({"id": "vid_1"})

    monkeypatch.setattr("src.platforms.facebook.requests.post", fake_post)
    fb = make_fb()

    pid = fb.publish_media("Reel caption", "https://raw/x.mp4", "feed", True)

    assert pid == "vid_1"
    assert calls["url"].endswith("/PAGE123/videos")
    assert calls["data"]["file_url"] == "https://raw/x.mp4"
    assert calls["data"]["description"] == "Reel caption"


def test_story_is_cross_posted_as_a_photo(fb_env, monkeypatch):
    calls = {}

    def fake_post(url, data=None, timeout=None):
        calls["url"] = url
        return FakeResp({"id": "p", "post_id": "PAGE123_10"})

    monkeypatch.setattr("src.platforms.facebook.requests.post", fake_post)
    fb = make_fb()

    fb.publish_media("", "https://raw/story.jpg", "story", False)
    assert calls["url"].endswith("/PAGE123/photos")


def test_text_publish_hits_feed_endpoint(fb_env, monkeypatch):
    calls = {}

    def fake_post(url, data=None, timeout=None):
        calls["url"] = url
        calls["data"] = data
        return FakeResp({"id": "PAGE123_11"})

    monkeypatch.setattr("src.platforms.facebook.requests.post", fake_post)
    assert make_fb().publish("Hello") == "PAGE123_11"
    assert calls["url"].endswith("/PAGE123/feed")
    assert calls["data"]["message"] == "Hello"


def test_api_error_raises_posterror(fb_env, monkeypatch):
    def fake_post(url, data=None, timeout=None):
        return FakeResp({"error": {"message": "Invalid OAuth token"}})

    monkeypatch.setattr("src.platforms.facebook.requests.post", fake_post)
    with pytest.raises(PostError, match="Invalid OAuth token"):
        make_fb().publish_media("c", "https://raw/x.jpg")


def test_non_json_response_raises_posterror(fb_env, monkeypatch):
    def fake_post(url, data=None, timeout=None):
        return FakeResp(None, status=502)

    monkeypatch.setattr("src.platforms.facebook.requests.post", fake_post)
    with pytest.raises(PostError, match="non-JSON"):
        make_fb().publish_media("c", "https://raw/x.jpg")
