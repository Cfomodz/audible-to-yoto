#!/usr/bin/env python3
"""Integration tests for the full pipeline.

These tests exercise the stages together (rather than in isolation) to catch
cross-stage contract bugs, e.g. the cover filename written by one stage not
matching the filename another stage looks up.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import generate_covers
import generate_chapter_icons
import generate_playlists

PROJECT_ROOT = Path(__file__).parent.parent

# A book title with characters that must survive every stage: ':' is stripped
# from cover filenames for Windows-safety, so every stage must agree on it.
TRICKY_BOOK_NAME = "Dune: Book One"


@pytest.fixture
def pipeline_dirs(tmp_path, monkeypatch):
    """Point all three generator modules at a temp directory tree."""
    books_dir = tmp_path / "yoto_mp3"
    covers_dir = tmp_path / "yoto_covers"
    icons_dir = tmp_path / "yoto_chapter_icons_16x16"
    playlists_dir = tmp_path / "yoto_playlists"

    monkeypatch.setattr(generate_covers, "BOOKS_DIR", books_dir)
    monkeypatch.setattr(generate_covers, "COVERS_DIR", covers_dir)
    monkeypatch.setattr(generate_chapter_icons, "BOOKS_DIR", books_dir)
    monkeypatch.setattr(generate_chapter_icons, "BOOK_COVERS_DIR", covers_dir)
    monkeypatch.setattr(generate_chapter_icons, "CHAPTER_ICONS_DIR", icons_dir)
    monkeypatch.setattr(generate_playlists, "BOOKS_DIR", books_dir)
    monkeypatch.setattr(generate_playlists, "BOOK_COVERS_DIR", covers_dir)
    monkeypatch.setattr(generate_playlists, "CHAPTER_ICONS_DIR", icons_dir)
    monkeypatch.setattr(generate_playlists, "PLAYLISTS_DIR", playlists_dir)

    # Fake converted book with three chapters
    book_dir = books_dir / TRICKY_BOOK_NAME
    book_dir.mkdir(parents=True)
    for i in range(1, 4):
        (book_dir / f"Chapter_{i:03d}_Test_Chapter.mp3").touch()

    return {
        "books": books_dir,
        "covers": covers_dir,
        "icons": icons_dir,
        "playlists": playlists_dir,
    }


def run_main(module, argv, monkeypatch):
    monkeypatch.setattr(sys, "argv", argv)
    module.main()


class TestPythonPipeline:
    """covers -> icons -> playlists over the same tree"""

    def test_full_pipeline_filename_contracts(self, pipeline_dirs, monkeypatch):
        # Stage 1: covers (placeholder method: no network)
        run_main(
            generate_covers,
            ["generate_covers.py", "--method", "placeholder", "--yes"],
            monkeypatch,
        )

        sanitized = generate_covers.sanitize_filename(TRICKY_BOOK_NAME)
        cover_path = pipeline_dirs["covers"] / f"{sanitized}.jpg"
        assert cover_path.exists(), "cover must be written under the sanitized name"
        # The sanitized name must actually differ here, or the test proves nothing
        assert sanitized != TRICKY_BOOK_NAME

        # Stage 2: icons (all styles; miniatures loads the cover from stage 1)
        run_main(
            generate_chapter_icons,
            ["generate_chapter_icons.py", "--style", "all", "--yes"],
            monkeypatch,
        )

        for style in ("numbers", "symbols", "miniatures"):
            style_dir = pipeline_dirs["icons"] / style / TRICKY_BOOK_NAME
            icons = sorted(style_dir.glob("chapter_*.png"))
            assert len(icons) == 3, f"expected 3 {style} icons, got {len(icons)}"

        # The icon generator must look up the cover under the sanitized name
        looked_up = pipeline_dirs["covers"] / (
            generate_chapter_icons.sanitize_filename(TRICKY_BOOK_NAME) + ".jpg"
        )
        assert looked_up == cover_path

        # Stage 3: playlists
        run_main(
            generate_playlists,
            ["generate_playlists.py", "--yes"],
            monkeypatch,
        )

        playlist_path = pipeline_dirs["playlists"] / f"{TRICKY_BOOK_NAME}.json"
        assert playlist_path.exists()
        playlist = json.loads(playlist_path.read_text(encoding="utf-8"))
        assert playlist["title"] == TRICKY_BOOK_NAME
        assert len(playlist["chapters"]) == 3

        # Instructions must reference the cover file that actually exists
        instructions_path = (
            pipeline_dirs["playlists"] / f"{TRICKY_BOOK_NAME}_INSTRUCTIONS.txt"
        )
        assert instructions_path.exists()
        instructions = instructions_path.read_text(encoding="utf-8")
        assert f"yoto_covers/{sanitized}.jpg" in instructions

    def test_sanitize_filename_consistent_across_modules(self):
        """All stages must agree on how a book name maps to a cover filename"""
        names = [TRICKY_BOOK_NAME, 'A "Quoted" Tale?', "Plain Name", "Slash/Back\\"]
        for name in names:
            assert (
                generate_covers.sanitize_filename(name)
                == generate_chapter_icons.sanitize_filename(name)
                == generate_playlists.sanitize_filename(name)
            )


FFMPEG_AVAILABLE = shutil.which("ffmpeg") and shutil.which("ffprobe")

FFMETADATA = """;FFMETADATA1
title=Test Book
[CHAPTER]
TIMEBASE=1/1000
START=0
END=2000
title=Intro
[CHAPTER]
TIMEBASE=1/1000
START=2000
END=4000
title=Part One|The/End
"""


@pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="ffmpeg/ffprobe not installed")
class TestConverterSmoke:
    """Run convert_audiobooks.sh end-to-end against an unencrypted test file.

    A plain MP4 audio file renamed to .aax goes through the exact same ffmpeg
    code path as a real AAX (-activation_bytes is accepted and ignored for
    unencrypted input), so this exercises chapter probing, title sanitization,
    per-chapter extraction, and progress tracking without an Audible account.
    """

    @pytest.fixture
    def converter_dir(self, tmp_path):
        shutil.copy(PROJECT_ROOT / "convert_audiobooks.sh", tmp_path)
        downloads = tmp_path / "aax_downloads"
        downloads.mkdir()

        meta_file = tmp_path / "chapters.txt"
        meta_file.write_text(FFMETADATA, encoding="utf-8")
        aax_file = downloads / "Test_Book-LC_64_22050_stereo.aax"
        subprocess.run(
            [
                "ffmpeg", "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
                "-i", str(meta_file), "-map_metadata", "1", "-map_chapters", "1",
                "-c:a", "aac", "-b:a", "32k", "-f", "ipod", str(aax_file), "-y",
                "-loglevel", "error",
            ],
            check=True,
            timeout=60,
        )
        return tmp_path

    def run_converter(self, cwd):
        env = dict(os.environ, ACTIVATION_BYTES="deadbeef")
        return subprocess.run(
            ["bash", "convert_audiobooks.sh"],
            cwd=cwd,
            input="4\n",
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )

    def test_converts_chapters_and_tracks_progress(self, converter_dir):
        result = self.run_converter(converter_dir)
        assert result.returncode == 0, result.stdout + result.stderr

        book_dir = converter_dir / "yoto_mp3" / "Test Book"
        mp3s = sorted(f.name for f in book_dir.glob("*.mp3"))
        assert mp3s == [
            "Chapter_001_Intro.mp3",
            # '|' and '/' in the chapter title must be sanitized to '-'
            "Chapter_002_Part One-The-End.mp3",
        ]
        for mp3 in book_dir.glob("*.mp3"):
            assert mp3.stat().st_size > 0

        progress = (converter_dir / ".conversion_progress").read_text()
        assert "Test Book" in progress

    def test_second_run_skips_completed_book(self, converter_dir):
        first = self.run_converter(converter_dir)
        assert first.returncode == 0, first.stdout + first.stderr

        second = self.run_converter(converter_dir)
        assert second.returncode == 0, second.stdout + second.stderr
        assert "Already converted, skipping" in second.stdout


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
