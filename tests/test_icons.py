#!/usr/bin/env python3
"""Tests for chapter icon generation"""

import pytest
import tempfile
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from generate_chapter_icons import (
    create_number_icon,
    create_symbol_icon,
    create_miniature_icon,
    ICON_SIZE
)


class TestIconGeneration:
    """Test icon generation functions"""
    
    def test_icon_size_is_16x16(self):
        """Verify icon size matches Yoto spec"""
        assert ICON_SIZE == (16, 16), "Icon size must be 16x16 per Yoto specification"
    
    def test_create_number_icon(self):
        """Test number icon creation"""
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            output_path = Path(f.name)
        
        try:
            result = create_number_icon(1, output_path)
            assert result is True, "Number icon creation should succeed"
            assert output_path.exists(), "Icon file should be created"
            
            # Verify it's a valid image
            from PIL import Image
            img = Image.open(output_path)
            assert img.size == ICON_SIZE, f"Icon should be {ICON_SIZE}"
        finally:
            output_path.unlink(missing_ok=True)
    
    def test_create_number_icon_double_digits(self):
        """Test number icon with double digit number"""
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            output_path = Path(f.name)
        
        try:
            result = create_number_icon(99, output_path)
            assert result is True, "Double digit icon creation should succeed"
            assert output_path.exists(), "Icon file should be created"
        finally:
            output_path.unlink(missing_ok=True)
    
    def test_create_symbol_icon_start(self):
        """Test symbol icon for start chapter"""
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            output_path = Path(f.name)
        
        try:
            result = create_symbol_icon('start', output_path)
            assert result is True, "Start symbol icon should be created"
            assert output_path.exists()
        finally:
            output_path.unlink(missing_ok=True)
    
    def test_create_symbol_icon_middle(self):
        """Test symbol icon for middle chapter"""
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            output_path = Path(f.name)
        
        try:
            result = create_symbol_icon('middle', output_path)
            assert result is True, "Middle symbol icon should be created"
        finally:
            output_path.unlink(missing_ok=True)
    
    def test_create_symbol_icon_end(self):
        """Test symbol icon for end chapter"""
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            output_path = Path(f.name)
        
        try:
            result = create_symbol_icon('end', output_path)
            assert result is True, "End symbol icon should be created"
        finally:
            output_path.unlink(missing_ok=True)
    
    def test_create_miniature_icon_no_cover(self):
        """Test miniature icon without book cover"""
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            output_path = Path(f.name)
        
        try:
            # No book cover - should create colored square
            result = create_miniature_icon(None, 5, 10, output_path)
            assert result is True, "Miniature icon without cover should succeed"
            assert output_path.exists()
        finally:
            output_path.unlink(missing_ok=True)


class TestIconColors:
    """Test icon color variations"""
    
    def test_custom_background_color(self):
        """Test icon with custom background color"""
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            output_path = Path(f.name)
        
        try:
            result = create_number_icon(1, output_path, bg_color=(255, 0, 0))
            assert result is True
            
            from PIL import Image
            img = Image.open(output_path)
            # Check a corner pixel for red background
            pixel = img.getpixel((0, 0))
            assert pixel[0] == 255, "Background should be red"
        finally:
            output_path.unlink(missing_ok=True)
    
    def test_custom_text_color(self):
        """Test icon with custom text color"""
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            output_path = Path(f.name)
        
        try:
            result = create_number_icon(1, output_path, text_color=(0, 255, 0))
            assert result is True
        finally:
            output_path.unlink(missing_ok=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
