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

# Words too generic to identify a book on their own.
GENERIC_TITLE_WORDS = {
    "book", "story", "stories", "storybook", "tale", "tales", "collection", "complete",
    "adventures", "adventure", "series", "anthology", "edition", "audio", "kids", "children",
}

# Descriptors that carry too little meaning to justify a match on their own: "The Black Thing"
# must not land on a black sheep, nor "The Man with Red Eyes" on a red-haired singer.
WEAK_WORDS = {
    "black", "white", "red", "blue", "green", "yellow", "brown", "grey", "gray", "golden", "gold",
    "silver", "dark", "light", "big", "little", "great", "small", "old", "new", "young", "long",
    "short", "happy", "sad", "good", "bad", "first", "last", "next", "thing", "things", "man",
    "woman", "boy", "girl", "men", "women", "people", "day", "night", "morning", "time", "way",
    "place", "world", "home", "house", "room", "back", "hand", "eye", "eyes", "face", "head",
    "super", "very", "really", "another", "again", "more", "most", "best", "whole", "full",
    "half", "same", "different", "special", "own", "part", "end", "beginning", "start",
}

# A match needs real signal, not one incidental word.
MIN_SCORE = 1.2


# Front and back matter: nothing in these titles describes a scene worth an icon.
_FRONT_MATTER_RE = re.compile(
    r"^\s*(?:a|an|the)?\s*(?:opening|end|closing)?\s*(?:credits|introduction|intro|dedication|"
    r"foreword|forward|preface|afterword|acknowledg\w*|appreciation|about the author|"
    r"author.s note|a note from[\w\s]*|copyright|title page|contents)\s*[:.]?\s*$",
    re.IGNORECASE,
)
_BYLINE_RE = re.compile(r"\s+by\s+.+$", re.IGNORECASE)
# "9: The Sorting Hat", "Chapter 4: The Black Thing", "1. A family from Jerusalem"
_LEADING_CHAPTER_RE = re.compile(r"^\s*(?:chapter|part|section|book)?\s*\d+\s*[:.\-–—]?\s*", re.IGNORECASE)


def is_front_matter(title: str) -> bool:
    """True for credits, intros, dedications and the like, which get a generated icon."""
    stripped = _BYLINE_RE.sub("", title or "").strip()
    return bool(_FRONT_MATTER_RE.match(stripped) or _FRONT_MATTER_RE.match(title or ""))


def matchable_title(title: str) -> str:
    """The part of a chapter title worth matching on.

    Drops the leading number and any byline, so "Afterword by Charlotte Jones" cannot reach
    icons of Charlotte's Web or Junie B. Jones through a person's name.
    """
    without_number = _LEADING_CHAPTER_RE.sub("", title or "")
    return _BYLINE_RE.sub("", without_number).strip()


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
        # Tags rarely carry the article: "hobbit" finds four times as much as "the hobbit".
        bare = re.sub(r"^(a|an|the)\s+", "", value).strip()
        if bare and bare != value and bare not in candidates:
            candidates.append(bare)

    cleaned = normalize(title)
    cleaned = re.sub(r"\b(book|volume|vol|part)\s+\d+\b", "", cleaned).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    # Drop a trailing subtitle: "Title, A Story" / "Title: A Story"
    head = normalize(re.split(r"[:,]", title)[0])
    head = re.sub(r"\b(book|volume|vol|part)\s+\d+\b", "", head).strip()

    add(head)
    add(cleaned)

    words = [w for w in head.split() if w]
    for cut in range(len(words) - 1, 1, -1):
        add(" ".join(words[:cut]))
    if len(words) >= 2:
        add(" ".join(words[:2]))
    # The series comes after the title. "The Hobbit" is filed under the Lord of the Rings
    # series, whose icons match none of its chapters, while "hobbit" matches plenty.
    if series_title:
        add(normalize(series_title))
    if author:
        add(normalize(author))
    return [c for c in candidates if is_useful_term(c)]


def is_useful_term(term: str) -> bool:
    """Reject tags too generic to identify a book, such as "book" or "the book"."""
    if len(term) < 3:
        return False
    words = [w for w in term.split() if w not in ("a", "an", "the")]
    if not words:
        return False
    return not all(w in STOPWORDS or w in GENERIC_TITLE_WORDS for w in words)


def chapter_terms(ch: Chapter, max_terms: int = 8) -> list[str]:
    """Search phrases for one chapter: the whole title, each adjacent pair, then each word.

    Community icons are tagged with the thing drawn, not with chapter titles, so the single
    words are what usually find something: "Riddles in the Dark" hits on "riddle".
    """
    if ch.credits or is_front_matter(ch.title):
        return []
    words = tokens(matchable_title(ch.title))
    if not words:
        return []
    out: list[str] = [" ".join(words)]
    for a, b in zip(words, words[1:]):
        out.append(f"{a} {b}")
    # Longest words first: they are the most distinctive.
    out.extend(sorted(words, key=len, reverse=True))
    seen: list[str] = []
    for t in out:
        if t and t not in seen:
            seen.append(t)
    return seen[:max_terms]


def title_word_terms(title: str, max_terms: int = 4) -> list[str]:
    """Single distinctive words from the book title, e.g. 'hobbit' from 'The Hobbit'."""
    words = [w for w in tokens(title) if w not in GENERIC_TITLE_WORDS and w not in WEAK_WORDS]
    return sorted(set(words), key=len, reverse=True)[:max_terms]


def author_terms(author: str, max_terms: int = 3) -> list[str]:
    """Search terms from the author: the full name and the surname.

    Uploaders often tag by author, so "tolkien" finds icons for a book whose own title
    turns up nothing.
    """
    if not author:
        return []
    out: list[str] = []
    for name in re.split(r"\s*[,;&]\s*| and ", author):
        cleaned = normalize(name)
        parts = [p for p in cleaned.split() if len(p) > 1]
        if not parts:
            continue
        if len(parts) > 1 and cleaned not in out:
            out.append(cleaned)
        surname = parts[-1]
        if len(surname) >= 4 and surname not in out:
            out.append(surname)
    return out[:max_terms]


def related(a: str, b: str) -> float:
    """Strength of the link between two stems: 1.0 identical, 0.6 one inside the other, else 0.

    Containment catches the compound words community tags are full of: a chapter about a
    "trapdoor" and an icon tagged "trap door hatch", or "fire" and "fireplace".
    """
    if a == b:
        return 1.0
    short, long = sorted((a, b), key=len)
    if len(short) >= 4 and len(long) >= 6 and short in long:
        return 0.6
    return 0.0


def shared_words(chapter_stems: set[str], icon_stems: set[str], book_stems: set[str]) -> dict[str, float]:
    """Chapter words the icon covers, with how strongly, ignoring words that name the book."""
    out: dict[str, float] = {}
    for c in chapter_stems - book_stems:
        best = max((related(c, i) for i in icon_stems - book_stems), default=0.0)
        if best:
            out[c] = best
    return out


def score(ch: Chapter, icon: Icon, book_stems: set[str]) -> float:
    """How well an icon fits a chapter. Higher is better; 0 means no signal."""
    if ch.credits or is_front_matter(ch.title):
        return 0.0
    chapter_words = tokens(matchable_title(ch.title))
    if not chapter_words:
        return 0.0
    chapter_stems = stems(chapter_words)

    icon_tag_words = tokens(f"{icon.tag1} {icon.tag2}")
    icon_stems = stems(icon_tag_words)
    if not icon_stems:
        return 0.0

    shared = shared_words(chapter_stems, icon_stems, book_stems)
    if not shared:
        return 0.0

    # How much of the icon's own meaning the shared words account for.
    own_stems = icon_stems - book_stems
    focus = sum(shared.values()) / max(1, len(own_stems) or 1)

    # An icon from another franchise needs to match two words, or to be *about* the one word it
    # shares. Otherwise "The Midnight Duel" picks up a Taylor Swift icon tagged "Midnights",
    # where "midnight" is one word among several.
    # Matching only on weak or generic words is noise however many of them line up: "The Man
    # with Red Eyes" shares "man" and "red" with a picture of a red-haired singer.
    if all(word in WEAK_WORDS or word in GENERIC_TITLE_WORDS for word in shared):
        return 0.0

    mentions_book = bool(book_stems and (icon_stems & book_stems))
    if len(shared) < 2:
        only, strength = next(iter(shared.items()))
        if not mentions_book and (len(only) < 4 or focus < 0.5 or strength < 1.0):
            return 0.0

    value = 0.0
    for word, strength in shared.items():
        # A rarer, longer word is stronger evidence than a short common one.
        value += strength * (1.0 + min(len(word), 10) / 20.0)

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
