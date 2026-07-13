# 🎧 Audible to Yoto Converter

[![Tests](https://github.com/cfomodz/audible-to-yoto/actions/workflows/test.yml/badge.svg)](https://github.com/cfomodz/audible-to-yoto/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

Convert your entire Audible library to Yoto-ready audiobooks with proper chapter splitting and cover images!

## Features

✅ **Download from Audible** - Uses official audible-cli  
✅ **AAX Format** - Works with activation bytes (not AAXC)  
✅ **Chapter Splitting** - Individual MP3 per chapter  
✅ **Resume Capability** - Pick up where you left off  
✅ **Cover Generation** - Download from Open Library or create placeholders  
✅ **Yoto Icons** - Proper 16x16 chapter icons  
✅ **Playlist JSON** - Auto-generate Yoto playlists  
✅ **Non-Interactive Mode** - Scriptable with `--yes` flag  
✅ **Portable** - No hardcoded paths, works anywhere  

---

## Quick Start

```bash
# 1. Setup
./setup.sh

# 2. Activate environment
source venv/bin/activate

# 3. Configure audible-cli
audible quickstart

# 4. Get activation bytes
audible activation-bytes

# 5. Convert all audiobooks
./convert_audiobooks.sh

# 6. Generate covers, icons, and playlists
python3 generate_covers.py --yes
python3 generate_chapter_icons.py --yes
python3 generate_playlists.py --yes
```

---

## What You Get

### Audiobooks
- **Location:** `yoto_mp3/`
- **Format:** Chapter-split MP3 files
- **Naming:** `Chapter_001_Title.mp3`, `Chapter_002_Title.mp3`, etc.
- **Quality:** High-quality VBR (~190 kbps)

### Book Covers
- **Location:** `yoto_covers/`
- **Format:** 400x400 JPEG (Yoto specification)
- **Sources:** Open Library API, Perplexity, or placeholder

### Chapter Icons
- **Location:** `yoto_chapter_icons_16x16/`
- **Format:** 16x16 PNG (Yoto specification)
- **Styles:** Numbers, Symbols, or Miniatures

### Playlist JSON
- **Location:** `yoto_playlists/`
- **Format:** Yoto-compatible JSON
- **Includes:** Chapter metadata, icon references, audio URLs

---

## Requirements

### System Dependencies
- Python 3.10+
- ffmpeg (with AAX support)
- ImageMagick
- curl

### Python Packages
- audible >= 0.8.2
- audible-cli >= 0.3.3
- Pillow >= 10.0.0
- requests >= 2.31.0

### Optional
- Book cover images (400x400 JPEG, manual download)

---

## Installation

### Arch/Manjaro
```bash
sudo pacman -S python ffmpeg imagemagick curl
./setup.sh
```

### Ubuntu/Debian
```bash
sudo apt install python3 python3-venv ffmpeg imagemagick curl
./setup.sh
```

### macOS
```bash
brew install python ffmpeg imagemagick curl
./setup.sh
```

---

## Usage

### 1. Convert Audiobooks

```bash
./convert_audiobooks.sh
```

**Options:**
1. Download ALL audiobooks and convert
2. Download specific book by title
3. Download specific book by ASIN
4. Convert existing AAX files
5. List library
6. **Resume previous conversion**
7. **Reset progress**

### 2. Generate Book Covers

```bash
python3 generate_covers.py                  # Interactive mode
python3 generate_covers.py --yes            # Non-interactive (auto mode)
python3 generate_covers.py --method openlibrary --yes
python3 generate_covers.py --method placeholder --yes
```

**Cover Sources:**
- **openlibrary** - Download from Open Library API (free, recommended)
- **perplexity** - Search via Perplexity CLI (if installed)
- **placeholder** - Create text-based cover with book title
- **auto** - Try openlibrary first, fall back to placeholder

### 3. Generate Chapter Icons

```bash
python3 generate_chapter_icons.py           # Interactive mode
python3 generate_chapter_icons.py --yes     # Non-interactive (default style)
python3 generate_chapter_icons.py --style numbers --yes
```

**Icon Styles:**
- **Numbers** (1, 2, 3...) - Recommended
- **Symbols** (shapes) - Visual variety
- **Miniatures** (tiny covers) - Recognizable

### 4. Generate Playlist JSON

```bash
python3 generate_playlists.py               # Interactive mode
python3 generate_playlists.py --yes         # Non-interactive
python3 generate_playlists.py --audio-url https://myserver.com/audio --yes
```

Creates Yoto-compatible JSON files for each book.

---

## Documentation

| Document | Description |
|----------|-------------|
| [YOTO_SPECIFICATIONS.md](docs/YOTO_SPECIFICATIONS.md) | Official Yoto specs & API reference |
| [YOTO_WORKFLOW.md](docs/YOTO_WORKFLOW.md) | Complete upload workflow |
| [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Common issues & solutions |

---

## How It Works

### 1. Download (AAX Format)
- Uses `audible-cli` to download from your library
- Downloads in AAX format (works with activation bytes)
- Includes chapter metadata

### 2. Convert (Chapter-Split MP3)
- Uses ffmpeg with activation bytes
- Decrypts AAX files
- Splits by chapters automatically
- Numbers files for proper ordering

### 3. Generate Covers
- Downloads from Open Library API (free)
- Falls back to placeholder covers
- Resizes to 400x400 (Yoto spec)

### 4. Generate Icons
- Creates 16x16 chapter icons (Yoto spec)
- Multiple styles: numbers, symbols, miniatures

### 5. Create Playlists
- Generates Yoto-compatible JSON
- Includes chapter metadata
- References icons and audio URLs

---

## File Structure

```
audible-to-yoto/
├── README.md                         # This file
├── LICENSE                           # MIT License
├── CONTRIBUTING.md                   # Contribution guidelines
├── requirements.txt                  # Python dependencies
├── setup.sh                          # Setup script
├── convert_audiobooks.sh             # Main conversion script
├── generate_covers.py                # Cover downloader (400x400)
├── generate_chapter_icons.py         # Icon generator (16x16)
├── generate_playlists.py             # Playlist JSON generator
├── docs/
│   ├── YOTO_SPECIFICATIONS.md        # Yoto API specs
│   ├── YOTO_WORKFLOW.md              # Upload workflow
│   └── TROUBLESHOOTING.md            # Common issues
└── [Generated directories]
    ├── aax_downloads/                # Downloaded AAX files
    ├── yoto_mp3/                     # Converted audiobooks
    ├── yoto_covers/                  # Book covers (400x400)
    ├── yoto_chapter_icons_16x16/     # Chapter icons (16x16)
    └── yoto_playlists/               # Playlist JSON files
```

---

## Progress Tracking

The conversion script tracks progress automatically:

- **Progress file:** `.conversion_progress`
- **Resume:** Choose option 6 in menu
- **Reset:** Choose option 7 in menu
- **Skip existing:** Automatically skips completed books

---

## Yoto Upload Process

After conversion:

1. **Upload audio files** to your web server
2. **Upload chapter icons** to Yoto API (get IDs)
3. **Edit playlist JSON** with icon IDs
4. **Upload JSON** to Yoto MYO website

See [YOTO_WORKFLOW.md](docs/YOTO_WORKFLOW.md) for details.

---

## Time & Storage Estimates

### For 120 Books:

**Time:**
- Download: 2-4 hours
- Convert: 15-30 minutes
- Generate covers: 5-15 minutes
- Generate icons: ~1 minute
- **Total: ~2-5 hours**

**Storage:**
- AAX files: ~12-24 GB
- MP3 files: ~6-12 GB
- Covers: ~10 MB
- Icons: ~1 MB
- **Total: ~20-35 GB**

---

## FAQ

### How long does conversion take?
- **Single book:** 2-5 minutes
- **120 books:** 2-5 hours (mostly downloading)

### Can I pause and resume?
Yes! The script tracks progress automatically. Press Ctrl+C to pause, then choose "Resume" from the menu.

### What if I have AAXC files?
AAXC files require voucher files. Re-download in AAX format using the script (it downloads AAX automatically).

### What about book covers?
Run `python3 generate_covers.py` to download covers from Open Library (free API). If a cover isn't found, a placeholder with the book title is created automatically.

### How much disk space needed?
- **Per book:** 150-450 MB
- **120 books:** 20-35 GB

### Is this legal?
Yes, for personal use. You're converting your own purchased audiobooks.

### More questions?
See [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for detailed solutions.

---

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

## License

MIT License - See LICENSE file for details

---

## Acknowledgments

- **[audible-cli](https://github.com/mkb79/audible-cli)** - Audible API client
- **[FFmpeg](https://ffmpeg.org/)** - Audio processing
- **[Pillow](https://python-pillow.org/)** - Image generation
- **[Yoto](https://yoto.io/)** - The amazing Yoto Player

---

## Disclaimer

This tool is for personal use only. You must own the audiobooks you convert. Respect copyright laws and Audible's terms of service.

---

## Support

- **Issues:** Open an issue on GitHub
- **Documentation:** See `docs/` directory
- **Questions:** Check FAQ in documentation

---

**Made with ❤️ for Yoto users**
