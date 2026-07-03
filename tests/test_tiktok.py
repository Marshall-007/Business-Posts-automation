"""tiktok: Content Posting API video/photo publishing, auth, story skip."""

import pytest

from src.config import Credentials
from src.platforms.base import PostError
from src.platforms.tiktok import TikTok


@pytest.fixture
def tt_env(monkeypatch):
    monkeypatch.setenv("TIKTOK_CLIENT_KEY", "ck")
    monkeypatch.setenv("TIKTOK_CLIENT_SECRET", "cs")
    monkeypatch.setenv("TIKTOK_REFRESH_TOKEN", "rt")
    monkeypatch.setenv("TIKTOK_ACCESS_TOKEN", "at_live")
    monkeypatch.delenv("TIKTOK_PRIVACY_LEVEL", raising=False)


def make_tt():
    return TikTok(Credentials(), {"business": {"name": "Gwalava"}})


class FakeResp:
    def __init__(self, payload=None, status=200):
        self._payload = payload
        self.status_code = status
        self.content = b"x"

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def test_not_configured_without_credentials(monkeypatch):
    for k in ("TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET",
              "TIKTOK_REFRESH_TOKEN", "TIKTOK_ACCESS_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    assert make_tt().is_configured() is False


def test_configured_with_client_and_refresh(tt_env):
    assert make_tt().is_configured() is True


def test_story_is_skipped(tt_env):
    with pytest.raises(PostError, match="no Stories API"):
        make_tt().publish_media("c", "https://raw/s.jpg", "story", False)


def test_photo_uses_pull_from_url_and_privacy_default(tt_env, monkeypatch):
    calls = {}

    def fake_post(url, json=None, headers=None, data=None, timeout=None):
        calls["url"] = url
        calls["json"] = json
        calls["auth"] = headers.get("Authorization")
        return FakeResp({"data": {"publish_id": "pub_photo_1"}, "error": {"code": "ok"}})

    monkeypatch.setattr("src.platforms.tiktok.requests.post", fake_post)

    pid = make_tt().publish_media("Kitchen boards", "https://raw/x.jpg", "feed", False)

    assert pid == "pub_photo_1"
    assert calls["url"].endswith("/post/publish/content/init/")
    assert calls["json"]["source_info"]["source"] == "PULL_FROM_URL"
    assert calls["json"]["source_info"]["photo_images"] == ["https://raw/x.jpg"]
    assert calls["json"]["media_type"] == "PHOTO"
    assert calls["json"]["post_info"]["privacy_level"] == "SELF_ONLY"   # unaudited default
    assert calls["auth"] == "Bearer at_live"                            # stored token used


def test_video_file_upload_reads_local_bytes_and_puts_them(tt_env, tmp_path, monkeypatch):
    vid = tmp_path / "clip.mp4"
    vid.write_bytes(b"VIDEO-BYTES-1234")
    posts, puts = [], []

    def fake_post(url, json=None, headers=None, data=None, timeout=None):
        posts.append({"url": url, "json": json})
        return FakeResp({"data": {"publish_id": "pub_vid_9",
                                  "upload_url": "https://upload.tiktok/abc"},
                         "error": {"code": "ok"}})

    def fake_put(url, data=None, headers=None, timeout=None):
        puts.append({"url": url, "data": data, "headers": headers})
        return FakeResp(status=201)

    monkeypatch.setattr("src.platforms.tiktok.requests.post", fake_post)
    monkeypatch.setattr("src.platforms.tiktok.requests.put", fake_put)

    pid = make_tt().publish_media("Reel!", "https://raw/clip.mp4", "feed", True, str(vid))

    assert pid == "pub_vid_9"
    assert posts[0]["url"].endswith("/post/publish/video/init/")
    assert posts[0]["json"]["source_info"]["source"] == "FILE_UPLOAD"
    assert posts[0]["json"]["source_info"]["video_size"] == len(b"VIDEO-BYTES-1234")
    # bytes uploaded to the returned URL with a full-range header
    assert puts[0]["url"] == "https://upload.tiktok/abc"
    assert puts[0]["data"] == b"VIDEO-BYTES-1234"
    assert puts[0]["headers"]["Content-Range"] == "bytes 0-15/16"


def test_public_privacy_when_configured(tt_env, monkeypatch):
    monkeypatch.setenv("TIKTOK_PRIVACY_LEVEL", "PUBLIC_TO_EVERYONE")
    captured = {}

    def fake_post(url, json=None, headers=None, data=None, timeout=None):
        captured["json"] = json
        return FakeResp({"data": {"publish_id": "p"}, "error": {"code": "ok"}})

    monkeypatch.setattr("src.platforms.tiktok.requests.post", fake_post)
    make_tt().publish_media("c", "https://raw/x.jpg", "feed", False)
    assert captured["json"]["post_info"]["privacy_level"] == "PUBLIC_TO_EVERYONE"


def test_access_token_minted_from_refresh_when_no_stored_token(monkeypatch):
    monkeypatch.setenv("TIKTOK_CLIENT_KEY", "ck")
    monkeypatch.setenv("TIKTOK_CLIENT_SECRET", "cs")
    monkeypatch.setenv("TIKTOK_REFRESH_TOKEN", "rt")
    monkeypatch.delenv("TIKTOK_ACCESS_TOKEN", raising=False)
    seen = {}

    def fake_post(url, json=None, headers=None, data=None, timeout=None):
        if url.endswith("/oauth/token/"):
            seen["refresh"] = data
            return FakeResp({"access_token": "at_fresh", "refresh_token": "rt2"})
        seen["auth"] = headers.get("Authorization")
        return FakeResp({"data": {"publish_id": "p"}, "error": {"code": "ok"}})

    monkeypatch.setattr("src.platforms.tiktok.requests.post", fake_post)
    make_tt().publish_media("c", "https://raw/x.jpg", "feed", False)

    assert seen["refresh"]["grant_type"] == "refresh_token"
    assert seen["auth"] == "Bearer at_fresh"


def test_api_error_raises_posterror(tt_env, monkeypatch):
    def fake_post(url, json=None, headers=None, data=None, timeout=None):
        return FakeResp({"error": {"code": "spam_risk_too_many_posts",
                                   "message": "Too many posts"}})

    monkeypatch.setattr("src.platforms.tiktok.requests.post", fake_post)
    with pytest.raises(PostError, match="Too many posts"):
        make_tt().publish_media("c", "https://raw/x.jpg", "feed", False)
