import pytest

from audible_to_yoto.chapters import Chapter
from audible_to_yoto.icon_match import assign, book_search_terms, chapter_terms, score, stem, stems, tokens
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


def test_book_search_terms_use_series_first():
    terms = book_search_terms("The Vanishing Glass", series_title="Harry Potter")
    assert terms[0] == "harry potter"


def test_chapter_terms():
    assert chapter_terms(ch(1, "9: The Midnight Duel"))[0] == "midnight duel"
    assert "duel" in chapter_terms(ch(1, "9: The Midnight Duel"))
    assert chapter_terms(ch(1, "Opening Credits")) == []


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
