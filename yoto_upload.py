#!/usr/bin/env python3
"""
Upload converted audiobooks straight to Yoto as MYO playlists.

This closes the loop end-to-end: audio is uploaded to Yoto's own media
storage (no self-hosted web server needed), chapter icons and the cover
are uploaded, and the card is created via the official Yoto API
(https://yoto.dev) - no manual JSON editing required.

Prerequisites:
    1. Create a (free) client at https://dashboard.yoto.dev/ and register
       the callback URL http://127.0.0.1:8787/callback
    2. Pass the client ID via --client-id or the YOTO_CLIENT_ID env var
       (it is remembered after the first run)

Usage:
    python3 yoto_upload.py --all                 # upload every book
    python3 yoto_upload.py --book "Dune"         # upload one book
    python3 yoto_upload.py --style symbols --all # pick an icon style

The first run opens a browser for login (authorization code + PKCE, the
flow yoto.dev recommends for CLIs). Tokens are cached in
~/.config/audible-to-yoto/tokens.json. On a headless machine, forward the
callback port first:  ssh -L 8787:127.0.0.1:8787 <host>
"""

import argparse
import base64
import hashlib
import http.server
import json
import os
import re
import secrets
import sys
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path

try:
    import requests
except ImportError:
    print("Error: requests is required. Install with: pip install requests")
    sys.exit(1)

# Get script directory for relative paths
SCRIPT_DIR = Path(__file__).parent.resolve()

# Configuration - relative to script directory
BOOKS_DIR = SCRIPT_DIR / "yoto_mp3"
BOOK_COVERS_DIR = SCRIPT_DIR / "yoto_covers"
CHAPTER_ICONS_DIR = SCRIPT_DIR / "yoto_chapter_icons_16x16"
UPLOADED_FILE = SCRIPT_DIR / ".yoto_uploaded"
ICON_CACHE_FILE = SCRIPT_DIR / ".yoto_icon_cache.json"

# Yoto API endpoints (see https://yoto.dev)
AUTH_BASE = "https://login.yotoplay.com"
API_BASE = "https://api.yotoplay.com"
AUDIENCE = API_BASE
SCOPES = "user:content:manage user:icons:manage offline_access"
CALLBACK_HOST = "127.0.0.1"
CALLBACK_PORT = 8787
CALLBACK_PATH = "/callback"

TOKEN_STORE = Path.home() / ".config" / "audible-to-yoto" / "tokens.json"

TRANSCODE_POLL_INTERVAL = 2  # seconds
TRANSCODE_POLL_TIMEOUT = 600  # seconds per file


class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'


def print_color(text, color):
    """Print colored text"""
    print(f"{color}{text}{Colors.NC}")


def sanitize_filename(name):
    """Sanitize filename for safe file operations (must match generate_covers.py)"""
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    return name.strip()


# ---------------------------------------------------------------------------
# Authentication (authorization code + PKCE with localhost callback)
# ---------------------------------------------------------------------------

class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    """Captures the OAuth authorization code from the browser redirect"""

    result = None

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != CALLBACK_PATH:
            self.send_response(404)
            self.end_headers()
            return
        params = urllib.parse.parse_qs(parsed.query)
        _CallbackHandler.result = {k: v[0] for k, v in params.items()}
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(
            b"<html><body><h2>Login complete.</h2>"
            b"<p>You can close this tab and return to the terminal.</p>"
            b"</body></html>"
        )

    def log_message(self, *args):
        pass  # keep the terminal clean


def _load_token_store():
    try:
        with open(TOKEN_STORE, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_token_store(store):
    TOKEN_STORE.parent.mkdir(parents=True, exist_ok=True)
    with open(TOKEN_STORE, 'w', encoding='utf-8') as f:
        json.dump(store, f, indent=2)
    os.chmod(TOKEN_STORE, 0o600)


def _token_request(data):
    response = requests.post(
        f"{AUTH_BASE}/oauth/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Token request failed ({response.status_code}): {response.text}")
    return response.json()


def _store_tokens(store, client_id, tokens):
    store["client_id"] = client_id
    store["access_token"] = tokens["access_token"]
    # Refresh tokens are single-use: always persist the newest one
    if tokens.get("refresh_token"):
        store["refresh_token"] = tokens["refresh_token"]
    store["expires_at"] = time.time() + tokens.get("expires_in", 3600)
    _save_token_store(store)


def _browser_login(client_id):
    """Run the authorization code + PKCE flow with a temporary local server"""
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode('ascii')).digest()
    ).rstrip(b'=').decode('ascii')
    state = secrets.token_urlsafe(16)
    redirect_uri = f"http://{CALLBACK_HOST}:{CALLBACK_PORT}{CALLBACK_PATH}"

    auth_url = f"{AUTH_BASE}/authorize?" + urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "audience": AUDIENCE,
        "scope": SCOPES,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })

    _CallbackHandler.result = None
    server = http.server.HTTPServer((CALLBACK_HOST, CALLBACK_PORT), _CallbackHandler)
    server.timeout = 1
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    print()
    print_color("Opening browser for Yoto login...", Colors.BLUE)
    print("If the browser doesn't open (e.g. on a headless machine), open this")
    print("URL yourself. On a remote machine, forward the callback port first:")
    print(f"  ssh -L {CALLBACK_PORT}:{CALLBACK_HOST}:{CALLBACK_PORT} <this-host>")
    print()
    print(auth_url)
    print()
    webbrowser.open(auth_url)

    try:
        deadline = time.time() + 300
        while _CallbackHandler.result is None:
            if time.time() > deadline:
                raise RuntimeError("Timed out waiting for browser login (5 minutes)")
            time.sleep(0.5)
    finally:
        server.shutdown()

    result = _CallbackHandler.result
    if "error" in result:
        raise RuntimeError(f"Login failed: {result.get('error_description', result['error'])}")
    if result.get("state") != state:
        raise RuntimeError("Login failed: state mismatch (possible CSRF)")

    return _token_request({
        "grant_type": "authorization_code",
        "client_id": client_id,
        "code": result["code"],
        "code_verifier": verifier,
        "redirect_uri": redirect_uri,
    })


def get_access_token(client_id):
    """Return a valid access token, refreshing or logging in as needed"""
    store = _load_token_store()

    if not client_id:
        client_id = store.get("client_id")
    if not client_id:
        print_color("Error: No Yoto client ID.", Colors.RED)
        print("Create one at https://dashboard.yoto.dev/ (register callback URL")
        print(f"http://{CALLBACK_HOST}:{CALLBACK_PORT}{CALLBACK_PATH}), then pass it")
        print("with --client-id or the YOTO_CLIENT_ID environment variable.")
        sys.exit(1)

    same_client = store.get("client_id") == client_id
    if same_client and store.get("access_token") and store.get("expires_at", 0) > time.time() + 60:
        return store["access_token"]

    if same_client and store.get("refresh_token"):
        try:
            tokens = _token_request({
                "grant_type": "refresh_token",
                "client_id": client_id,
                "refresh_token": store["refresh_token"],
            })
            _store_tokens(store, client_id, tokens)
            return tokens["access_token"]
        except RuntimeError as e:
            print_color(f"Token refresh failed, logging in again: {e}", Colors.YELLOW)

    tokens = _browser_login(client_id)
    _store_tokens(store, client_id, tokens)
    return tokens["access_token"]


# ---------------------------------------------------------------------------
# Yoto API operations
# ---------------------------------------------------------------------------

def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def upload_audio(token, mp3_path):
    """Upload one audio file and wait for transcoding.

    Returns the transcode result dict containing transcodedSha256 (used as
    yoto:#<sha> trackUrl) and transcodedInfo (duration, fileSize, ...).
    """
    # Step 1: get a one-time upload URL
    response = requests.get(
        f"{API_BASE}/media/transcode/audio/uploadUrl",
        headers={**_auth_headers(token), "Accept": "application/json"},
        timeout=30,
    )
    if response.status_code != 200:
        raise RuntimeError(f"uploadUrl request failed ({response.status_code}): {response.text}")
    upload = response.json().get("upload", {})
    upload_url = upload.get("uploadUrl")
    upload_id = upload.get("uploadId")
    if not upload_url or not upload_id:
        raise RuntimeError(f"Unexpected uploadUrl response: {response.text}")

    # Step 2: PUT the file
    with open(mp3_path, 'rb') as f:
        put = requests.put(
            upload_url,
            data=f,
            headers={"Content-Type": "audio/mpeg"},
            timeout=600,
        )
    if put.status_code not in (200, 201, 204):
        raise RuntimeError(f"Audio upload failed ({put.status_code}): {put.text}")

    # Step 3: poll until transcoded
    deadline = time.time() + TRANSCODE_POLL_TIMEOUT
    while True:
        response = requests.get(
            f"{API_BASE}/media/upload/{upload_id}/transcoded",
            params={"loudnorm": "false"},
            headers={**_auth_headers(token), "Accept": "application/json"},
            timeout=30,
        )
        if response.status_code == 200:
            body = response.json()
            transcode = body.get("transcode") or body.get("data", {}).get("transcode") or {}
            if transcode.get("transcodedSha256"):
                return transcode
        elif response.status_code not in (202, 404):
            raise RuntimeError(f"Transcode poll failed ({response.status_code}): {response.text}")
        if time.time() > deadline:
            raise RuntimeError(f"Timed out waiting for transcode of {mp3_path.name}")
        time.sleep(TRANSCODE_POLL_INTERVAL)


def _load_icon_cache():
    try:
        with open(ICON_CACHE_FILE, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def upload_icon(token, icon_path, icon_cache):
    """Upload a 16x16 icon; returns its yoto:#<mediaId> reference.

    Identical icons (e.g. the numbers style repeats across books) are
    deduplicated through a local content-hash cache.
    """
    data = icon_path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest in icon_cache:
        return icon_cache[digest]

    response = requests.post(
        f"{API_BASE}/media/displayIcons/user/me/upload",
        params={"autoConvert": "true", "filename": icon_path.stem},
        headers=_auth_headers(token),
        files={"file": (icon_path.name, data, "image/png")},
        timeout=60,
    )
    if response.status_code not in (200, 201):
        raise RuntimeError(f"Icon upload failed ({response.status_code}): {response.text}")
    media_id = response.json().get("displayIcon", {}).get("mediaId")
    if not media_id:
        raise RuntimeError(f"Unexpected icon upload response: {response.text}")

    ref = f"yoto:#{media_id}"
    icon_cache[digest] = ref
    with open(ICON_CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(icon_cache, f, indent=2)
    return ref


def upload_cover(token, cover_path):
    """Upload a cover image; returns its mediaUrl for metadata.cover.imageL"""
    response = requests.post(
        f"{API_BASE}/media/coverImage/user/me/upload",
        params={"autoconvert": "true", "coverType": "default"},
        headers={**_auth_headers(token), "Content-Type": "image/jpeg"},
        data=cover_path.read_bytes(),
        timeout=120,
    )
    if response.status_code not in (200, 201):
        raise RuntimeError(f"Cover upload failed ({response.status_code}): {response.text}")
    media_url = response.json().get("coverImage", {}).get("mediaUrl")
    if not media_url:
        raise RuntimeError(f"Unexpected cover upload response: {response.text}")
    return media_url


def parse_chapter_filename(filename):
    """Parse Chapter_NNN_Title.mp3 -> (number, title) or None"""
    match = re.match(r'Chapter_(\d+)_(.+)\.mp3$', filename)
    if not match:
        return None
    return int(match.group(1)), match.group(2)


def build_card_content(book_name, tracks, cover_url=None):
    """Build the POST /content body from uploaded track/icon results.

    tracks: list of dicts with keys: num, title, sha256, info (transcodedInfo
    dict with duration/fileSize/channels/format), icon (yoto:#id or None).
    """
    chapters = []
    total_duration = 0
    total_size = 0

    for track in tracks:
        info = track.get("info") or {}
        duration = info.get("duration") or 0
        file_size = info.get("fileSize") or 0
        total_duration += duration
        total_size += file_size

        key = f"{track['num']:02d}"
        entry = {
            "key": key,
            "title": track["title"],
            "overlayLabel": str(track["num"]),
            "tracks": [
                {
                    "key": key,
                    "title": track["title"],
                    "trackUrl": f"yoto:#{track['sha256']}",
                    "type": "audio",
                    "format": info.get("format", "aac"),
                    "duration": duration,
                    "fileSize": file_size,
                    "channels": info.get("channels", 2),
                }
            ],
        }
        if track.get("icon"):
            entry["display"] = {"icon16x16": track["icon"]}
            entry["tracks"][0]["display"] = {"icon16x16": track["icon"]}
        chapters.append(entry)

    content = {
        "title": book_name,
        "content": {"chapters": chapters},
        "metadata": {
            "description": f"Audiobook: {book_name}",
            "media": {
                "duration": total_duration,
                "fileSize": total_size,
                "readableFileSize": round(total_size / (1024 * 1024), 1),
            },
        },
    }
    if cover_url:
        content["metadata"]["cover"] = {"imageL": cover_url}
    return content


def create_card(token, content):
    """POST the card content; returns the created card's JSON"""
    response = requests.post(
        f"{API_BASE}/content",
        headers={**_auth_headers(token), "Content-Type": "application/json"},
        json=content,
        timeout=60,
    )
    if response.status_code not in (200, 201):
        raise RuntimeError(f"Card creation failed ({response.status_code}): {response.text}")
    return response.json()


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------

def load_uploaded():
    try:
        return set(UPLOADED_FILE.read_text(encoding='utf-8').splitlines())
    except OSError:
        return set()


def mark_uploaded(book_name):
    with open(UPLOADED_FILE, 'a', encoding='utf-8') as f:
        f.write(book_name + "\n")


def upload_book(token, book_dir, icon_style, icon_cache):
    """Upload one book end-to-end; returns the created card JSON"""
    book_name = book_dir.name
    chapter_files = sorted(book_dir.glob("Chapter_*.mp3"))
    parsed = [(f, parse_chapter_filename(f.name)) for f in chapter_files]
    parsed = [(f, p) for f, p in parsed if p]
    if not parsed:
        raise RuntimeError("No Chapter_*.mp3 files found")

    icons_dir = CHAPTER_ICONS_DIR / icon_style / book_name

    tracks = []
    for i, (mp3_path, (num, title)) in enumerate(parsed, 1):
        print_color(f"  [{i}/{len(parsed)}] Uploading: {title}", Colors.BLUE)
        transcode = upload_audio(token, mp3_path)

        icon_ref = None
        icon_path = icons_dir / f"chapter_{num:03d}.png"
        if icon_path.exists():
            icon_ref = upload_icon(token, icon_path, icon_cache)

        tracks.append({
            "num": num,
            "title": title.replace('_', ' '),
            "sha256": transcode["transcodedSha256"],
            "info": transcode.get("transcodedInfo") or {},
            "icon": icon_ref,
        })

    cover_url = None
    cover_path = BOOK_COVERS_DIR / f"{sanitize_filename(book_name)}.jpg"
    if cover_path.exists():
        print_color("  Uploading cover...", Colors.BLUE)
        cover_url = upload_cover(token, cover_path)
    else:
        print_color("  No cover found (run generate_covers.py first) - skipping", Colors.YELLOW)

    print_color("  Creating card...", Colors.BLUE)
    content = build_card_content(book_name, tracks, cover_url)
    return create_card(token, content)


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Upload converted audiobooks to Yoto as MYO playlists',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python3 yoto_upload.py --all
    python3 yoto_upload.py --book "Dune"
    python3 yoto_upload.py --all --style symbols --yes
        """
    )
    parser.add_argument('--book', help='Upload a single book (directory name or unique substring)')
    parser.add_argument('--all', action='store_true', help='Upload every book in yoto_mp3/')
    parser.add_argument(
        '--style',
        choices=['numbers', 'symbols', 'miniatures'],
        default='numbers',
        help='Chapter icon style to upload (default: numbers)'
    )
    parser.add_argument('--client-id', default=os.environ.get('YOTO_CLIENT_ID'),
                        help='Yoto API client ID (from https://dashboard.yoto.dev/)')
    parser.add_argument('--force', action='store_true',
                        help='Re-upload books already recorded in .yoto_uploaded')
    parser.add_argument('--yes', '-y', action='store_true',
                        help='Skip confirmation prompts (non-interactive mode)')
    return parser.parse_args()


def main():
    """Main function"""
    args = parse_args()

    print("=" * 60)
    print("Yoto MYO Uploader")
    print("=" * 60)
    print()

    if not BOOKS_DIR.exists():
        print_color(f"Error: Books directory not found: {BOOKS_DIR}", Colors.RED)
        print("Run convert_audiobooks.sh first to create audiobook files.")
        sys.exit(1)

    book_dirs = sorted([d for d in BOOKS_DIR.iterdir() if d.is_dir()])
    if args.book:
        exact = [d for d in book_dirs if d.name == args.book]
        matches = exact or [d for d in book_dirs if args.book.lower() in d.name.lower()]
        if not matches:
            print_color(f"Error: No book matching '{args.book}'", Colors.RED)
            sys.exit(1)
        if len(matches) > 1:
            print_color(f"Error: '{args.book}' matches multiple books:", Colors.RED)
            for d in matches:
                print(f"  - {d.name}")
            sys.exit(1)
        book_dirs = matches
    elif not args.all:
        print_color("Error: Pass --book NAME or --all", Colors.RED)
        sys.exit(1)

    uploaded = load_uploaded()
    if not args.force:
        skipped = [d for d in book_dirs if d.name in uploaded]
        book_dirs = [d for d in book_dirs if d.name not in uploaded]
        if skipped:
            print_color(f"Skipping {len(skipped)} already-uploaded book(s) (--force to redo)", Colors.YELLOW)

    if not book_dirs:
        print_color("Nothing to upload.", Colors.YELLOW)
        sys.exit(0)

    print_color(f"Will upload {len(book_dirs)} book(s) with '{args.style}' icons:", Colors.GREEN)
    for d in book_dirs:
        print(f"  - {d.name}")
    print()

    if not args.yes:
        response = input("Continue? (y/n): ")
        if response.lower() != 'y':
            sys.exit(0)

    token = get_access_token(args.client_id)
    icon_cache = _load_icon_cache()

    success = 0
    failed = 0
    for i, book_dir in enumerate(book_dirs, 1):
        print()
        print(f"[{i}/{len(book_dirs)}] {book_dir.name}")
        try:
            card = upload_book(token, book_dir, args.style, icon_cache)
            card_id = card.get("cardId") or card.get("card", {}).get("cardId", "?")
            print_color(f"  ✓ Card created (id: {card_id})", Colors.GREEN)
            mark_uploaded(book_dir.name)
            success += 1
        except RuntimeError as e:
            print_color(f"  ✗ Failed: {e}", Colors.RED)
            failed += 1

    print()
    print("=" * 60)
    print("Upload Summary")
    print("=" * 60)
    print_color(f"Uploaded: {success}", Colors.GREEN)
    if failed > 0:
        print_color(f"Failed: {failed}", Colors.RED)
    print()
    print("Your playlists are now in the Yoto app under 'My Cards' /")
    print("MYO Studio (https://my.yotoplay.com) - link one to a blank")
    print("MYO card from the app and it's ready to play.")
    print("=" * 60)


if __name__ == "__main__":
    main()
