import pytest

from audible_to_yoto.chapters import Chapter, plan_tracks

HP_RAW = {
    "content_metadata": {
        "chapter_info": {
            "chapters": [
                {"length_ms": 63970, "start_offset_ms": 0, "title": "Opening Credits"},
                {"length_ms": 1730444, "start_offset_ms": 63970, "title": "1: The Boy Who Lived"},
                {"length_ms": 1306377, "start_offset_ms": 1794414, "title": "2: The Vanishing Glass"},
                {"length_ms": 80618, "start_offset_ms": 3100791, "title": "End Credits"},
            ],
            "runtime_length_ms": 3181409,
        },
        "content_reference": {"asin": "B017V4IM1G"},
    }
}


@pytest.fixture
def hp_raw():
    return HP_RAW


@pytest.fixture
def chapters():
    chs = [
        Chapter(index=1, title="Opening Credits", start_ms=0, length_ms=63970, credits=True),
        Chapter(index=2, title="1: The Boy Who Lived", start_ms=63970, length_ms=1730444),
        Chapter(index=3, title="2: The Vanishing Glass", start_ms=1794414, length_ms=1306377),
        Chapter(index=4, title="End Credits", start_ms=3100791, length_ms=80618, credits=True),
    ]
    return plan_tracks(chs, "64k")
