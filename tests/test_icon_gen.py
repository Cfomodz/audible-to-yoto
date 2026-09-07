import hashlib

from PIL import Image

from audible_to_yoto.chapters import Chapter, plan_tracks
from audible_to_yoto.icon_gen import chapter_icon, credits, generate_icons, write_preview
from audible_to_yoto.pixel import book_icon, number_icon, png_bytes
from audible_to_yoto.state import WorkDir, load_json
from audible_to_yoto.yotoicons import Icon, YotoIconsError


def _quiet(_msg):
    return None


def _icon(id_, tag1, tag2="harry potter"):
    return Icon(id=id_, category="objects", tag1=tag1, tag2=tag2, author="someone", downloads=100)


class StubClient:
    """Stands in for YotoIconsClient: canned search results, coloured PNGs, no network."""

    def __init__(self, results=None, fail_download=False):
        self.results = results or {}
        self.searches = []
        self.downloads = []
        self.fail_download = fail_download

    def search(self, tag, pages=1):
        self.searches.append(tag)
        return list(self.results.get(tag.lower(), []))

    def download(self, icon):
        self.downloads.append(icon.id)
        if self.fail_download:
            raise YotoIconsError("boom")
        return png_bytes(number_icon(int(icon.id) % 100))


def _pool():
    return {
        "harry potter": [
            _icon("101", "sorting hat"),
            _icon("102", "quidditch"),
            _icon("103", "cauldron potion"),
        ]
    }


def _chapters():
    chs = [
        Chapter(index=1, title="Opening Credits", start_ms=0, length_ms=1000, credits=True),
        Chapter(index=2, title="7: The Sorting Hat", start_ms=1000, length_ms=1000),
        Chapter(index=3, title="11: Quidditch", start_ms=2000, length_ms=1000),
        Chapter(index=4, title="99: Nothing Matches Here", start_ms=3000, length_ms=1000),
    ]
    return plan_tracks(chs, "64k")


def test_chapter_icon_fallback_glyphs(chapters):
    assert chapter_icon(chapters[0]).tobytes() == book_icon(closed=False).tobytes()
    assert chapter_icon(chapters[3]).tobytes() == book_icon(closed=True).tobytes()
    assert chapter_icon(chapters[1]).tobytes() == number_icon(1).tobytes()


def test_matches_from_yotoicons_and_falls_back(tmp_path):
    chs = _chapters()
    wd = WorkDir(tmp_path, "ASIN").ensure()
    client = StubClient(_pool())

    paths = generate_icons(wd, chs, title="Harry Potter", source="yotoicons", client=client, log=_quiet)
    assert all(p.exists() for p in paths.values())

    meta = load_json(wd.icons_json)
    assert meta["search_tag"] == "harry potter"
    assert meta["icons"]["2"]["yotoicon"]["id"] == "101"
    assert meta["icons"]["3"]["yotoicon"]["id"] == "102"
    assert meta["icons"]["2"]["source"] == "yotoicons"
    # Credits and unmatched chapters get generated drawings.
    assert meta["icons"]["1"]["source"] == "generated"
    assert meta["icons"]["4"]["source"] == "generated"
    assert wd.icon_path(1).read_bytes() == png_bytes(book_icon(closed=False))
    assert credits(wd) == ["chapter 2: yotoicons #101 by someone", "chapter 3: yotoicons #102 by someone"]


def test_icons_are_unique_per_book(tmp_path):
    chs = _chapters()
    # Two chapters that both want the same icon; only one can have it.
    chs[2].title = "12: The Sorting Hat Again"
    wd = WorkDir(tmp_path, "ASIN").ensure()
    generate_icons(wd, chs, title="Harry Potter", source="yotoicons", client=StubClient(_pool()), log=_quiet)
    meta = load_json(wd.icons_json)
    used = [v["yotoicon"]["id"] for v in meta["icons"].values() if v.get("yotoicon")]
    assert len(used) == len(set(used))


def test_second_run_reuses_matches_without_searching(tmp_path):
    chs = _chapters()
    wd = WorkDir(tmp_path, "ASIN").ensure()
    generate_icons(wd, chs, title="Harry Potter", source="yotoicons", client=StubClient(_pool()), log=_quiet)

    again = StubClient(_pool())
    generate_icons(wd, chs, title="Harry Potter", source="yotoicons", client=again, log=_quiet)
    assert again.searches == [] and again.downloads == []


def test_regenerate_searches_again(tmp_path):
    chs = _chapters()
    wd = WorkDir(tmp_path, "ASIN").ensure()
    generate_icons(wd, chs, title="Harry Potter", source="yotoicons", client=StubClient(_pool()), log=_quiet)
    again = StubClient(_pool())
    generate_icons(wd, chs, title="Harry Potter", source="yotoicons", client=again, force=True, log=_quiet)
    assert "harry potter" in again.searches
    # The PNG itself comes from the on-disk cache, so no second download is needed.
    assert again.downloads == []


def test_changed_chapters_trigger_a_new_search(tmp_path):
    chs = _chapters()
    wd = WorkDir(tmp_path, "ASIN").ensure()
    generate_icons(wd, chs, title="Harry Potter", source="yotoicons", client=StubClient(_pool()), log=_quiet)
    renamed = _chapters()
    renamed[3].title = "99: Quidditch Practice"
    again = StubClient(_pool())
    generate_icons(wd, renamed, title="Harry Potter", source="yotoicons", client=again, log=_quiet)
    assert "harry potter" in again.searches


def test_generated_source_never_searches(tmp_path):
    chs = _chapters()
    wd = WorkDir(tmp_path, "ASIN").ensure()
    client = StubClient(_pool())
    generate_icons(wd, chs, title="Harry Potter", source="generated", client=client, log=_quiet)
    assert client.searches == []
    meta = load_json(wd.icons_json)
    assert all(v["source"] == "generated" for v in meta["icons"].values())


def test_empty_search_falls_back_to_generated(tmp_path):
    chs = _chapters()
    wd = WorkDir(tmp_path, "ASIN").ensure()
    generate_icons(wd, chs, title="Unknown Book", source="yotoicons", client=StubClient({}), log=_quiet)
    meta = load_json(wd.icons_json)
    assert all(v["source"] == "generated" for v in meta["icons"].values())
    assert all(wd.icon_path(c.index).exists() for c in chs)


def test_download_failure_falls_back(tmp_path):
    chs = _chapters()
    wd = WorkDir(tmp_path, "ASIN").ensure()
    generate_icons(wd, chs, title="Harry Potter", source="yotoicons", client=StubClient(_pool(), fail_download=True), log=_quiet)
    meta = load_json(wd.icons_json)
    assert all(v["source"] == "generated" for v in meta["icons"].values())
    assert all(wd.icon_path(c.index).exists() for c in chs)


def test_explicit_tag_overrides_book_title(tmp_path):
    chs = _chapters()
    wd = WorkDir(tmp_path, "ASIN").ensure()
    client = StubClient({"wizarding world": [_icon("101", "sorting hat")]})
    generate_icons(wd, chs, title="Harry Potter", source="yotoicons", tag="wizarding world", client=client, log=_quiet)
    assert client.searches[0] == "wizarding world"
    assert "harry potter" not in client.searches  # the book title is never searched
    assert load_json(wd.icons_json)["icons"]["2"]["yotoicon"]["id"] == "101"


def test_custom_icon_is_never_clobbered(tmp_path):
    chs = _chapters()
    wd = WorkDir(tmp_path, "ASIN").ensure()
    generate_icons(wd, chs, title="Harry Potter", source="yotoicons", client=StubClient(_pool()), log=_quiet)

    mine = png_bytes(number_icon(7))
    wd.icon_path(2).write_bytes(mine)
    generate_icons(wd, chs, title="Harry Potter", source="yotoicons", client=StubClient(_pool()), log=_quiet)
    assert wd.icon_path(2).read_bytes() == mine
    assert load_json(wd.icons_json)["icons"]["2"]["png_sha256"] == hashlib.sha256(mine).hexdigest()

    generate_icons(wd, chs, title="Harry Potter", source="yotoicons", client=StubClient(_pool()), force=True, log=_quiet)
    assert wd.icon_path(2).read_bytes() != mine


def test_generated_icon_refreshes_when_chapter_changes(tmp_path, chapters):
    wd = WorkDir(tmp_path, "ASIN").ensure()
    generate_icons(wd, chapters, source="generated", log=_quiet)
    before = wd.icon_path(2).read_bytes()
    renamed = [Chapter(index=c.index, title=c.title, start_ms=c.start_ms, length_ms=c.length_ms, credits=c.credits) for c in chapters]
    renamed[1].title = "9: Renamed"
    plan_tracks(renamed, "64k")
    generate_icons(wd, renamed, source="generated", log=_quiet)
    assert wd.icon_path(2).read_bytes() != before


def test_missing_file_is_rewritten(tmp_path, chapters):
    wd = WorkDir(tmp_path, "ASIN").ensure()
    generate_icons(wd, chapters, source="generated", log=_quiet)
    wd.icon_path(3).unlink()
    generate_icons(wd, chapters, source="generated", log=_quiet)
    assert wd.icon_path(3).exists()


def test_dropped_chapters_are_forgotten(tmp_path, chapters):
    wd = WorkDir(tmp_path, "ASIN").ensure()
    generate_icons(wd, chapters, source="generated", log=_quiet)
    generate_icons(wd, chapters[:2], source="generated", log=_quiet)
    assert set(load_json(wd.icons_json)["icons"]) == {"1", "2"}


def test_preview_labels_matched_icons(tmp_path):
    chs = _chapters()
    wd = WorkDir(tmp_path, "ASIN").ensure()
    generate_icons(wd, chs, title="Harry Potter", source="yotoicons", client=StubClient(_pool()), log=_quiet)
    preview = write_preview(wd, chs)
    assert preview.exists() and Image.open(preview).size[0] > 0
