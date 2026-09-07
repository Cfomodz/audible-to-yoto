"""Yoto login: OAuth2 authorization code + PKCE with a loopback redirect, plus token storage and refresh."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import secrets
import shutil
import subprocess
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urlencode, urlparse

import requests

AUTH_BASE = "https://login.yotoplay.com"
API_AUDIENCE = "https://api.yotoplay.com"
# content:manage does not imply content:view, and reading a card back needs the latter.
SCOPES = "user:content:manage user:content:view user:icons:manage offline_access"


class AuthError(Exception):
    pass


def make_verifier() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b"=").decode("ascii")


def code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def redirect_uri(port: int) -> str:
    return f"http://127.0.0.1:{port}/callback"


def build_authorize_url(client_id: str, challenge: str, state: str, redirect: str) -> str:
    params = {
        "audience": API_AUDIENCE,
        "scope": SCOPES,
        "response_type": "code",
        "client_id": client_id,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "redirect_uri": redirect,
        "state": state,
    }
    return f"{AUTH_BASE}/authorize?{urlencode(params)}"


def parse_callback(text: str, expected_state: str | None = None) -> str:
    """Accept a full callback URL, a bare query string, or a bare code. Returns the code."""
    text = text.strip()
    parsed = urlparse(text)
    query = parsed.query if parsed.query else (text if "=" in text else f"code={text}")
    qs = parse_qs(query)
    if "error" in qs:
        raise AuthError(qs.get("error_description", qs["error"])[0])
    if "code" not in qs:
        raise AuthError("no authorization code found in the pasted text")
    if expected_state and qs.get("state", [None])[0] != expected_state:
        raise AuthError("state mismatch; start the login again")
    return qs["code"][0]


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return
        self.server.callback_query = parsed.query  # type: ignore[attr-defined]
        body = b"<html><body style='font-family:sans-serif'><h2>Signed in to Yoto.</h2><p>You can close this tab and return to the terminal.</p></body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # silence
        return


def wait_for_callback(server: HTTPServer, expected_state: str, timeout: int = 300) -> str:
    server.timeout = 1
    server.callback_query = None  # type: ignore[attr-defined]
    deadline = time.time() + timeout
    while time.time() < deadline:
        server.handle_request()
        if server.callback_query is not None:  # type: ignore[attr-defined]
            return parse_callback(server.callback_query, expected_state)  # type: ignore[attr-defined]
    raise AuthError("timed out waiting for the browser to come back; run `audible-to-yoto login` again")


def bind_callback_server(port: int) -> HTTPServer:
    try:
        return HTTPServer(("127.0.0.1", port), _CallbackHandler)
    except OSError as exc:
        raise AuthError(f"port {port} is busy ({exc}). Free it, or set redirect_port in the config and update the redirect URL in the Yoto dashboard.") from exc


def _is_wsl() -> bool:
    return "microsoft" in platform.release().lower() or os.path.exists("/proc/sys/fs/binfmt_misc/WSLInterop")


def open_browser(url: str) -> bool:
    if _is_wsl():
        for cmd in (["wslview", url], ["cmd.exe", "/c", "start", "", url]):
            if shutil.which(cmd[0]):
                try:
                    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return True
                except OSError:
                    continue
    try:
        return webbrowser.open(url)
    except Exception:
        return False


def _token_request(data: dict) -> dict:
    resp = requests.post(f"{AUTH_BASE}/oauth/token", data=data, headers={"Accept": "application/json"}, timeout=30)
    if resp.status_code != 200:
        raise AuthError(f"token request failed ({resp.status_code}): {resp.text[:300]}")
    tokens = resp.json()
    if "access_token" not in tokens:
        raise AuthError(f"token response had no access_token: {tokens}")
    return tokens


def exchange_code(client_id: str, code: str, verifier: str, redirect: str) -> dict:
    return _token_request({"grant_type": "authorization_code", "client_id": client_id, "code_verifier": verifier, "code": code, "redirect_uri": redirect})


def refresh_tokens(client_id: str, refresh_token: str) -> dict:
    return _token_request({"grant_type": "refresh_token", "client_id": client_id, "refresh_token": refresh_token})


def jwt_exp(token: str) -> int | None:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return int(json.loads(base64.urlsafe_b64decode(payload)).get("exp"))
    except Exception:
        return None


class TokenStore:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> dict | None:
        if not self.path.exists():
            return None
        try:
            return json.loads(self.path.read_text())
        except json.JSONDecodeError:
            return None

    def save(self, tokens: dict) -> dict:
        record = {
            "access_token": tokens["access_token"],
            "refresh_token": tokens.get("refresh_token") or (self.load() or {}).get("refresh_token"),
            "expires_at": int(time.time()) + int(tokens.get("expires_in", 3600)),
            "scope": tokens.get("scope"),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            json.dump(record, fh, indent=2)
        os.chmod(self.path, 0o600)
        return record

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)


def login(client_id: str, store: TokenStore, port: int = 8787, no_browser: bool = False, log: Callable[[str], None] = print) -> dict:
    verifier = make_verifier()
    state = secrets.token_urlsafe(16)
    redirect = redirect_uri(port)
    url = build_authorize_url(client_id, code_challenge(verifier), state, redirect)

    if no_browser:
        log("Open this URL in any browser and sign in to Yoto:\n\n  " + url + "\n")
        log("After signing in the browser lands on a 127.0.0.1 page that will not load. Copy that page's full URL and paste it here.")
        code = parse_callback(input("Callback URL: "), state)
    else:
        server = bind_callback_server(port)
        try:
            opened = open_browser(url)
            log("Opening your browser to sign in to Yoto..." if opened else "Could not open a browser automatically.")
            log("If nothing opened, visit:\n\n  " + url + "\n")
            log("(On a machine without a browser, run `audible-to-yoto login --no-browser`.)")
            code = wait_for_callback(server, state)
        finally:
            server.server_close()

    tokens = exchange_code(client_id, code, verifier, redirect)
    record = store.save(tokens)
    if not record.get("refresh_token"):
        log("Warning: no refresh token was issued; you will need to log in again when the access token expires.")
    log("Logged in to Yoto.")
    return record


def get_access_token(client_id: str, store: TokenStore) -> str:
    tokens = store.load()
    if not tokens or not tokens.get("access_token"):
        raise AuthError("not logged in to Yoto. Run `audible-to-yoto login`.")
    exp = jwt_exp(tokens["access_token"]) or tokens.get("expires_at") or 0
    if time.time() < exp - 30:
        return tokens["access_token"]
    if not tokens.get("refresh_token"):
        raise AuthError("Yoto session expired and no refresh token is stored. Run `audible-to-yoto login`.")
    try:
        fresh = refresh_tokens(client_id, tokens["refresh_token"])
    except AuthError as exc:
        raise AuthError(f"could not refresh the Yoto session ({exc}). Run `audible-to-yoto login`.") from exc
    return store.save(fresh)["access_token"]
