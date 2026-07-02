"""queue_runner: due-time posting, media deletion, retries, legacy items."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import src.queue_runner as qr
from src.platforms.base import PostError
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


def test_unconfigured_instagram_posts_nothing(tmp_path, monkeypatch, fake_publish):
    monkeypatch.delenv("INSTAGRAM_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("INSTAGRAM_USER_ID", raising=False)
    qp = tmp_path / "data/queue.json"
    write_queue(qp, [item(tmp_path)])

    items = qr.process_due(now=NOW, root=tmp_path, queue_path=qp)

    assert items[0]["status"] == "pending"
    assert fake_publish == []
