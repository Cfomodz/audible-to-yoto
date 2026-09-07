from pathlib import Path

import pytest

from audible_to_yoto.convert import AudioSource, ConversionError, build_ffmpeg_cmd


def test_aax_cmd_uses_input_seeking():
    src = AudioSource(path=Path("/x/book.aax"), kind="aax", activation_bytes="1a2b3c4d")
    cmd = build_ffmpeg_cmd(src, 63970, 1730444, Path("/out/002.mp3.part"), "64k", {"title": "1: The Boy Who Lived", "track": "2/19"})
    assert cmd[0] == "ffmpeg"
    assert cmd[cmd.index("-activation_bytes") + 1] == "1a2b3c4d"
    i_idx = cmd.index("-i")
    assert cmd.index("-ss") < i_idx and cmd.index("-t") < i_idx
    assert cmd[cmd.index("-ss") + 1] == "63.970" and cmd[cmd.index("-t") + 1] == "1730.444"
    assert cmd[i_idx + 1] == "/x/book.aax"
    assert cmd[cmd.index("-b:a") + 1] == "64k" and cmd[cmd.index("-ac") + 1] == "1"
    assert "-metadata" in cmd and "title=1: The Boy Who Lived" in cmd
    assert cmd[-3:] == ["-f", "mp3", "/out/002.mp3.part"]


def test_aaxc_cmd_uses_key_iv():
    src = AudioSource(path=Path("/x/book.aaxc"), kind="aaxc", key="k" * 32, iv="i" * 32)
    cmd = build_ffmpeg_cmd(src, 0, 1000, Path("/out/001.mp3.part"), "96k")
    assert cmd[cmd.index("-audible_key") + 1] == "k" * 32
    assert cmd[cmd.index("-audible_iv") + 1] == "i" * 32
    assert "-activation_bytes" not in cmd


def test_missing_secrets_raise():
    with pytest.raises(ConversionError):
        AudioSource(path=Path("/x"), kind="aax").decrypt_args()
    with pytest.raises(ConversionError):
        AudioSource(path=Path("/x"), kind="aaxc", key="k").decrypt_args()
