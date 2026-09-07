"""ffmpeg: decrypt AAX/AAXC and cut chapter tracks to mono MP3, in parallel."""

from __future__ import annotations

import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .chapters import Chapter, TrackSpec, track_title


class ConversionError(Exception):
    pass


@dataclass
class AudioSource:
    path: Path
    kind: str  # "aax" or "aaxc"
    activation_bytes: str | None = None
    key: str | None = None
    iv: str | None = None

    def decrypt_args(self) -> list[str]:
        if self.kind == "aaxc":
            if not (self.key and self.iv):
                raise ConversionError("AAXC file needs key and iv from its .voucher")
            return ["-audible_key", self.key, "-audible_iv", self.iv]
        if not self.activation_bytes:
            raise ConversionError("AAX file needs activation bytes (audible activation-bytes)")
        return ["-activation_bytes", self.activation_bytes]


def build_ffmpeg_cmd(src: AudioSource, start_ms: int, length_ms: int, out_path: Path, bitrate: str, metadata: dict[str, str] | None = None) -> list[str]:
    """Input seeking (-ss/-t before -i) so each track decodes only its own slice."""
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
        *src.decrypt_args(),
        "-ss", f"{start_ms / 1000:.3f}",
        "-t", f"{length_ms / 1000:.3f}",
        "-i", str(src.path),
        "-vn", "-map_metadata", "-1",
        "-c:a", "libmp3lame", "-b:a", bitrate, "-ac", "1",
        "-id3v2_version", "3",
    ]
    for k, v in (metadata or {}).items():
        cmd += ["-metadata", f"{k}={v}"]
    cmd += ["-f", "mp3", str(out_path)]
    return cmd


def _convert_one(src: AudioSource, track: TrackSpec, out: Path, bitrate: str, metadata: dict[str, str]) -> Path:
    tmp = out.with_name(out.name + ".part")
    cmd = build_ffmpeg_cmd(src, track.start_ms, track.length_ms, tmp, bitrate, metadata)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not tmp.exists() or tmp.stat().st_size == 0:
        tmp.unlink(missing_ok=True)
        raise ConversionError(f"ffmpeg failed on track {track.no}: {proc.stderr.strip()[-400:]}")
    os.replace(tmp, out)
    return out


def convert_tracks(
    src: AudioSource,
    chapters: list[Chapter],
    mp3_dir: Path,
    bitrate: str,
    album: str,
    artist: str | None = None,
    force: bool = False,
    workers: int | None = None,
    log: Callable[[str], None] = print,
) -> int:
    """Encode every planned track that is missing. Returns how many were (re)encoded."""
    mp3_dir.mkdir(parents=True, exist_ok=True)
    total = sum(len(c.tracks) for c in chapters)
    jobs: list[tuple[Chapter, TrackSpec, Path, dict[str, str]]] = []
    for ch in chapters:
        for t in ch.tracks:
            out = mp3_dir / f"{t.no:03d}.mp3"
            if out.exists() and out.stat().st_size > 0 and not force:
                continue
            meta = {"title": track_title(ch, t), "track": f"{t.no}/{total}", "album": album}
            if artist:
                meta["artist"] = artist
            jobs.append((ch, t, out, meta))
    if not jobs:
        log(f"  audio: all {total} tracks already converted")
        return 0

    log(f"  audio: encoding {len(jobs)} of {total} tracks at {bitrate} mono ({workers or os.cpu_count()} parallel)")
    done = 0
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=workers or os.cpu_count() or 2) as pool:
        futures = {pool.submit(_convert_one, src, t, out, bitrate, meta): (ch, t) for ch, t, out, meta in jobs}
        for fut in as_completed(futures):
            ch, t = futures[fut]
            try:
                fut.result()
                done += 1
                log(f"    [{done}/{len(jobs)}] {track_title(ch, t)}")
            except ConversionError as exc:
                errors.append(str(exc))
    if errors:
        raise ConversionError("; ".join(errors[:3]))
    return done


def probe_duration_ms(path: Path) -> int:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise ConversionError(f"ffprobe failed: {proc.stderr.strip()[-200:]}")
    return int(float(json.loads(proc.stdout)["format"]["duration"]) * 1000)
