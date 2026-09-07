import base64
import json
import os
import re
import threading
import time
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

import pytest

from audible_to_yoto import yoto_auth
from audible_to_yoto.yoto_auth import (
    AuthError,
    TokenStore,
    bind_callback_server,
    build_authorize_url,
    code_challenge,
    get_access_token,
    jwt_exp,
    make_verifier,
    parse_callback,
    wait_for_callback,
)


def test_verifier_shape():
    v = make_verifier()
    assert 43 <= len(v) <= 128
    assert re.fullmatch(r"[A-Za-z0-9\-_]+", v)


def test_code_challenge_rfc7636_vector():
    assert code_challenge("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk") == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


def test_authorize_url():
    url = build_authorize_url("cid", "chal", "st", "http://127.0.0.1:8787/callback")
    parsed = urlparse(url)
    assert parsed.scheme == "https" and parsed.netloc == "login.yotoplay.com" and parsed.path == "/authorize"
    qs = parse_qs(parsed.query)
    assert qs["client_id"] == ["cid"] and qs["code_challenge"] == ["chal"] and qs["code_challenge_method"] == ["S256"]
    assert qs["audience"] == ["https://api.yotoplay.com"] and qs["response_type"] == ["code"] and qs["state"] == ["st"]
    for scope in ("offline_access", "user:content:manage", "user:content:view", "user:icons:manage"):
        assert scope in qs["scope"][0]
    assert qs["redirect_uri"] == ["http://127.0.0.1:8787/callback"]


def test_parse_callback_variants():
    assert parse_callback("http://127.0.0.1:8787/callback?code=abc&state=s1", "s1") == "abc"
    assert parse_callback("code=abc&state=s1", "s1") == "abc"
    assert parse_callback("abc", None) == "abc"
    with pytest.raises(AuthError, match="state"):
        parse_callback("http://127.0.0.1:8787/callback?code=abc&state=other", "s1")
    with pytest.raises(AuthError, match="denied"):
        parse_callback("http://127.0.0.1:8787/callback?error=access_denied&error_description=denied", None)
    with pytest.raises(AuthError):
        parse_callback("http://127.0.0.1:8787/callback?state=s1", "s1")


def test_jwt_exp():
    payload = base64.urlsafe_b64encode(json.dumps({"exp": 1234}).encode()).rstrip(b"=").decode()
    assert jwt_exp(f"h.{payload}.s") == 1234
    assert jwt_exp("garbage") is None


def test_token_store_perms_and_refresh_preserved(tmp_path):
    store = TokenStore(tmp_path / "t.json")
    rec = store.save({"access_token": "a1", "refresh_token": "r1", "expires_in": 100})
    assert rec["refresh_token"] == "r1" and rec["expires_at"] > time.time()
    assert oct(os.stat(store.path).st_mode & 0o777) == "0o600"
    rec2 = store.save({"access_token": "a2", "expires_in": 100})
    assert rec2["refresh_token"] == "r1"
    assert store.load()["access_token"] == "a2"


def test_get_access_token_refreshes_when_expired(tmp_path, monkeypatch):
    store = TokenStore(tmp_path / "t.json")
    store.save({"access_token": "old", "refresh_token": "r1", "expires_in": 0})
    monkeypatch.setattr(yoto_auth, "refresh_tokens", lambda cid, rt: {"access_token": "new", "refresh_token": "r2", "expires_in": 3600})
    assert get_access_token("cid", store) == "new"
    assert store.load()["refresh_token"] == "r2"
    assert get_access_token("cid", store) == "new"  # now fresh, no refresh needed


def test_get_access_token_errors(tmp_path):
    store = TokenStore(tmp_path / "t.json")
    with pytest.raises(AuthError, match="login"):
        get_access_token("cid", store)
    store.save({"access_token": "old", "expires_in": 0})
    with pytest.raises(AuthError, match="login"):
        get_access_token("cid", store)


def test_loopback_callback_roundtrip():
    server = bind_callback_server(0)
    port = server.server_address[1]
    result = {}

    def serve():
        result["code"] = wait_for_callback(server, "st", timeout=10)

    t = threading.Thread(target=serve)
    t.start()
    try:
        with urlopen(f"http://127.0.0.1:{port}/callback?code=xyz&state=st", timeout=5) as resp:
            assert b"Signed in" in resp.read()
    finally:
        t.join(timeout=10)
        server.server_close()
    assert result["code"] == "xyz"
