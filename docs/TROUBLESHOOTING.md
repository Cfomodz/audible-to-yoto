# Troubleshooting Guide

Common issues and solutions for the Audible to Yoto converter.

---

## Setup Issues

### "Command not found: audible"

**Cause:** Virtual environment not activated.

**Solution:**
```bash
source venv/bin/activate
```

### "No module named 'PIL'"

**Cause:** Dependencies not installed.

**Solution:**
```bash
./setup.sh
source venv/bin/activate
```

---

## Audible CLI Issues

### "Not authenticated"

**Cause:** audible-cli not configured.

**Solution:**
```bash
source venv/bin/activate
audible quickstart
```

Follow the prompts to authenticate with your Audible account.

### "No activation bytes found"

**Cause:** Need to retrieve activation bytes.

**Solution:**
```bash
audible activation-bytes
```

This retrieves and stores your activation bytes automatically. The conversion script uses these automatically.

---

## Download Issues

### "AAXC files won't convert"

**Cause:** AAXC format requires voucher files that aren't available.

**Solution:** Download in AAX format instead:
```bash
./convert_audiobooks.sh
# Choose option 1 or 2
```

The script automatically downloads in AAX format which works with activation bytes.

### "Download fails"

**Cause:** Network issue or authentication expired.

**Solution:**
1. Check internet connection
2. Re-authenticate:
   ```bash
   audible quickstart
   ```

---

## Conversion Issues

### "AAC decoding errors"

**Cause:** File is AAXC format or activation bytes don't match.

**Solution:**
1. Verify file format:
   ```bash
   ffprobe -v quiet -print_format json -show_format "file.aax" | grep major_brand
   ```
2. If shows `"aaxc"`, re-download in AAX format
3. If shows `"aax"`, verify activation bytes:
   ```bash
   audible activation-bytes
   ```

### "Activation bytes invalid"

**Cause:** Activation bytes don't match your Audible account.

**Solution:**
```bash
# Re-retrieve activation bytes
audible activation-bytes

# Test with a file
ffprobe -activation_bytes $(audible activation-bytes) -v quiet -print_format json -show_format "file.aax"
```

### "No chapters found"

**Cause:** Some audiobooks don't have chapter metadata.

**Solution:** This is expected for some books. The script creates a single file for the entire book.

### "Conversion very slow"

**Cause:** CPU-intensive processing or very large file.

**Solution:** This is normal. Conversion is typically 100x+ realtime. Very long books (20+ hours) may take several minutes.

---

## Cover Generation Issues

### "No covers downloaded"

**Cause:** Book not found in Open Library database.

**Solution:** The script automatically creates placeholder covers with the book title when downloads fail.

### "Cover quality is poor"

**Cause:** Open Library may have low-resolution covers for some books.

**Solution:** Manually download a better cover image and place it in `yoto_covers/` as `BookName.jpg` (400x400 pixels).

---

## Icon Generation Issues

### "No icons generated"

**Cause:** No converted audiobooks found.

**Solution:** Convert audiobooks first:
```bash
./convert_audiobooks.sh
```

Then generate icons:
```bash
python3 generate_chapter_icons.py --yes
```

---

## Playlist Issues

### "JSON invalid"

**Cause:** Malformed JSON structure.

**Solution:** Regenerate playlists:
```bash
python3 generate_playlists.py --yes
```

### "Missing chapter info"

**Cause:** Audiobook doesn't have chapter metadata.

**Solution:** The script creates a single-chapter playlist. This is expected for some books.

---

## File Organization

### "Can't find output files"

**Solution:** Check these locations:

| Content | Location |
|---------|----------|
| Audio | `yoto_mp3/` |
| Covers | `yoto_covers/` |
| Icons | `yoto_chapter_icons_16x16/` |
| Playlists | `yoto_playlists/` |

### "Duplicate files"

**Cause:** Ran conversion multiple times.

**Solution:** The script skips existing files. To reconvert:
```bash
./convert_audiobooks.sh
# Choose option 7 to reset progress
```

---

## Progress Tracking

### "Progress not saving"

**Cause:** File permission issue or disk full.

**Solution:**
```bash
# Check disk space
df -h .

# Reset progress if needed
./convert_audiobooks.sh
# Choose option 7
```

### "Can't resume"

**Cause:** Progress file was deleted.

**Solution:** The script will start fresh. Already-converted books (with existing output folders) will be skipped automatically.

---

## Storage Issues

### "Not enough disk space"

**Estimates for 120 books:**
- AAX files: ~12-24 GB
- MP3 files: ~6-12 GB
- Covers: ~10 MB
- Icons: ~1 MB
- **Total:** ~20-35 GB

**Solutions:**
- Delete AAX files after successful conversion
- Use external storage
- Convert in batches

### "Where are AAX files?"

**Location:** `aax_downloads/` directory

These can be deleted after successful conversion to save space.

---

## Yoto Upload Issues

### "Yoto won't accept files"

**Verify formats:**
- Audio: MP3 format ✓
- Book covers: 400x400 JPEG ✓
- Chapter icons: 16x16 PNG ✓
- Playlist: Valid JSON ✓

### "Icons not showing"

**Check:**
1. Icon was uploaded to Yoto API successfully
2. Icon ID format is `yoto:#<id>`
3. JSON references the correct ID

### "Audio not playing"

**Check:**
1. URL is HTTPS (not HTTP)
2. URL is publicly accessible
3. URL is direct link to MP3 (not a sharing page)

---

## Performance

### "Conversion taking too long"

**Expected times:**
- Single book: 2-5 minutes
- 120 books: 2-5 hours

If significantly slower:
1. Check CPU usage
2. Check disk I/O
3. Close other applications

### "High memory usage"

**Cause:** Processing very large audiobooks (20+ hours).

**Solution:** This is normal. The script processes one book at a time to minimize memory usage.

---

## Debug Mode

Enable verbose output for troubleshooting:

```bash
# For bash scripts
bash -x ./convert_audiobooks.sh

# For Python scripts
python3 generate_chapter_icons.py --help
```

### Common Error Patterns

| Pattern | Meaning |
|---------|---------|
| `[aac @ ...]` | Audio decoding issue |
| `[aaxc]` | AAXC format (needs AAX) |
| `HTTP 4xx` | Authentication or access issue |
| `HTTP 5xx` | Server error (retry later) |

---

## Quick Checklist

If something isn't working, verify:

- [ ] Virtual environment is activated
- [ ] Dependencies are installed (`./setup.sh`)
- [ ] audible-cli is configured (`audible quickstart`)
- [ ] Activation bytes are retrieved (`audible activation-bytes`)
- [ ] Files are AAX format (not AAXC)
- [ ] Sufficient disk space available
- [ ] Internet connection is working

---

## Getting Help

1. Check this troubleshooting guide
2. See [YOTO_SPECIFICATIONS.md](YOTO_SPECIFICATIONS.md) for technical details
3. See [YOTO_WORKFLOW.md](YOTO_WORKFLOW.md) for complete workflow
4. Open an issue on GitHub with:
   - Error message
   - Steps to reproduce
   - System information (OS, Python version)
