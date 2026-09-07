import pytest

from audible_to_yoto.card import CardLimitError, Limits, body_hash, build_content_body, card_title, readable_size, split_into_cards
from audible_to_yoto.chapters import Chapter, plan_tracks


def _chapters(n, length_ms=60_000):
    chs = [Chapter(index=i, title=f"{i}: Chapter {i}", start_ms=(i - 1) * length_ms, length_ms=length_ms) for i in range(1, n + 1)]
    return plan_tracks(chs, "64k")


def test_split_by_track_count():
    chs = _chapters(101)
    sizes = {t.no: 1000 for c in chs for t in c.tracks}
    cards = split_into_cards(chs, sizes)
    assert [len(c) for c in cards] == [100, 1]


def test_split_by_bytes_keeps_chapters_whole():
    chs = _chapters(5)
    sizes = {t.no: 200 * 1024 * 1024 for c in chs for t in c.tracks}  # 200 MB each
    cards = split_into_cards(chs, sizes, Limits(max_card_bytes=480 * 1024 * 1024))
    assert [len(c) for c in cards] == [2, 2, 1]
    assert cards[0][0].index == 1 and cards[2][0].index == 5


def test_single_card_when_small():
    chs = _chapters(19)
    sizes = {t.no: 10_000_000 for c in chs for t in c.tracks}
    assert len(split_into_cards(chs, sizes)) == 1


def test_oversized_chapter_raises():
    chs = _chapters(1)
    sizes = {1: 600 * 1024 * 1024}
    with pytest.raises(CardLimitError):
        split_into_cards(chs, sizes)


def test_card_title_and_sizes():
    assert card_title("Book", 1, 1) == "Book"
    assert card_title("Book", 2, 3) == "Book (Part 2 of 3)"
    assert readable_size(238 * 1024 * 1024) == "238 MB"
    assert readable_size(1_500_000_000).endswith("GB")


def test_build_content_body_shape(chapters):
    track_info = {t.no: {"trackUrl": f"yoto:#sha{t.no}", "duration": 100 * t.no, "fileSize": 1000 * t.no, "channels": "mono", "format": "mp3"} for c in chapters for t in c.tracks}
    icon_ids = {1: "iconA", 2: "iconB", 3: None, 4: "iconD"}
    body = build_content_body("Harry Potter", chapters, track_info, icon_ids, cover_url="https://img", author="J.K. Rowling", description="desc", card_id="abc12")

    assert body["cardId"] == "abc12"
    assert body["title"] == "Harry Potter"
    chs = body["content"]["chapters"]
    assert [c["key"] for c in chs] == ["01", "02", "03", "04"]
    assert chs[1]["title"] == "1: The Boy Who Lived"
    assert chs[1]["overlayLabel"] == "1" and chs[0]["overlayLabel"] == ""
    assert chs[1]["display"] == {"icon16x16": "yoto:#iconB"}
    assert "display" not in chs[2]
    t = chs[1]["tracks"][0]
    assert t == {
        "key": "01", "title": "1: The Boy Who Lived", "trackUrl": "yoto:#sha2", "type": "audio", "format": "mp3",
        "duration": 200, "fileSize": 2000, "overlayLabel": "1", "channels": "mono", "display": {"icon16x16": "yoto:#iconB"},
    }
    media = body["metadata"]["media"]
    assert media["duration"] == 100 * (1 + 2 + 3 + 4)
    assert media["fileSize"] == 1000 * (1 + 2 + 3 + 4)
    assert media["readableFileSize"] == round(10000 / (1024 * 1024), 1)
    assert body["metadata"]["cover"] == {"imageL": "https://img"}
    assert body["metadata"]["author"] == "J.K. Rowling"
    assert body["metadata"]["category"] == "stories"


def test_body_hash_ignores_card_id(chapters):
    track_info = {t.no: {"trackUrl": "yoto:#x", "duration": 1, "fileSize": 1} for c in chapters for t in c.tracks}
    a = build_content_body("T", chapters, track_info, {}, card_id=None)
    b = build_content_body("T", chapters, track_info, {}, card_id="zzz")
    assert body_hash(a) == body_hash(b)
    c = build_content_body("T2", chapters, track_info, {})
    assert body_hash(a) != body_hash(c)


def test_no_card_id_when_new(chapters):
    track_info = {t.no: {"trackUrl": "yoto:#x", "duration": 1, "fileSize": 1} for c in chapters for t in c.tracks}
    body = build_content_body("T", chapters, track_info, {})
    assert "cardId" not in body and "cover" not in body["metadata"]
