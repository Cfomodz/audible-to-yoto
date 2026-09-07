"""audible-to-yoto command line."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, audible_lib
from .audible_lib import AudibleError
from .card import CardLimitError
from .config import DEFAULT_BITRATE, TOKENS_PATH, Config, load_config, save_config
from .convert import ConversionError
from .icon_gen import credits as icon_credits
from .pipeline import PipelineError, RunOptions, run_book
from .state import WorkDir, load_json
from .yotoicons import YotoIconsError
from .yoto_api import YotoApiError, YotoClient
from .yoto_auth import AuthError, TokenStore, get_access_token, login

DASHBOARD_STEPS = """\
Create your Yoto app (one time, about two minutes):

  1. Open https://dashboard.yoto.dev/ and sign in with the Yoto account you use in the app.
  2. Create a new application. Any name works, e.g. "Audible to Yoto".
     Choose the public / native client type: this tool needs NO client secret.
  3. Add this redirect URL, exactly:  http://127.0.0.1:{port}/callback
  4. Copy the Client ID and paste it below.
"""


def _log(msg: str) -> None:
    print(msg, flush=True)


def _client_factory(cfg: Config):
    if not cfg.client_id:
        raise AuthError("no Yoto client ID configured. Run `audible-to-yoto setup`.")
    store = TokenStore(TOKENS_PATH)
    return lambda: YotoClient(lambda: get_access_token(cfg.client_id, store))


def _books(cfg: Config, args) -> list[audible_lib.Book]:
    if not audible_lib.is_configured():
        raise AudibleError("audible-cli is not set up. Run `audible-to-yoto setup`.")
    books = audible_lib.library_export(cfg.aax_dir / "library.json", refresh=getattr(args, "refresh", False))
    return audible_lib.resolve_books(books, asin=getattr(args, "asin", None), title=getattr(args, "title", None), all_=getattr(args, "all", False))


def cmd_setup(cfg: Config, args) -> int:
    cfg.data_dir = str(Path(args.data_dir or cfg.data_dir).expanduser().resolve())
    cfg.aax_dir.mkdir(parents=True, exist_ok=True)
    cfg.work_dir.mkdir(parents=True, exist_ok=True)
    _log(f"Data directory: {cfg.data_path}")

    if not audible_lib.is_configured():
        _log("\nStep 1 of 2: Audible. This runs `audible quickstart` to sign in to your Audible account.\n")
        audible_lib.quickstart()
    else:
        _log("Audible: already configured (~/.audible)")

    _log("\nStep 2 of 2: Yoto.\n")
    _log(DASHBOARD_STEPS.format(port=cfg.redirect_port))
    prompt = f"Client ID [{cfg.client_id}]: " if cfg.client_id else "Client ID: "
    entered = input(prompt).strip()
    client_id = entered or cfg.client_id
    if not client_id:
        raise AuthError("a Client ID is required")
    cfg.client_id = client_id
    save_config(cfg)

    if not args.skip_login:
        login(cfg.client_id, TokenStore(TOKENS_PATH), port=cfg.redirect_port, no_browser=args.no_browser, log=_log)

    _log("\nSetup complete. Try:")
    _log("  audible-to-yoto list")
    _log('  audible-to-yoto run --title "Sorcerer\'s Stone"')
    return 0


def cmd_login(cfg: Config, args) -> int:
    if not cfg.client_id:
        raise AuthError("no client ID configured. Run `audible-to-yoto setup` first.")
    login(cfg.client_id, TokenStore(TOKENS_PATH), port=cfg.redirect_port, no_browser=args.no_browser, log=_log)
    return 0


def cmd_list(cfg: Config, args) -> int:
    if not audible_lib.is_configured():
        raise AudibleError("audible-cli is not set up. Run `audible-to-yoto setup`.")
    books = audible_lib.library_export(cfg.aax_dir / "library.json", refresh=args.refresh)
    books.sort(key=lambda b: b.title.lower())
    _log(f"{'ASIN':<12} {'Hours':>5}  {'Yoto':<5} Title")
    for b in books:
        state = load_json(WorkDir(cfg.work_dir, b.asin).card_json, None)
        on_yoto = "yes" if state and any(c.get("cardId") for c in state.get("cards", [])) else ""
        _log(f"{b.asin:<12} {b.hours:>5.1f}  {on_yoto:<5} {b.title}")
    _log(f"\n{len(books)} books. Convert one with: audible-to-yoto run --asin <ASIN>")
    return 0


def cmd_run(cfg: Config, args) -> int:
    opts = RunOptions(
        upload=not args.no_upload,
        bitrate=args.bitrate,
        skip_credits=args.skip_credits,
        force_convert=args.force_convert,
        force_icons=args.force_icons,
        preview=args.preview,
        icons=args.icons,
        icon_tag=args.icon_tag,
    )
    factory = _client_factory(cfg) if opts.upload else None
    books = _books(cfg, args)
    failures = []
    for book in books:
        try:
            run_book(cfg, book, opts, client_factory=factory, log=_log)
        except (AudibleError, PipelineError, ConversionError, CardLimitError, YotoApiError, AuthError, YotoIconsError) as exc:
            if len(books) == 1:
                raise
            failures.append((book, exc))
            _log(f"  FAILED: {exc}")
    if failures:
        _log(f"\n{len(failures)} of {len(books)} books failed:")
        for book, exc in failures:
            _log(f"  {book.asin}  {book.title}: {exc}")
        return 1
    return 0


def cmd_icons(cfg: Config, args) -> int:
    opts = RunOptions(upload=False, force_icons=args.regenerate, only_icons=True, preview=True, icons=args.icons, icon_tag=args.icon_tag)
    for book in _books(cfg, args):
        run_book(cfg, book, opts, log=_log)
        for line in icon_credits(WorkDir(cfg.work_dir, book.asin)):
            _log(f"    {line}")
    return 0


def _add_selector(p: argparse.ArgumentParser, allow_all: bool) -> None:
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--asin", help="Audible ASIN (see `list`)")
    g.add_argument("--title", help="part of the title, case-insensitive")
    if allow_all:
        g.add_argument("--all", action="store_true", help="every book in your library")


def _add_icon_opts(p: argparse.ArgumentParser) -> None:
    p.add_argument("--icons", choices=["yotoicons", "generated"], default="yotoicons", help="icon source: community icons from yotoicons.com (default), or generated numbers")
    p.add_argument("--icon-tag", help="search yotoicons.com for this tag instead of one derived from the book title")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="audible-to-yoto", description="Turn Audible audiobooks into Yoto Make-Your-Own cards.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--data-dir", help="where aax_downloads/ and work/ live (default: from config, else the current directory)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("setup", help="one-time: sign in to Audible, register your Yoto app, sign in to Yoto")
    p.add_argument("--skip-login", action="store_true", help="save the client ID without logging in")
    p.add_argument("--no-browser", action="store_true", help="print the login URL and accept the pasted callback URL")
    p.set_defaults(func=cmd_setup)

    p = sub.add_parser("login", help="sign in to Yoto again")
    p.add_argument("--no-browser", action="store_true", help="print the login URL and accept the pasted callback URL")
    p.set_defaults(func=cmd_login)

    p = sub.add_parser("list", help="show your Audible library")
    p.add_argument("--refresh", action="store_true", help="re-export the library from Audible")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("run", help="download, convert, draw icons, upload, and publish the card(s)")
    _add_selector(p, allow_all=True)
    p.add_argument("--no-upload", action="store_true", help="stop after conversion and icons; nothing is sent to Yoto")
    p.add_argument("--bitrate", default=DEFAULT_BITRATE, help=f"MP3 bitrate, mono (default: {DEFAULT_BITRATE})")
    p.add_argument("--skip-credits", action="store_true", help="drop 'Opening Credits' / 'End Credits' chapters")
    p.add_argument("--force-convert", action="store_true", help="re-encode audio even if MP3s exist")
    p.add_argument("--force-icons", action="store_true", help="rewrite all chapter icons")
    p.add_argument("--preview", action="store_true", help="also write work/<ASIN>/preview.png of the icons")
    p.add_argument("--refresh", action="store_true", help="re-export the Audible library first")
    _add_icon_opts(p)
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("icons", help="match the chapter icons and write a preview sheet, nothing else")
    _add_selector(p, allow_all=False)
    p.add_argument("--regenerate", action="store_true", help="search again and rewrite the icons")
    _add_icon_opts(p)
    p.set_defaults(func=cmd_icons)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = load_config()
    if args.data_dir and args.command != "setup":
        cfg.data_dir = args.data_dir
    try:
        return args.func(cfg, args)
    except (AudibleError, PipelineError, ConversionError, CardLimitError, YotoApiError, AuthError, YotoIconsError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
