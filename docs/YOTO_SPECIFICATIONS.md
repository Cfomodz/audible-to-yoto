# Yoto Official Specifications

Technical reference for Yoto's image and playlist requirements, based on official documentation at yoto.dev.

---

## Image Requirements

### Book Cover (Card Artwork)

**Purpose:** Main card image shown in app and on physical card

| Attribute | Requirement |
|-----------|-------------|
| **Size** | 400x400 pixels minimum |
| **Format** | JPEG or PNG |
| **Aspect Ratio** | Square (1:1) |
| **Quality** | High resolution recommended |

Yoto will auto-resize if needed, but 400x400 is optimal.

---

### Chapter Icons

**Purpose:** Small icons shown on Yoto Player display during chapter selection

| Attribute | Requirement |
|-----------|-------------|
| **Size** | 16x16 pixels |
| **Format** | PNG or GIF |
| **Style** | Pixel art recommended |
| **Usage** | One icon per chapter |

Set `autoConvert: true` when uploading and Yoto will handle any needed conversion.

---

## Playlist JSON Format

Yoto uses JSON to define card content. Here's the complete structure:

```json
{
  "title": "Book Title",
  "description": "Book description",
  "cover": {
    "imageL": "https://url-to-cover-image.jpg"
  },
  "chapters": [
    {
      "key": "01",
      "title": "Chapter 1: Introduction",
      "display": {
        "icon16x16": "yoto:#<icon-identifier>"
      },
      "tracks": [
        {
          "key": "01",
          "title": "Chapter 1",
          "trackUrl": "https://url-to-audio.mp3",
          "type": "audio"
        }
      ]
    },
    {
      "key": "02",
      "title": "Chapter 2: The Beginning",
      "display": {
        "icon16x16": "yoto:#<icon-identifier>"
      },
      "tracks": [
        {
          "key": "02",
          "title": "Chapter 2",
          "trackUrl": "https://url-to-audio.mp3",
          "type": "audio"
        }
      ]
    }
  ]
}
```

---

## Icon Upload API

### Uploading Custom Icons

```bash
curl -X POST https://api.yoto.io/v1/icons \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@chapter_icon.png" \
  -F "autoConvert=true"
```

### Response

```json
{
  "id": "abc123def456",
  "url": "https://yoto.io/icons/abc123def456"
}
```

### Using the Icon

Reference the ID in your playlist JSON:

```json
"display": {
  "icon16x16": "yoto:#abc123def456"
}
```

### Using Yoto's Public Icons

- Browse available icons at: https://www.yotoicons.com
- Each icon has a SHA256 hash ID
- Use directly: `"icon16x16": "yoto:#<hash>"`

---

## Audio Requirements

| Attribute | Requirement |
|-----------|-------------|
| **Format** | MP3 |
| **Hosting** | Your own server (HTTPS) |
| **Access** | Publicly accessible URL |

Yoto does not host audio files. You must provide direct URLs to your MP3 files.

---

## Organization System

**Important:** Yoto does NOT auto-organize content.

You must:
1. ✅ Create playlist JSON manually
2. ✅ Upload icons via API
3. ✅ Reference icons by ID in JSON
4. ✅ Upload JSON to Yoto MYO

Yoto will NOT:
- ❌ Auto-detect chapter order from filenames
- ❌ Auto-match icons to chapters
- ❌ Auto-create playlist from folder structure

**Everything must be explicitly defined in the playlist JSON.**

---

## Icon Design Guidelines

### For 16x16 Pixel Art

**Recommended:**
- Simple, clear designs
- High contrast colors
- Recognizable at small size
- Consistent style across chapters

**Examples:**
- Numbers (1, 2, 3...)
- Simple symbols
- Basic shapes
- Minimal detail

**Avoid:**
- Complex images (won't be visible)
- Text (too small to read)
- Photos (need pixel art style)

---

## File Size Estimates

### Per Book (50 chapters)

| Item | Size |
|------|------|
| Book cover (400x400) | ~80 KB |
| Chapter icons (16x16 × 50) | ~50 KB |
| **Total** | ~130 KB |

### For 120 Books

| Item | Size |
|------|------|
| Book covers | ~10 MB |
| Chapter icons | ~6 MB |
| **Total images** | ~16 MB |

---

## API Authentication

To upload icons to Yoto, you need an API token:

1. Go to https://yoto.io/account
2. Navigate to API settings
3. Generate an API token
4. Store securely (don't commit to git!)

**Note:** Yoto API may have rate limits. Plan uploads accordingly.

---

## Summary

| Component | Specification |
|-----------|---------------|
| Book cover | 400x400 JPEG |
| Chapter icons | 16x16 PNG |
| Audio | MP3 (self-hosted) |
| Playlist | JSON format |
| Organization | Manual via JSON |
| Icon upload | Yoto API |

---

## Resources

- **Yoto MYO:** https://yoto.io/myo
- **Icon Browser:** https://www.yotoicons.com
- **Developer Docs:** https://yoto.dev
