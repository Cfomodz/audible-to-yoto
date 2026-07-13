#!/usr/bin/env python3
"""Tests for yoto_upload.py (pure functions only - no network)"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import generate_covers
import yoto_upload
from yoto_upload import build_card_content, parse_chapter_filename


class TestParseChapterFilename:
    def test_parses_number_and_title(self):
        assert parse_chapter_filename("Chapter_001_Intro.mp3") == (1, "Intro")

    def test_parses_multi_word_title(self):
        num, title = parse_chapter_filename("Chapter_042_The Long Road.mp3")
        assert num == 42
        assert title == "The Long Road"

    def test_rejects_non_chapter_files(self):
        assert parse_chapter_filename("Full Book.mp3") is None
        assert parse_chapter_filename("Chapter_abc_Bad.mp3") is None

    def test_rejects_non_mp3(self):
        assert parse_chapter_filename("Chapter_001_Intro.wav") is None


class TestBuildCardContent:
    def make_tracks(self, count=2):
        return [
            {
                "num": i,
                "title": f"Chapter {i}",
                "sha256": f"sha{i}",
                "info": {"duration": 60, "fileSize": 1000, "channels": 2, "format": "aac"},
                "icon": f"yoto:#icon{i}",
            }
            for i in range(1, count + 1)
        ]

    def test_basic_structure(self):
        content = build_card_content("My Book", self.make_tracks())
        assert content["title"] == "My Book"
        assert len(content["content"]["chapters"]) == 2
        chapter = content["content"]["chapters"][0]
        assert chapter["key"] == "01"
        assert chapter["display"]["icon16x16"] == "yoto:#icon1"
        track = chapter["tracks"][0]
        assert track["trackUrl"] == "yoto:#sha1"
        assert track["type"] == "audio"
        assert track["duration"] == 60

    def test_media_totals(self):
        content = build_card_content("My Book", self.make_tracks(3))
        media = content["metadata"]["media"]
        assert media["duration"] == 180
        assert media["fileSize"] == 3000

    def test_cover_url_included_when_given(self):
        content = build_card_content("My Book", self.make_tracks(), cover_url="https://x/y.jpg")
        assert content["metadata"]["cover"]["imageL"] == "https://x/y.jpg"

    def test_cover_omitted_when_missing(self):
        content = build_card_content("My Book", self.make_tracks())
        assert "cover" not in content["metadata"]

    def test_missing_icon_omits_display(self):
        tracks = self.make_tracks(1)
        tracks[0]["icon"] = None
        content = build_card_content("My Book", tracks)
        assert "display" not in content["content"]["chapters"][0]

    def test_missing_transcode_info_defaults(self):
        tracks = self.make_tracks(1)
        tracks[0]["info"] = {}
        content = build_card_content("My Book", tracks)
        track = content["content"]["chapters"][0]["tracks"][0]
        assert track["duration"] == 0
        assert track["format"] == "aac"


class TestFilenameContract:
    def test_cover_lookup_matches_covers_output(self):
        """yoto_upload must find covers written by generate_covers"""
        name = "Dune: Book One"
        assert yoto_upload.sanitize_filename(name) == generate_covers.sanitize_filename(name)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
