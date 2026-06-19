from __future__ import annotations

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"


class _Config:
    def get_proxy_settings(self) -> str:
        return ""


config = _Config()

