import json

import pytest

from audible_to_yoto.audible_lib import AudibleError, Book, _title_base, book_from_export, find_download, read_voucher, resolve_books


def test_book_from_export_handles_lists_and_dashes():
    row = {
        "asin": "B01", "title": "T", "authors": [{"name": "A"}, {"name": "B"}], "narrators": "N",
        "cover_url": "-", "runtime_length_min": "499", "extended_product_description": "<p>Hi <b>there</b></p>",
    }
    b = book_from_export(row)
    assert b.authors == "A, B" and b.narrators == "N" and b.cover_url == "" and b.runtime_min == 499
    assert b.description == "Hi there"
    assert round(b.hours, 2) == 8.32


def _books():
    return [Book(asin="B1", title="Harry Potter and the Sorcerer's Stone"), Book(asin="B2", title="Harry Potter and the Chamber of Secrets"), Book(asin="B3", title="Matilda")]


def test_resolve_by_asin_case_insensitive():
    assert resolve_books(_books(), asin="b3")[0].title == "Matilda"
    with pytest.raises(AudibleError):
        resolve_books(_books(), asin="nope")


def test_resolve_by_title():
    assert resolve_books(_books(), title="matilda")[0].asin == "B3"
    assert resolve_books(_books(), title="chamber")[0].asin == "B2"
    with pytest.raises(AudibleError, match="2 books match"):
        resolve_books(_books(), title="harry potter")
    with pytest.raises(AudibleError, match="No book"):
        resolve_books(_books(), title="zzz")


def test_resolve_all_sorted():
    assert [b.asin for b in resolve_books(_books(), all_=True)] == ["B2", "B1", "B3"]


def test_title_base():
    assert _title_base("Harry Potter and the Sorcerer's Stone, Book 1") == "Harry_Potter_and_the_Sorcerers_Stone_Book_1"


def _make_download(tmp_path, base="Harry_Potter_Book_1", asin="B017V4IM1G", kind="aax", with_chapters=True, cover=True):
    if with_chapters:
        (tmp_path / f"{base}-chapters.json").write_text(json.dumps({"content_metadata": {"content_reference": {"asin": asin}}}))
    if kind == "aax":
        (tmp_path / f"{base}-LC_128_44100_stereo.aax").write_bytes(b"x")
    else:
        (tmp_path / f"{base}-AAX_44_128.aaxc").write_bytes(b"x")
        (tmp_path / f"{base}-AAX_44_128.voucher").write_text(json.dumps({"content_license": {"license_response": {"key": "K", "iv": "I"}}}))
    if cover:
        (tmp_path / f"{base}_(500).jpg").write_bytes(b"j")
        (tmp_path / f"{base}_(1215).jpg").write_bytes(b"j")


def test_find_download_by_asin_in_chapters(tmp_path):
    _make_download(tmp_path)
    ds = find_download(tmp_path, Book(asin="b017v4im1g", title="Whatever"))
    assert ds and ds.kind == "aax" and ds.audio_path.name.endswith(".aax")
    assert ds.chapters_path.name == "Harry_Potter_Book_1-chapters.json"
    assert ds.cover_path.name == "Harry_Potter_Book_1_(1215).jpg"


def test_find_download_aaxc_and_voucher(tmp_path):
    _make_download(tmp_path, kind="aaxc", cover=False)
    ds = find_download(tmp_path, Book(asin="B017V4IM1G", title="x"))
    assert ds.kind == "aaxc" and ds.voucher_path.exists() and ds.cover_path is None
    assert read_voucher(ds.voucher_path) == ("K", "I")


def test_find_download_legacy_by_title(tmp_path):
    _make_download(tmp_path, base="Matilda", with_chapters=False, cover=False)
    ds = find_download(tmp_path, Book(asin="B9", title="Matilda"))
    assert ds and ds.chapters_path is None and ds.audio_path.name.startswith("Matilda")


def test_find_download_missing(tmp_path):
    _make_download(tmp_path)
    assert find_download(tmp_path, Book(asin="OTHER", title="Nope")) is None
    assert find_download(tmp_path / "missing", Book(asin="OTHER", title="Nope")) is None
