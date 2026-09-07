"""The end-to-end pipeline for one book. Every stage is skipped when its cached output is current."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import audible_lib
from .audible_lib import Book, DownloadSet
from .card import build_content_body, body_hash, card_title, readable_size, split_into_cards
from .chapters import Chapter, normalize_chapters, plan_tracks
from .config import DEFAULT_BITRATE, Config
from .convert import convert_tracks, probe_duration_ms
from .covers import prepare_cover
from .icon_gen import generate_icons, write_preview
from .state import WorkDir, load_json, save_json
from .yoto_api import YotoClient


class PipelineError(Exception):
    pass


@dataclass
class RunOptions:
    upload: bool = True
    bitrate: str = DEFAULT_BITRATE
    skip_credits: bool = False
    force_convert: bool = False
    force_icons: bool = False
    only_icons: bool = False
    preview: bool = False
    icons: str = "yotoicons"  # yotoicons | generated
    icon_tag: str | None = None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stage_download(cfg: Config, book: Book, log: Callable[[str], None]) -> DownloadSet:
    ds = audible_lib.find_download(cfg.aax_dir, book)
    if ds is None:
        audible_lib.download(book, cfg.aax_dir, log)
        ds = audible_lib.find_download(cfg.aax_dir, book)
    if ds is None:
        raise PipelineError(f"download finished but no audio file for {book.asin} was found in {cfg.aax_dir}")
    if ds.chapters_path is None or ds.cover_path is None:
        log("  audible: fetching chapter metadata and cover")
        audible_lib.fetch_extras(book, cfg.aax_dir)
        ds = audible_lib.find_download(cfg.aax_dir, book) or ds
    if ds.chapters_path is None:
        raise PipelineError(f"no chapter JSON for {book.title}; re-run `audible download --asin {book.asin} --chapter`")
    log(f"  audible: {ds.audio_path.name} ({ds.kind})")
    return ds


def stage_chapters(wd: WorkDir, ds: DownloadSet, opts: RunOptions, log: Callable[[str], None]) -> tuple[list[Chapter], bool]:
    """Returns (chapters, reconvert_needed)."""
    previous = load_json(wd.chapters_json, None)
    if previous and previous.get("bitrate") == opts.bitrate and previous.get("skip_credits") == opts.skip_credits and previous.get("source", {}).get("path") == str(ds.audio_path):
        chapters = [Chapter.from_dict(c) for c in previous["chapters"]]
        return chapters, opts.force_convert

    raw = load_json(ds.chapters_path, {})
    chapters = normalize_chapters(raw, skip_credits=opts.skip_credits)
    if not chapters:
        raise PipelineError(f"{ds.chapters_path.name} has no chapters")
    plan_tracks(chapters, opts.bitrate)
    reconvert = bool(previous)
    if reconvert:
        log("  chapters: settings changed since last run; audio will be re-encoded")
        for old in wd.mp3_dir.glob("*.mp3"):
            old.unlink()
    save_json(wd.chapters_json, {
        "asin": wd.asin,
        "source": {"path": str(ds.audio_path), "kind": ds.kind},
        "bitrate": opts.bitrate,
        "skip_credits": opts.skip_credits,
        "chapters": [c.to_dict() for c in chapters],
    })
    return chapters, reconvert or opts.force_convert


def stage_convert(wd: WorkDir, book: Book, ds: DownloadSet, chapters: list[Chapter], opts: RunOptions, force: bool, log: Callable[[str], None]) -> None:
    src = audible_lib.audio_source(ds)
    convert_tracks(src, chapters, wd.mp3_dir, opts.bitrate, album=book.title, artist=book.author or None, force=force, log=log)


def stage_icons(wd: WorkDir, book: Book, chapters: list[Chapter], opts: RunOptions, log: Callable[[str], None]) -> dict[int, Path]:
    return generate_icons(
        wd,
        chapters,
        title=book.title,
        series_title=book.series_title,
        author=book.author,
        source=opts.icons,
        tag=opts.icon_tag,
        force=opts.force_icons,
        log=log,
    )


def stage_cover(wd: WorkDir, book: Book, ds: DownloadSet, log: Callable[[str], None]) -> Path | None:
    cover = prepare_cover(wd.cover_jpg, ds.cover_path, book.cover_url or None)
    log("  cover: ready" if cover else "  cover: none found (card will have no artwork)")
    return cover


def _channels_label(value) -> str | None:
    """Yoto's card schema wants "mono"/"stereo"; the transcode report may say 1/2 or "mono"."""
    if value in (None, ""):
        return None
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("mono", "stereo"):
            return v
        value = v
    try:
        return "mono" if int(value) <= 1 else "stereo"
    except (TypeError, ValueError):
        return None


def stage_upload(wd: WorkDir, chapters: list[Chapter], cover: Path | None, client: YotoClient, log: Callable[[str], None]) -> tuple[dict[int, dict], dict[int, str | None], str | None]:
    uploads = load_json(wd.uploads_json, None) or {"audio": {}, "cover": None}

    cover_url = None
    if cover:
        sha = sha256_file(cover)
        rec = uploads.get("cover") or {}
        if rec.get("sha256") == sha and rec.get("mediaUrl"):
            cover_url = rec["mediaUrl"]
        else:
            media_id, cover_url = client.upload_cover(cover.read_bytes())
            uploads["cover"] = {"sha256": sha, "mediaId": media_id, "mediaUrl": cover_url}
            save_json(wd.uploads_json, uploads)
            log("  upload: cover")

    icons_meta = load_json(wd.icons_json, {}) or {}
    icon_entries = icons_meta.setdefault("icons", {})
    icon_ids: dict[int, str | None] = {}
    uploaded_icons = 0
    for ch in chapters:
        path = wd.icon_path(ch.index)
        entry = icon_entries.setdefault(str(ch.index), {})
        if not path.exists():
            icon_ids[ch.index] = None
            continue
        data = path.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        if entry.get("mediaId") and entry.get("uploaded_sha256") == sha:
            icon_ids[ch.index] = entry["mediaId"]
            continue
        entry["mediaId"] = client.upload_icon(data, f"{wd.asin}-{ch.index:03d}.png")
        entry["uploaded_sha256"] = sha
        icon_ids[ch.index] = entry["mediaId"]
        uploaded_icons += 1
        save_json(wd.icons_json, icons_meta)
    log(f"  upload: icons ({uploaded_icons} new, {len(chapters) - uploaded_icons} cached)")

    track_info: dict[int, dict] = {}
    total = sum(len(c.tracks) for c in chapters)
    n = 0
    uploaded_audio = 0
    for ch in chapters:
        for t in ch.tracks:
            n += 1
            path = wd.track_path(t.no)
            if not path.exists():
                raise PipelineError(f"missing {path}; run without --no-upload first")
            sha = sha256_file(path)
            rec = uploads["audio"].get(sha)
            if not rec or not rec.get("transcodedSha256"):
                log(f"    uploading {n}/{total}: {ch.title}")
                rec = client.upload_audio(path, sha, log)
                rec["file"] = f"mp3/{t.no:03d}.mp3"
                uploads["audio"][sha] = rec
                save_json(wd.uploads_json, uploads)
                uploaded_audio += 1
            duration = rec.get("duration") or probe_duration_ms(path) / 1000
            info = {
                "trackUrl": f"yoto:#{rec['transcodedSha256']}",
                "duration": int(round(duration)),
                "fileSize": int(rec.get("fileSize") or path.stat().st_size),
                "format": rec.get("format") or "mp3",
            }
            channels = _channels_label(rec.get("channels"))
            if channels:
                info["channels"] = channels
            track_info[t.no] = info
    log(f"  upload: audio ({uploaded_audio} new, {total - uploaded_audio} cached)")
    return track_info, icon_ids, cover_url


def stage_cards(wd: WorkDir, book: Book, chapters: list[Chapter], track_info: dict[int, dict], icon_ids: dict[int, str | None], cover_url: str | None, client: YotoClient, log: Callable[[str], None]) -> list[dict]:
    sizes = {no: info["fileSize"] for no, info in track_info.items()}
    groups = split_into_cards(chapters, sizes)
    state = load_json(wd.card_json, None) or {"cards": []}
    existing = {c.get("part", 1): c for c in state["cards"]}
    results: list[dict] = []
    for part, group in enumerate(groups, 1):
        title = card_title(book.title, part, len(groups))
        prev = existing.get(part) or {}
        body = build_content_body(title, group, track_info, icon_ids, cover_url=cover_url, author=book.author or None, description=book.description or None, card_id=prev.get("cardId"))
        h = body_hash(body)
        record = {
            "part": part,
            "parts": len(groups),
            "title": title,
            "chapters": [group[0].index, group[-1].index],
            "tracks": sum(len(c.tracks) for c in group),
            "bytes": body["metadata"]["media"]["fileSize"],
            "body_hash": h,
        }
        if prev.get("cardId") and prev.get("body_hash") == h:
            record.update({"cardId": prev["cardId"], "updated_at": prev.get("updated_at"), "changed": False})
        else:
            card = client.create_or_update_card(body)
            record.update({"cardId": card["cardId"], "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "changed": True})
        results.append(record)
    leftovers = [c for p, c in existing.items() if p > len(groups) and c.get("cardId")]
    state = {"cards": [{k: v for k, v in r.items() if k != "changed"} for r in results] + leftovers}
    save_json(wd.card_json, state)
    for c in leftovers:
        log(f"  note: card {c['cardId']} ({c.get('title')}) is no longer needed; delete it in the Yoto app if you like")
    return results


def run_book(cfg: Config, book: Book, opts: RunOptions, client_factory: Callable[[], YotoClient] | None = None, log: Callable[[str], None] = print) -> dict:
    log(f"\n== {book.title}  [{book.asin}]")
    wd = WorkDir(cfg.work_dir, book.asin).ensure()
    ds = stage_download(cfg, book, log)
    chapters, reconvert = stage_chapters(wd, ds, opts, log)
    n_tracks = sum(len(c.tracks) for c in chapters)
    log(f"  chapters: {len(chapters)} ({n_tracks} tracks, {sum(c.length_ms for c in chapters) / 3_600_000:.1f} h)")

    if not opts.only_icons:
        stage_convert(wd, book, ds, chapters, opts, reconvert, log)

    stage_icons(wd, book, chapters, opts, log)
    if opts.preview or opts.only_icons:
        log(f"  icons: preview at {write_preview(wd, chapters)}")
    if opts.only_icons:
        return {"asin": book.asin, "title": book.title, "cards": []}

    cover = stage_cover(wd, book, ds, log)
    if not opts.upload:
        log(f"  done (no upload). Files in {wd.path}")
        return {"asin": book.asin, "title": book.title, "cards": []}

    if client_factory is None:
        raise PipelineError("Yoto client is not configured. Run `audible-to-yoto setup`.")
    client = client_factory()
    track_info, icon_ids, cover_url = stage_upload(wd, chapters, cover, client, log)
    cards = stage_cards(wd, book, chapters, track_info, icon_ids, cover_url, client, log)
    for c in cards:
        verb = "updated" if c["changed"] else "unchanged"
        log(f"  card {c['cardId']} {verb}: {c['title']} ({c['tracks']} tracks, {readable_size(c['bytes'])})")
    return {"asin": book.asin, "title": book.title, "cards": cards}
