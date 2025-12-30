#!/usr/bin/env python3
"""Tests for book cover generation"""

import pytest
import tempfile
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from generate_covers import (
    create_placeholder_cover,
    sanitize_filename,
    COVER_SIZE
)


class TestCoverGeneration:
    """Test cover generation functions"""
    
    def test_cover_size_is_400x400(self):
        """Verify cover size matches Yoto spec"""
        assert COVER_SIZE == (400, 400), "Cover size must be 400x400 per Yoto specification"
    
    def test_create_placeholder_cover(self):
        """Test placeholder cover creation"""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            output_path = Path(f.name)
        
        try:
            result = create_placeholder_cover("Test Book Title", output_path)
            assert result is True, "Placeholder cover creation should succeed"
            assert output_path.exists(), "Cover file should be created"
            
            # Verify it's a valid image
            from PIL import Image
            img = Image.open(output_path)
            assert img.size == COVER_SIZE, f"Cover should be {COVER_SIZE}"
        finally:
            output_path.unlink(missing_ok=True)
    
    def test_placeholder_cover_long_title(self):
        """Test placeholder with very long title"""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            output_path = Path(f.name)
        
        long_title = "This Is A Very Long Book Title That Should Be Wrapped Across Multiple Lines In The Cover Image"
        
        try:
            result = create_placeholder_cover(long_title, output_path)
            assert result is True, "Long title placeholder should succeed"
            assert output_path.exists()
        finally:
            output_path.unlink(missing_ok=True)
    
    def test_placeholder_cover_short_title(self):
        """Test placeholder with short title"""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            output_path = Path(f.name)
        
        try:
            result = create_placeholder_cover("A", output_path)
            assert result is True, "Short title placeholder should succeed"
        finally:
            output_path.unlink(missing_ok=True)
    
    def test_placeholder_cover_special_chars(self):
        """Test placeholder with special characters in title"""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            output_path = Path(f.name)
        
        try:
            result = create_placeholder_cover("Book: A Story! (Part 1)", output_path)
            assert result is True, "Special chars placeholder should succeed"
        finally:
            output_path.unlink(missing_ok=True)


class TestFilenameSanitization:
    """Test filename sanitization"""
    
    def test_removes_colons(self):
        """Test that colons are removed"""
        result = sanitize_filename("Book: A Story")
        assert ":" not in result
    
    def test_removes_slashes(self):
        """Test that slashes are removed"""
        result = sanitize_filename("Book/Story")
        assert "/" not in result
    
    def test_removes_backslashes(self):
        """Test that backslashes are removed"""
        result = sanitize_filename("Book\\Story")
        assert "\\" not in result
    
    def test_removes_question_marks(self):
        """Test that question marks are removed"""
        result = sanitize_filename("What is this?")
        assert "?" not in result
    
    def test_removes_asterisks(self):
        """Test that asterisks are removed"""
        result = sanitize_filename("Best * Book")
        assert "*" not in result
    
    def test_preserves_normal_chars(self):
        """Test that normal characters are preserved"""
        result = sanitize_filename("Normal Book Title")
        assert result == "Normal Book Title"
    
    def test_preserves_numbers(self):
        """Test that numbers are preserved"""
        result = sanitize_filename("Book 123")
        assert result == "Book 123"
    
    def test_strips_whitespace(self):
        """Test that leading/trailing whitespace is stripped"""
        result = sanitize_filename("  Book Title  ")
        assert result == "Book Title"


class TestCoverFormat:
    """Test cover image format and quality"""
    
    def test_cover_is_jpeg(self):
        """Test that cover is saved as JPEG"""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            output_path = Path(f.name)
        
        try:
            create_placeholder_cover("Test", output_path)
            
            from PIL import Image
            img = Image.open(output_path)
            assert img.format == "JPEG", "Cover should be JPEG format"
        finally:
            output_path.unlink(missing_ok=True)
    
    def test_cover_is_rgb(self):
        """Test that cover is RGB mode"""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            output_path = Path(f.name)
        
        try:
            create_placeholder_cover("Test", output_path)
            
            from PIL import Image
            img = Image.open(output_path)
            assert img.mode == "RGB", "Cover should be RGB mode"
        finally:
            output_path.unlink(missing_ok=True)


class TestCoverScript:
    """Test cover script functionality"""
    
    def test_script_has_help_flag(self):
        """Test that script accepts --help flag"""
        import subprocess
        result = subprocess.run(
            [sys.executable, str(Path(__file__).parent.parent / "generate_covers.py"), "--help"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, "Script should accept --help"
        assert "usage" in result.stdout.lower() or "options" in result.stdout.lower()
    
    def test_script_syntax(self):
        """Test that script has valid syntax"""
        import subprocess
        script = Path(__file__).parent.parent / "generate_covers.py"
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(script)],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr}"
    
    def test_script_imports(self):
        """Test that script can be imported"""
        sys.path.insert(0, str(Path(__file__).parent.parent))
        try:
            import generate_covers
            assert hasattr(generate_covers, 'main')
            assert hasattr(generate_covers, 'create_placeholder_cover')
            assert hasattr(generate_covers, 'download_from_openlibrary')
        finally:
            sys.path.pop(0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
