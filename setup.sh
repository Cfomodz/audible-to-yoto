#!/usr/bin/env bash
# One-time environment setup: checks ffmpeg, creates a venv, installs the CLI.
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "ffmpeg is required. Install it first:"
    echo "  Ubuntu/Debian: sudo apt install ffmpeg"
    echo "  macOS:         brew install ffmpeg"
    echo "  Arch:          sudo pacman -S ffmpeg"
    exit 1
fi

[ -d venv ] || python3 -m venv venv
venv/bin/pip install -q --upgrade pip
venv/bin/pip install -q -e ".[dev]"

echo "Installed. Next:"
echo "  source venv/bin/activate"
echo "  audible-to-yoto setup"
