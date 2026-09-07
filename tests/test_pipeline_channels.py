import pytest

from audible_to_yoto.pipeline import _channels_label


@pytest.mark.parametrize("value,expected", [(1, "mono"), (2, "stereo"), ("mono", "mono"), ("Stereo", "stereo"), ("1", "mono"), (None, None), ("", None), ("weird", None)])
def test_channels_label(value, expected):
    assert _channels_label(value) == expected
