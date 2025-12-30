#!/usr/bin/env python3
"""
Generate Yoto playlist JSON files for each book
Based on official Yoto API specifications

Usage:
    python3 generate_playlists.py [OPTIONS]

Options:
    --style STYLE       Icon style: numbers, symbols, miniatures (default: numbers)
    --audio-url URL     Base URL for audio files (default: placeholder)
    --cover-url URL     Base URL for cover images (default: placeholder)
    --yes, -y           Skip confirmation prompts (non-interactive mode)
    --help, -h          Show this help message
"""

import os
import sys
import json
import re
import argparse
from pathlib import Path
from datetime import datetime

# Get script directory for relative paths
SCRIPT_DIR = Path(__file__).parent.resolve()

# Configuration - relative to script directory
BOOKS_DIR = SCRIPT_DIR / "yoto_mp3"
BOOK_COVERS_DIR = SCRIPT_DIR / "yoto_covers"
CHAPTER_ICONS_DIR = SCRIPT_DIR / "yoto_chapter_icons_16x16"
PLAYLISTS_DIR = SCRIPT_DIR / "yoto_playlists"

# Default placeholder URLs
DEFAULT_AUDIO_URL = "https://your-server.com/audiobooks"
DEFAULT_COVER_URL = "https://your-server.com/covers"


class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'


def print_color(text, color):
    """Print colored text"""
    print(f"{color}{text}{Colors.NC}")


def sanitize_for_url(text):
    """Sanitize text for URL"""
    # Replace spaces with underscores, remove special chars
    text = text.replace(' ', '_')
    text = re.sub(r'[^\w\-_]', '', text)
    return text


def create_playlist_json(book_name, chapter_files, audio_base_url, cover_base_url, use_placeholders=True):
    """Create Yoto playlist JSON for a book"""
    
    playlist = {
        "title": book_name,
        "description": f"Audiobook: {book_name}",
        "cover": {},
        "chapters": []
    }
    
    # Add cover image
    if use_placeholders and audio_base_url != DEFAULT_AUDIO_URL:
        playlist["cover"]["imageL"] = f"{cover_base_url}/{sanitize_for_url(book_name)}.jpg"
    else:
        playlist["cover"]["imageL"] = "TODO: Upload cover and add URL here"
    
    # Add chapters
    for i, chapter_file in enumerate(chapter_files, 1):
        # Extract chapter info from filename
        match = re.match(r'Chapter_(\d+)_(.+)\.mp3', chapter_file.name)
        if not match:
            continue
        
        chapter_num = int(match.group(1))
        chapter_title = match.group(2)
        
        chapter = {
            "key": f"{chapter_num:02d}",
            "title": f"Chapter {chapter_num}: {chapter_title}",
            "display": {
                "icon16x16": "TODO: Upload icon and add yoto:#<id> here"
            },
            "tracks": [
                {
                    "key": f"{chapter_num:02d}",
                    "title": chapter_title,
                    "type": "audio"
                }
            ]
        }
        
        # Add audio URL
        if use_placeholders and audio_base_url != DEFAULT_AUDIO_URL:
            audio_filename = sanitize_for_url(chapter_file.name)
            chapter["tracks"][0]["trackUrl"] = f"{audio_base_url}/{sanitize_for_url(book_name)}/{audio_filename}"
        else:
            chapter["tracks"][0]["trackUrl"] = "TODO: Upload audio and add URL here"
        
        playlist["chapters"].append(chapter)
    
    return playlist


def create_upload_instructions(book_name, chapter_count, icon_style, audio_base_url, cover_base_url):
    """Create instructions file for uploading to Yoto"""
    
    instructions = f"""
# Yoto Upload Instructions for: {book_name}

## Step 1: Upload Audio Files

Upload these files to your web server:

Book: {book_name}
Chapters: {chapter_count}

Files to upload:
  - yoto_mp3/{book_name}/*.mp3

Upload to: {audio_base_url}/{sanitize_for_url(book_name)}/

## Step 2: Upload Book Cover

Upload the book cover image:
  - File: yoto_covers/{book_name}.jpg
  - Upload to: {cover_base_url}/{sanitize_for_url(book_name)}.jpg

## Step 3: Upload Chapter Icons to Yoto

For each chapter, upload the 16x16 icon to Yoto API:

```bash
# Example for Chapter 1
curl -X POST https://api.yoto.io/v1/icons \\
  -H "Authorization: Bearer YOUR_YOTO_API_TOKEN" \\
  -F "file=@yoto_chapter_icons_16x16/{icon_style}/{book_name}/chapter_001.png" \\
  -F "autoConvert=true"

# Save the returned ID (e.g., "abc123def456")
# Repeat for all {chapter_count} chapters
```

## Step 4: Update Playlist JSON

Edit the playlist JSON file:
  - File: yoto_playlists/{book_name}.json

For each chapter, replace:
  "icon16x16": "TODO: Upload icon and add yoto:#<id> here"

With:
  "icon16x16": "yoto:#abc123def456"  (use the ID from step 3)

## Step 5: Upload Playlist to Yoto

1. Go to https://yoto.io/myo (Make Your Own)
2. Create a new card
3. Upload the edited playlist JSON
4. Test on your Yoto Player!

## Quick Reference

- Book: {book_name}
- Chapters: {chapter_count}
- Icons: yoto_chapter_icons_16x16/{icon_style}/{book_name}/
- Playlist: yoto_playlists/{book_name}.json
"""
    
    return instructions


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Generate Yoto playlist JSON files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python3 generate_playlists.py --yes
    python3 generate_playlists.py --style symbols --yes
    python3 generate_playlists.py --audio-url https://myserver.com/audio -y
        """
    )
    parser.add_argument(
        '--style',
        choices=['numbers', 'symbols', 'miniatures'],
        default='numbers',
        help='Icon style to reference (default: numbers)'
    )
    parser.add_argument(
        '--audio-url',
        default=DEFAULT_AUDIO_URL,
        help='Base URL for audio files'
    )
    parser.add_argument(
        '--cover-url',
        default=DEFAULT_COVER_URL,
        help='Base URL for cover images'
    )
    parser.add_argument(
        '--yes', '-y',
        action='store_true',
        help='Skip confirmation prompts (non-interactive mode)'
    )
    return parser.parse_args()


def main():
    """Main function"""
    args = parse_args()
    
    print("=" * 60)
    print("Yoto Playlist JSON Generator")
    print("=" * 60)
    print()
    
    # Create directory
    PLAYLISTS_DIR.mkdir(parents=True, exist_ok=True)
    
    if not BOOKS_DIR.exists():
        print_color(f"Error: Books directory not found: {BOOKS_DIR}", Colors.RED)
        print("Run convert_audiobooks.sh first to create audiobook files.")
        sys.exit(1)
    
    # Check if icons exist
    icon_styles = []
    if (CHAPTER_ICONS_DIR / "numbers").exists():
        icon_styles.append("numbers")
    if (CHAPTER_ICONS_DIR / "symbols").exists():
        icon_styles.append("symbols")
    if (CHAPTER_ICONS_DIR / "miniatures").exists():
        icon_styles.append("miniatures")
    
    # Determine icon style
    if args.yes:
        # Non-interactive mode - use args or default
        icon_style = args.style if args.style in icon_styles or not icon_styles else (icon_styles[0] if icon_styles else "numbers")
        use_placeholders = args.audio_url != DEFAULT_AUDIO_URL
        audio_base_url = args.audio_url
        cover_base_url = args.cover_url
    else:
        # Interactive mode
        if not icon_styles:
            print_color("Warning: No chapter icons found!", Colors.YELLOW)
            print("Run generate_chapter_icons.py first")
            print()
            response = input("Continue anyway? (y/n): ")
            if response.lower() != 'y':
                sys.exit(0)
            icon_style = "numbers"
        else:
            print("Available icon styles:")
            for i, style in enumerate(icon_styles, 1):
                print(f"  {i}) {style}")
            print()
            choice = input(f"Choose icon style (1-{len(icon_styles)}): ").strip()
            try:
                icon_style = icon_styles[int(choice) - 1]
            except:
                icon_style = icon_styles[0]
        
        print()
        print_color(f"Using icon style: {icon_style}", Colors.BLUE)
        print()
        
        # Ask about URL placeholders
        print("Audio/Cover URL options:")
        print("  1) Use placeholder URLs (you'll host files yourself)")
        print("  2) Leave as TODO (manual entry)")
        print()
        url_choice = input("Enter choice (1-2): ").strip()
        use_placeholders = url_choice == '1'
        
        audio_base_url = args.audio_url
        cover_base_url = args.cover_url
        
        if use_placeholders and audio_base_url == DEFAULT_AUDIO_URL:
            print()
            print_color("Note: Update these URLs after generation:", Colors.YELLOW)
            print(f"  Audio: {audio_base_url}")
            print(f"  Cover: {cover_base_url}")
            print()
    
    # Get list of books
    book_dirs = sorted([d for d in BOOKS_DIR.iterdir() if d.is_dir()])
    book_count = len(book_dirs)
    
    if book_count == 0:
        print_color(f"No books found in {BOOKS_DIR}", Colors.YELLOW)
        sys.exit(0)
    
    print_color(f"Found {book_count} books", Colors.GREEN)
    print()
    
    if not args.yes:
        response = input("Generate playlist JSON files? (y/n): ")
        if response.lower() != 'y':
            sys.exit(0)
    
    print()
    print("=" * 60)
    print("Generating Playlist JSON Files")
    print("=" * 60)
    print()
    
    success = 0
    
    for i, book_dir in enumerate(book_dirs, 1):
        book_name = book_dir.name
        print(f"[{i}/{book_count}] {book_name}")
        
        # Get chapter files
        chapter_files = sorted(book_dir.glob("Chapter_*.mp3"))
        
        if not chapter_files:
            print_color("  ⊙ No chapters found", Colors.YELLOW)
            continue
        
        chapter_count = len(chapter_files)
        
        # Create playlist JSON
        playlist = create_playlist_json(book_name, chapter_files, audio_base_url, cover_base_url, use_placeholders)
        
        # Save JSON
        json_path = PLAYLISTS_DIR / f"{book_name}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(playlist, f, indent=2, ensure_ascii=False)
        
        # Create instructions
        instructions = create_upload_instructions(book_name, chapter_count, icon_style, audio_base_url, cover_base_url)
        instructions_path = PLAYLISTS_DIR / f"{book_name}_INSTRUCTIONS.txt"
        with open(instructions_path, 'w', encoding='utf-8') as f:
            f.write(instructions)
        
        print_color(f"  ✓ Created playlist with {chapter_count} chapters", Colors.GREEN)
        success += 1
    
    print()
    print("=" * 60)
    print("Playlist Generation Complete")
    print("=" * 60)
    print(f"Total playlists created: {success}")
    print()
    print(f"Playlists saved to: {PLAYLISTS_DIR}")
    print()
    print("Each book has:")
    print("  - <BookName>.json - Playlist JSON file")
    print("  - <BookName>_INSTRUCTIONS.txt - Upload instructions")
    print()
    print_color("IMPORTANT: Next Steps", Colors.YELLOW)
    print("1. Upload audio files to your web server")
    print("2. Upload cover images to your web server")
    print("3. Upload chapter icons to Yoto API (get IDs)")
    print("4. Edit JSON files to add icon IDs")
    print("5. Upload JSON to Yoto MYO")
    print()
    print("See individual _INSTRUCTIONS.txt files for details!")
    print("=" * 60)


if __name__ == "__main__":
    main()
