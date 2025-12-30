#!/usr/bin/env python3
"""Tests for script integrity and imports"""

import pytest
import subprocess
import sys
from pathlib import Path


# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent


class TestPythonScripts:
    """Test Python script syntax and imports"""
    
    def test_generate_covers_syntax(self):
        """Test that generate_covers.py has valid syntax"""
        script = PROJECT_ROOT / "generate_covers.py"
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(script)],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr}"
    
    def test_generate_chapter_icons_syntax(self):
        """Test that generate_chapter_icons.py has valid syntax"""
        script = PROJECT_ROOT / "generate_chapter_icons.py"
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(script)],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr}"
    
    def test_generate_playlists_syntax(self):
        """Test that generate_playlists.py has valid syntax"""
        script = PROJECT_ROOT / "generate_playlists.py"
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(script)],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr}"
    
    def test_generate_covers_imports(self):
        """Test that generate_covers.py can be imported"""
        sys.path.insert(0, str(PROJECT_ROOT))
        try:
            import generate_covers
            assert hasattr(generate_covers, 'main')
            assert hasattr(generate_covers, 'create_placeholder_cover')
        finally:
            sys.path.pop(0)
    
    def test_generate_chapter_icons_imports(self):
        """Test that generate_chapter_icons.py can be imported"""
        sys.path.insert(0, str(PROJECT_ROOT))
        try:
            import generate_chapter_icons
            assert hasattr(generate_chapter_icons, 'main')
            assert hasattr(generate_chapter_icons, 'create_number_icon')
        finally:
            sys.path.pop(0)
    
    def test_generate_playlists_imports(self):
        """Test that generate_playlists.py can be imported"""
        sys.path.insert(0, str(PROJECT_ROOT))
        try:
            import generate_playlists
            assert hasattr(generate_playlists, 'main')
            assert hasattr(generate_playlists, 'create_playlist_json')
        finally:
            sys.path.pop(0)
    
    def test_scripts_have_help_flag(self):
        """Test that Python scripts accept --help flag"""
        for script_name in ['generate_covers.py', 'generate_chapter_icons.py', 'generate_playlists.py']:
            script = PROJECT_ROOT / script_name
            result = subprocess.run(
                [sys.executable, str(script), "--help"],
                capture_output=True,
                text=True
            )
            assert result.returncode == 0, f"{script_name} should accept --help"
            assert "usage" in result.stdout.lower() or "options" in result.stdout.lower()


class TestBashScripts:
    """Test Bash script syntax"""
    
    def test_setup_sh_syntax(self):
        """Test that setup.sh has valid bash syntax"""
        script = PROJECT_ROOT / "setup.sh"
        if not script.exists():
            pytest.skip("setup.sh not found")
        
        result = subprocess.run(
            ["bash", "-n", str(script)],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Syntax error in setup.sh: {result.stderr}"
    
    def test_convert_audiobooks_sh_syntax(self):
        """Test that convert_audiobooks.sh has valid bash syntax"""
        script = PROJECT_ROOT / "convert_audiobooks.sh"
        if not script.exists():
            pytest.skip("convert_audiobooks.sh not found")
        
        result = subprocess.run(
            ["bash", "-n", str(script)],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Syntax error in convert_audiobooks.sh: {result.stderr}"


class TestProjectStructure:
    """Test project structure and required files"""
    
    def test_readme_exists(self):
        """Test that README.md exists"""
        assert (PROJECT_ROOT / "README.md").exists()
    
    def test_license_exists(self):
        """Test that LICENSE exists"""
        assert (PROJECT_ROOT / "LICENSE").exists()
    
    def test_requirements_exists(self):
        """Test that requirements.txt exists"""
        assert (PROJECT_ROOT / "requirements.txt").exists()
    
    def test_setup_script_exists(self):
        """Test that setup.sh exists"""
        assert (PROJECT_ROOT / "setup.sh").exists()
    
    def test_gitignore_exists(self):
        """Test that .gitignore exists"""
        assert (PROJECT_ROOT / ".gitignore").exists()
    
    def test_docs_directory_exists(self):
        """Test that docs directory exists"""
        assert (PROJECT_ROOT / "docs").is_dir()
    
    def test_yoto_specs_doc_exists(self):
        """Test that YOTO_SPECIFICATIONS.md exists"""
        assert (PROJECT_ROOT / "docs" / "YOTO_SPECIFICATIONS.md").exists()
    
    def test_troubleshooting_doc_exists(self):
        """Test that TROUBLESHOOTING.md exists"""
        assert (PROJECT_ROOT / "docs" / "TROUBLESHOOTING.md").exists()


class TestDependencies:
    """Test that required dependencies can be imported"""
    
    def test_pillow_import(self):
        """Test that Pillow can be imported"""
        from PIL import Image, ImageDraw, ImageFont
        assert Image is not None
        assert ImageDraw is not None
        assert ImageFont is not None
    
    def test_pathlib_import(self):
        """Test that pathlib is available"""
        from pathlib import Path
        assert Path is not None
    
    def test_json_import(self):
        """Test that json is available"""
        import json
        assert json is not None
    
    def test_argparse_import(self):
        """Test that argparse is available"""
        import argparse
        assert argparse is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
