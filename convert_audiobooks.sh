#!/bin/bash
#
# Download audiobooks from Audible in AAX format and convert to chapter-split MP3s for Yoto
# Features: Resume capability, progress tracking, chapter splitting
#

set -e

# Get script directory (works even if called from different location)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Configuration - relative to script directory
DOWNLOAD_DIR="$SCRIPT_DIR/aax_downloads"
OUTPUT_DIR="$SCRIPT_DIR/yoto_mp3"
PROGRESS_FILE="$SCRIPT_DIR/.conversion_progress"
VENV_PATH="$SCRIPT_DIR/venv"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "============================================================"
echo "Audible to Yoto Converter"
echo "============================================================"
echo ""

# If ACTIVATION_BYTES is already set in the environment, skip audible-cli
# setup entirely (useful for converting existing AAX files offline or in tests)
if [ -n "${ACTIVATION_BYTES:-}" ]; then
    echo -e "${BLUE}Using ACTIVATION_BYTES from environment${NC}"
else
    # Activate virtual environment
    if [ -f "$VENV_PATH/bin/activate" ]; then
        source "$VENV_PATH/bin/activate"
    else
        echo -e "${RED}Error: Virtual environment not found at $VENV_PATH${NC}"
        echo "Run ./setup.sh first to create the virtual environment."
        exit 1
    fi

    # Check if audible-cli is configured
    if [ ! -f ~/.audible/config.toml ]; then
        echo -e "${YELLOW}Audible CLI not configured. Running quickstart...${NC}"
        audible quickstart
    fi

    # Get activation bytes dynamically from audible-cli
    echo -e "${BLUE}Retrieving activation bytes from audible-cli...${NC}"
    ACTIVATION_BYTES=$(audible activation-bytes 2>/dev/null | tail -n 1 || true)

    if [ -z "$ACTIVATION_BYTES" ]; then
        echo -e "${RED}Error: Could not retrieve activation bytes.${NC}"
        echo "Make sure audible-cli is configured: audible quickstart"
        exit 1
    fi
fi

echo -e "${GREEN}Activation bytes: $ACTIVATION_BYTES${NC}"
echo ""

# Create directories
mkdir -p "$DOWNLOAD_DIR"
mkdir -p "$OUTPUT_DIR"

# Check for existing progress
if [ -f "$PROGRESS_FILE" ]; then
    completed_count=$(wc -l < "$PROGRESS_FILE")
    echo -e "${BLUE}Found progress file: $completed_count book(s) already converted${NC}"
    echo ""
fi

# Show menu
echo "What would you like to do?"
echo ""
echo "1) Download ALL audiobooks and convert to chapter-split MP3s"
echo "2) Download specific audiobook by title"
echo "3) Download specific audiobook by ASIN"
echo "4) Convert existing AAX files to chapter-split MP3s"
echo "5) List library"
echo "6) Resume previous conversion"
echo "7) Reset progress (start fresh)"
echo ""
read -p "Enter choice (1-7): " choice

case $choice in
    1)
        echo -e "${GREEN}Downloading all audiobooks in AAX format...${NC}"
        echo -e "${YELLOW}This will take a while - downloading your entire library!${NC}"
        read -p "Are you sure? (y/n): " confirm
        if [ "$confirm" != "y" ]; then
            echo "Cancelled."
            exit 0
        fi
        cd "$DOWNLOAD_DIR"
        audible download --all --aax --quality best --chapter
        ;;
    2)
        read -p "Enter book title (partial match ok): " title
        echo -e "${GREEN}Downloading: $title${NC}"
        cd "$DOWNLOAD_DIR"
        audible download --title "$title" --aax --quality best --chapter
        ;;
    3)
        read -p "Enter ASIN: " asin
        echo -e "${GREEN}Downloading ASIN: $asin${NC}"
        cd "$DOWNLOAD_DIR"
        audible download --asin "$asin" --aax --quality best --chapter
        ;;
    4)
        echo "Skipping download, will convert existing files..."
        ;;
    5)
        echo -e "${GREEN}Your Audible Library:${NC}"
        audible library list
        exit 0
        ;;
    6)
        echo -e "${BLUE}Resuming previous conversion...${NC}"
        ;;
    7)
        if [ -f "$PROGRESS_FILE" ]; then
            rm "$PROGRESS_FILE"
            echo -e "${GREEN}Progress reset. Starting fresh.${NC}"
        else
            echo -e "${YELLOW}No progress file found.${NC}"
        fi
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

echo ""
echo "============================================================"
echo "Converting to Chapter-Split MP3s for Yoto"
echo "============================================================"
echo ""

# Find AAX files
AAX_FILES=$(find "$DOWNLOAD_DIR" -name "*.aax" -o -name "*.AAX" 2>/dev/null)

if [ -z "$AAX_FILES" ]; then
    echo -e "${YELLOW}No AAX files found in $DOWNLOAD_DIR${NC}"
    exit 0
fi

# Count files
FILE_COUNT=$(echo "$AAX_FILES" | wc -l)
echo -e "${GREEN}Found $FILE_COUNT AAX file(s) total${NC}"

# Check how many already completed
if [ -f "$PROGRESS_FILE" ]; then
    completed_count=$(wc -l < "$PROGRESS_FILE")
    remaining=$((FILE_COUNT - completed_count))
    if [ $remaining -lt 0 ]; then
        remaining=0
    fi
    echo -e "${BLUE}Already completed: $completed_count${NC}"
    echo -e "${BLUE}Remaining: $remaining${NC}"
else
    echo -e "${BLUE}Starting fresh conversion${NC}"
fi
echo ""

# Convert each file
CURRENT=0
SUCCESS=0
FAILED=0
SKIPPED=0

while IFS= read -r aax_file; do
    CURRENT=$((CURRENT + 1))
    filename=$(basename "$aax_file")
    book_name="${filename%.*}"
    
    # Clean up book name (remove quality suffix)
    book_name=$(echo "$book_name" | sed 's/-LC_[0-9]*_[0-9]*_stereo$//' | sed 's/_/ /g')
    
    # Check if already converted
    if [ -f "$PROGRESS_FILE" ] && grep -Fxq "$book_name" "$PROGRESS_FILE"; then
        echo "[$CURRENT/$FILE_COUNT] ${book_name}"
        echo -e "${YELLOW}  ⊙ Already converted, skipping${NC}"
        SKIPPED=$((SKIPPED + 1))
        continue
    fi
    
    # Check if output directory exists and has files
    book_output_dir="$OUTPUT_DIR/$book_name"
    if [ -d "$book_output_dir" ] && [ "$(ls -A "$book_output_dir" 2>/dev/null | wc -l)" -gt 0 ]; then
        echo "[$CURRENT/$FILE_COUNT] ${book_name}"
        echo -e "${YELLOW}  ⊙ Output folder exists with files, skipping${NC}"
        echo -e "${BLUE}  → Marking as completed${NC}"
        echo "$book_name" >> "$PROGRESS_FILE"
        SKIPPED=$((SKIPPED + 1))
        continue
    fi
    
    echo ""
    echo "============================================================"
    echo "[$CURRENT/$FILE_COUNT] Processing: $book_name"
    echo "============================================================"
    
    # Create output directory for this book
    mkdir -p "$book_output_dir"
    
    # Get chapter information
    echo -e "${BLUE}Extracting chapter information...${NC}"
    chapter_json=$(ffprobe -activation_bytes "$ACTIVATION_BYTES" \
        -v quiet -print_format json -show_chapters "$aax_file" 2>/dev/null || true)
    
    if [ -z "$chapter_json" ]; then
        echo -e "${RED}✗ Failed to read chapters from: $book_name${NC}"
        FAILED=$((FAILED + 1))
        continue
    fi
    
    # Count chapters
    chapter_count=$(echo "$chapter_json" | python3 -c "import sys, json; d=json.load(sys.stdin); print(len(d.get('chapters', [])))" 2>/dev/null || echo "0")
    
    if [ "$chapter_count" -eq "0" ]; then
        echo -e "${YELLOW}No chapters found, converting as single file...${NC}"
        if ffmpeg -activation_bytes "$ACTIVATION_BYTES" -i "$aax_file" \
            -vn -c:a libmp3lame -q:a 2 \
            "$book_output_dir/Full Book.mp3" \
            -y -loglevel error -stats; then
            echo -e "${GREEN}✓ Successfully converted: $book_name${NC}"
            echo "$book_name" >> "$PROGRESS_FILE"
            SUCCESS=$((SUCCESS + 1))
        else
            echo -e "${RED}✗ Failed to convert: $book_name${NC}"
            FAILED=$((FAILED + 1))
        fi
        continue
    fi
    
    echo -e "${BLUE}Found $chapter_count chapters${NC}"
    
    # Extract each chapter
    chapter_success=0
    chapter_failed=0
    
    for i in $(seq 0 $((chapter_count - 1))); do
        # Get chapter info
        chapter_info=$(echo "$chapter_json" | python3 -c "
import sys, json
d = json.load(sys.stdin)
ch = d['chapters'][$i]
start = float(ch['start_time'])
end = float(ch['end_time'])
title = ch.get('tags', {}).get('title', f'Chapter {$i + 1}')
# Clean up title: strip path separators and the '|' field delimiter used below
title = title.replace('/', '-').replace('\\\\', '-').replace('|', '-')
print(f'{start}|{max(end - start, 0)}|{title}')
" 2>/dev/null || true)

        if [ -z "$chapter_info" ]; then
            continue
        fi

        start_time=$(echo "$chapter_info" | cut -d'|' -f1)
        duration=$(echo "$chapter_info" | cut -d'|' -f2)
        chapter_title=$(echo "$chapter_info" | cut -d'|' -f3-)
        
        # Format chapter number with leading zeros
        chapter_num=$(printf "%03d" $((i + 1)))
        output_file="$book_output_dir/Chapter_${chapter_num}_${chapter_title}.mp3"
        
        # Skip if file already exists
        if [ -f "$output_file" ]; then
            echo -e "${YELLOW}  [$((i + 1))/$chapter_count] $chapter_title (exists, skipping)${NC}"
            chapter_success=$((chapter_success + 1))
            continue
        fi
        
        echo -e "${BLUE}  [$((i + 1))/$chapter_count] $chapter_title${NC}"
        
        # Extract chapter. -ss before -i seeks the input directly instead of
        # decoding from the start of the book for every chapter.
        if ffmpeg -activation_bytes "$ACTIVATION_BYTES" \
            -ss "$start_time" -i "$aax_file" -t "$duration" \
            -vn -c:a libmp3lame -q:a 2 \
            -metadata title="$chapter_title" \
            -metadata track="$((i + 1))/$chapter_count" \
            -metadata album="$book_name" \
            "$output_file" \
            -y -loglevel error -nostats; then
            chapter_success=$((chapter_success + 1))
        else
            echo -e "${RED}    ✗ Failed${NC}"
            chapter_failed=$((chapter_failed + 1))
        fi
    done
    
    if [ $chapter_failed -eq 0 ]; then
        echo -e "${GREEN}✓ Successfully converted all $chapter_count chapters${NC}"
        echo "$book_name" >> "$PROGRESS_FILE"
        SUCCESS=$((SUCCESS + 1))
    else
        echo -e "${YELLOW}⚠ Converted $chapter_success/$chapter_count chapters${NC}"
        if [ $chapter_success -gt 0 ]; then
            echo "$book_name" >> "$PROGRESS_FILE"
            SUCCESS=$((SUCCESS + 1))
        else
            FAILED=$((FAILED + 1))
        fi
    fi
    
done <<< "$AAX_FILES"

echo ""
echo "============================================================"
echo "Conversion Summary"
echo "============================================================"
echo "Total books: $FILE_COUNT"
echo -e "${GREEN}Successful: $SUCCESS${NC}"
echo -e "${YELLOW}Skipped (already done): $SKIPPED${NC}"
if [ $FAILED -gt 0 ]; then
    echo -e "${RED}Failed: $FAILED${NC}"
fi
echo ""
echo "Output directory: $OUTPUT_DIR"
echo "Progress file: $PROGRESS_FILE"
echo ""
echo "Your audiobooks are ready for Yoto!"
echo "Next steps:"
echo "  python3 generate_chapter_icons.py"
echo "  python3 generate_playlists.py"
echo "============================================================"
