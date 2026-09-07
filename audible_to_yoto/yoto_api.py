"""Yoto API client: audio/icon/cover uploads and card create/update, with retries."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

import requests

API_BASE = "https://api.yotoplay.com"
RETRY_STATUSES = {429, 500, 502, 503, 504}


class YotoApiError(Exception):
    pass


class YotoClient:
    def __init__(self, token_provider: Callable[[], str], base: str = API_BASE, session: requests.Session | None = None):
        self.token_provider = token_provider
        self.base = base.rstrip("/")
        self.session = session or requests.Session()

    def _request(self, method: str, path: str, *, retries: int = 5, timeout: int = 120, **kwargs) -> requests.Response:
        headers = dict(kwargs.pop("headers", {}) or {})
        for attempt in range(retries):
            headers["Authorization"] = f"Bearer {self.token_provider()}"
            headers.setdefault("Accept", "application/json")
            try:
                resp = self.session.request(method, f"{self.base}{path}", headers=headers, timeout=timeout, **kwargs)
            except requests.RequestException as exc:
                if attempt < retries - 1:
                    time.sleep(min(2 ** attempt, 32))
                    continue
                raise YotoApiError(f"{method} {path} -> network error: {exc}") from exc
            if resp.status_code in RETRY_STATUSES and attempt < retries - 1:
                wait = float(resp.headers.get("Retry-After") or min(2 ** attempt, 32))
                time.sleep(wait)
                continue
            if resp.status_code >= 400:
                raise YotoApiError(f"{method} {path} -> {resp.status_code}: {resp.text[:400]}")
            return resp
        raise YotoApiError(f"{method} {path}: gave up after {retries} attempts")

    # -- audio -----------------------------------------------------------------

    def get_upload_url(self, sha256: str, filename: str | None = None) -> dict:
        params = {"sha256": sha256}
        if filename:
            params["filename"] = filename
        return self._request("GET", "/media/transcode/audio/uploadUrl", params=params).json().get("upload", {})

    def put_upload(self, upload_url: str, data: bytes, content_type: str = "audio/mpeg") -> None:
        """PUT to the signed URL. No bearer token here; the URL carries its own signature."""
        for attempt in range(4):
            resp = requests.put(upload_url, data=data, headers={"Content-Type": content_type}, timeout=900)
            if resp.status_code < 400:
                return
            if resp.status_code in RETRY_STATUSES and attempt < 3:
                time.sleep(min(2 ** attempt, 16))
                continue
            raise YotoApiError(f"upload PUT failed ({resp.status_code}): {resp.text[:300]}")

    def wait_transcoded(self, upload_id: str, timeout: int = 900, interval: float = 3.0) -> dict:
        deadline = time.time() + timeout
        while True:
            data = self._request("GET", f"/media/upload/{upload_id}/transcoded", params={"loudnorm": "false"}).json()
            transcode = data.get("transcode") or {}
            if transcode.get("transcodedSha256"):
                return transcode
            if transcode.get("error") or data.get("error"):
                raise YotoApiError(f"transcode failed: {transcode.get('error') or data.get('error')}")
            if time.time() > deadline:
                raise YotoApiError(f"transcode of upload {upload_id} did not finish within {timeout}s")
            time.sleep(interval)

    def upload_audio(self, path: Path, sha256: str, log: Callable[[str], None] = print) -> dict:
        """Upload one MP3 (skipped if Yoto already has this sha256) and wait for the transcode."""
        upload = self.get_upload_url(sha256, path.name)
        upload_id = upload.get("uploadId")
        if not upload_id:
            raise YotoApiError(f"no uploadId in upload URL response: {upload}")
        if upload.get("uploadUrl"):
            self.put_upload(upload["uploadUrl"], path.read_bytes())
        transcode = self.wait_transcoded(upload_id)
        info = transcode.get("transcodedInfo") or {}
        return {
            "uploadId": upload_id,
            "transcodedSha256": transcode["transcodedSha256"],
            "duration": info.get("duration"),
            "fileSize": info.get("fileSize"),
            "channels": info.get("channels"),
            "format": info.get("format") or "mp3",
        }

    # -- images ----------------------------------------------------------------

    def upload_icon(self, png: bytes, filename: str) -> str:
        resp = self._request(
            "POST", "/media/displayIcons/user/me/upload",
            params={"autoConvert": "true", "filename": filename},
            data=png, headers={"Content-Type": "image/png"},
        )
        icon = resp.json().get("displayIcon") or {}
        media_id = icon.get("mediaId")
        if not media_id:
            raise YotoApiError(f"icon upload returned no mediaId: {resp.text[:300]}")
        return media_id

    def upload_cover(self, jpeg: bytes) -> tuple[str, str]:
        resp = self._request(
            "POST", "/media/coverImage/user/me/upload",
            params={"autoconvert": "true", "coverType": "default"},
            data=jpeg, headers={"Content-Type": "image/jpeg"},
        )
        cover = resp.json().get("coverImage") or {}
        if not cover.get("mediaUrl"):
            raise YotoApiError(f"cover upload returned no mediaUrl: {resp.text[:300]}")
        return cover.get("mediaId", ""), cover["mediaUrl"]

    # -- cards -----------------------------------------------------------------

    def create_or_update_card(self, body: dict) -> dict:
        data = self._request("POST", "/content", json=body).json()
        card = data.get("card") or data
        if not card.get("cardId"):
            raise YotoApiError(f"content response had no cardId: {str(data)[:300]}")
        return card

    def my_content(self) -> list[dict]:
        data = self._request("GET", "/content/mine").json()
        return data.get("cards") or data.get("content") or []
