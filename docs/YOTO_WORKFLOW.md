# Complete Yoto Upload Workflow

Step-by-step guide to convert your audiobooks and upload them to Yoto.

---

## Overview

The complete workflow has 7 steps:

1. Convert audiobooks to chapter-split MP3s
2. Generate book covers (400x400)
3. Generate chapter icons (16x16)
4. Generate playlist JSON files
5. Upload files to your server
6. Upload icons to Yoto API
7. Upload JSON to Yoto MYO

---

## Step 1: Convert Audiobooks

```bash
./convert_audiobooks.sh
```

**Output:**
- Chapter-split MP3 files in `yoto_mp3/`
- One folder per book
- Naming: `Chapter_001_Title.mp3`

---

## Step 2: Generate Book Covers

```bash
python3 generate_covers.py --yes
```

**Output:**
- `yoto_covers/`
- 400x400 JPEG files
- One per book

---

## Step 3: Generate Chapter Icons

```bash
python3 generate_chapter_icons.py --yes
```

**Options:**
1. **Numbers** (1, 2, 3...) - Simplest, most clear
2. **Symbols** (shapes) - Visual variety
3. **Miniatures** (tiny covers) - Recognizable

**Output:**
```
yoto_chapter_icons_16x16/
├── numbers/
│   ├── Book 1/
│   │   ├── chapter_001.png (16x16)
│   │   ├── chapter_002.png
│   │   └── ...
│   └── ...
├── symbols/
│   └── ...
└── miniatures/
    └── ...
```

---

## Step 4: Generate Playlist JSON

```bash
python3 generate_playlists.py --yes
```

**Output:**
```
yoto_playlists/
├── Book 1.json
├── Book 1_INSTRUCTIONS.txt
├── Book 2.json
├── Book 2_INSTRUCTIONS.txt
└── ...
```

Each JSON contains:
- Book metadata
- Chapter list
- Icon placeholders (to be filled in)
- Audio URL placeholders

---

## Step 5: Upload Files to Your Server

### Audio Files

Upload MP3 files to your web hosting:

```
your-server.com/audiobooks/
├── Book_1/
│   ├── Chapter_001_Introduction.mp3
│   ├── Chapter_002_Chapter_One.mp3
│   └── ...
└── ...
```

### Cover Images

```
your-server.com/covers/
├── Book_1.jpg
├── Book_2.jpg
└── ...
```

**Requirements:**
- HTTPS URLs
- Publicly accessible
- Direct links (not sharing links)

---

## Step 6: Upload Icons to Yoto API

For each chapter icon:

```bash
curl -X POST https://api.yoto.io/v1/icons \
  -H "Authorization: Bearer YOUR_YOTO_API_TOKEN" \
  -F "file=@chapter_001.png" \
  -F "autoConvert=true"
```

**Response:**
```json
{
  "id": "abc123def456",
  "url": "https://yoto.io/icons/abc123def456"
}
```

**Save every ID!** You'll need them for the playlist JSON.

---

## Step 7: Edit and Upload Playlist JSON

### Update the JSON

Replace placeholders with actual values:

**Audio URLs:**
```json
"trackUrl": "https://your-server.com/audiobooks/Book_1/Chapter_001.mp3"
```

**Icon IDs:**
```json
"display": {
  "icon16x16": "yoto:#abc123def456"
}
```

### Upload to Yoto MYO

1. Go to https://yoto.io/myo
2. Create a new card
3. Upload your edited JSON file
4. Yoto creates the card!
5. Test on your Yoto Player

---

## File Structure Summary

```
project/
├── yoto_mp3/                          # Audio files
│   ├── Book 1/
│   │   ├── Chapter_001_Title.mp3
│   │   └── ...
│   └── ...
│
├── yoto_covers/                       # Book covers (400x400)
│   ├── Book 1.jpg
│   └── ...
│
├── yoto_chapter_icons_16x16/          # Chapter icons (16x16)
│   ├── numbers/
│   │   ├── Book 1/
│   │   │   ├── chapter_001.png
│   │   │   └── ...
│   │   └── ...
│   └── ...
│
└── yoto_playlists/                    # Playlist JSONs
    ├── Book 1.json
    ├── Book 1_INSTRUCTIONS.txt
    └── ...
```

---

## Icon Style Comparison

### Numbers (Recommended)

```
┌──────┐
│  1   │  Simple, clear, universal
└──────┘
```

**Pros:** Instantly recognizable, works for any book, clear at 16x16

**Cons:** Less visually interesting

### Symbols

```
┌──────┐
│  ▶   │  Start: Triangle
│  ●   │  Middle: Circle
│  ■   │  End: Square
└──────┘
```

**Pros:** Visual variety, shows progress

**Cons:** Less clear which chapter

### Miniatures

```
┌──────┐
│[tiny]│  Miniature book cover
│cover │  with indicator dot
└──────┘
```

**Pros:** Recognizable, consistent

**Cons:** Hard to see details at 16x16

---

## Time Estimates

### For a Large Library (120 books)

| Task | Time |
|------|------|
| Convert audiobooks | 2-5 hours |
| Generate covers | 5-15 minutes |
| Generate icons | ~1 minute |
| Generate playlists | ~1 minute |
| Upload to server | 1-2 hours |
| Upload icons to Yoto | 1-2 hours (manual) |
| Edit JSONs | 1-2 hours |
| Upload to MYO | 1-2 hours |
| **Total** | ~8-15 hours |

### Automation Tips

Many steps can be automated:
- ✅ Conversion (fully automated)
- ✅ Cover generation (fully automated)
- ✅ Icon generation (fully automated)
- ✅ Playlist generation (fully automated)
- ⚠️ Icon upload (can be scripted)
- ⚠️ JSON editing (can be scripted)
- ❌ Yoto MYO upload (manual)

---

## Hosting Options

### Audio File Hosting

| Option | Pros | Cons |
|--------|------|------|
| AWS S3 | Reliable, scalable | Cost |
| Google Cloud | Same as S3 | Cost |
| DigitalOcean Spaces | Cheaper | Smaller ecosystem |
| Your own VPS | Full control | Maintenance |
| GitHub Pages | Free | Size limits |

### Requirements

- HTTPS (required by Yoto)
- Direct file URLs
- Sufficient bandwidth
- Reliable uptime

---

## Troubleshooting

### Icons Not Showing

- Verify icon is 16x16 PNG
- Check icon ID format: `yoto:#<id>`
- Ensure icon was uploaded successfully

### Audio Not Playing

- Verify URL is HTTPS
- Check URL is publicly accessible
- Ensure direct link to MP3 file

### JSON Upload Fails

- Validate JSON syntax
- Check all required fields present
- Verify URL formats

---

## Quick Reference

### Scripts

```bash
# Convert audiobooks
./convert_audiobooks.sh

# Generate covers
python3 generate_covers.py --yes

# Generate icons
python3 generate_chapter_icons.py --style numbers --yes

# Generate playlists
python3 generate_playlists.py --yes
```

### File Locations

| Content | Location |
|---------|----------|
| Audio files | `yoto_mp3/` |
| Book covers | `yoto_covers/` |
| Chapter icons | `yoto_chapter_icons_16x16/` |
| Playlists | `yoto_playlists/` |

### Yoto Requirements

| Item | Specification |
|------|---------------|
| Cover | 400x400 JPEG |
| Icon | 16x16 PNG |
| Audio | MP3 (HTTPS) |
| Playlist | JSON |

---

## Next Steps

After completing all steps:

1. Test the card on your Yoto Player
2. Verify all chapters play correctly
3. Check icons display properly
4. Share with your family!

---

See [YOTO_SPECIFICATIONS.md](YOTO_SPECIFICATIONS.md) for detailed technical specifications.
