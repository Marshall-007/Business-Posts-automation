"""queue_runner: due-time posting, media deletion, retries, legacy items."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import src.queue_runner as qr
from src.platforms.base import PostError
from src.platforms.facebook import Facebook
from src.platforms.instagram import Instagram

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


def test_platforms_list_routes_the_post(tmp_path, ig_env, fb_env,
                                         fake_publish, monkeypatch):
    fb_calls = []
    monkeypatch.setattr(Facebook, "publish_media",
                        lambda self, *a, **k: fb_calls.append(a) or "fb_1")
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


def test_comment_is_posted_on_both_platforms_after_publish(
        tmp_path, ig_env, fb_env, fake_publish, monkeypatch):
    # A queue item carrying a "comment" gets it posted onto both the Instagram
    # and Facebook posts, and logged to the activity feed.
    monkeypatch.setattr(Facebook, "publish_media", lambda self, *a, **k: "fb_1")
    ig_comments, fb_comments = [], []
    monkeypatch.setattr(Instagram, "post_comment",
                        lambda self, pid, msg: ig_comments.append((pid, msg)) or "igc")
    monkeypatch.setattr(Facebook, "post_comment",
                        lambda self, pid, msg: fb_comments.append((pid, msg)) or "fbc")
    qp = tmp_path / "data/queue.json"
    write_queue(qp, [item(tmp_path, platforms=["instagram", "facebook"],
                          comment="Love this!")])

    qr.process_due(now=NOW, root=tmp_path, queue_path=qp)

    assert ig_comments == [("post_123", "Love this!")]
    assert fb_comments == [("fb_1", "Love this!")]
    log = json.loads((tmp_path / "data/activity.json").read_text())["entries"]
    kinds = {(e["platform"], e["kind"], e["ok"]) for e in log}
    assert ("instagram", "comment", True) in kinds
    assert ("facebook", "comment", True) in kinds


def test_comment_failure_never_breaks_the_post(
        tmp_path, ig_env, fake_publish, monkeypatch):
    def boom(self, pid, msg):
        raise RuntimeError("comment API down")

    monkeypatch.setattr(Instagram, "post_comment", boom)
    qp = tmp_path / "data/queue.json"
    write_queue(qp, [item(tmp_path, comment="Hi")])

    items = qr.process_due(now=NOW, root=tmp_path, queue_path=qp)

    assert items[0]["status"] == "posted"                   # post still succeeded
    assert not (tmp_path / "docs/uploads/a.jpg").exists()    # media cleaned up
    log = json.loads((tmp_path / "data/activity.json").read_text())["entries"]
    assert any(e["kind"] == "comment" and e["ok"] is False for e in log)


def test_no_comment_call_when_item_has_no_comment(
        tmp_path, ig_env, fake_publish, monkeypatch):
    called = []
    monkeypatch.setattr(Instagram, "post_comment", lambda self, *a: called.append(1))
    qp = tmp_path / "data/queue.json"
    write_queue(qp, [item(tmp_path)])                       # no "comment" field

    qr.process_due(now=NOW, root=tmp_path, queue_path=qp)

    assert called == []


def test_paused_automation_posts_nothing(tmp_path, ig_env, fake_publish):
    qp = tmp_path / "data/queue.json"
    write_queue(qp, [item(tmp_path)])
    (tmp_path / "data/automation.json").write_text('{"paused": true}')

    items = qr.process_due(now=NOW, root=tmp_path, queue_path=qp)

    assert fake_publish == []                      # nothing posted
    assert items[0]["status"] == "pending"         # left untouched
    assert (tmp_path / "docs/uploads/a.jpg").exists()

    # Resuming lets it post again.
    (tmp_path / "data/automation.json").write_text('{"paused": false}')
    qr.process_due(now=NOW, root=tmp_path, queue_path=qp)
    assert len(fake_publish) == 1


def test_is_paused_defaults_to_false_when_no_file(tmp_path):
    assert qr.is_paused(tmp_path) is False


def test_failure_alert_is_sent_when_webhook_configured(
        tmp_path, ig_env, monkeypatch):
    # A publish failure posts a compact message to ALERT_WEBHOOK_URL.
    monkeypatch.setenv("ALERT_WEBHOOK_URL", "https://hooks.test/abc")

    def boom(self, *a, **k):
        raise PostError("api down")

    monkeypatch.setattr(Instagram, "publish_media", boom)
    sent = []
    monkeypatch.setattr(qr.requests, "post",
                        lambda url, **k: sent.append((url, k)) or None)
    qp = tmp_path / "data/queue.json"
    write_queue(qp, [item(tmp_path)])

    qr.process_due(now=NOW, root=tmp_path, queue_path=qp)

    assert len(sent) == 1
    url, kw = sent[0]
    assert url == "https://hooks.test/abc"
    body = kw["json"]
    # Slack ("text") and Discord ("content") both understood, same message.
    assert body["text"] == body["content"]
    assert "i1" in body["text"] and "api down" in body["text"]


def test_no_alert_when_all_succeed(tmp_path, ig_env, fake_publish, monkeypatch):
    monkeypatch.setenv("ALERT_WEBHOOK_URL", "https://hooks.test/abc")
    sent = []
    monkeypatch.setattr(qr.requests, "post", lambda url, **k: sent.append(url))
    qp = tmp_path / "data/queue.json"
    write_queue(qp, [item(tmp_path)])

    qr.process_due(now=NOW, root=tmp_path, queue_path=qp)

    assert sent == []


def test_no_alert_without_webhook_url(tmp_path, ig_env, monkeypatch):
    monkeypatch.delenv("ALERT_WEBHOOK_URL", raising=False)

    def boom(self, *a, **k):
        raise PostError("api down")

    monkeypatch.setattr(Instagram, "publish_media", boom)
    sent = []
    monkeypatch.setattr(qr.requests, "post", lambda url, **k: sent.append(url))
    qp = tmp_path / "data/queue.json"
    write_queue(qp, [item(tmp_path)])

    qr.process_due(now=NOW, root=tmp_path, queue_path=qp)

    assert sent == []


def test_alert_webhook_error_never_breaks_the_run(tmp_path, ig_env, monkeypatch):
    # A dead webhook must not raise out of process_due.
    monkeypatch.setenv("ALERT_WEBHOOK_URL", "https://hooks.test/abc")

    def boom(self, *a, **k):
        raise PostError("api down")

    monkeypatch.setattr(Instagram, "publish_media", boom)

    def dead_post(url, **k):
        raise qr.requests.RequestException("connection refused")

    monkeypatch.setattr(qr.requests, "post", dead_post)
    qp = tmp_path / "data/queue.json"
    write_queue(qp, [item(tmp_path)])

    # Does not raise; the failure is still recorded on the item.
    items = qr.process_due(now=NOW, root=tmp_path, queue_path=qp)
    assert items[0]["attempts"] == 1


def test_unconfigured_instagram_posts_nothing(tmp_path, monkeypatch, fake_publish):
    monkeypatch.delenv("INSTAGRAM_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("INSTAGRAM_USER_ID", raising=False)
    qp = tmp_path / "data/queue.json"
    write_queue(qp, [item(tmp_path)])

    items = qr.process_due(now=NOW, root=tmp_path, queue_path=qp)

    assert items[0]["status"] == "pending"
    assert fake_publish == []
