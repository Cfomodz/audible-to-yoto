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
from .icon_match import Match, assign, author_terms, book_search_terms, chapter_terms, stems, title_word_terms, tokens
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
    """Search progressively broader tags, keeping every icon found along the way.

    The most specific tag that returns anything names the book best, so it decides the label,
    but broader tags still contribute candidates: "the bible storybook" finds five icons drawn
    for that book, and "bible" adds two dozen more to choose from.
    """
    label = ""
    pool: list[Icon] = []
    seen: set[str] = set()
    for term in book_search_terms(title, series_title, author):
        try:
            found = client.search(term, pages=POOL_PAGES)
        except YotoIconsError as exc:
            log(f"  icons: search for {term!r} failed ({exc})")
            continue
        if found and not label:
            label = term
        for icon in found:
            if icon.id not in seen:
                seen.add(icon.id)
                pool.append(icon)
        if len(pool) >= MIN_POOL:
            break
    return label, pool


def gather_candidates(client: YotoIconsClient, chapters: list[Chapter], title: str, author: str, log: Callable[[str], None]) -> list[Icon]:
    """Search every chapter's title, word pairs, and single words, plus the book's own words.

    Community icons are tagged with what they depict, so a chapter usually finds its icon
    through one word rather than its whole title. Searches are cached, so the repeated words
    across a book cost nothing after the first look.
    """
    extra: dict[str, Icon] = {}
    terms: list[str] = list(title_word_terms(title)) + [t for t in author_terms(author) if t not in title_word_terms(title)]
    for ch in chapters:
        if ch.credits:
            continue
        for term in chapter_terms(ch):
            if term not in terms:
                terms.append(term)

    failures = 0
    for term in terms:
        try:
            for icon in client.search(term, pages=1):
                extra.setdefault(icon.id, icon)
        except YotoIconsError as exc:
            failures += 1
            if failures <= 2:
                log(f"  icons: search for {term!r} failed ({exc})")
            if failures > 10:
                log("  icons: too many failed searches, continuing with what was found")
                break
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
            client = client or YotoIconsClient(cache_dir=(cache_dir or (wd.path.parent / ".icon_cache")) / "searches")
            matches = _lookup(client, chapters, title, series_title, author, tag, meta, log)
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
        try:
            term, pool = find_book_pool(client, title, series_title, author, log)
        except YotoIconsError as exc:
            log(f"  icons: yotoicons.com search failed ({exc}); using generated icons")
            return {}

    if pool:
        log(f"  icons: yotoicons.com tag {term!r} returned {len(pool)} icons")
    else:
        log("  icons: nothing on yotoicons.com under this book's name")

    # Icons tagged with the author belong to this book's world too, so treat the author's name
    # like the book's name: it earns the relevance bonus but is not itself a content match.
    book_stems = stems(tokens(term, keep_stopwords=True)) if term else set()
    for author_term in author_terms(author):
        book_stems |= stems(tokens(author_term, keep_stopwords=True))
    extra = gather_candidates(client, chapters, title, author, log)
    candidates = pool + [i for i in extra if i.id not in {p.id for p in pool}]
    if not candidates:
        log("  icons: no candidates found at all; using generated icons")
        return {}
    log(f"  icons: {len(candidates)} candidate icons after searching chapter titles and words")

    matches = assign(chapters, candidates, book_stems)
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
