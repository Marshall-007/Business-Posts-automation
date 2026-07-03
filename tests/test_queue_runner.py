"""queue_runner: due-time posting, media deletion, retries, legacy items."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import src.queue_runner as qr
from src.platforms.base import PostError
from src.platforms.facebook import Facebook
from src.platforms.instagram import Instagram
from src.platforms.tiktok import TikTok

NOW = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)


def write_queue(path: Path, items: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"items": items}))


def item(tmp_path, **over):
    media = tmp_path / over.get("media_path", "docs/uploads/a.jpg")
    media.parent.mkdir(parents=True, exist_ok=True)
    media.write_bytes(b"x")
    base = {
        "id": "i1",
        "media_path": "docs/uploads/a.jpg",
        "media_url": "https://raw.test/a.jpg",
        "post_type": "feed",
        "is_video": False,
        "caption": "cap",
        "scheduled_at": (NOW - timedelta(minutes=5)).isoformat(),
        "status": "pending",
        "attempts": 0,
    }
    base.update(over)
    return base


@pytest.fixture
def fake_publish(monkeypatch):
    calls = []

    def publish(self, caption, url, post_type="feed", is_video=False):
        calls.append({"caption": caption, "url": url,
                      "post_type": post_type, "is_video": is_video})
        return "post_123"

    monkeypatch.setattr(Instagram, "publish_media", publish)
    return calls


def test_due_item_posts_and_media_is_removed(tmp_path, ig_env, fake_publish):
    qp = tmp_path / "data/queue.json"
    write_queue(qp, [item(tmp_path)])

    items = qr.process_due(now=NOW, root=tmp_path, queue_path=qp)

    assert items[0]["status"] == "posted"
    assert items[0]["post_id"] == "post_123"
    assert not (tmp_path / "docs/uploads/a.jpg").exists()
    assert fake_publish == [{
        "caption": "cap", "url": "https://raw.test/a.jpg",
        "post_type": "feed", "is_video": False,
    }]
    # persisted
    assert json.loads(qp.read_text())["items"][0]["status"] == "posted"


def test_future_item_is_untouched(tmp_path, ig_env, fake_publish):
    qp = tmp_path / "data/queue.json"
    future = item(tmp_path, scheduled_at=(NOW + timedelta(hours=2)).isoformat())
    write_queue(qp, [future])

    items = qr.process_due(now=NOW, root=tmp_path, queue_path=qp)

    assert items[0]["status"] == "pending"
    assert fake_publish == []
    assert (tmp_path / "docs/uploads/a.jpg").exists()


def test_story_and_legacy_reels_fields_map_through(tmp_path, ig_env, fake_publish):
    qp = tmp_path / "data/queue.json"
    story = item(tmp_path, id="s", post_type="story",
                 media_path="docs/uploads/s.jpg")
    legacy = item(tmp_path, id="l", media_path="docs/uploads/l.mp4",
                  media_type="REELS")
    del legacy["post_type"], legacy["is_video"]
    write_queue(qp, [story, legacy])

    qr.process_due(now=NOW, root=tmp_path, queue_path=qp)

    assert fake_publish[0]["post_type"] == "story"
    assert fake_publish[1] == {
        "caption": "cap", "url": "https://raw.test/a.jpg",
        "post_type": "feed", "is_video": True,
    }


def test_failure_retries_then_errors_after_three_attempts(tmp_path, ig_env, monkeypatch):
    qp = tmp_path / "data/queue.json"
    write_queue(qp, [item(tmp_path)])

    def boom(self, *a, **k):
        raise PostError("api down")

    monkeypatch.setattr(Instagram, "publish_media", boom)

    for expected_attempts, expected_status in ((1, "pending"), (2, "pending"), (3, "error")):
        items = qr.process_due(now=NOW, root=tmp_path, queue_path=qp)
        assert items[0]["attempts"] == expected_attempts
        assert items[0]["status"] == expected_status
        assert items[0]["last_error"] == "api down"

    # media stays for inspection; a fourth run does nothing more
    assert (tmp_path / "docs/uploads/a.jpg").exists()
    assert qr.process_due(now=NOW, root=tmp_path, queue_path=qp)[0]["attempts"] == 3


def test_daily_cap_defers_excess_posts(tmp_path, ig_env, fake_publish, monkeypatch):
    monkeypatch.setenv("IG_DAILY_CAP", "2")
    qp = tmp_path / "data/queue.json"
    write_queue(qp, [
        item(tmp_path, id="a", media_path="docs/uploads/a.jpg"),
        item(tmp_path, id="b", media_path="docs/uploads/b.jpg"),
        item(tmp_path, id="c", media_path="docs/uploads/c.jpg"),
    ])

    items = qr.process_due(now=NOW, root=tmp_path, queue_path=qp)

    assert [it["status"] for it in items] == ["posted", "posted", "pending"]
    assert len(fake_publish) == 2
    # the deferred item posts on a later run once the window allows
    later = NOW + timedelta(hours=25)
    items = qr.process_due(now=later, root=tmp_path, queue_path=qp)
    assert [it["status"] for it in items] == ["posted", "posted", "posted"]


def test_recent_posted_items_count_against_the_cap(tmp_path, ig_env, fake_publish, monkeypatch):
    monkeypatch.setenv("IG_DAILY_CAP", "2")
    qp = tmp_path / "data/queue.json"
    already = item(tmp_path, id="done", media_path="docs/uploads/done.jpg",
                   status="posted", posted_at=(NOW - timedelta(hours=1)).isoformat())
    write_queue(qp, [
        already,
        item(tmp_path, id="a", media_path="docs/uploads/a.jpg"),
        item(tmp_path, id="b", media_path="docs/uploads/b.jpg"),
    ])

    items = qr.process_due(now=NOW, root=tmp_path, queue_path=qp)

    # 1 already posted in the window + cap 2 -> only one more goes out.
    assert len(fake_publish) == 1
    assert [it["status"] for it in items] == ["posted", "posted", "pending"]


def test_due_items_post_oldest_first(tmp_path, ig_env, fake_publish):
    qp = tmp_path / "data/queue.json"
    newer = item(tmp_path, id="newer", media_path="docs/uploads/n.jpg",
                 media_url="https://raw.test/n.jpg",
                 scheduled_at=(NOW - timedelta(minutes=5)).isoformat())
    older = item(tmp_path, id="older", media_path="docs/uploads/o.jpg",
                 media_url="https://raw.test/o.jpg",
                 scheduled_at=(NOW - timedelta(hours=3)).isoformat())
    write_queue(qp, [newer, older])

    qr.process_due(now=NOW, root=tmp_path, queue_path=qp)

    assert [c["url"] for c in fake_publish] == \
        ["https://raw.test/o.jpg", "https://raw.test/n.jpg"]


@pytest.fixture
def fb_env(monkeypatch):
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "PAGE123")
    monkeypatch.setenv("FACEBOOK_PAGE_ACCESS_TOKEN", "EAAtoken")


@pytest.fixture
def tt_env(monkeypatch):
    monkeypatch.setenv("TIKTOK_CLIENT_KEY", "ck")
    monkeypatch.setenv("TIKTOK_CLIENT_SECRET", "cs")
    monkeypatch.setenv("TIKTOK_ACCESS_TOKEN", "at_live")


def test_tiktok_gets_feed_items_but_not_stories(
        tmp_path, ig_env, tt_env, fake_publish, monkeypatch):
    tt_calls = []

    def tt_pub(self, caption, url, post_type="feed", is_video=False, media_path=None):
        tt_calls.append({"post_type": post_type, "is_video": is_video, "path": media_path})
        return "tt_777"

    monkeypatch.setattr(TikTok, "publish_media", tt_pub)
    qp = tmp_path / "data/queue.json"
    write_queue(qp, [
        item(tmp_path, id="feed", media_path="docs/uploads/a.jpg"),
        item(tmp_path, id="story", post_type="story", media_path="docs/uploads/s.jpg"),
    ])

    items = qr.process_due(now=NOW, root=tmp_path, queue_path=qp)

    # Only the feed item is sent to TikTok; the story is skipped there.
    assert len(tt_calls) == 1
    assert tt_calls[0]["post_type"] == "feed"
    assert tt_calls[0]["path"].endswith("docs/uploads/a.jpg")   # local path for byte upload
    feed = next(it for it in items if it["id"] == "feed")
    story = next(it for it in items if it["id"] == "story")
    assert feed["tiktok_publish_id"] == "tt_777"
    assert "tiktok_publish_id" not in story
    assert all(it["status"] == "posted" for it in items)


def test_tiktok_failure_does_not_block_instagram(
        tmp_path, ig_env, tt_env, fake_publish, monkeypatch):
    monkeypatch.setattr(TikTok, "publish_media",
                        lambda self, *a, **k: (_ for _ in ()).throw(PostError("tt down")))
    qp = tmp_path / "data/queue.json"
    write_queue(qp, [item(tmp_path)])

    items = qr.process_due(now=NOW, root=tmp_path, queue_path=qp)

    assert items[0]["status"] == "posted"
    assert items[0]["tiktok_error"] == "tt down"
    assert not (tmp_path / "docs/uploads/a.jpg").exists()


def test_platforms_list_routes_the_post(tmp_path, ig_env, fb_env, tt_env,
                                         fake_publish, monkeypatch):
    fb_calls, tt_calls = [], []
    monkeypatch.setattr(Facebook, "publish_media",
                        lambda self, *a, **k: fb_calls.append(a) or "fb_1")
    monkeypatch.setattr(TikTok, "publish_media",
                        lambda self, *a, **k: tt_calls.append(a) or "tt_1")
    qp = tmp_path / "data/queue.json"
    write_queue(qp, [
        item(tmp_path, id="ig_fb", media_path="docs/uploads/a.jpg",
             platforms=["instagram", "facebook"]),
        item(tmp_path, id="ig_only", media_path="docs/uploads/b.jpg",
             platforms=["instagram"]),
    ])

    items = qr.process_due(now=NOW, root=tmp_path, queue_path=qp)

    assert len(fake_publish) == 2                 # both went to Instagram
    assert len(fb_calls) == 1                     # only ig_fb mirrored to FB
    assert tt_calls == []                         # tiktok never selected
    by = {it["id"]: it for it in items}
    assert by["ig_fb"]["fb_post_id"] == "fb_1"
    assert "fb_post_id" not in by["ig_only"]
    assert all(it["status"] == "posted" for it in items)


def test_facebook_becomes_primary_when_instagram_not_selected(
        tmp_path, ig_env, fb_env, fake_publish, monkeypatch):
    monkeypatch.setattr(Facebook, "publish_media",
                        lambda self, *a, **k: "fb_primary_9")
    qp = tmp_path / "data/queue.json"
    write_queue(qp, [item(tmp_path, platforms=["facebook"])])

    items = qr.process_due(now=NOW, root=tmp_path, queue_path=qp)

    assert fake_publish == []                     # Instagram untouched
    assert items[0]["status"] == "posted"
    assert items[0]["post_id"] == "fb_primary_9"
    assert items[0]["fb_post_id"] == "fb_primary_9"
    assert not (tmp_path / "docs/uploads/a.jpg").exists()   # media cleaned up


def test_no_tiktok_when_unconfigured(tmp_path, ig_env, fake_publish, monkeypatch):
    for k in ("TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET",
              "TIKTOK_REFRESH_TOKEN", "TIKTOK_ACCESS_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    called = []
    monkeypatch.setattr(TikTok, "publish_media", lambda self, *a, **k: called.append(1))
    qp = tmp_path / "data/queue.json"
    write_queue(qp, [item(tmp_path)])

    items = qr.process_due(now=NOW, root=tmp_path, queue_path=qp)
    assert called == []
    assert "tiktok_publish_id" not in items[0] and "tiktok_error" not in items[0]


def test_configured_facebook_gets_every_item_cross_posted(
        tmp_path, ig_env, fb_env, fake_publish, monkeypatch):
    fb_calls = []

    def fb_pub(self, caption, url, post_type="feed", is_video=False):
        fb_calls.append({"url": url, "post_type": post_type, "is_video": is_video})
        return "fb_999"

    monkeypatch.setattr(Facebook, "publish_media", fb_pub)
    qp = tmp_path / "data/queue.json"
    write_queue(qp, [
        item(tmp_path, id="feed", media_path="docs/uploads/a.jpg"),
        item(tmp_path, id="story", post_type="story", media_path="docs/uploads/s.jpg"),
    ])

    items = qr.process_due(now=NOW, root=tmp_path, queue_path=qp)

    assert len(fb_calls) == 2                       # both mirrored to Facebook
    assert all(it["fb_post_id"] == "fb_999" for it in items)
    assert all(it["status"] == "posted" for it in items)


def test_facebook_failure_does_not_block_instagram_or_deletion(
        tmp_path, ig_env, fb_env, fake_publish, monkeypatch):
    def fb_boom(self, *a, **k):
        raise PostError("bad page token")

    monkeypatch.setattr(Facebook, "publish_media", fb_boom)
    qp = tmp_path / "data/queue.json"
    write_queue(qp, [item(tmp_path)])

    items = qr.process_due(now=NOW, root=tmp_path, queue_path=qp)

    # Instagram still succeeded, media still removed, FB error recorded only.
    assert items[0]["status"] == "posted"
    assert items[0]["fb_error"] == "bad page token"
    assert "fb_post_id" not in items[0]
    assert not (tmp_path / "docs/uploads/a.jpg").exists()


def test_no_facebook_cross_post_when_unconfigured(
        tmp_path, ig_env, fake_publish, monkeypatch):
    monkeypatch.delenv("FACEBOOK_PAGE_ID", raising=False)
    monkeypatch.delenv("FACEBOOK_PAGE_ACCESS_TOKEN", raising=False)
    called = []
    monkeypatch.setattr(Facebook, "publish_media",
                        lambda self, *a, **k: called.append(1))
    qp = tmp_path / "data/queue.json"
    write_queue(qp, [item(tmp_path)])

    items = qr.process_due(now=NOW, root=tmp_path, queue_path=qp)

    assert called == []
    assert "fb_post_id" not in items[0] and "fb_error" not in items[0]


def test_activity_log_records_successes_and_story_failures(
        tmp_path, ig_env, fb_env, fake_publish, monkeypatch):
    # A failing Facebook story mirror must land in data/activity.json with the
    # full API error, alongside the Instagram success.
    def fb_boom(self, *a, **k):
        raise PostError("Facebook API error: (#10) Page does not have permission")

    monkeypatch.setattr(Facebook, "publish_media", fb_boom)
    qp = tmp_path / "data/queue.json"
    write_queue(qp, [item(tmp_path, id="story1", post_type="story",
                          media_path="docs/uploads/s.jpg")])

    qr.process_due(now=NOW, root=tmp_path, queue_path=qp)

    log = json.loads((tmp_path / "data/activity.json").read_text())["entries"]
    assert len(log) == 2
    by_platform = {e["platform"]: e for e in log}
    assert by_platform["instagram"]["ok"] is True
    assert by_platform["instagram"]["kind"] == "story"
    assert by_platform["facebook"]["ok"] is False
    assert "Page does not have permission" in by_platform["facebook"]["error"]


def test_unconfigured_instagram_posts_nothing(tmp_path, monkeypatch, fake_publish):
    monkeypatch.delenv("INSTAGRAM_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("INSTAGRAM_USER_ID", raising=False)
    qp = tmp_path / "data/queue.json"
    write_queue(qp, [item(tmp_path)])

    items = qr.process_due(now=NOW, root=tmp_path, queue_path=qp)

    assert items[0]["status"] == "pending"
    assert fake_publish == []
