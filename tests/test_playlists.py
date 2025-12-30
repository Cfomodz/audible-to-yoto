#!/usr/bin/env python3
"""Tests for playlist JSON generation"""

import pytest
import json
import tempfile
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from generate_playlists import (
    sanitize_for_url,
    create_playlist_json,
    DEFAULT_AUDIO_URL,
    DEFAULT_COVER_URL
)


class TestUrlSanitization:
    """Test URL sanitization function"""
    
    def test_spaces_to_underscores(self):
        """Test that spaces are converted to underscores"""
        result = sanitize_for_url("Book Title Here")
        assert result == "Book_Title_Here"
    
    def test_special_chars_removed(self):
        """Test that special characters are removed"""
        result = sanitize_for_url("Book: A Story!")
        assert ":" not in result
        assert "!" not in result
    
    def test_preserves_alphanumeric(self):
        """Test that alphanumeric characters are preserved"""
        result = sanitize_for_url("Book123")
        assert result == "Book123"
    
    def test_preserves_underscores(self):
        """Test that underscores are preserved"""
        result = sanitize_for_url("Book_Title")
        assert result == "Book_Title"
    
    def test_preserves_hyphens(self):
        """Test that hyphens are preserved"""
        result = sanitize_for_url("Book-Title")
        assert result == "Book-Title"
    
    def test_empty_string(self):
        """Test empty string handling"""
        result = sanitize_for_url("")
        assert result == ""


class TestPlaylistJson:
    """Test playlist JSON creation"""
    
    def create_mock_chapter_files(self, tmpdir, count=3):
        """Create mock chapter files for testing"""
        files = []
        for i in range(1, count + 1):
            filename = f"Chapter_{i:03d}_Test_Chapter.mp3"
            filepath = tmpdir / filename
            filepath.touch()
            files.append(filepath)
        return sorted(files)
    
    def test_playlist_has_title(self):
        """Test that playlist has title"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            files = self.create_mock_chapter_files(tmpdir)
            
            playlist = create_playlist_json(
                "Test Book",
                files,
                DEFAULT_AUDIO_URL,
                DEFAULT_COVER_URL,
                use_placeholders=False
            )
            
            assert playlist["title"] == "Test Book"
    
    def test_playlist_has_description(self):
        """Test that playlist has description"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            files = self.create_mock_chapter_files(tmpdir)
            
            playlist = create_playlist_json(
                "Test Book",
                files,
                DEFAULT_AUDIO_URL,
                DEFAULT_COVER_URL,
                use_placeholders=False
            )
            
            assert "description" in playlist
            assert "Test Book" in playlist["description"]
    
    def test_playlist_has_chapters(self):
        """Test that playlist has correct number of chapters"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            files = self.create_mock_chapter_files(tmpdir, count=5)
            
            playlist = create_playlist_json(
                "Test Book",
                files,
                DEFAULT_AUDIO_URL,
                DEFAULT_COVER_URL,
                use_placeholders=False
            )
            
            assert len(playlist["chapters"]) == 5
    
    def test_chapter_has_required_fields(self):
        """Test that each chapter has required fields"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            files = self.create_mock_chapter_files(tmpdir, count=1)
            
            playlist = create_playlist_json(
                "Test Book",
                files,
                DEFAULT_AUDIO_URL,
                DEFAULT_COVER_URL,
                use_placeholders=False
            )
            
            chapter = playlist["chapters"][0]
            assert "key" in chapter
            assert "title" in chapter
            assert "display" in chapter
            assert "tracks" in chapter
    
    def test_chapter_has_track(self):
        """Test that each chapter has a track"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            files = self.create_mock_chapter_files(tmpdir, count=1)
            
            playlist = create_playlist_json(
                "Test Book",
                files,
                DEFAULT_AUDIO_URL,
                DEFAULT_COVER_URL,
                use_placeholders=False
            )
            
            track = playlist["chapters"][0]["tracks"][0]
            assert "key" in track
            assert "title" in track
            assert "type" in track
            assert track["type"] == "audio"
    
    def test_playlist_json_serializable(self):
        """Test that playlist can be serialized to JSON"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            files = self.create_mock_chapter_files(tmpdir)
            
            playlist = create_playlist_json(
                "Test Book",
                files,
                DEFAULT_AUDIO_URL,
                DEFAULT_COVER_URL,
                use_placeholders=True
            )
            
            # Should not raise
            json_str = json.dumps(playlist)
            assert len(json_str) > 0
            
            # Should round-trip
            parsed = json.loads(json_str)
            assert parsed["title"] == playlist["title"]


class TestChapterKeys:
    """Test chapter key formatting"""
    
    def test_chapter_keys_are_zero_padded(self):
        """Test that chapter keys are zero-padded"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Create files with various chapter numbers
            for i in [1, 5, 10]:
                filename = f"Chapter_{i:03d}_Test.mp3"
                (tmpdir / filename).touch()
            
            files = sorted(tmpdir.glob("Chapter_*.mp3"))
            
            playlist = create_playlist_json(
                "Test Book",
                files,
                DEFAULT_AUDIO_URL,
                DEFAULT_COVER_URL,
                use_placeholders=False
            )
            
            keys = [ch["key"] for ch in playlist["chapters"]]
            assert "01" in keys
            assert "05" in keys
            assert "10" in keys


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
