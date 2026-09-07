import pytest

from audible_to_yoto.yotoicons import Icon, YotoIconsClient, YotoIconsError, is_empty_result, parse_icons

PAGE = """
<div class="icon" onclick="populate_icon_modal('691', 'people', 'harry potter', '', 'hedooley@gmail.', '4953');">
<div class="icon_background"><img src="/static/uploads/691.png"></div>
<div class="icon" onclick="populate_icon_modal('11393', 'vehicles', 'Hogwarts Express train', 'Harry Potter', 'curiouscat', '3470');">
<div class="icon_background"><img src="/static/uploads/11393.png"></div>
<div class="icon" onclick="populate_icon_modal('488', 'objects', 'snitch &amp; wings', 'harry potter', 'pangolinpaw', '2093');">
"""

EMPTY = "<p>Sorry, there aren&#39;t any icons with that tag. Maybe add your own?</p>"


def test_parse_icons():
    icons = parse_icons(PAGE)
    assert [i.id for i in icons] == ["691", "11393", "488"]
    first = icons[0]
    assert first.category == "people" and first.tag1 == "harry potter" and first.tag2 == ""
    assert first.author == "hedooley@gmail." and first.downloads == 4953
    assert first.url == "https://yotoicons.com/static/uploads/691.png"
    assert icons[2].tag1 == "snitch & wings"  # HTML entities decoded
    assert "harry potter" in icons[1].text and "vehicles" in icons[1].text


def test_parse_deduplicates():
    assert len(parse_icons(PAGE + PAGE)) == 3


def test_empty_marker():
    assert is_empty_result(EMPTY)
    assert not is_empty_result(PAGE)


def test_credit_line():
    assert Icon("5", "objects", "key", "", "kaylyn", 3).credit == "yotoicons #5 by kaylyn"
    assert Icon("5", "objects", "key", "", "", 3).credit == "yotoicons #5"


class FakeClient(YotoIconsClient):
    def __init__(self, pages):
        super().__init__(delay=0)
        self.pages = pages
        self.requested = []

    def _get(self, path, params=None):
        self.requested.append(params)
        page = int((params or {}).get("page", 1))
        return self.pages.get(page, EMPTY)


def test_search_paginates_until_no_new_icons():
    page2 = PAGE.replace("'691'", "'900'").replace("'11393'", "'901'").replace("'488'", "'902'")
    client = FakeClient({1: PAGE, 2: page2})
    icons = client.search("harry potter", pages=4)
    assert [i.id for i in icons] == ["691", "11393", "488", "900", "901", "902"]
    # Page 3 is empty, so it stops there rather than asking for page 4.
    assert len(client.requested) == 3


def test_search_stops_when_page_adds_nothing_new():
    client = FakeClient({1: PAGE, 2: PAGE, 3: PAGE})
    assert len(client.search("x", pages=3)) == 3
    assert len(client.requested) == 2


def test_search_caches_pages():
    client = FakeClient({1: PAGE})
    client.search("x", pages=1)
    client.search("X", pages=1)
    assert len(client.requested) == 1


def test_empty_search_returns_nothing():
    client = FakeClient({})
    assert client.search("zzqq", pages=2) == []


def test_http_error_raises():
    class Boom(YotoIconsClient):
        def _get(self, path, params=None):
            raise YotoIconsError("500")

    with pytest.raises(YotoIconsError):
        Boom(delay=0).search("x")
