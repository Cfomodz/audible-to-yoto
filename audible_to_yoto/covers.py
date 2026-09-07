"""Book cover: Audible's 1215px JPG (or the library cover URL) -> square JPEG for Yoto."""

from __future__ import annotations

import io
from pathlib import Path

import requests
from PIL import Image

MAX_SIDE = 1215


def prepare_cover(dest: Path, cover_path: Path | None = None, cover_url: str | None = None) -> Path | None:
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    data: bytes | None = None
    if cover_path and cover_path.exists():
        data = cover_path.read_bytes()
    elif cover_url:
        try:
            resp = requests.get(cover_url, timeout=30)
            if resp.ok and len(resp.content) > 1000:
                data = resp.content
        except requests.RequestException:
            data = None
    if not data:
        return None
    img = Image.open(io.BytesIO(data)).convert("RGB")
    w, h = img.size
    side = min(w, h)
    left, top = (w - side) // 2, (h - side) // 2
    img = img.crop((left, top, left + side, top + side))
    if side > MAX_SIDE:
        img = img.resize((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, "JPEG", quality=90)
    return dest
