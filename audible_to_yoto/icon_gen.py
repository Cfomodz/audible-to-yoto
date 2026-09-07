"""Chapter icons.

Default source is yotoicons.com: search the community library for the book, then give each
chapter the icon whose tags best match its title, never reusing an icon within a book. Chapters
with no good match fall back to a generated icon (pixel digits, or a book glyph for credits).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable

from PIL import Image

from .chapters import Chapter
from .icon_match import Match, assign, book_search_terms, chapter_terms, stems, tokens
from .pixel import book_icon, contact_sheet, normalize_icon, number_icon, png_bytes
from .state import WorkDir, load_json, save_json
from .yotoicons import Icon, YotoIconsClient, YotoIconsError, download_cached

MIN_POOL = 8  # a book tag with at least this many icons is specific enough to use
POOL_PAGES = 4  # up to 104 icons for the book itself


def lookup_hash(chapters: list[Chapter], title: str, series_title: str, author: str, tag: str | None) -> str:
    """Identifies one search: the same book, chapters, and tag never needs searching twice."""
    payload = "\x1f".join([title, series_title, author, tag or "", *(f"{c.index}\x1e{c.title}" for c in chapters)])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def chapter_icon(ch: Chapter) -> Image.Image:
    """The generated fallback drawing for a chapter."""
    if ch.credits:
        return book_icon(closed=any(w in ch.title.lower() for w in ("end", "closing")))
    return number_icon(ch.number or ch.index)


def find_book_pool(client: YotoIconsClient, title: str, series_title: str = "", author: str = "", log: Callable[[str], None] = print) -> tuple[str, list[Icon]]:
    """Search progressively broader tags until one returns a usable pool of icons."""
    best_term, best_pool = "", []
    for term in book_search_terms(title, series_title, author):
        try:
            pool = client.search(term, pages=POOL_PAGES)
        except YotoIconsError as exc:
            log(f"  icons: search for {term!r} failed ({exc})")
            continue
        if len(pool) > len(best_pool):
            best_term, best_pool = term, pool
        if len(pool) >= MIN_POOL:
            break
    return best_term, best_pool


def gather_candidates(client: YotoIconsClient, chapters: list[Chapter], matched: dict[int, Match], book_stems: set[str], log: Callable[[str], None]) -> list[Icon]:
    """Second pass: search the chapter's own words for chapters the book pool could not cover."""
    extra: dict[str, Icon] = {}
    for ch in chapters:
        if ch.index in matched or ch.credits:
            continue
        # Try every phrasing, not just the first that returns anything: the whole title may hit
        # an unrelated icon while a single key word finds the right one.
        for term in chapter_terms(ch):
            try:
                found = client.search(term, pages=1)
            except YotoIconsError as exc:
                log(f"  icons: search for {term!r} failed ({exc})")
                break
            for icon in found:
                extra.setdefault(icon.id, icon)
    return list(extra.values())


def generate_icons(
    wd: WorkDir,
    chapters: list[Chapter],
    title: str = "",
    series_title: str = "",
    author: str = "",
    source: str = "yotoicons",
    tag: str | None = None,
    cache_dir: Path | None = None,
    force: bool = False,
    client: YotoIconsClient | None = None,
    log: Callable[[str], None] = print,
) -> dict[int, Path]:
    """Ensure every chapter has icons/NNN.png.

    Icons this tool wrote are refreshed when the chapter or the match changes. An icon the user
    supplied or edited is left alone; `force` re-matches and overwrites everything.
    """
    wd.icons_dir.mkdir(parents=True, exist_ok=True)
    meta = load_json(wd.icons_json, {}) or {}
    icons: dict[str, dict] = meta.setdefault("icons", {})
    if force:
        meta.pop("search_tag", None)
        meta.pop("lookup_hash", None)

    matches: dict[int, Match] = {}
    if source == "yotoicons":
        # Search once per (book, chapter list, tag). Chapters that legitimately have no match
        # must not trigger a fresh search on every run.
        want = lookup_hash(chapters, title, series_title, author, tag)
        if force or meta.get("lookup_hash") != want:
            matches = _lookup(client or YotoIconsClient(), chapters, title, series_title, author, tag, meta, log)
            meta["lookup_hash"] = want
        else:
            found = sum(1 for c in chapters if icons.get(str(c.index), {}).get("yotoicon"))
            log(f"  icons: reusing {found} icon(s) matched earlier on yotoicons.com")

    written, kept_custom, from_library = 0, 0, 0
    client = client or YotoIconsClient()
    for ch in chapters:
        path = wd.icon_path(ch.index)
        entry = icons.setdefault(str(ch.index), {})
        match = matches.get(ch.index)

        if match is not None:
            try:
                raw = download_cached(client, match.icon, cache_dir or (wd.path.parent / ".icon_cache"))
                wanted = normalize_icon(raw)
                entry_source = {"yotoicon": match.icon.to_dict(), "match_score": match.score, "credit": match.icon.credit, "source": "yotoicons"}
            except (YotoIconsError, OSError, ValueError) as exc:
                log(f"  icons: could not use the icon for {ch.title!r} ({exc}); using a generated one")
                wanted, entry_source = png_bytes(chapter_icon(ch)), {"source": "generated"}
        elif entry.get("yotoicon") and not force:
            # Keep the icon matched on an earlier run.
            wanted, entry_source = None, {}
        else:
            wanted, entry_source = png_bytes(chapter_icon(ch)), {"source": "generated"}
            entry.pop("yotoicon", None)
            entry.pop("credit", None)
            entry.pop("match_score", None)

        on_disk = path.read_bytes() if path.exists() else None
        on_disk_sha = hashlib.sha256(on_disk).hexdigest() if on_disk is not None else None
        ours = entry.get("generated_sha256")
        is_ours = on_disk_sha is not None and ours is not None and on_disk_sha == ours

        if wanted is None:
            if on_disk is None:
                wanted = png_bytes(chapter_icon(ch))
                entry_source = {"source": "generated"}
            else:
                entry["png_sha256"] = on_disk_sha
                if entry.get("source") == "yotoicons":
                    from_library += 1
                continue

        wanted_sha = hashlib.sha256(wanted).hexdigest()
        if on_disk is None or force or (is_ours and on_disk_sha != wanted_sha):
            path.write_bytes(wanted)
            entry.update(entry_source)
            entry["generated_sha256"] = wanted_sha
            entry["png_sha256"] = wanted_sha
            written += 1
            if entry.get("source") == "yotoicons":
                from_library += 1
        else:
            entry["png_sha256"] = on_disk_sha
            if on_disk_sha != ours:
                kept_custom += 1
            elif entry.get("source") == "yotoicons":
                from_library += 1

    keep = {str(ch.index) for ch in chapters}
    for gone in [k for k in icons if k not in keep]:
        del icons[gone]

    save_json(wd.icons_json, meta)
    parts = [f"{len(chapters)} chapter icons ready"]
    if from_library:
        parts.append(f"{from_library} from yotoicons.com")
    generated = len(chapters) - from_library - kept_custom
    if generated > 0:
        parts.append(f"{generated} generated")
    if kept_custom:
        parts.append(f"{kept_custom} of your own kept")
    log("  icons: " + ", ".join(parts))
    return {ch.index: wd.icon_path(ch.index) for ch in chapters}


def _lookup(client: YotoIconsClient, chapters: list[Chapter], title: str, series_title: str, author: str, tag: str | None, meta: dict, log: Callable[[str], None]) -> dict[int, Match]:
    if tag:
        try:
            pool = client.search(tag, pages=POOL_PAGES)
        except YotoIconsError as exc:
            log(f"  icons: yotoicons.com search failed ({exc}); using generated icons")
            return {}
        term = tag
    else:
        term, pool = find_book_pool(client, title, series_title, author, log)

    if not pool:
        log("  icons: nothing on yotoicons.com for this book; using generated icons")
        return {}
    log(f"  icons: yotoicons.com tag {term!r} returned {len(pool)} icons")

    book_stems = stems(tokens(term, keep_stopwords=True))
    matches = assign(chapters, pool, book_stems)
    extra = gather_candidates(client, chapters, matches, book_stems, log)
    if extra:
        matches = assign(chapters, pool + extra, book_stems)
    meta["search_tag"] = term
    unmatched = [ch for ch in chapters if ch.index not in matches]
    if unmatched:
        log(f"  icons: {len(unmatched)} chapter(s) had no good match, generating those")
    return matches


def write_preview(wd: WorkDir, chapters: list[Chapter]) -> Path:
    meta = load_json(wd.icons_json, {}) or {}
    items = []
    for ch in chapters:
        path = wd.icon_path(ch.index)
        if not path.exists():
            continue
        entry = meta.get("icons", {}).get(str(ch.index), {})
        icon_info = entry.get("yotoicon") or {}
        label = f"{ch.index}. {ch.title}"
        if icon_info:
            label += f" [{icon_info.get('tag1', '')}]"
        items.append((label, Image.open(path)))
    contact_sheet(items).save(wd.preview_png, "PNG")
    return wd.preview_png


def credits(wd: WorkDir) -> list[str]:
    """Attribution lines for every yotoicons icon used, for the user to credit uploaders."""
    meta = load_json(wd.icons_json, {}) or {}
    out = []
    for key in sorted(meta.get("icons", {}), key=lambda k: int(k)):
        credit = meta["icons"][key].get("credit")
        if credit:
            out.append(f"chapter {key}: {credit}")
    return out
