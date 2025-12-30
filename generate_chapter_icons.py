#!/usr/bin/env python3
"""
Generate Yoto chapter icons (16x16 pixels)
Based on official Yoto specifications from yoto.dev

Usage:
    python3 generate_chapter_icons.py [OPTIONS]

Options:
    --style STYLE    Icon style: numbers, symbols, miniatures, all (default: prompt)
    --yes, -y        Skip confirmation prompts (non-interactive mode)
    --help, -h       Show this help message
"""

import os
import sys
import argparse
import re
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Error: Pillow is required. Install with: pip install Pillow")
    sys.exit(1)

# Get script directory for relative paths
SCRIPT_DIR = Path(__file__).parent.resolve()

# Configuration - relative to script directory
BOOKS_DIR = SCRIPT_DIR / "yoto_mp3"
BOOK_COVERS_DIR = SCRIPT_DIR / "yoto_covers"
CHAPTER_ICONS_DIR = SCRIPT_DIR / "yoto_chapter_icons_16x16"
ICON_SIZE = (16, 16)  # Yoto specification
IMAGE_FORMAT = "PNG"  # PNG for transparency support


class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'


def print_color(text, color):
    """Print colored text"""
    print(f"{color}{text}{Colors.NC}")


def create_number_icon(number, output_path, bg_color=(50, 50, 200), text_color=(255, 255, 255)):
    """Create a simple numbered icon (16x16)"""
    try:
        img = Image.new('RGB', ICON_SIZE, bg_color)
        draw = ImageDraw.Draw(img)
        
        # Use default font (tiny for 16x16)
        font = ImageFont.load_default()
        
        # Draw number
        text = str(number)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        x = (ICON_SIZE[0] - text_width) // 2
        y = (ICON_SIZE[1] - text_height) // 2 - 2  # Adjust for better centering
        
        draw.text((x, y), text, fill=text_color, font=font)
        
        img.save(output_path, IMAGE_FORMAT)
        return True
    except Exception as e:
        print_color(f"  Error creating icon: {e}", Colors.RED)
        return False


def create_symbol_icon(symbol, output_path, bg_color=(50, 150, 50), symbol_color=(255, 255, 255)):
    """Create a simple symbol icon (16x16)"""
    try:
        img = Image.new('RGB', ICON_SIZE, bg_color)
        draw = ImageDraw.Draw(img)
        
        # Draw simple shapes based on chapter position
        if symbol == 'start':
            # Triangle (play symbol)
            draw.polygon([(4, 3), (4, 13), (12, 8)], fill=symbol_color)
        elif symbol == 'middle':
            # Circle
            draw.ellipse([3, 3, 13, 13], fill=symbol_color)
        elif symbol == 'end':
            # Square
            draw.rectangle([3, 3, 13, 13], fill=symbol_color)
        else:
            # Default: small square
            draw.rectangle([5, 5, 11, 11], fill=symbol_color)
        
        img.save(output_path, IMAGE_FORMAT)
        return True
    except Exception as e:
        return False


def create_miniature_icon(book_cover_path, chapter_num, total_chapters, output_path):
    """Create a miniature version of book cover with chapter indicator"""
    try:
        # Try to load book cover
        if book_cover_path and book_cover_path.exists():
            img = Image.open(book_cover_path)
            # Resize to 16x16
            img = img.resize(ICON_SIZE, Image.Resampling.LANCZOS)
        else:
            # Create colored square
            # Use different colors for different parts of book
            progress = chapter_num / total_chapters
            if progress < 0.33:
                color = (50, 100, 200)  # Blue for start
            elif progress < 0.66:
                color = (50, 150, 100)  # Green for middle
            else:
                color = (200, 100, 50)  # Orange for end
            
            img = Image.new('RGB', ICON_SIZE, color)
        
        # Add small indicator dot in corner
        draw = ImageDraw.Draw(img)
        # White dot in top-right corner
        draw.ellipse([12, 1, 15, 4], fill=(255, 255, 255))
        
        img.save(output_path, IMAGE_FORMAT)
        return True
    except Exception as e:
        return False


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Generate Yoto chapter icons (16x16 pixels)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python3 generate_chapter_icons.py --style numbers --yes
    python3 generate_chapter_icons.py --style all -y
    python3 generate_chapter_icons.py  # Interactive mode
        """
    )
    parser.add_argument(
        '--style',
        choices=['numbers', 'symbols', 'miniatures', 'all'],
        help='Icon style to generate'
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
    print("Yoto Chapter Icon Generator (16x16)")
    print("=" * 60)
    print()
    
    # Create directory
    CHAPTER_ICONS_DIR.mkdir(parents=True, exist_ok=True)
    
    if not BOOKS_DIR.exists():
        print_color(f"Error: Books directory not found: {BOOKS_DIR}", Colors.RED)
        print("Run convert_audiobooks.sh first to create audiobook files.")
        sys.exit(1)
    
    # Determine icon style
    if args.style:
        choice = {'numbers': '1', 'symbols': '2', 'miniatures': '3', 'all': '4'}[args.style]
    else:
        # Interactive mode
        print("Choose icon style:")
        print()
        print("1) Numbers (1, 2, 3...) - Simple and clear")
        print("2) Symbols (shapes) - Visual variety")
        print("3) Miniature covers - Tiny book cover with indicator")
        print("4) All three (for comparison)")
        print()
        choice = input("Enter choice (1-4): ").strip()
    
    generate_numbers = choice in ['1', '4']
    generate_symbols = choice in ['2', '4']
    generate_miniatures = choice in ['3', '4']
    
    # Get list of books
    book_dirs = sorted([d for d in BOOKS_DIR.iterdir() if d.is_dir()])
    book_count = len(book_dirs)
    
    if book_count == 0:
        print_color(f"No books found in {BOOKS_DIR}", Colors.YELLOW)
        sys.exit(0)
    
    print_color(f"Found {book_count} books", Colors.GREEN)
    print()
    
    if not args.yes:
        response = input("Continue? (y/n): ")
        if response.lower() != 'y':
            sys.exit(0)
    
    print()
    print("=" * 60)
    print("Generating 16x16 Chapter Icons")
    print("=" * 60)
    print()
    
    total_icons = 0
    
    for i, book_dir in enumerate(book_dirs, 1):
        book_name = book_dir.name
        print(f"[{i}/{book_count}] {book_name}")
        
        # Get chapter files
        chapter_files = sorted(book_dir.glob("Chapter_*.mp3"))
        
        if not chapter_files:
            print_color("  ⊙ No chapters found", Colors.YELLOW)
            continue
        
        chapter_count = len(chapter_files)
        book_cover_path = BOOK_COVERS_DIR / f"{book_name}.jpg"
        
        # Create icon directory for this book
        if generate_numbers:
            icon_dir = CHAPTER_ICONS_DIR / "numbers" / book_name
            icon_dir.mkdir(parents=True, exist_ok=True)
        
        if generate_symbols:
            icon_dir = CHAPTER_ICONS_DIR / "symbols" / book_name
            icon_dir.mkdir(parents=True, exist_ok=True)
        
        if generate_miniatures:
            icon_dir = CHAPTER_ICONS_DIR / "miniatures" / book_name
            icon_dir.mkdir(parents=True, exist_ok=True)
        
        print_color(f"  → Generating {chapter_count} icons...", Colors.BLUE)
        
        for j, chapter_file in enumerate(chapter_files, 1):
            # Extract chapter number
            match = re.match(r'Chapter_(\d+)', chapter_file.name)
            if not match:
                continue
            
            chapter_num = int(match.group(1))
            
            # Generate different icon styles
            if generate_numbers:
                icon_path = CHAPTER_ICONS_DIR / "numbers" / book_name / f"chapter_{chapter_num:03d}.png"
                create_number_icon(chapter_num, icon_path)
            
            if generate_symbols:
                icon_path = CHAPTER_ICONS_DIR / "symbols" / book_name / f"chapter_{chapter_num:03d}.png"
                if j == 1:
                    symbol = 'start'
                elif j == chapter_count:
                    symbol = 'end'
                else:
                    symbol = 'middle'
                create_symbol_icon(symbol, icon_path)
            
            if generate_miniatures:
                icon_path = CHAPTER_ICONS_DIR / "miniatures" / book_name / f"chapter_{chapter_num:03d}.png"
                create_miniature_icon(book_cover_path, chapter_num, chapter_count, icon_path)
            
            total_icons += (generate_numbers + generate_symbols + generate_miniatures)
        
        print_color(f"  ✓ Created {chapter_count} icons", Colors.GREEN)
    
    print()
    print("=" * 60)
    print("Icon Generation Complete")
    print("=" * 60)
    print(f"Total icons created: {total_icons}")
    print(f"Icon size: 16x16 pixels (Yoto specification)")
    print(f"Format: PNG")
    print()
    print(f"Icons saved to: {CHAPTER_ICONS_DIR}")
    print()
    if generate_numbers:
        print(f"  - numbers/    (numbered 1, 2, 3...)")
    if generate_symbols:
        print(f"  - symbols/    (shapes: triangle, circle, square)")
    if generate_miniatures:
        print(f"  - miniatures/ (tiny book covers)")
    print()
    print("Next step: Generate playlist JSON files")
    print("  python3 generate_playlists.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
