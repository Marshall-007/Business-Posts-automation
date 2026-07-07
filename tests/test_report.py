"""report: pure aggregation, posted-only filtering, and generate() writeout."""

import json
from datetime import datetime, timezone
from pathlib import Path

import src.report as rp

NOW = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)


def posted(**over):
    base = {
        "id": "i1", "status": "posted", "campaign": "WC", "post_type": "feed",
        "posted_at": "2026-07-09T07:00:00+00:00", "caption": "hello",
        "ig_post_id": "IG1", "fb_post_id": "FB1",
    }
    base.update(over)
    return base


def test_build_report_aggregates_both_platforms():
    items = [
        posted(id="a", ig_post_id="IGa", fb_post_id="FBa"),
        posted(id="b", ig_post_id="IGb", fb_post_id=None),
    ]
    ig = lambda mid: {"likes": 10, "comments": 2, "reach": 100}
    fb = lambda pid: {"likes": 5, "comments": 1, "shares": 3}

    rep = rp.build_report(items, ig, fb, now=NOW)

    assert rep["totals"]["posts"] == 2
    assert rep["totals"]["instagram"] == {"likes": 20, "comments": 4, "reach": 200}
    # Only item "a" had a Facebook id, so FB totals count it once.
    assert rep["totals"]["facebook"] == {"likes": 5, "comments": 1, "shares": 3}
    a = next(r for r in rep["items"] if r["id"] == "a")
    assert a["instagram"]["post_id"] == "IGa"
    assert a["facebook"]["likes"] == 5
    b = next(r for r in rep["items"] if r["id"] == "b")
    assert "facebook" not in b


def test_pending_and_idless_items_are_skipped():
    items = [
        posted(id="ok"),
        {"id": "pending", "status": "pending", "ig_post_id": "X"},
        {"id": "noid", "status": "posted"},
    ]
    rep = rp.build_report(items, lambda m: {"likes": 1}, lambda p: {"likes": 1}, now=NOW)
    assert [r["id"] for r in rep["items"]] == ["ok"]
    assert rep["totals"]["posts"] == 1


def test_missing_metrics_are_tolerated():
    # A fetcher that returns nothing (e.g. a story with no like_count) must not
    # break aggregation; the item still appears, just without those numbers.
    rep = rp.build_report([posted(fb_post_id=None)], lambda m: {}, lambda p: {}, now=NOW)
    assert rep["totals"]["posts"] == 1
    assert rep["totals"]["instagram"] == {}
    assert rep["items"][0]["instagram"] == {"post_id": "IG1"}


def test_items_sorted_newest_first():
    items = [
        posted(id="old", posted_at="2026-07-01T07:00:00+00:00"),
        posted(id="new", posted_at="2026-07-09T07:00:00+00:00"),
    ]
    rep = rp.build_report(items, lambda m: {}, lambda p: {}, now=NOW)
    assert [r["id"] for r in rep["items"]] == ["new", "old"]


def test_generate_writes_report_json(tmp_path, monkeypatch):
    qp = tmp_path / "data/queue.json"
    qp.parent.mkdir(parents=True)
    qp.write_text(json.dumps({"items": [posted()]}))
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "IGAAtok")
    monkeypatch.setenv("FACEBOOK_PAGE_ACCESS_TOKEN", "EAAtok")
    monkeypatch.setattr(rp, "fetch_instagram_metrics", lambda mid, tok: {"likes": 7})
    monkeypatch.setattr(rp, "fetch_facebook_metrics", lambda pid, tok: {"likes": 4})

    rep = rp.generate(root=tmp_path, now=NOW)

    on_disk = json.loads((tmp_path / "data/report.json").read_text())
    assert on_disk == rep
    assert rep["totals"]["instagram"]["likes"] == 7
    assert rep["totals"]["facebook"]["likes"] == 4


def test_generate_without_tokens_fetches_nothing(tmp_path, monkeypatch):
    qp = tmp_path / "data/queue.json"
    qp.parent.mkdir(parents=True)
    qp.write_text(json.dumps({"items": [posted()]}))
    monkeypatch.delenv("INSTAGRAM_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("FACEBOOK_PAGE_ACCESS_TOKEN", raising=False)
    # If the fetchers were called they'd hit the network; assert they are not.
    monkeypatch.setattr(rp, "fetch_instagram_metrics",
                        lambda *a: (_ for _ in ()).throw(AssertionError("called")))
    monkeypatch.setattr(rp, "fetch_facebook_metrics",
                        lambda *a: (_ for _ in ()).throw(AssertionError("called")))

    rep = rp.generate(root=tmp_path, now=NOW)

    assert rep["totals"]["posts"] == 1
    assert rep["items"][0]["instagram"] == {"post_id": "IG1"}
