"""Per-book work directory and atomic JSON state files."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def save_json(path: Path, obj: Any) -> None:
    """Write JSON atomically so an interrupted run never leaves a half-written state file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


class WorkDir:
    """work/<ASIN>/ layout. Every stage of the pipeline reads and writes here."""

    def __init__(self, root: Path, asin: str):
        self.asin = asin
        self.path = root / asin

    @property
    def chapters_json(self) -> Path:
        return self.path / "chapters.json"

    @property
    def icons_json(self) -> Path:
        return self.path / "icons.json"

    @property
    def uploads_json(self) -> Path:
        return self.path / "uploads.json"

    @property
    def card_json(self) -> Path:
        return self.path / "card.json"

    @property
    def mp3_dir(self) -> Path:
        return self.path / "mp3"

    @property
    def icons_dir(self) -> Path:
        return self.path / "icons"

    @property
    def cover_jpg(self) -> Path:
        return self.path / "cover.jpg"

    @property
    def preview_png(self) -> Path:
        return self.path / "preview.png"

    def ensure(self) -> "WorkDir":
        self.mp3_dir.mkdir(parents=True, exist_ok=True)
        self.icons_dir.mkdir(parents=True, exist_ok=True)
        return self

    def icon_path(self, chapter_index: int) -> Path:
        return self.icons_dir / f"{chapter_index:03d}.png"

    def track_path(self, track_no: int) -> Path:
        return self.mp3_dir / f"{track_no:03d}.mp3"
