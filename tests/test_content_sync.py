"""content_sync: folder scanning, day mapping, spacing, captions, dedupe."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

import src.content_sync as cs

NOW = datetime(2026, 7, 10, 6, 0, tzinfo=timezone.utc)


def setup_repo(tmp_path: Path, campaign: dict) -> Path:
    (tmp_path / "data").mkdir()
    (tmp_path / "data/campaign.json").write_text(json.dumps(campaign))
    return tmp_path / "data/queue.json"


def write(path: Path, content: bytes | str = b"x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, str):
        path.write_text(content, encoding="utf-8")
    else:
        path.write_bytes(content)


CAMPAIGN = {
    "enabled": True,
    "start_date": "2026-07-10",
    "posts_time_utc": "07:00",
    "stories_time_utc": "10:00",
}


@pytest.fixture(autouse=True)
def base_url(monkeypatch):
    monkeypatch.setenv("CONTENT_BASE_URL", "https://raw.test/")


def test_interval_rule():
    assert cs.interval_minutes(1) == 0
    assert cs.interval_minutes(2) == 360   # 6h
    assert cs.interval_minutes(3) == 240   # 4h
    assert cs.interval_minutes(4) == 180   # 3h
    assert cs.interval_minutes(10) == 180  # clamped at 3h


def test_two_posts_spread_six_hours_apart(tmp_path, ig_env, business_config):
    qp = setup_repo(tmp_path, CAMPAIGN)
    write(tmp_path / "content/day1/posts/a.jpg")
    write(tmp_path / "content/day1/posts/b.jpg")
    write(tmp_path / "content/day1/posts/caption.txt", "Folder caption")

    added = cs.sync(root=tmp_path, now=NOW, business_config=business_config, queue_path=qp)

    assert [it["scheduled_at"] for it in added] == [
        "2026-07-10T07:00:00+00:00", "2026-07-10T13:00:00+00:00",
    ]
    assert all(it["post_type"] == "feed" for it in added)
    assert all(it["caption"] == "Folder caption" for it in added)
    assert added[0]["media_url"] == "https://raw.test/content/day1/posts/a.jpg"


def test_three_stories_spread_four_hours_apart_with_no_caption(
    tmp_path, ig_env, business_config
):
    qp = setup_repo(tmp_path, CAMPAIGN)
    for name in ("s1.jpg", "s2.jpg", "s3.jpg"):
        write(tmp_path / "content/day1/stories" / name)

    added = cs.sync(root=tmp_path, now=NOW, business_config=business_config, queue_path=qp)

    assert [it["scheduled_at"] for it in added] == [
        "2026-07-10T10:00:00+00:00",
        "2026-07-10T14:00:00+00:00",
        "2026-07-10T18:00:00+00:00",
    ]
    assert all(it["post_type"] == "story" for it in added)
    assert all(it["caption"] == "" for it in added)


def test_day2_maps_to_next_date_and_videos_flagged(tmp_path, ig_env, business_config):
    qp = setup_repo(tmp_path, CAMPAIGN)
    write(tmp_path / "content/day2/posts/reel.mp4")
    write(tmp_path / "content/day2/posts/reel.txt", "Reel caption")

    added = cs.sync(root=tmp_path, now=NOW, business_config=business_config, queue_path=qp)

    assert added[0]["scheduled_at"] == "2026-07-11T07:00:00+00:00"
    assert added[0]["is_video"] is True
    assert added[0]["caption"] == "Reel caption"  # sidecar wins


def test_sidecar_caption_beats_folder_caption(tmp_path, ig_env, business_config):
    qp = setup_repo(tmp_path, CAMPAIGN)
    write(tmp_path / "content/day1/posts/a.jpg")
    write(tmp_path / "content/day1/posts/a.txt", "Sidecar")
    write(tmp_path / "content/day1/posts/caption.txt", "Folder")

    added = cs.sync(root=tmp_path, now=NOW, business_config=business_config, queue_path=qp)
    assert added[0]["caption"] == "Sidecar"


def test_generated_caption_when_no_text_files(tmp_path, ig_env, business_config, monkeypatch):
    qp = setup_repo(tmp_path, CAMPAIGN)
    write(tmp_path / "content/day1/posts/a.jpg")
    monkeypatch.setattr(
        cs.content_generator, "generate_posts",
        lambda bc, key: ("topic", {"instagram": "GENERATED"}),
    )

    added = cs.sync(root=tmp_path, now=NOW, business_config=business_config, queue_path=qp)
    assert added[0]["caption"] == "GENERATED"


def test_rerun_does_not_duplicate_and_new_files_continue_after_last_slot(
    tmp_path, ig_env, business_config
):
    qp = setup_repo(tmp_path, CAMPAIGN)
    write(tmp_path / "content/day1/posts/a.jpg")
    write(tmp_path / "content/day1/posts/b.jpg")
    write(tmp_path / "content/day1/posts/caption.txt", "C")

    first = cs.sync(root=tmp_path, now=NOW, business_config=business_config, queue_path=qp)
    assert len(first) == 2
    assert cs.sync(root=tmp_path, now=NOW, business_config=business_config, queue_path=qp) == []

    # A file added later gets the next slot after the folder's last one.
    write(tmp_path / "content/day1/posts/c.jpg")
    third = cs.sync(root=tmp_path, now=NOW, business_config=business_config, queue_path=qp)
    assert len(third) == 1
    # last slot was 13:00 (6h spacing); 3 files now -> 4h step -> 17:00
    assert third[0]["scheduled_at"] == "2026-07-10T17:00:00+00:00"

    items = json.loads(qp.read_text())["items"]
    assert len(items) == 3


def test_disabled_or_unconfigured_campaign_is_a_noop(tmp_path, ig_env, business_config):
    qp = setup_repo(tmp_path, {**CAMPAIGN, "enabled": False})
    write(tmp_path / "content/day1/posts/a.jpg")
    assert cs.sync(root=tmp_path, now=NOW, business_config=business_config, queue_path=qp) == []

    (tmp_path / "data/campaign.json").write_text(
        json.dumps({**CAMPAIGN, "start_date": ""})
    )
    assert cs.sync(root=tmp_path, now=NOW, business_config=business_config, queue_path=qp) == []


def test_unconverted_webp_waits_for_prepare(tmp_path, ig_env, business_config):
    """A .webp still present (prepare hasn't run) must not be enqueued."""
    qp = setup_repo(tmp_path, CAMPAIGN)
    write(tmp_path / "content/day1/posts/raw.webp")
    assert cs.sync(root=tmp_path, now=NOW, business_config=business_config, queue_path=qp) == []
