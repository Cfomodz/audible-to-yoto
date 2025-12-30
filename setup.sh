#!/bin/bash
#
# Setup script for Audible to Yoto Converter
#

set -e

echo "============================================================"
echo "Audible to Yoto Converter - Setup"
echo "============================================================"
echo ""

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $PYTHON_VERSION"

if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not found"
    exit 1
fi

# Check for required system tools
echo ""
echo "Checking system dependencies..."

MISSING_DEPS=()

if ! command -v ffmpeg &> /dev/null; then
    MISSING_DEPS+=("ffmpeg")
fi

if ! command -v magick &> /dev/null && ! command -v convert &> /dev/null; then
    MISSING_DEPS+=("imagemagick")
fi

if ! command -v curl &> /dev/null; then
    MISSING_DEPS+=("curl")
fi

if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
    echo ""
    echo "Missing required dependencies:"
    for dep in "${MISSING_DEPS[@]}"; do
        echo "  - $dep"
    done
    echo ""
    echo "Install them with:"
    echo "  Arch/Manjaro: sudo pacman -S ffmpeg imagemagick curl"
    echo "  Ubuntu/Debian: sudo apt install ffmpeg imagemagick curl"
    echo "  macOS: brew install ffmpeg imagemagick curl"
    echo ""
    read -p "Continue anyway? (y/n): " continue
    if [ "$continue" != "y" ]; then
        exit 1
    fi
fi

echo ""
echo "Creating virtual environment..."
if [ -d "venv" ]; then
    echo "Virtual environment already exists. Removing old one..."
    rm -rf venv
fi

python3 -m venv venv

echo ""
echo "Activating virtual environment..."
source venv/bin/activate

echo ""
echo "Upgrading pip..."
pip install --upgrade pip

echo ""
echo "Installing Python dependencies..."
pip install -r requirements.txt

echo ""
echo "============================================================"
echo "Setup Complete!"
echo "============================================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Activate the virtual environment:"
echo "   source venv/bin/activate"
echo ""
echo "2. Configure audible-cli:"
echo "   audible quickstart"
echo ""
echo "3. Get your activation bytes:"
echo "   audible activation-bytes"
echo ""
echo "4. Start converting:"
echo "   ./convert_audiobooks.sh"
echo ""
echo "See docs/README.md for complete documentation"
echo "============================================================"
