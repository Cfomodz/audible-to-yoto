"""Pure card logic: split a book into Yoto-sized cards and build the /content body."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .chapters import Chapter, overlay_label, track_title


@dataclass(frozen=True)
class Limits:
    max_tracks: int = 100  # Yoto: 100 tracks per card
    max_card_bytes: int = 480 * 1024 * 1024  # Yoto: 500 MB per card, keep headroom


class CardLimitError(Exception):
    pass


def split_into_cards(chapters: list[Chapter], sizes: dict[int, int], limits: Limits = Limits()) -> list[list[Chapter]]:
    """Greedy split. Chapters are never divided across cards.

    `sizes` maps track number -> transcoded file size in bytes.
    """
    cards: list[list[Chapter]] = []
    current: list[Chapter] = []
    tracks = 0
    total = 0
    for ch in chapters:
        ch_tracks = len(ch.tracks)
        ch_bytes = sum(sizes.get(t.no, 0) for t in ch.tracks)
        if ch_tracks > limits.max_tracks or ch_bytes > limits.max_card_bytes:
            raise CardLimitError(f"Chapter {ch.index} '{ch.title}' alone exceeds a card limit ({ch_tracks} tracks, {readable_size(ch_bytes)})")
        if current and (tracks + ch_tracks > limits.max_tracks or total + ch_bytes > limits.max_card_bytes):
            cards.append(current)
            current, tracks, total = [], 0, 0
        current.append(ch)
        tracks += ch_tracks
        total += ch_bytes
    if current:
        cards.append(current)
    return cards


def card_title(title: str, part: int, parts: int) -> str:
    return title if parts == 1 else f"{title} (Part {part} of {parts})"


def readable_size(n: int) -> str:
    if n >= 1024 * 1024 * 1024:
        return f"{n / (1024 ** 3):.1f} GB"
    if n >= 1024 * 1024:
        return f"{n / (1024 ** 2):.0f} MB"
    return f"{n / 1024:.0f} KB"


def _key(i: int, width: int) -> str:
    return f"{i:0{width}d}"


def build_content_body(
    title: str,
    chapters: list[Chapter],
    track_info: dict[int, dict],
    icon_ids: dict[int, str | None],
    cover_url: str | None = None,
    author: str | None = None,
    description: str | None = None,
    card_id: str | None = None,
) -> dict:
    """Build the JSON for POST /content.

    `track_info[no]` = {"trackUrl", "duration", "fileSize", "channels", "format"} from the transcode.
    `icon_ids[chapter.index]` = Yoto mediaId of the chapter icon (or None).
    """
    width = max(2, len(str(len(chapters))))
    out_chapters = []
    total_duration = 0
    total_bytes = 0
    for ci, ch in enumerate(chapters, 1):
        label = overlay_label(ch)
        icon = f"yoto:#{icon_ids[ch.index]}" if icon_ids.get(ch.index) else None
        display = {"icon16x16": icon} if icon else {}
        tracks = []
        for ti, t in enumerate(ch.tracks, 1):
            info = track_info[t.no]
            total_duration += info["duration"]
            total_bytes += info["fileSize"]
            track = {
                "key": _key(ti, 2),
                "title": track_title(ch, t),
                "trackUrl": info["trackUrl"],
                "type": "audio",
                "format": info.get("format", "mp3"),
                "duration": info["duration"],
                "fileSize": info["fileSize"],
                "overlayLabel": label,
            }
            if info.get("channels") is not None:
                track["channels"] = info["channels"]
            if display:
                track["display"] = dict(display)
            tracks.append(track)
        chapter = {
            "key": _key(ci, width),
            "title": ch.title,
            "overlayLabel": label,
            "duration": sum(track_info[t.no]["duration"] for t in ch.tracks),
            "fileSize": sum(track_info[t.no]["fileSize"] for t in ch.tracks),
            "tracks": tracks,
        }
        if display:
            chapter["display"] = display
        out_chapters.append(chapter)

    metadata: dict = {
        "category": "stories",
        "media": {"duration": total_duration, "fileSize": total_bytes, "readableFileSize": round(total_bytes / (1024 * 1024), 1)},
    }
    if author:
        metadata["author"] = author
    if description:
        metadata["description"] = description[:1000]
    if cover_url:
        metadata["cover"] = {"imageL": cover_url}

    body: dict = {"title": title[:140], "content": {"chapters": out_chapters}, "metadata": metadata}
    if card_id:
        body["cardId"] = card_id
    return body


def body_hash(body: dict) -> str:
    canonical = json.dumps({k: v for k, v in body.items() if k != "cardId"}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
