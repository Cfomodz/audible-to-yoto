"""16x16 icon drawing: pixel digits, a book glyph, and the preview contact sheet."""

from __future__ import annotations

import io

from PIL import Image, ImageDraw, ImageFont

SIZE = 16

DIGITS_3x5: dict[str, list[str]] = {
    "0": ["111", "101", "101", "101", "111"],
    "1": ["010", "110", "010", "010", "111"],
    "2": ["111", "001", "111", "100", "111"],
    "3": ["111", "001", "111", "001", "111"],
    "4": ["101", "101", "111", "001", "001"],
    "5": ["111", "100", "111", "001", "111"],
    "6": ["111", "100", "111", "101", "111"],
    "7": ["111", "001", "001", "001", "001"],
    "8": ["111", "101", "111", "101", "111"],
    "9": ["111", "101", "111", "001", "111"],
}

NUMBER_BG = (30, 58, 138)
NUMBER_FG = (255, 255, 255)


def number_icon(n: int, fg: tuple[int, int, int] = NUMBER_FG, bg: tuple[int, int, int] = NUMBER_BG) -> Image.Image:
    """Crisp pixel digits on a solid background. 1-2 digits at 2x, 3 digits at 1x wide / 2x tall."""
    text = str(max(0, min(n, 999)))
    sx = 2 if len(text) <= 2 else 1
    sy = 2
    gap = 2 if len(text) <= 2 else 1
    glyph_w, glyph_h = 3 * sx, 5 * sy
    total_w = len(text) * glyph_w + (len(text) - 1) * gap
    img = Image.new("RGBA", (SIZE, SIZE), (*bg, 255))
    px = img.load()
    x0 = (SIZE - total_w) // 2
    y0 = (SIZE - glyph_h) // 2
    for i, ch in enumerate(text):
        glyph = DIGITS_3x5[ch]
        gx = x0 + i * (glyph_w + gap)
        for gy, row in enumerate(glyph):
            for gxx, bit in enumerate(row):
                if bit == "1":
                    for dy in range(sy):
                        for dx in range(sx):
                            px[gx + gxx * sx + dx, y0 + gy * sy + dy] = (*fg, 255)
    return img


_OPEN_BOOK = [
    "0000000000000000",
    "0000000000000000",
    "0000000000000000",
    "0111111001111110",
    "1111111001111111",
    "1100001001000011",
    "1111111001111111",
    "1100001001000011",
    "1111111001111111",
    "1100001001000011",
    "1111111001111111",
    "1111111001111111",
    "0111111001111110",
    "0011111111111100",
    "0000000000000000",
    "0000000000000000",
]


def book_icon(closed: bool = False, fg: tuple[int, int, int] = NUMBER_FG, bg: tuple[int, int, int] = NUMBER_BG) -> Image.Image:
    """Credits icon: an open book (opening credits) or a closed book (end credits)."""
    img = Image.new("RGBA", (SIZE, SIZE), (*bg, 255))
    if closed:
        d = ImageDraw.Draw(img)
        d.rectangle([3, 2, 12, 13], fill=fg)
        d.rectangle([5, 2, 12, 13], fill=(200, 60, 60))
        d.line([(6, 4), (11, 4)], fill=fg)
        return img
    px = img.load()
    for y, row in enumerate(_OPEN_BOOK):
        for x, bit in enumerate(row):
            if bit == "1":
                px[x, y] = (*fg, 255)
    return img


def png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def normalize_icon(data: bytes) -> bytes:
    """Return the icon as a 16x16 RGBA PNG.

    Community icons are sometimes uploaded as upscaled copies (128x128 is common). Downscaling
    with nearest-neighbour recovers the original pixels exactly when the size is a multiple of
    16, and keeps hard edges when it is not.
    """
    img = Image.open(io.BytesIO(data))
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    if img.size != (SIZE, SIZE):
        img = img.resize((SIZE, SIZE), Image.Resampling.NEAREST)
    return png_bytes(img)


def contact_sheet(items: list[tuple[str, Image.Image]], scale: int = 8, cols: int = 5) -> Image.Image:
    """Preview sheet: each icon scaled up with its caption underneath."""
    cell_w = SIZE * scale + 24
    cell_h = SIZE * scale + 44
    rows = max(1, (len(items) + cols - 1) // cols)
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), (245, 245, 245))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for i, (caption, icon) in enumerate(items):
        cx = (i % cols) * cell_w + 12
        cy = (i // cols) * cell_h + 8
        big = icon.convert("RGBA").resize((SIZE * scale, SIZE * scale), Image.Resampling.NEAREST)
        backdrop = Image.new("RGBA", big.size, (255, 255, 255, 255))
        backdrop.alpha_composite(big)
        sheet.paste(backdrop.convert("RGB"), (cx, cy))
        draw.text((cx, cy + SIZE * scale + 4), caption[: (cell_w - 12) // 6], fill=(20, 20, 20), font=font)
    return sheet
