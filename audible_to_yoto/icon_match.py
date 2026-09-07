"""Pure matching: pick one unique yotoicons icon per chapter from candidate pools.

Two inputs decide everything: the search tag derived from the book title, and the overlap
between a chapter's title and an icon's tags. No network and no model calls happen here.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from .chapters import Chapter
from .yotoicons import Icon

STOPWORDS = {
    "a", "an", "and", "the", "of", "in", "on", "at", "to", "from", "for", "with", "by", "into",
    "through", "over", "under", "about", "after", "before", "between", "against", "upon",
    "is", "was", "it", "its", "his", "her", "their", "he", "she", "they", "who", "that", "this",
    "part", "chapter", "book", "vol", "volume", "unabridged", "novel", "audiobook", "credits",
    "opening", "end", "closing", "prologue", "epilogue", "introduction", "one", "two", "three",
}

# A match needs real signal, not one incidental word.
MIN_SCORE = 1.2


def normalize(text: str) -> str:
    text = text.lower().replace("&", " and ")
    text = re.sub(r"[’']", "", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def tokens(text: str, keep_stopwords: bool = False) -> list[str]:
    words = normalize(text).split()
    if keep_stopwords:
        return words
    return [w for w in words if w not in STOPWORDS and len(w) > 2]


def singular(word: str) -> str:
    """Light plural stripping: letters -> letter, faces -> face, boxes -> box, stories -> story."""
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("es") and len(word) > 3:
        root = word[:-2]
        if root.endswith(("s", "x", "z", "ch", "sh")):
            return root
        return word[:-1]
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]
    return word


def stem(word: str) -> str:
    """Fold plurals and verb endings so 'duel' matches an icon tagged 'duelling'."""
    for suffix in ("ing", "ed"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            root = word[: -len(suffix)]
            if len(root) >= 4 and root[-1] == root[-2] and root[-1] not in "aeiou":
                root = root[:-1]  # duelling -> duell -> duel
            return singular(root)
    return singular(word)


def stems(words: list[str]) -> set[str]:
    return {stem(w) for w in words}


def book_search_terms(title: str, series_title: str = "", author: str = "") -> list[str]:
    """Candidate yotoicons tags for a book, most specific first.

    "Harry Potter and the Sorcerer's Stone, Book 1" yields
    ["harry potter and the sorcerers stone", "harry potter and the sorcerers", ..., "harry potter"].
    """
    candidates: list[str] = []

    def add(value: str) -> None:
        value = value.strip()
        if value and value not in candidates:
            candidates.append(value)

    cleaned = normalize(title)
    cleaned = re.sub(r"\b(book|volume|vol|part)\s+\d+\b", "", cleaned).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    # Drop a trailing subtitle: "Title, A Story" / "Title: A Story"
    head = normalize(re.split(r"[:,]", title)[0])
    head = re.sub(r"\b(book|volume|vol|part)\s+\d+\b", "", head).strip()

    if series_title:
        add(normalize(series_title))
    add(head)
    add(cleaned)

    words = [w for w in head.split() if w]
    for cut in range(len(words) - 1, 1, -1):
        add(" ".join(words[:cut]))
    if len(words) >= 2:
        add(" ".join(words[:2]))
    if author:
        add(normalize(author))
    return [c for c in candidates if len(c) >= 3]


def chapter_terms(ch: Chapter) -> list[str]:
    """Search phrases for a single chapter, most specific first."""
    title = re.sub(r"^\s*\d+\s*[:.\-–—]\s*", "", ch.title)
    words = tokens(title)
    if not words:
        return []
    out = [" ".join(words)]
    if len(words) > 2:
        out.append(" ".join(words[:2]))
        out.append(" ".join(words[-2:]))
    for w in words:
        if w not in out:
            out.append(w)
    seen: list[str] = []
    for t in out:
        if t and t not in seen:
            seen.append(t)
    return seen[:4]


def score(ch: Chapter, icon: Icon, book_stems: set[str]) -> float:
    """How well an icon fits a chapter. Higher is better; 0 means no signal."""
    chapter_words = tokens(re.sub(r"^\s*\d+\s*[:.\-–—]\s*", "", ch.title))
    if not chapter_words:
        return 0.0
    chapter_stems = stems(chapter_words)

    icon_tag_words = tokens(f"{icon.tag1} {icon.tag2}")
    icon_stems = stems(icon_tag_words)
    if not icon_stems:
        return 0.0

    # Words the icon shares with the chapter, ignoring words that merely name the book.
    shared = (chapter_stems & icon_stems) - book_stems
    if not shared:
        return 0.0

    # How much of the icon's own meaning the shared words account for.
    own_stems = icon_stems - book_stems
    focus = len(shared) / max(1, len(own_stems) or 1)

    # An icon from another franchise needs to match two words, or to be *about* the one
    # distinctive word it shares. Otherwise "The Midnight Duel" picks up a Taylor Swift icon
    # tagged "Midnights", where "midnight" is one word among several.
    mentions_book = bool(book_stems and (icon_stems & book_stems))
    if not mentions_book and len(shared) < 2:
        only = next(iter(shared))
        if len(only) < 6 or focus < 0.5:
            return 0.0

    value = 0.0
    for word in shared:
        # A rarer, longer word is stronger evidence than a short common one.
        value += 1.0 + min(len(word), 10) / 20.0

    # Reward icons that spend most of their tags on the matched idea.
    value *= 0.75 + 0.5 * min(focus, 1.0)

    # Prefer icons that also name this book, and popular ones, but only as tiebreakers.
    if mentions_book:
        value += 0.35
    value += min(math.log10(icon.downloads + 1) / 10.0, 0.3)
    return value


@dataclass
class Match:
    chapter_index: int
    icon: Icon
    score: float


def assign(chapters: list[Chapter], icons: list[Icon], book_stems: set[str], min_score: float = MIN_SCORE) -> dict[int, Match]:
    """Give each chapter its own icon: best scoring pairs first, no icon used twice."""
    pairs: list[tuple[float, int, str, Chapter, Icon]] = []
    for ch in chapters:
        for icon in icons:
            s = score(ch, icon, book_stems)
            if s >= min_score:
                pairs.append((s, ch.index, icon.id, ch, icon))
    # Sort by score, then deterministically by chapter and icon id.
    pairs.sort(key=lambda p: (-p[0], p[1], int(p[2])))

    taken_chapters: set[int] = set()
    taken_icons: set[str] = set()
    out: dict[int, Match] = {}
    for s, ch_index, icon_id, ch, icon in pairs:
        if ch_index in taken_chapters or icon_id in taken_icons:
            continue
        taken_chapters.add(ch_index)
        taken_icons.add(icon_id)
        out[ch_index] = Match(chapter_index=ch_index, icon=icon, score=round(s, 3))
    return out
