from audible_to_yoto.chapters import (
    Chapter,
    bytes_per_second,
    chapter_number,
    estimate_bytes,
    flatten_raw,
    is_credits,
    normalize_chapters,
    overlay_label,
    plan_tracks,
    track_title,
)


def test_normalize_keeps_real_titles_and_order(hp_raw):
    chs = normalize_chapters(hp_raw)
    assert [c.title for c in chs] == ["Opening Credits", "1: The Boy Who Lived", "2: The Vanishing Glass", "End Credits"]
    assert [c.index for c in chs] == [1, 2, 3, 4]
    assert chs[0].credits and chs[3].credits and not chs[1].credits
    assert chs[1].start_ms == 63970 and chs[1].end_ms == 1794414


def test_normalize_skip_credits_renumbers(hp_raw):
    chs = normalize_chapters(hp_raw, skip_credits=True)
    assert [c.title for c in chs] == ["1: The Boy Who Lived", "2: The Vanishing Glass"]
    assert [c.index for c in chs] == [1, 2]


def test_normalize_drops_zero_length_and_sorts():
    raw = {"content_metadata": {"chapter_info": {"chapters": [
        {"title": "B", "start_offset_ms": 500, "length_ms": 10},
        {"title": "Z", "start_offset_ms": 900, "length_ms": 0},
        {"title": "A", "start_offset_ms": 0, "length_ms": 500},
    ]}}}
    assert [c.title for c in normalize_chapters(raw)] == ["A", "B"]


def test_flatten_nested_prefixes_parent():
    nested = [{"title": "Part One", "start_offset_ms": 0, "length_ms": 0, "chapters": [
        {"title": "Chapter 1", "start_offset_ms": 0, "length_ms": 5},
        {"title": "Chapter 2", "start_offset_ms": 5, "length_ms": 5},
    ]}]
    flat = flatten_raw(nested)
    assert [c["title"] for c in flat] == ["Part One - Chapter 1", "Part One - Chapter 2"]


def test_credits_and_numbers():
    assert is_credits("Opening Credits") and is_credits(" end credits ") and is_credits("Closing Credits")
    assert not is_credits("Credits Roll")
    assert chapter_number("7: The Sorting Hat") == 7
    assert chapter_number("Chapter 12") == 12
    assert chapter_number("12 - Quidditch") == 12
    assert chapter_number("Epilogue") is None


def test_overlay_label():
    assert overlay_label(Chapter(index=3, title="7: The Sorting Hat", start_ms=0, length_ms=1)) == "7"
    assert overlay_label(Chapter(index=3, title="Epilogue", start_ms=0, length_ms=1)) == "3"
    assert overlay_label(Chapter(index=1, title="Opening Credits", start_ms=0, length_ms=1, credits=True)) == ""


def test_bitrate_math():
    assert bytes_per_second("64k") == 8000
    assert bytes_per_second("128K") == 16000
    assert estimate_bytes(3_600_000, "64k") == 28_800_000


def test_plan_tracks_splits_long_chapter():
    hour = 60 * 60 * 1000
    chs = [
        Chapter(index=1, title="Short", start_ms=0, length_ms=1000),
        Chapter(index=2, title="Long", start_ms=1000, length_ms=hour + 60_000),
        Chapter(index=3, title="After", start_ms=hour + 61_000, length_ms=1000),
    ]
    plan_tracks(chs, "64k")
    assert [len(c.tracks) for c in chs] == [1, 2, 1]
    assert [t.no for c in chs for t in c.tracks] == [1, 2, 3, 4]
    long_tracks = chs[1].tracks
    assert long_tracks[0].start_ms == 1000
    assert long_tracks[1].start_ms == 1000 + long_tracks[0].length_ms
    assert sum(t.length_ms for t in long_tracks) == hour + 60_000
    assert all(t.length_ms <= hour for t in long_tracks)
    assert track_title(chs[1], long_tracks[1]) == "Long (2/2)"
    assert track_title(chs[0], chs[0].tracks[0]) == "Short"
    assert chs[1].tracks[0].file == "mp3/002.mp3"


def test_plan_tracks_splits_by_size_at_high_bitrate():
    ch = Chapter(index=1, title="Big", start_ms=0, length_ms=50 * 60 * 1000)
    plan_tracks([ch], "320k")  # 50 min at 40 KB/s = 120 MB > 95 MB cap
    assert len(ch.tracks) == 2


def test_round_trip_dict(chapters):
    d = chapters[1].to_dict()
    assert d["tracks"][0]["file"] == "mp3/002.mp3"
    back = Chapter.from_dict(d)
    assert back == chapters[1]
