from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any


class LocalAccountService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._accounts_file = Path(__file__).resolve().parents[1] / "data" / "accounts.jsonl"

    def configure(self, accounts_file: str | Path) -> None:
        self._accounts_file = Path(accounts_file)

    def add_account_items(self, items: list[dict[str, Any]]) -> None:
        self._accounts_file.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self._accounts_file.open("a", encoding="utf-8") as handle:
            for item in items:
                handle.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")

    def refresh_accounts(self, access_tokens: list[str]) -> dict[str, Any]:
        return {"ok": len(access_tokens), "errors": []}


account_service = LocalAccountService()

