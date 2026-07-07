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


def test_photo_story_uploads_unpublished_then_posts_photo_story(fb_env, monkeypatch):
    calls = []

    def fake_post(url, data=None, headers=None, timeout=None):
        calls.append({"url": url, "data": dict(data or {}), "headers": headers})
        if url.endswith("/PAGE123/photos"):
            return FakeResp({"id": "photo_77"})
        if url.endswith("/PAGE123/photo_stories"):
            return FakeResp({"success": True, "post_id": "PAGE123_STORY_5"})
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr("src.platforms.facebook.requests.post", fake_post)

    pid = make_fb().publish_media("", "https://raw/story.jpg", "story", False)

    assert pid == "PAGE123_STORY_5"
    assert calls[0]["url"].endswith("/PAGE123/photos")
    assert calls[0]["data"]["published"] == "false"     # unpublished first
    assert calls[0]["data"]["url"] == "https://raw/story.jpg"
    assert calls[1]["url"].endswith("/PAGE123/photo_stories")
    assert calls[1]["data"]["photo_id"] == "photo_77"


def test_video_story_runs_the_three_step_upload(fb_env, monkeypatch):
    calls = []
    UPLOAD_URL = "https://rupload.facebook.com/video-upload/v21.0/vid_99"

    def fake_post(url, data=None, headers=None, timeout=None):
        calls.append({"url": url, "data": dict(data or {}), "headers": headers})
        if url.endswith("/PAGE123/video_stories") and (data or {}).get("upload_phase") == "start":
            return FakeResp({"video_id": "vid_99", "upload_url": UPLOAD_URL})
        if url == UPLOAD_URL:
            return FakeResp({"success": True})
        if url.endswith("/PAGE123/video_stories") and (data or {}).get("upload_phase") == "finish":
            return FakeResp({"post_id": "PAGE123_STORY_6"})
        raise AssertionError(f"unexpected URL {url} / data {data}")

    monkeypatch.setattr("src.platforms.facebook.requests.post", fake_post)

    pid = make_fb().publish_media("", "https://raw/story.mp4", "story", True)

    assert pid == "PAGE123_STORY_6"
    assert [c["url"] for c in calls] == [
        f"{'https://graph.facebook.com/v21.0'}/PAGE123/video_stories",
        UPLOAD_URL,
        f"{'https://graph.facebook.com/v21.0'}/PAGE123/video_stories",
    ]
    # Upload step must forward the public URL and Page token as headers.
    assert calls[1]["headers"]["file_url"] == "https://raw/story.mp4"
    assert calls[1]["headers"]["Authorization"] == "OAuth EAAtoken"
    # Finish step publishes the video.
    assert calls[2]["data"]["upload_phase"] == "finish"
    assert calls[2]["data"]["video_id"] == "vid_99"
    assert calls[2]["data"]["video_state"] == "PUBLISHED"


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


def test_post_comment_hits_comments_edge(fb_env, monkeypatch):
    calls = {}

    def fake_post(url, data=None, timeout=None):
        calls["url"] = url
        calls["data"] = data
        return FakeResp({"id": "comment_1"})

    monkeypatch.setattr("src.platforms.facebook.requests.post", fake_post)
    cid = make_fb().post_comment("PAGE123_9", "Great work")

    assert cid == "comment_1"
    assert calls["url"].endswith("/PAGE123_9/comments")
    assert calls["data"]["message"] == "Great work"
    assert calls["data"]["access_token"] == "EAAtoken"


def test_post_comment_skips_when_blank(fb_env, monkeypatch):
    calls = []
    monkeypatch.setattr("src.platforms.facebook.requests.post",
                        lambda *a, **k: calls.append(1))
    assert make_fb().post_comment("PAGE123_9", "  ") == ""
    assert make_fb().post_comment("", "hi") == ""
    assert calls == []


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
