"""Client for yotoicons.com, the community icon library.

Icons there are already 16x16 PNGs, so they can go straight to Yoto. Search results are parsed
out of the page markup, which puts every field we need in one call:

    <div class="icon" onclick="populate_icon_modal('488', 'objects', 'snitch', 'harry potter', 'pangolinpaw', '2093');">

That is: icon id, category, primary tag, secondary tag, author, download count.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlencode

import requests

BASE = "https://yotoicons.com"
USER_AGENT = "audible-to-yoto (+https://github.com/, personal audiobook tool)"
PER_PAGE = 26
REQUEST_DELAY = 0.34  # be gentle with a community site
CACHE_TTL = 30 * 24 * 3600  # the icon library changes slowly; a month is plenty

_ICON_RE = re.compile(
    r"populate_icon_modal\(\s*'(?P<id>\d+)'\s*,\s*'(?P<category>[^']*)'\s*,\s*'(?P<tag1>[^']*)'\s*,\s*'(?P<tag2>[^']*)'\s*,\s*'(?P<author>[^']*)'\s*,\s*'(?P<downloads>\d+)'"
)
_EMPTY_MARKER = "aren&#39;t any icons with that tag"


class YotoIconsError(Exception):
    pass


@dataclass(frozen=True)
class Icon:
    id: str
    category: str
    tag1: str
    tag2: str
    author: str
    downloads: int

    @property
    def url(self) -> str:
        return f"{BASE}/static/uploads/{self.id}.png"

    @property
    def text(self) -> str:
        """Everything searchable about the icon, lowercased."""
        return " ".join(p for p in (self.tag1, self.tag2, self.category) if p).lower()

    @property
    def credit(self) -> str:
        return f"yotoicons #{self.id} by {self.author}" if self.author else f"yotoicons #{self.id}"

    def to_dict(self) -> dict:
        return asdict(self)


def parse_icons(page_html: str) -> list[Icon]:
    icons: list[Icon] = []
    seen: set[str] = set()
    for m in _ICON_RE.finditer(page_html):
        icon_id = m.group("id")
        if icon_id in seen:
            continue
        seen.add(icon_id)
        icons.append(
            Icon(
                id=icon_id,
                category=html.unescape(m.group("category")).strip(),
                tag1=html.unescape(m.group("tag1")).strip(),
                tag2=html.unescape(m.group("tag2")).strip(),
                author=html.unescape(m.group("author")).strip(),
                downloads=int(m.group("downloads")),
            )
        )
    return icons


def is_empty_result(page_html: str) -> bool:
    return _EMPTY_MARKER in page_html


class YotoIconsClient:
    def __init__(self, session: requests.Session | None = None, delay: float = REQUEST_DELAY, cache_dir: Path | None = None):
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.delay = delay
        self._search_cache: dict[tuple[str, int], list[Icon]] = {}
        self._last_request = 0.0
        self.cache_dir = cache_dir
        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_file(self, tag: str, page: int) -> Path | None:
        if not self.cache_dir:
            return None
        key = hashlib.sha256(f"{tag.lower()}\x1f{page}".encode("utf-8")).hexdigest()[:24]
        return self.cache_dir / f"{key}.json"

    def _cached_page(self, tag: str, page: int) -> list[Icon] | None:
        """Search results are reused across books and runs: the library changes slowly."""
        path = self._cache_file(tag, page)
        if not path or not path.exists():
            return None
        if time.time() - path.stat().st_mtime > CACHE_TTL:
            return None
        try:
            rows = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return None
        return [Icon(**row) for row in rows]

    def _store_page(self, tag: str, page: int, icons: list[Icon]) -> None:
        path = self._cache_file(tag, page)
        if not path:
            return
        try:
            path.write_text(json.dumps([i.to_dict() for i in icons]))
        except OSError:
            pass

    def _get(self, path: str, params: dict | None = None) -> str:
        wait = self.delay - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        url = f"{BASE}{path}" + (f"?{urlencode(params)}" if params else "")
        try:
            resp = self.session.get(url, timeout=30)
        except requests.RequestException as exc:
            raise YotoIconsError(f"yotoicons.com request failed: {exc}") from exc
        self._last_request = time.monotonic()
        if resp.status_code != 200:
            raise YotoIconsError(f"yotoicons.com returned {resp.status_code} for {url}")
        return resp.text

    def search(self, tag: str, pages: int = 1) -> list[Icon]:
        """Icons matching a tag, most downloaded first, across `pages` result pages."""
        out: list[Icon] = []
        seen: set[str] = set()
        for page in range(1, pages + 1):
            key = (tag.lower(), page)
            if key in self._search_cache:
                found = self._search_cache[key]
            else:
                found = self._cached_page(tag, page)
                if found is None:
                    body = self._get("/icons", {"tag": tag, "page": page} if page > 1 else {"tag": tag})
                    found = [] if is_empty_result(body) else parse_icons(body)
                    self._store_page(tag, page, found)
                self._search_cache[key] = found
            added = 0
            for icon in found:
                if icon.id not in seen:
                    seen.add(icon.id)
                    out.append(icon)
                    added += 1
            # Stop at the end of the results, not on a short page: a page can hold fewer than
            # PER_PAGE parseable entries and still be followed by more pages.
            if not added:
                break
        return out

    def download(self, icon: Icon) -> bytes:
        try:
            resp = self.session.get(icon.url, timeout=30)
        except requests.RequestException as exc:
            raise YotoIconsError(f"could not download {icon.url}: {exc}") from exc
        if resp.status_code != 200 or not resp.content:
            raise YotoIconsError(f"could not download {icon.url} ({resp.status_code})")
        return resp.content


def cache_path(root: Path, icon: Icon) -> Path:
    return root / f"{icon.id}.png"


def download_cached(client: YotoIconsClient, icon: Icon, cache_dir: Path) -> bytes:
    """Download an icon once and reuse it for every later book."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_path(cache_dir, icon)
    if path.exists() and path.stat().st_size > 0:
        return path.read_bytes()
    data = client.download(icon)
    path.write_bytes(data)
    return data
