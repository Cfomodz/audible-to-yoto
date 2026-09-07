from audible_to_yoto.icon_gen import find_book_pool
from audible_to_yoto.yotoicons import Icon, YotoIconsError


def icon(id_, tag1, tag2=""):
    return Icon(id=id_, category="objects", tag1=tag1, tag2=tag2, author="a", downloads=1)


class Stub:
    def __init__(self, results, failing=()):
        self.results = results
        self.failing = set(failing)
        self.searches = []

    def search(self, tag, pages=1):
        self.searches.append(tag)
        if tag in self.failing:
            raise YotoIconsError("boom")
        return list(self.results.get(tag, []))


def test_specific_tag_labels_the_pool_and_broader_tags_add_candidates():
    stub = Stub({
        "the bible storybook": [icon(str(i), "scene", "the bible storybook") for i in range(5)],
        "bible storybook": [icon("5", "ark", "bible storybook")],
        "the bible": [icon("6", "jesus", "bible"), icon("7", "psalm", "bible")],
    })
    label, pool = find_book_pool(stub, "The Bible Storybook", log=lambda m: None)
    assert label == "the bible storybook"  # the most specific hit names the book
    assert len(pool) >= 8
    assert {i.id for i in pool} >= {"0", "5", "6"}


def test_stops_once_the_pool_is_big_enough():
    stub = Stub({"harry potter and the sorcerers stone": [icon(str(i), f"t{i}") for i in range(10)]})
    label, pool = find_book_pool(stub, "Harry Potter and the Sorcerer's Stone, Book 1", log=lambda m: None)
    assert label == "harry potter and the sorcerers stone"
    assert len(stub.searches) == 1  # no need to broaden


def test_article_free_variant_is_tried():
    stub = Stub({"hobbit": [icon(str(i), f"t{i}") for i in range(12)]})
    label, pool = find_book_pool(stub, "The Hobbit", log=lambda m: None)
    assert "the hobbit" in stub.searches and "hobbit" in stub.searches
    assert label == "hobbit" and len(pool) == 12


def test_no_results_anywhere():
    label, pool = find_book_pool(Stub({}), "A Wrinkle in Time", log=lambda m: None)
    assert label == "" and pool == []


def test_search_failure_does_not_abort():
    stub = Stub({"hobbit": [icon("1", "ring")]}, failing={"the hobbit"})
    label, pool = find_book_pool(stub, "The Hobbit", log=lambda m: None)
    assert label == "hobbit" and len(pool) == 1
