import io

import pytest
from PIL import Image

from audible_to_yoto.pixel import SIZE, book_icon, contact_sheet, normalize_icon, number_icon, png_bytes


@pytest.mark.parametrize("n", [1, 7, 12, 99, 123])
def test_number_icon(n):
    img = number_icon(n)
    assert img.size == (SIZE, SIZE)
    white = sum(1 for y in range(SIZE) for x in range(SIZE) if img.getpixel((x, y))[:3] == (255, 255, 255))
    assert white > 8
    assert img.getpixel((0, 0))[:3] == (30, 58, 138)


def test_number_icons_differ():
    assert number_icon(1).tobytes() != number_icon(2).tobytes()
    assert number_icon(12).tobytes() != number_icon(21).tobytes()


def test_number_icon_clamps():
    assert number_icon(-5).size == (SIZE, SIZE)
    assert number_icon(10_000).tobytes() == number_icon(999).tobytes()


def test_book_icons():
    assert book_icon(closed=False).size == (SIZE, SIZE)
    assert book_icon(True).tobytes() != book_icon(False).tobytes()


def test_png_bytes():
    data = png_bytes(number_icon(3))
    assert data[:8] == b"\x89PNG\r\n\x1a\n"


def test_normalize_icon_passes_through_16x16():
    original = png_bytes(number_icon(3))
    assert Image.open(io.BytesIO(normalize_icon(original))).size == (SIZE, SIZE)


def test_normalize_icon_downscales_an_upscaled_copy():
    """A 128x128 upscale must come back as the exact original 16x16 pixels."""
    small = number_icon(5)
    big = small.resize((128, 128), Image.Resampling.NEAREST)
    restored = Image.open(io.BytesIO(normalize_icon(png_bytes(big))))
    assert restored.size == (SIZE, SIZE)
    assert restored.tobytes() == small.tobytes()


def test_normalize_icon_converts_palette_mode():
    paletted = number_icon(6).convert("P")
    out = Image.open(io.BytesIO(normalize_icon(png_bytes(paletted))))
    assert out.mode == "RGBA" and out.size == (SIZE, SIZE)


def test_normalize_icon_handles_odd_size():
    odd = number_icon(7).resize((37, 21), Image.Resampling.NEAREST)
    assert Image.open(io.BytesIO(normalize_icon(png_bytes(odd)))).size == (SIZE, SIZE)


def test_contact_sheet():
    sheet = contact_sheet([("1. One", number_icon(1)), ("2. Two", number_icon(2))], scale=4, cols=2)
    assert isinstance(sheet, Image.Image)
    assert sheet.size[0] == 2 * (SIZE * 4 + 24)
