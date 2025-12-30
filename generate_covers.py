#!/usr/bin/env python3
"""
Generate book cover images for Yoto audiobooks

Supports multiple methods:
1. Download from Open Library API (free, no API key needed)
2. Search via Perplexity CLI (if installed)
3. Create placeholder covers with book title

Usage:
    python3 generate_covers.py [OPTIONS]

Options:
    --method METHOD    Cover source: openlibrary, perplexity, placeholder (default: openlibrary)
    --yes, -y          Skip confirmation prompts (non-interactive mode)
    --help, -h         Show this help message
"""

import os
import sys
import argparse
import re
import subprocess
import urllib.request
import urllib.parse
import json
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Error: Pillow is required. Install with: pip install Pillow")
    sys.exit(1)

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# Get script directory for relative paths
SCRIPT_DIR = Path(__file__).parent.resolve()

# Configuration - relative to script directory
BOOKS_DIR = SCRIPT_DIR / "yoto_mp3"
COVERS_DIR = SCRIPT_DIR / "yoto_covers"
COVER_SIZE = (400, 400)  # Yoto specification
IMAGE_FORMAT = "JPEG"
JPEG_QUALITY = 90


class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'


def print_color(text, color):
    """Print colored text"""
    print(f"{color}{text}{Colors.NC}")


def sanitize_filename(name):
    """Sanitize filename for safe file operations"""
    # Remove or replace problematic characters
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    return name.strip()


def create_placeholder_cover(book_name, output_path):
    """Create a simple placeholder cover with book title"""
    try:
        # Create image with gradient background
        img = Image.new('RGB', COVER_SIZE, (40, 60, 100))
        draw = ImageDraw.Draw(img)
        
        # Add some visual interest - darker rectangle in center
        margin = 20
        draw.rectangle(
            [margin, margin, COVER_SIZE[0] - margin, COVER_SIZE[1] - margin],
            fill=(30, 45, 80),
            outline=(100, 130, 180),
            width=2
        )
        
        # Try to load a font, fall back to default
        try:
            # Try common system fonts
            font_paths = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
                "C:\\Windows\\Fonts\\arial.ttf",
            ]
            font = None
            for font_path in font_paths:
                if os.path.exists(font_path):
                    font = ImageFont.truetype(font_path, 24)
                    break
            if font is None:
                font = ImageFont.load_default()
        except:
            font = ImageFont.load_default()
        
        # Word wrap the title
        words = book_name.split()
        lines = []
        current_line = []
        max_width = COVER_SIZE[0] - 60
        
        for word in words:
            current_line.append(word)
            test_line = ' '.join(current_line)
            bbox = draw.textbbox((0, 0), test_line, font=font)
            if bbox[2] - bbox[0] > max_width:
                if len(current_line) > 1:
                    current_line.pop()
                    lines.append(' '.join(current_line))
                    current_line = [word]
                else:
                    lines.append(test_line)
                    current_line = []
        
        if current_line:
            lines.append(' '.join(current_line))
        
        # Limit to 6 lines
        if len(lines) > 6:
            lines = lines[:6]
            lines[-1] = lines[-1][:20] + "..."
        
        # Calculate total text height
        line_height = 30
        total_height = len(lines) * line_height
        start_y = (COVER_SIZE[1] - total_height) // 2
        
        # Draw text
        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]
            x = (COVER_SIZE[0] - text_width) // 2
            y = start_y + i * line_height
            draw.text((x, y), line, fill=(220, 220, 240), font=font)
        
        # Add "AUDIOBOOK" label at bottom
        try:
            small_font = ImageFont.truetype(font_paths[0], 14) if font_paths else ImageFont.load_default()
        except:
            small_font = ImageFont.load_default()
        
        label = "AUDIOBOOK"
        bbox = draw.textbbox((0, 0), label, font=small_font)
        label_width = bbox[2] - bbox[0]
        draw.text(
            ((COVER_SIZE[0] - label_width) // 2, COVER_SIZE[1] - 45),
            label,
            fill=(150, 170, 200),
            font=small_font
        )
        
        img.save(output_path, IMAGE_FORMAT, quality=JPEG_QUALITY)
        return True
    except Exception as e:
        print_color(f"  Error creating placeholder: {e}", Colors.RED)
        return False


def download_from_openlibrary(book_name, output_path):
    """Try to download cover from Open Library API"""
    try:
        # Search for the book
        search_query = urllib.parse.quote(book_name)
        search_url = f"https://openlibrary.org/search.json?title={search_query}&limit=1"
        
        if HAS_REQUESTS:
            response = requests.get(search_url, timeout=10)
            data = response.json()
        else:
            with urllib.request.urlopen(search_url, timeout=10) as response:
                data = json.loads(response.read().decode())
        
        if not data.get('docs'):
            return False
        
        # Get cover ID
        doc = data['docs'][0]
        cover_id = doc.get('cover_i')
        
        if not cover_id:
            # Try ISBN-based cover
            isbns = doc.get('isbn', [])
            if isbns:
                cover_url = f"https://covers.openlibrary.org/b/isbn/{isbns[0]}-L.jpg"
            else:
                return False
        else:
            cover_url = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
        
        # Download the cover
        if HAS_REQUESTS:
            response = requests.get(cover_url, timeout=15)
            if response.status_code != 200:
                return False
            img_data = response.content
        else:
            with urllib.request.urlopen(cover_url, timeout=15) as response:
                img_data = response.read()
        
        # Check if we got a valid image (not a placeholder)
        if len(img_data) < 1000:  # Too small, probably a placeholder
            return False
        
        # Save temporarily and resize
        import io
        img = Image.open(io.BytesIO(img_data))
        
        # Convert to RGB if necessary
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Resize to 400x400, maintaining aspect ratio with padding
        img.thumbnail((COVER_SIZE[0], COVER_SIZE[1]), Image.Resampling.LANCZOS)
        
        # Create square image with padding if needed
        if img.size != COVER_SIZE:
            new_img = Image.new('RGB', COVER_SIZE, (255, 255, 255))
            paste_x = (COVER_SIZE[0] - img.size[0]) // 2
            paste_y = (COVER_SIZE[1] - img.size[1]) // 2
            new_img.paste(img, (paste_x, paste_y))
            img = new_img
        
        img.save(output_path, IMAGE_FORMAT, quality=JPEG_QUALITY)
        return True
        
    except Exception as e:
        return False


def search_with_perplexity(book_name, output_path):
    """Try to find cover using Perplexity CLI"""
    try:
        # Check if perplexity CLI is available
        result = subprocess.run(
            ['which', 'perplexity-ai'],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            return False
        
        # Query perplexity for cover image URL
        query = f"What is the direct URL to the book cover image for '{book_name}' audiobook? Just give me the URL."
        
        result = subprocess.run(
            ['perplexity-ai', query],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            return False
        
        # Try to extract URL from response
        response = result.stdout
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        urls = re.findall(url_pattern, response)
        
        # Filter for image URLs
        image_urls = [u for u in urls if any(ext in u.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp'])]
        
        if not image_urls:
            return False
        
        # Try to download the first image URL
        for url in image_urls[:3]:  # Try first 3 URLs
            try:
                if HAS_REQUESTS:
                    response = requests.get(url, timeout=10)
                    if response.status_code == 200:
                        img_data = response.content
                    else:
                        continue
                else:
                    with urllib.request.urlopen(url, timeout=10) as response:
                        img_data = response.read()
                
                import io
                img = Image.open(io.BytesIO(img_data))
                
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Resize to 400x400
                img = img.resize(COVER_SIZE, Image.Resampling.LANCZOS)
                img.save(output_path, IMAGE_FORMAT, quality=JPEG_QUALITY)
                return True
            except:
                continue
        
        return False
        
    except Exception as e:
        return False


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Generate book cover images for Yoto audiobooks',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Methods:
    openlibrary  - Download from Open Library API (free, recommended)
    perplexity   - Search via Perplexity CLI (requires perplexity-ai installed)
    placeholder  - Create text-based placeholder covers

Examples:
    python3 generate_covers.py --yes
    python3 generate_covers.py --method placeholder --yes
    python3 generate_covers.py --method openlibrary -y
        """
    )
    parser.add_argument(
        '--method',
        choices=['openlibrary', 'perplexity', 'placeholder', 'auto'],
        default='auto',
        help='Cover source method (default: auto - tries openlibrary, then placeholder)'
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
    print("Yoto Book Cover Generator (400x400)")
    print("=" * 60)
    print()
    
    # Create directory
    COVERS_DIR.mkdir(parents=True, exist_ok=True)
    
    if not BOOKS_DIR.exists():
        print_color(f"Error: Books directory not found: {BOOKS_DIR}", Colors.RED)
        print("Run convert_audiobooks.sh first to create audiobook files.")
        sys.exit(1)
    
    # Determine method
    if args.method == 'auto':
        method = 'openlibrary'
        print_color("Using auto mode: Will try Open Library, then create placeholders", Colors.BLUE)
    else:
        method = args.method
        print_color(f"Using method: {method}", Colors.BLUE)
    
    print()
    
    # Get list of books
    book_dirs = sorted([d for d in BOOKS_DIR.iterdir() if d.is_dir()])
    book_count = len(book_dirs)
    
    if book_count == 0:
        print_color(f"No books found in {BOOKS_DIR}", Colors.YELLOW)
        sys.exit(0)
    
    # Check existing covers
    existing = sum(1 for d in book_dirs if (COVERS_DIR / f"{d.name}.jpg").exists())
    
    print_color(f"Found {book_count} books", Colors.GREEN)
    if existing > 0:
        print_color(f"Already have {existing} covers (will skip)", Colors.BLUE)
    print()
    
    if not args.yes:
        response = input("Generate covers? (y/n): ")
        if response.lower() != 'y':
            sys.exit(0)
    
    print()
    print("=" * 60)
    print("Generating Book Covers")
    print("=" * 60)
    print()
    
    success = 0
    skipped = 0
    failed = 0
    
    for i, book_dir in enumerate(book_dirs, 1):
        book_name = book_dir.name
        output_path = COVERS_DIR / f"{sanitize_filename(book_name)}.jpg"
        
        print(f"[{i}/{book_count}] {book_name}")
        
        # Skip if exists
        if output_path.exists():
            print_color("  ⊙ Already exists, skipping", Colors.YELLOW)
            skipped += 1
            continue
        
        # Try to get cover
        got_cover = False
        
        if method in ['openlibrary', 'auto']:
            print_color("  → Searching Open Library...", Colors.BLUE)
            got_cover = download_from_openlibrary(book_name, output_path)
            if got_cover:
                print_color("  ✓ Downloaded from Open Library", Colors.GREEN)
        
        if not got_cover and method == 'perplexity':
            print_color("  → Searching with Perplexity...", Colors.BLUE)
            got_cover = search_with_perplexity(book_name, output_path)
            if got_cover:
                print_color("  ✓ Found via Perplexity", Colors.GREEN)
        
        if not got_cover and method in ['placeholder', 'auto']:
            print_color("  → Creating placeholder...", Colors.BLUE)
            got_cover = create_placeholder_cover(book_name, output_path)
            if got_cover:
                print_color("  ✓ Created placeholder cover", Colors.GREEN)
        
        if got_cover:
            success += 1
        else:
            print_color("  ✗ Failed to create cover", Colors.RED)
            failed += 1
    
    print()
    print("=" * 60)
    print("Cover Generation Complete")
    print("=" * 60)
    print(f"Total books: {book_count}")
    print_color(f"Generated: {success}", Colors.GREEN)
    if skipped > 0:
        print_color(f"Skipped (already exist): {skipped}", Colors.YELLOW)
    if failed > 0:
        print_color(f"Failed: {failed}", Colors.RED)
    print()
    print(f"Covers saved to: {COVERS_DIR}")
    print(f"Size: 400x400 pixels (Yoto specification)")
    print(f"Format: JPEG")
    print()
    print("Next steps:")
    print("  python3 generate_chapter_icons.py")
    print("  python3 generate_playlists.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
