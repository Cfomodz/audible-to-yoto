from audible_to_yoto.audible_lib import Book
from audible_to_yoto.pipeline import stage_cards, stage_upload
from audible_to_yoto.pixel import number_icon, png_bytes
from audible_to_yoto.state import WorkDir, load_json


class FakeClient:
    def __init__(self):
        self.audio = []
        self.icons = []
        self.covers = []
        self.cards = []

    def upload_cover(self, jpeg):
        self.covers.append(jpeg)
        return "cov1", "https://cdn/cover.jpg"

    def upload_icon(self, png, filename):
        self.icons.append(filename)
        return f"icon{len(self.icons)}"

    def upload_audio(self, path, sha256, log=print):
        self.audio.append(path.name)
        return {"uploadId": "u", "transcodedSha256": f"t{sha256[:6]}", "duration": 120, "fileSize": 1000, "channels": "mono", "format": "mp3"}

    def create_or_update_card(self, body):
        self.cards.append(body)
        return {"cardId": body.get("cardId") or f"card{len(self.cards)}"}


def _prepare(tmp_path, chapters):
    wd = WorkDir(tmp_path, "ASIN").ensure()
    for ch in chapters:
        for t in ch.tracks:
            wd.track_path(t.no).write_bytes(f"audio{t.no}".encode())
        wd.icon_path(ch.index).write_bytes(png_bytes(number_icon(ch.index)))
    wd.cover_jpg.write_bytes(b"jpegdata")
    return wd


def test_upload_and_cards_are_idempotent(tmp_path, chapters):
    wd = _prepare(tmp_path, chapters)
    client = FakeClient()
    book = Book(asin="ASIN", title="Book", authors="Auth", description="D")
    log = lambda m: None

    track_info, icon_ids, cover_url = stage_upload(wd, chapters, wd.cover_jpg, client, log)
    assert cover_url == "https://cdn/cover.jpg"
    assert len(client.audio) == 4 and len(client.icons) == 4 and len(client.covers) == 1
    assert set(track_info) == {1, 2, 3, 4} and track_info[2]["trackUrl"].startswith("yoto:#t")
    assert icon_ids == {1: "icon1", 2: "icon2", 3: "icon3", 4: "icon4"}

    cards = stage_cards(wd, book, chapters, track_info, icon_ids, cover_url, client, log)
    assert len(cards) == 1 and cards[0]["cardId"] == "card1" and cards[0]["changed"]
    assert client.cards[0]["metadata"]["cover"] == {"imageL": "https://cdn/cover.jpg"}
    assert "cardId" not in client.cards[0]
    state = load_json(wd.card_json)
    assert state["cards"][0]["cardId"] == "card1"

    # Re-run: nothing re-uploaded, card not re-posted.
    track_info2, icon_ids2, cover_url2 = stage_upload(wd, chapters, wd.cover_jpg, client, log)
    assert len(client.audio) == 4 and len(client.icons) == 4 and len(client.covers) == 1
    cards2 = stage_cards(wd, book, chapters, track_info2, icon_ids2, cover_url2, client, log)
    assert cards2[0]["cardId"] == "card1" and not cards2[0]["changed"]
    assert len(client.cards) == 1

    # Change one icon -> that icon re-uploaded, card updated in place with cardId.
    wd.icon_path(2).write_bytes(png_bytes(number_icon(42)))
    track_info3, icon_ids3, cover_url3 = stage_upload(wd, chapters, wd.cover_jpg, client, log)
    assert len(client.icons) == 5 and icon_ids3[2] == "icon5"
    cards3 = stage_cards(wd, book, chapters, track_info3, icon_ids3, cover_url3, client, log)
    assert cards3[0]["changed"] and cards3[0]["cardId"] == "card1"
    assert client.cards[-1]["cardId"] == "card1"


def test_upload_without_cover_or_icon(tmp_path, chapters):
    wd = _prepare(tmp_path, chapters)
    wd.icon_path(3).unlink()
    client = FakeClient()
    track_info, icon_ids, cover_url = stage_upload(wd, chapters, None, client, lambda m: None)
    assert cover_url is None and icon_ids[3] is None and len(client.icons) == 3
    body_cards = stage_cards(wd, Book(asin="ASIN", title="B"), chapters, track_info, icon_ids, None, client, lambda m: None)
    assert body_cards[0]["cardId"] == "card1"
    assert "cover" not in client.cards[0]["metadata"]
    assert "display" not in client.cards[0]["content"]["chapters"][2]
