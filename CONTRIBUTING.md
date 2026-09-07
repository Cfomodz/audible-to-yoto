# Contributing

Bug reports and pull requests are welcome.

## Setup

```bash
./setup.sh
source venv/bin/activate
pytest -q
```

## Layout

- `audible_to_yoto/cli.py` — argparse entry point (`setup`, `login`, `list`, `run`, `icons`)
- `pipeline.py` — the per-book stages: download, chapters, convert, icons, cover, upload, card
- `chapters.py`, `card.py`, `pixel.py`, `icon_match.py` — pure logic, fully unit-tested
- `audible_lib.py`, `convert.py` — audible-cli and ffmpeg wrappers
- `yotoicons.py`, `icon_gen.py` — the yotoicons.com client and the icon selection pipeline
- `yoto_auth.py`, `yoto_api.py` — PKCE login and the Yoto API client

## Guidelines

- Keep stages idempotent: a re-run with nothing changed must do no work and send nothing.
- Prefer pure functions plus a thin I/O wrapper; test the pure part.
- Do not add interactive prompts outside `setup`.
- Yoto API facts live in `yoto_api.py` docstrings and come from https://yoto.dev. Cite the doc page when changing an endpoint.
- yotoicons.com is a volunteer-run community site. Keep the request rate low, cache what you fetch, and keep the uploader credit in `icons.json`.
- Icon matching must stay deterministic and offline-testable: no network in `icon_match.py`, and tests use a stub client rather than real requests.
