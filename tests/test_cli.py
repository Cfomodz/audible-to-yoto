import pytest

from audible_to_yoto.cli import build_parser


def test_run_requires_selector():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["run"])
    with pytest.raises(SystemExit):
        parser.parse_args(["run", "--asin", "A", "--title", "T"])


def test_run_defaults():
    args = build_parser().parse_args(["run", "--asin", "B017V4IM1G"])
    assert args.asin == "B017V4IM1G" and args.bitrate == "64k"
    assert not args.no_upload and not args.skip_credits


def test_run_all_and_options():
    args = build_parser().parse_args(["run", "--all", "--no-upload", "--bitrate", "96k", "--skip-credits", "--force-icons", "--preview"])
    assert args.all and args.no_upload and args.bitrate == "96k" and args.skip_credits
    assert args.force_icons and args.preview


def test_no_model_or_effort_flags():
    parser = build_parser()
    for argv in (["run", "--asin", "A", "--model", "opus"], ["run", "--asin", "A", "--effort", "high"], ["run", "--asin", "A", "--icons", "numbers"]):
        with pytest.raises(SystemExit):
            parser.parse_args(argv)


def test_icons_has_no_all():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["icons", "--all"])
    args = parser.parse_args(["icons", "--title", "matilda", "--regenerate"])
    assert args.title == "matilda" and args.regenerate


def test_setup_and_login_flags():
    parser = build_parser()
    assert parser.parse_args(["setup", "--skip-login", "--no-browser"]).skip_login
    assert parser.parse_args(["login", "--no-browser"]).no_browser
    assert parser.parse_args(["list", "--refresh"]).refresh
