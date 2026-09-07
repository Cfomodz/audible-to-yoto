# Audible to Yoto

One command turns an Audible audiobook into a Yoto Make-Your-Own card: chapter-split audio with the real chapter titles, a matching community icon for every chapter, the official cover, all uploaded to Yoto and published as a playlist you link to a blank MYO card.

```
$ audible-to-yoto run --title "Sorcerer's Stone"

== Harry Potter and the Sorcerer's Stone, Book 1  [B017V4IM1G]
  audible: Harry_Potter_and_the_Sorcerers_Stone_Book_1-LC_128_44100_stereo.aax (aax)
  chapters: 19 (19 tracks, 8.3 h)
  audio: encoding 19 of 19 tracks at 64k mono (12 parallel)
  icons: yotoicons.com tag 'harry potter' returned 100 icons
  icons: 19 chapter icons ready, 16 from yotoicons.com, 3 generated
  cover: ready
  upload: cover
  upload: icons (19 new, 0 cached)
  upload: audio (19 new, 0 cached)
  card 7Xk2q updated: Harry Potter and the Sorcerer's Stone, Book 1 (19 tracks, 239 MB)
```

Re-running is free: converted audio, generated icons, uploads, and the card itself are all cached and only redone when something changed.

## Setup (once)

Requirements: Python 3.10+, ffmpeg, an Audible account, and a Yoto account.

```bash
git clone <this repo> && cd audible-to-yoto
./setup.sh                   # creates venv/ and installs the audible-to-yoto command
source venv/bin/activate
audible-to-yoto setup        # Audible sign-in, Yoto app registration, Yoto sign-in
```

`setup` walks you through two sign-ins:

1. **Audible.** Runs `audible quickstart` (from [audible-cli](https://github.com/mkb79/audible-cli)). Pick your marketplace, sign in, accept the defaults. Skipped if `~/.audible` already exists.
2. **Yoto.** Yoto's API needs an app of your own. It takes two minutes:
   1. Open https://dashboard.yoto.dev/ and sign in with the Yoto account you use in the app.
   2. Create a new application. Any name works ("Audible to Yoto"). Choose the public / native client type. No client secret is needed or used.
   3. Add this redirect URL exactly: `http://127.0.0.1:8787/callback`
   4. Copy the Client ID and paste it into the terminal when asked.

   A browser tab then opens for the Yoto login. Tokens are stored in `~/.config/audible-to-yoto/tokens.json` (mode 600) and refresh themselves. On a machine without a browser use `audible-to-yoto login --no-browser` and paste the callback URL back.

## Use

```bash
audible-to-yoto list                              # your library: ASIN, hours, whether it is on Yoto
audible-to-yoto run --title "Matilda"             # everything, end to end
audible-to-yoto run --asin B017V4IM1G --preview   # same, plus work/<ASIN>/preview.png of the icons
audible-to-yoto run --all                         # the whole library
audible-to-yoto icons --title "Matilda"           # match icons and write the preview sheet only
```

The finished playlist appears under "My playlists" in the Yoto app and at https://my.yotoplay.com, where you link it to a blank Make-Your-Own card.

Useful `run` flags:

| Flag | What it does |
|---|---|
| `--no-upload` | Download, convert, and match icons only. Nothing is sent to Yoto. |
| `--icon-tag "harry potter"` | Search yotoicons.com for this tag instead of one derived from the book title. |
| `--icons generated` | Skip yotoicons.com entirely and use numbered icons. |
| `--bitrate 96k` | Mono MP3 bitrate. Default `64k` (about 29 MB per hour). |
| `--skip-credits` | Drop the "Opening Credits" and "End Credits" chapters. |
| `--preview` | Also write `work/<ASIN>/preview.png`, a contact sheet of the chapter icons. |
| `--force-convert`, `--force-icons` | Redo audio or icons even though they are current. |

## What happens

1. **Download.** `audible download` fetches the book as AAX (or AAXC with its voucher), the chapter JSON, and the 1215px cover into `aax_downloads/`. Already-downloaded books are reused.
2. **Chapters.** The chapter JSON has the real titles and split points ("1: The Boy Who Lived", not "Chapter 1"). Chapters over 60 minutes become several tracks inside the same chapter.
3. **Convert.** ffmpeg decrypts and cuts every track in parallel, straight to mono MP3, seeking into the source so a 19-chapter book takes about a minute.
4. **Icons.** [yotoicons.com](https://yotoicons.com) is searched for the book, narrowing the tag until it finds a pool of icons ("Harry Potter and the Sorcerer's Stone, Book 1" ends up at `harry potter`). Each chapter title is then compared against every icon's tags, and the best scoring pairs are assigned first so no icon is used twice on a card. Chapters the pool cannot cover get a second search on their own key words. Anything still unmatched falls back to a generated icon: pixel digits for the chapter number, a book glyph for the credits. Icons are normalized to 16x16 and cached, so the search happens once per book.
5. **Upload.** Cover, icons, and audio go to Yoto's media endpoints. Yoto deduplicates by SHA-256, so nothing is sent twice.
6. **Card.** The playlist is created with `POST /content`, or updated in place when it already exists. Books over Yoto's 500 MB / 100 track card limit are split into "Part 1 of 2" cards without breaking a chapter.

Everything for a book lives in `work/<ASIN>/`: `chapters.json`, `mp3/`, `icons/`, `icons.json` (which icon each chapter got, who uploaded it, and its Yoto media ID), `uploads.json`, `card.json`, `cover.jpg`, `preview.png`.

Check the matches before uploading with `audible-to-yoto icons --asin <ASIN>`, which writes `preview.png` and prints the uploader of every icon it used. Not happy with a match? Two options:

- Search a different tag: `audible-to-yoto icons --asin <ASIN> --icon-tag "hogwarts" --regenerate`
- Use your own art: drop a PNG into `work/<ASIN>/icons/` as `001.png`, `002.png` and so on. Files you put there are never overwritten, and they are uploaded on the next run. `--force-icons` goes back to the matched icons.

Icons come from the yotoicons.com community. Credit the uploaders if you share a card; the `icons` command prints them.

## Yoto limits

From Yoto's Make-Your-Own documentation: 100 tracks per card, 100 MB or 60 minutes per track, 500 MB per card. At the default 64 kbps mono that is about 17 hours per card. The tool enforces all three.

## Troubleshooting

- **`Error: not logged in to Yoto`**: run `audible-to-yoto login`.
- **`port 8787 is busy`**: free the port, or set `"redirect_port"` in `~/.config/audible-to-yoto/config.json` and register the matching redirect URL in the Yoto dashboard.
- **`Could not get activation bytes`**: run `audible activation-bytes` once inside the venv and check its output.
- **Chapters are just "Chapter 1, 2, 3"**: some titles ship without chapter names in their metadata. The audio splits are still correct, but there is nothing for the icon search to match on, so every chapter gets a numbered icon.
- **Few or no icons matched**: the book may not be tagged on yotoicons.com under a name derived from its title. Try `--icon-tag` with the name people would actually tag it with, then `--regenerate`.
- **A match is plainly wrong**: replace that one file in `work/<ASIN>/icons/` with your own 16x16 PNG and run again. Your file is kept and uploaded.
- **Old download without chapter JSON**: the tool fetches the chapter JSON and cover for existing audio automatically. If it cannot match the file, run `audible download --asin <ASIN> --chapter --cover --cover-size 1215 -o aax_downloads`.

## Development

```bash
source venv/bin/activate
pytest -q
```

The pure logic (chapter normalization, card splitting, icon matching, PKCE, content body) is unit-tested. Network calls to yotoicons.com and Yoto run against stubs, so the suite needs no network and no credentials.

## Legal

For personal use with audiobooks you own. Respect Audible's and Yoto's terms of service. MIT license.
