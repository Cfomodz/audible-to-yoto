import pytest

from audible_to_yoto.chapters import Chapter
from audible_to_yoto.icon_match import (
    assign,
    author_terms,
    book_search_terms,
    chapter_terms,
    is_front_matter,
    matchable_title,
    related,
    score,
    stem,
    stems,
    title_word_terms,
    tokens,
)
from audible_to_yoto.yotoicons import Icon

HP = stems(tokens("harry potter", keep_stopwords=True))


def ch(index, title):
    return Chapter(index=index, title=title, start_ms=0, length_ms=1000)


def icon(id_, tag1, tag2="", category="objects", downloads=100):
    return Icon(id=id_, category=category, tag1=tag1, tag2=tag2, author="someone", downloads=downloads)


@pytest.mark.parametrize("word,expected", [
    ("duelling", "duel"), ("dueling", "duel"), ("duel", "duel"),
    ("letters", "letter"), ("faces", "face"), ("boxes", "box"), ("stories", "story"),
    ("glass", "glass"), ("keys", "key"), ("vanishing", "vanish"), ("hat", "hat"),
])
def test_stem(word, expected):
    assert stem(word) == expected


def test_tokens_drop_stopwords_and_short_words():
    assert tokens("The Boy Who Lived") == ["boy", "lived"]
    assert tokens("Through the Trapdoor") == ["trapdoor"]
    assert tokens("Opening Credits") == []


def test_book_search_terms_narrow_progressively():
    terms = book_search_terms("Harry Potter and the Sorcerer's Stone, Book 1", "", "J.K. Rowling")
    assert terms[0] == "harry potter and the sorcerers stone"
    assert "harry potter" in terms
    assert terms.index("harry potter and the sorcerers stone") < terms.index("harry potter")
    assert "j k rowling" in terms


def test_book_search_terms_drop_leading_article():
    """Community tags omit the article: 'hobbit' finds far more than 'the hobbit'."""
    terms = book_search_terms("The Hobbit")
    assert terms[0] == "the hobbit"
    assert "hobbit" in terms
    assert terms.index("the hobbit") < terms.index("hobbit")
    assert "a wrinkle in time" in book_search_terms("A Wrinkle in Time")
    assert "wrinkle in time" in book_search_terms("A Wrinkle in Time")


def test_title_is_searched_before_series():
    """The Hobbit is filed under Lord of the Rings, whose icons fit none of its chapters."""
    terms = book_search_terms("The Hobbit", series_title="The Lord of the Rings")
    assert terms[0] == "the hobbit"
    assert terms.index("hobbit") < terms.index("the lord of the rings")


def test_series_is_still_offered_as_a_fallback():
    terms = book_search_terms("The Vanishing Glass", series_title="Harry Potter")
    assert "harry potter" in terms


def test_generic_terms_are_not_searched():
    """Narrowing must stop before 'book' or 'the book', which pull in unrelated icons."""
    terms = book_search_terms("The Book of Mormon Storybook for Little Saints")
    assert "book of mormon" in terms
    for junk in ("book", "the book", "the", "stories", "storybook", "the storybook"):
        assert junk not in terms


def test_chapter_terms():
    terms = chapter_terms(ch(1, "9: The Midnight Duel"))
    assert terms[0] == "midnight duel"
    assert "duel" in terms and "midnight" in terms
    assert chapter_terms(ch(1, "Opening Credits")) == []


def test_chapter_terms_include_pairs_and_single_words():
    terms = chapter_terms(ch(1, "4: Out of the Frying Pan into the Fire"))
    assert "frying pan" in terms  # adjacent pair
    assert "frying" in terms and "fire" in terms  # single words
    assert len(terms) <= 8


def test_author_terms():
    # Initials are dropped, so "J.K. Rowling" searches the surname only.
    assert author_terms("J.K. Rowling") == ["rowling"]
    assert "tolkien" in author_terms("J.R.R. Tolkien")
    assert author_terms("Madeleine L'Engle") == ["madeleine lengle", "lengle"]
    assert author_terms("Josh Sabey, Sarah Sabey")[:2] == ["josh sabey", "sabey"]
    assert author_terms("") == []


def test_title_word_terms_skip_weak_and_generic():
    assert title_word_terms("The Hobbit") == ["hobbit"]
    assert "black" not in title_word_terms("The Black Cauldron")
    assert "storybook" not in title_word_terms("The Bible Storybook")


def test_weak_single_word_never_matches():
    """"The Black Thing" must not land on a black sheep."""
    sheep = icon("30", "Black sheep", "sheep farm")
    assert score(ch(4, "4: The Black Thing"), sheep, set()) == 0
    singer = icon("31", "Ed Sheeran", "man red hair")
    assert score(ch(7, "7: The Man with Red Eyes"), singer, set()) == 0


def test_weak_word_rejected_even_for_a_book_icon():
    generic = icon("32", "dark corridor", "harry potter")
    assert score(ch(1, "1: The Dark"), generic, HP) == 0


@pytest.mark.parametrize("title", [
    "Opening Credits", "End Credits", "Introduction", "Intro", "Dedication",
    "Foreword by Madeleine L'Engle", "Afterword by Charlotte Jones Voiklis",
    "An Appreciation by Ava DuVernay", "Acknowledgements", "About the Author",
])
def test_front_matter_is_never_matched(title):
    assert is_front_matter(title)
    assert chapter_terms(ch(1, title)) == []
    assert score(ch(1, title), icon("40", "book", "library"), set()) == 0


@pytest.mark.parametrize("title", ["7: The Sorting Hat", "Quidditch", "A dream about a tree"])
def test_real_chapters_are_not_front_matter(title):
    assert not is_front_matter(title)


def test_byline_is_stripped_before_matching():
    """A person's name in a byline must not reach unrelated icons."""
    assert matchable_title("Afterword by Charlotte Jones Voiklis") == "Afterword"
    assert matchable_title("Chapter 4: The Black Thing") == "The Black Thing"
    web = icon("41", "Charlotte's Web", "spider pig")
    assert score(ch(1, "Afterword by Charlotte Jones Voiklis"), web, set()) == 0


def test_generic_word_alone_never_matches():
    shelf = icon("42", "organized bookshelf", "library bookshelf reading")
    assert score(ch(1, "A sad story"), shelf, set()) == 0


def test_weak_words_rejected_however_many_line_up():
    singer = icon("35", "Ed Sheeran", "man red hair")
    assert score(ch(7, "7: The Man with Red Eyes"), singer, set()) == 0


def test_a_strong_word_alongside_a_weak_one_still_counts():
    """"The Boy Who Lived" keeps its match: "boy" is weak but "lived" is not."""
    baby = icon("36", "baby boy", "harry potter boy who lived")
    assert score(ch(1, "1: The Boy Who Lived"), baby, HP) > 1.2


def test_related_containment_thresholds():
    assert related("trapdoor", "trap") == 0.6
    assert related("fire", "fireplace") == 0.6
    assert related("hat", "hatch") == 0.0  # too short to be meaningful
    assert related("cauldron", "cauldron") == 1.0


def test_distinctive_single_word_still_matches():
    beast = icon("33", "beast", "beauty and the beast")
    assert score(ch(11, "11: Aunt Beast"), beast, set()) > 1.2


def test_containment_links_compound_words():
    """"Trapdoor" reaches an icon tagged "trap door" once the icon also names the book."""
    trap = icon("34", "trap door", "harry potter")
    assert score(ch(16, "16: The Trapdoor"), trap, HP) > 0
    # On its own, a partial single-word hit from an unrelated icon is not enough.
    assert score(ch(16, "16: The Trapdoor"), icon("37", "trap door", "hatch"), set()) == 0


def test_score_rewards_book_icons():
    quidditch = icon("1", "harry potter", "quidditch")
    assert score(ch(11, "11: Quidditch"), quidditch, HP) > 2


def test_cross_franchise_single_word_rejected():
    """"The Midnight Duel" must not pick up a Taylor Swift icon tagged Midnights."""
    swift = icon("2", "Taylor Swift", "Midnights album")
    assert score(ch(9, "9: The Midnight Duel"), swift, HP) == 0
    bible = icon("3", "Cross stained glass", "Bible church")
    assert score(ch(2, "2: The Vanishing Glass"), bible, HP) == 0


def test_single_word_allowed_when_it_is_the_whole_icon():
    trapdoor = icon("4", "trapdoor", "hatch")
    assert score(ch(16, "16: Through the Trapdoor"), trapdoor, HP) > 1.2


def test_short_single_word_never_matches():
    aladdin = icon("5", "Aladdin Disney", "Boy Man")
    assert score(ch(17, "17: The Man with Two Faces"), aladdin, HP) == 0


def test_verb_form_matches_book_icon():
    duel = icon("6", "Duelling wizards", "Harry Potter")
    assert score(ch(9, "9: The Midnight Duel"), duel, HP) > 1.2


def test_no_shared_words_scores_zero():
    assert score(ch(1, "1: The Boy Who Lived"), icon("7", "cauldron", "harry potter"), HP) == 0


def test_chapter_with_no_usable_words_scores_zero():
    assert score(ch(1, "Opening Credits"), icon("8", "credits", "book"), HP) == 0


def test_assign_is_unique_and_prefers_best():
    chapters = [ch(1, "1: The Sorting Hat"), ch(2, "2: The Sorting Hat Returns")]
    best = icon("10", "sorting hat", "harry potter", downloads=5000)
    other = icon("11", "hat", "harry potter", downloads=10)
    result = assign(chapters, [best, other], HP)
    assert len(result) == 2
    assert {m.icon.id for m in result.values()} == {"10", "11"}
    assert result[1].icon.id == "10"  # the stronger match wins the first chapter


def test_assign_leaves_chapter_unmatched_when_pool_too_small():
    chapters = [ch(1, "1: Quidditch"), ch(2, "2: Quidditch Again")]
    result = assign(chapters, [icon("12", "quidditch", "harry potter")], HP)
    assert len(result) == 1


def test_assign_is_deterministic():
    chapters = [ch(1, "1: Quidditch"), ch(2, "2: The Sorting Hat")]
    icons = [icon("20", "quidditch", "harry potter"), icon("21", "sorting hat", "harry potter")]
    first = assign(chapters, icons, HP)
    second = assign(chapters, list(reversed(icons)), HP)
    assert {k: v.icon.id for k, v in first.items()} == {k: v.icon.id for k, v in second.items()}
