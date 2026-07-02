"""content_sync: multi-campaign folder scanning, day mapping, spacing, dedupe."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

import src.content_sync as cs

NOW = datetime(2026, 7, 10, 6, 0, tzinfo=timezone.utc)


def write_campaigns(tmp_path: Path, campaigns: dict) -> Path:
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data/campaigns.json").write_text(json.dumps({"campaigns": campaigns}))
    return tmp_path / "data/queue.json"


def write(path: Path, content: bytes | str = b"x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, str):
        path.write_text(content, encoding="utf-8")
    else:
        path.write_bytes(content)


CFG = {
    "enabled": True,
    "start_date": "2026-07-10",
    "posts_time_utc": "07:00",
    "stories_time_utc": "10:00",
}


@pytest.fixture(autouse=True)
def base_url(monkeypatch):
    monkeypatch.setenv("CONTENT_BASE_URL", "https://raw.test/")


def run(tmp_path, qp, business_config):
    return cs.sync(root=tmp_path, now=NOW, business_config=business_config, queue_path=qp)


def test_interval_rule():
    assert cs.interval_minutes(1) == 0
    assert cs.interval_minutes(2) == 360   # 6h
    assert cs.interval_minutes(3) == 240   # 4h
    assert cs.interval_minutes(4) == 180   # 3h
    assert cs.interval_minutes(10) == 180


def test_named_campaign_two_posts_six_hours_apart(tmp_path, ig_env, business_config):
    qp = write_campaigns(tmp_path, {"William Collins Ghost 1": CFG})
    base = tmp_path / "content/William Collins Ghost 1/day1/posts"
    write(base / "a.jpg")
    write(base / "b.jpg")
    write(base / "caption.txt", "Folder caption")

    added = run(tmp_path, qp, business_config)

    assert [it["scheduled_at"] for it in added] == [
        "2026-07-10T07:00:00+00:00", "2026-07-10T13:00:00+00:00",
    ]
    assert all(it["campaign"] == "William Collins Ghost 1" for it in added)
    assert all(it["post_type"] == "feed" and it["caption"] == "Folder caption" for it in added)
    assert added[0]["media_url"] == \
        "https://raw.test/content/William%20Collins%20Ghost%201/day1/posts/a.jpg"


def test_three_stories_four_hours_apart_no_caption(tmp_path, ig_env, business_config):
    qp = write_campaigns(tmp_path, {"Camp": CFG})
    for n in ("s1.jpg", "s2.jpg", "s3.jpg"):
        write(tmp_path / "content/Camp/day1/stories" / n)

    added = run(tmp_path, qp, business_config)

    assert [it["scheduled_at"] for it in added] == [
        "2026-07-10T10:00:00+00:00",
        "2026-07-10T14:00:00+00:00",
        "2026-07-10T18:00:00+00:00",
    ]
    assert all(it["post_type"] == "story" and it["caption"] == "" for it in added)


def test_day2_maps_to_next_date(tmp_path, ig_env, business_config):
    qp = write_campaigns(tmp_path, {"Camp": CFG})
    write(tmp_path / "content/Camp/day2/posts/reel.mp4")
    write(tmp_path / "content/Camp/day2/posts/reel.txt", "Reel cap")

    added = run(tmp_path, qp, business_config)
    assert added[0]["scheduled_at"] == "2026-07-11T07:00:00+00:00"
    assert added[0]["is_video"] is True
    assert added[0]["caption"] == "Reel cap"


def test_multiple_campaigns_each_own_start_date(tmp_path, ig_env, business_config):
    qp = write_campaigns(tmp_path, {
        "A": {**CFG, "start_date": "2026-07-10"},
        "B": {**CFG, "start_date": "2026-08-01"},
    })
    write(tmp_path / "content/A/day1/posts/a.jpg")
    write(tmp_path / "content/B/day1/posts/b.jpg")

    added = run(tmp_path, qp, business_config)
    by_campaign = {it["campaign"]: it["scheduled_at"] for it in added}
    assert by_campaign["A"].startswith("2026-07-10")
    assert by_campaign["B"].startswith("2026-08-01")


def test_disabled_campaign_is_skipped_enabled_one_runs(tmp_path, ig_env, business_config):
    qp = write_campaigns(tmp_path, {
        "On": {**CFG},
        "Off": {**CFG, "enabled": False},
    })
    write(tmp_path / "content/On/day1/posts/a.jpg")
    write(tmp_path / "content/Off/day1/posts/b.jpg")

    added = run(tmp_path, qp, business_config)
    assert [it["campaign"] for it in added] == ["On"]


def test_campaign_without_day_folders_treated_as_day1(tmp_path, ig_env, business_config):
    qp = write_campaigns(tmp_path, {"Flat": CFG})
    write(tmp_path / "content/Flat/posts/a.jpg")
    write(tmp_path / "content/Flat/stories/s.jpg")

    added = run(tmp_path, qp, business_config)
    assert {it["post_type"] for it in added} == {"feed", "story"}
    assert all(it["scheduled_at"].startswith("2026-07-10") for it in added)


def test_default_campaign_content_dayN(tmp_path, ig_env, business_config):
    qp = write_campaigns(tmp_path, {"": CFG})
    write(tmp_path / "content/day1/posts/a.jpg")

    added = run(tmp_path, qp, business_config)
    assert added and added[0]["campaign"] == ""
    assert added[0]["scheduled_at"].startswith("2026-07-10")


def test_legacy_campaign_json_seeds_default(tmp_path, ig_env, business_config):
    (tmp_path / "data").mkdir()
    (tmp_path / "data/campaign.json").write_text(json.dumps(CFG))
    qp = tmp_path / "data/queue.json"
    write(tmp_path / "content/day1/posts/a.jpg")

    added = cs.sync(root=tmp_path, now=NOW, business_config=business_config, queue_path=qp)
    assert added and added[0]["campaign"] == ""


def test_sidecar_beats_folder_caption(tmp_path, ig_env, business_config):
    qp = write_campaigns(tmp_path, {"C": CFG})
    write(tmp_path / "content/C/day1/posts/a.jpg")
    write(tmp_path / "content/C/day1/posts/a.txt", "Sidecar")
    write(tmp_path / "content/C/day1/posts/caption.txt", "Folder")
    added = run(tmp_path, qp, business_config)
    assert added[0]["caption"] == "Sidecar"


def test_generated_caption_when_no_text(tmp_path, ig_env, business_config, monkeypatch):
    qp = write_campaigns(tmp_path, {"C": CFG})
    write(tmp_path / "content/C/day1/posts/a.jpg")
    monkeypatch.setattr(cs.content_generator, "generate_posts",
                        lambda bc, key: ("t", {"instagram": "GENERATED"}))
    added = run(tmp_path, qp, business_config)
    assert added[0]["caption"] == "GENERATED"


def test_rerun_no_duplicate_and_new_file_continues(tmp_path, ig_env, business_config):
    qp = write_campaigns(tmp_path, {"C": CFG})
    d = tmp_path / "content/C/day1/posts"
    write(d / "a.jpg")
    write(d / "b.jpg")
    write(d / "caption.txt", "C")

    first = run(tmp_path, qp, business_config)
    assert len(first) == 2
    assert run(tmp_path, qp, business_config) == []

    write(d / "c.jpg")
    third = run(tmp_path, qp, business_config)
    assert len(third) == 1
    # 3 files now -> 4h step after last (13:00) -> 17:00
    assert third[0]["scheduled_at"] == "2026-07-10T17:00:00+00:00"
    assert len(json.loads(qp.read_text())["items"]) == 3


def test_unconverted_webp_waits_for_prepare(tmp_path, ig_env, business_config):
    qp = write_campaigns(tmp_path, {"C": CFG})
    write(tmp_path / "content/C/day1/posts/raw.webp")
    assert run(tmp_path, qp, business_config) == []
