"""User configuration: where the Yoto client ID, tokens, and project data live."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("AUDIBLE_TO_YOTO_CONFIG_DIR", Path.home() / ".config" / "audible-to-yoto"))
CONFIG_PATH = CONFIG_DIR / "config.json"
TOKENS_PATH = CONFIG_DIR / "tokens.json"

DEFAULT_PORT = 8787
DEFAULT_BITRATE = "64k"


@dataclass
class Config:
    client_id: str | None = None
    data_dir: str = field(default_factory=lambda: str(Path.cwd()))
    redirect_port: int = DEFAULT_PORT

    @property
    def data_path(self) -> Path:
        return Path(self.data_dir).expanduser().resolve()

    @property
    def aax_dir(self) -> Path:
        return self.data_path / "aax_downloads"

    @property
    def work_dir(self) -> Path:
        return self.data_path / "work"


def load_config() -> Config:
    if not CONFIG_PATH.exists():
        return Config()
    raw = json.loads(CONFIG_PATH.read_text())
    known = {k: v for k, v in raw.items() if k in Config.__dataclass_fields__}
    return Config(**known)


def save_config(cfg: Config) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(asdict(cfg), indent=2) + "\n")
