"""Optional, opt-in local history.

Wispr Flow keeps your dictation history on their servers; here it is an
SQLite file in your home directory, and only if history.enabled = true.
Delete the file and the history is gone — it exists nowhere else.
"""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

from .config import HistoryConfig

_DEFAULT_DIR = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "flowlocal"


class History:
    def __init__(self, cfg: HistoryConfig):
        self.enabled = cfg.enabled
        if not self.enabled:
            self._db = None
            return
        path = Path(cfg.path) if cfg.path else _DEFAULT_DIR / "history.db"
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS utterances ("
            " id INTEGER PRIMARY KEY,"
            " ts REAL NOT NULL,"
            " raw TEXT NOT NULL,"
            " formatted TEXT NOT NULL)"
        )
        self._db.commit()

    def record(self, raw: str, formatted: str) -> None:
        if self._db is None:
            return
        self._db.execute(
            "INSERT INTO utterances (ts, raw, formatted) VALUES (?, ?, ?)",
            (time.time(), raw, formatted),
        )
        self._db.commit()
