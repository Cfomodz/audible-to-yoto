"""Pure chapter logic: normalize audible-cli chapter JSON and plan the MP3 tracks.

Source of truth is the `{book}-chapters.json` that audible-cli writes. It carries the
real chapter titles ("1: The Boy Who Lived") and correct split points; the chapter
atoms embedded in the AAX only say "Chapter 1" and merge the credits.
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field

MAX_TRACK_MS = 60 * 60 * 1000  # Yoto: 60 minutes per track
MAX_TRACK_BYTES = 95 * 1024 * 1024  # Yoto: 100 MB per track, keep headroom

_CREDITS_RE = re.compile(r"^\s*(opening|end|closing)\s+credits\s*$", re.IGNORECASE)
_LEADING_NUMBER_RE = re.compile(r"^\s*(?:chapter\s+)?(\d{1,3})\s*[:.\-–—]?\s*", re.IGNORECASE)


@dataclass
class TrackSpec:
    no: int  # global track number within the book, 1-based
    start_ms: int
    length_ms: int
    part: int = 1
    parts: int = 1

    @property
    def file(self) -> str:
        return f"mp3/{self.no:03d}.mp3"


@dataclass
class Chapter:
    index: int  # 1-based position in the book
    title: str
    start_ms: int
    length_ms: int
    credits: bool = False
    tracks: list[TrackSpec] = field(default_factory=list)

    @property
    def end_ms(self) -> int:
        return self.start_ms + self.length_ms

    @property
    def number(self) -> int | None:
        return chapter_number(self.title)

    def to_dict(self) -> dict:
        d = asdict(self)
        for t in d["tracks"]:
            t["file"] = f"mp3/{t['no']:03d}.mp3"
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Chapter":
        tracks = [
            TrackSpec(no=t["no"], start_ms=t["start_ms"], length_ms=t["length_ms"], part=t.get("part", 1), parts=t.get("parts", 1))
            for t in d.get("tracks", [])
        ]
        return cls(index=d["index"], title=d["title"], start_ms=d["start_ms"], length_ms=d["length_ms"], credits=d.get("credits", False), tracks=tracks)


def is_credits(title: str) -> bool:
    return bool(_CREDITS_RE.match(title or ""))


def chapter_number(title: str) -> int | None:
    """"7: The Sorting Hat" -> 7, "Chapter 12" -> 12, "Epilogue" -> None."""
    m = _LEADING_NUMBER_RE.match(title or "")
    return int(m.group(1)) if m else None


def overlay_label(chapter: Chapter) -> str:
    """Short label shown over the icon on the player. Blank for credits."""
    if chapter.credits:
        return ""
    n = chapter.number
    return str(n) if n is not None else str(chapter.index)


def flatten_raw(chapters: list[dict], parent_title: str | None = None) -> list[dict]:
    """Flatten audible's optional nested chapter tree into a flat, ordered list."""
    out: list[dict] = []
    for ch in chapters or []:
        title = (ch.get("title") or "").strip()
        if parent_title and title:
            title = f"{parent_title} - {title}"
        elif parent_title:
            title = parent_title
        children = ch.get("chapters")
        if children:
            out.extend(flatten_raw(children, title or None))
        else:
            out.append({"title": title, "start_offset_ms": int(ch.get("start_offset_ms", 0)), "length_ms": int(ch.get("length_ms", 0))})
    return out


def normalize_chapters(raw: dict, skip_credits: bool = False) -> list[Chapter]:
    """Turn the whole `-chapters.json` document into ordered Chapter objects."""
    info = raw.get("content_metadata", {}).get("chapter_info", {})
    flat = flatten_raw(info.get("chapters", []))
    flat = [c for c in flat if c["length_ms"] > 0]
    flat.sort(key=lambda c: c["start_offset_ms"])

    chapters: list[Chapter] = []
    for i, c in enumerate(flat, 1):
        title = c["title"] or f"Chapter {i}"
        credits = is_credits(title)
        if skip_credits and credits:
            continue
        chapters.append(Chapter(index=len(chapters) + 1, title=title, start_ms=c["start_offset_ms"], length_ms=c["length_ms"], credits=credits))
    return chapters


def bytes_per_second(bitrate: str) -> float:
    """"64k" -> 8000.0 bytes/second."""
    s = bitrate.strip().lower()
    mult = 1
    if s.endswith("k"):
        mult, s = 1000, s[:-1]
    elif s.endswith("m"):
        mult, s = 1_000_000, s[:-1]
    return float(s) * mult / 8


def estimate_bytes(length_ms: int, bitrate: str) -> int:
    return int(length_ms / 1000 * bytes_per_second(bitrate))


def plan_tracks(chapters: list[Chapter], bitrate: str, max_track_ms: int = MAX_TRACK_MS, max_track_bytes: int = MAX_TRACK_BYTES) -> list[Chapter]:
    """Assign one or more tracks to every chapter, numbering tracks globally.

    A chapter longer than 60 minutes (or over the per-track size cap) becomes several
    equal slices that stay inside the same chapter, so the player treats them as one.
    """
    no = 0
    for ch in chapters:
        n = max(1, math.ceil(ch.length_ms / max_track_ms), math.ceil(estimate_bytes(ch.length_ms, bitrate) / max_track_bytes))
        base = ch.length_ms // n
        ch.tracks = []
        for part in range(n):
            no += 1
            start = ch.start_ms + part * base
            length = ch.length_ms - part * base if part == n - 1 else base
            ch.tracks.append(TrackSpec(no=no, start_ms=start, length_ms=length, part=part + 1, parts=n))
    return chapters


def track_title(chapter: Chapter, track: TrackSpec) -> str:
    return chapter.title if track.parts == 1 else f"{chapter.title} ({track.part}/{track.parts})"
