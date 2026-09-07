"""Thin wrapper over audible-cli: library metadata, downloads, and locating downloaded files."""

from __future__ import annotations

import glob
import json
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .convert import AudioSource
from .state import load_json

AUDIBLE_CONFIG = Path.home() / ".audible" / "config.toml"
COVER_SIZE = "1215"


class AudibleError(Exception):
    pass


def audible_cmd() -> list[str]:
    exe = Path(sys.executable).parent / "audible"
    if exe.exists():
        return [str(exe)]
    found = shutil.which("audible")
    if found:
        return [found]
    raise AudibleError("audible-cli not found. Run ./setup.sh and activate the venv.")


def is_configured() -> bool:
    return AUDIBLE_CONFIG.exists()


def quickstart() -> None:
    subprocess.run(audible_cmd() + ["quickstart"], check=True)


@dataclass
class Book:
    asin: str
    title: str
    subtitle: str = ""
    authors: str = ""
    narrators: str = ""
    series_title: str = ""
    series_sequence: str = ""
    description: str = ""
    runtime_min: int = 0
    cover_url: str = ""

    @property
    def hours(self) -> float:
        return self.runtime_min / 60

    @property
    def author(self) -> str:
        return self.authors


def _join(value) -> str:
    if value is None or value == "-":
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return ", ".join(v.get("name", "") if isinstance(v, dict) else str(v) for v in value)
    return str(value)


def _strip_html(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or "")).strip()


def book_from_export(row: dict) -> Book:
    return Book(
        asin=str(row.get("asin", "")).strip(),
        title=_join(row.get("title")),
        subtitle=_join(row.get("subtitle")),
        authors=_join(row.get("authors")),
        narrators=_join(row.get("narrators")),
        series_title=_join(row.get("series_title")),
        series_sequence=_join(row.get("series_sequence")),
        description=_strip_html(_join(row.get("extended_product_description"))),
        runtime_min=int(row.get("runtime_length_min") or 0),
        cover_url=_join(row.get("cover_url")),
    )


def library_export(cache_path: Path, refresh: bool = False, max_age_hours: float = 24) -> list[Book]:
    """Export the Audible library to JSON (cached) and parse it."""
    stale = not cache_path.exists() or (time.time() - cache_path.stat().st_mtime) > max_age_hours * 3600
    if refresh or stale:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(audible_cmd() + ["library", "export", "-f", "json", "-o", str(cache_path)], check=True, capture_output=True, text=True)
    rows = json.loads(cache_path.read_text(encoding="utf-8"))
    return [book_from_export(r) for r in rows if r.get("asin")]


def resolve_books(books: list[Book], asin: str | None = None, title: str | None = None, all_: bool = False) -> list[Book]:
    if all_:
        return sorted(books, key=lambda b: b.title.lower())
    if asin:
        for b in books:
            if b.asin.upper() == asin.upper():
                return [b]
        raise AudibleError(f"ASIN {asin} is not in your Audible library (try `audible-to-yoto list --refresh`)")
    if title:
        needle = title.lower()
        hits = [b for b in books if needle in b.title.lower()]
        if len(hits) == 1:
            return hits
        exact = [b for b in hits if b.title.lower() == needle]
        if len(exact) == 1:
            return exact
        if not hits:
            raise AudibleError(f"No book title contains {title!r}")
        listing = "\n".join(f"  {b.asin}  {b.title}" for b in hits[:20])
        raise AudibleError(f"{len(hits)} books match {title!r}; pick one with --asin:\n{listing}")
    raise AudibleError("Choose a book with --asin, --title, or --all")


def download(book: Book, dest_dir: Path, log: Callable[[str], None] = print) -> None:
    """Download audio (AAX, falling back to AAXC + voucher), chapter JSON, and cover."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    cmd = audible_cmd() + [
        "download", "--asin", book.asin, "--aax-fallback", "--quality", "best",
        "--chapter", "--cover", "--cover-size", COVER_SIZE, "-y", "-o", str(dest_dir),
    ]
    log(f"  audible: downloading {book.title}")
    subprocess.run(cmd, check=True)


def fetch_extras(book: Book, dest_dir: Path) -> None:
    """Fetch only the chapter JSON and cover for a book whose audio is already downloaded."""
    cmd = audible_cmd() + ["download", "--asin", book.asin, "--chapter", "--cover", "--cover-size", COVER_SIZE, "-y", "-o", str(dest_dir)]
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def activation_bytes() -> str:
    proc = subprocess.run(audible_cmd() + ["activation-bytes"], capture_output=True, text=True)
    tokens = re.findall(r"\b[0-9a-fA-F]{8}\b", proc.stdout)
    if proc.returncode != 0 or not tokens:
        raise AudibleError("Could not get activation bytes. Run `audible activation-bytes` once and check for errors.")
    return tokens[-1]


def read_voucher(path: Path) -> tuple[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    lic = data.get("content_license", {}).get("license_response", {})
    key, iv = lic.get("key"), lic.get("iv")
    if not (key and iv):
        raise AudibleError(f"Voucher {path.name} has no key/iv")
    return key, iv


@dataclass
class DownloadSet:
    base: str
    audio_path: Path
    kind: str  # aax | aaxc
    chapters_path: Path | None
    cover_path: Path | None
    voucher_path: Path | None = None


def _title_base(title: str) -> str:
    """Approximate audible-cli's ascii filename mode for legacy downloads without chapter JSON."""
    ascii_title = title.encode("ascii", "ignore").decode()
    cleaned = re.sub(r"[^\w\s\-]", "", ascii_title)
    return re.sub(r"\s+", "_", cleaned).strip("_")


def _audio_for_base(dest_dir: Path, base: str) -> tuple[Path, str] | None:
    escaped = glob.escape(base)
    for pattern, kind in ((f"{escaped}-*.aax", "aax"), (f"{escaped}.aax", "aax"), (f"{escaped}-*.aaxc", "aaxc"), (f"{escaped}.aaxc", "aaxc")):
        hits = sorted(dest_dir.glob(pattern))
        if hits:
            return hits[0], kind
    return None


def _cover_for_base(dest_dir: Path, base: str) -> Path | None:
    hits = list(dest_dir.glob(f"{glob.escape(base)}_(*).jpg"))
    if not hits:
        return None

    def size_of(p: Path) -> int:
        m = re.search(r"_\((\d+)\)\.jpg$", p.name)
        return int(m.group(1)) if m else 0

    return max(hits, key=size_of)


def find_download(dest_dir: Path, book: Book) -> DownloadSet | None:
    """Locate the downloaded files for a book by matching the ASIN inside its chapter JSON."""
    if not dest_dir.exists():
        return None
    base = None
    chapters_path = None
    for cj in sorted(dest_dir.glob("*-chapters.json")):
        data = load_json(cj, {})
        found = data.get("content_metadata", {}).get("content_reference", {}).get("asin", "")
        if found.upper() == book.asin.upper():
            base = cj.name[: -len("-chapters.json")]
            chapters_path = cj
            break
    if base is None:
        candidate = _title_base(book.title)
        if candidate and _audio_for_base(dest_dir, candidate):
            base = candidate
        else:
            return None
    audio = _audio_for_base(dest_dir, base)
    if not audio:
        return None
    audio_path, kind = audio
    voucher = audio_path.with_suffix(".voucher") if kind == "aaxc" else None
    return DownloadSet(base=base, audio_path=audio_path, kind=kind, chapters_path=chapters_path, cover_path=_cover_for_base(dest_dir, base), voucher_path=voucher)


def audio_source(ds: DownloadSet) -> AudioSource:
    if ds.kind == "aaxc":
        if not ds.voucher_path or not ds.voucher_path.exists():
            raise AudibleError(f"{ds.audio_path.name} is AAXC but its .voucher is missing")
        key, iv = read_voucher(ds.voucher_path)
        return AudioSource(path=ds.audio_path, kind="aaxc", key=key, iv=iv)
    return AudioSource(path=ds.audio_path, kind="aax", activation_bytes=activation_bytes())
