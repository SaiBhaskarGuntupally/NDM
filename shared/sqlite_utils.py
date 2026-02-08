from __future__ import annotations

import sqlite3
from typing import Optional


def connect_sqlite(db_path: str, busy_timeout_ms: int = 8000) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute(f"PRAGMA busy_timeout = {int(busy_timeout_ms)}")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def get_journal_mode(conn: sqlite3.Connection) -> Optional[str]:
    row = conn.execute("PRAGMA journal_mode").fetchone()
    if not row:
        return None
    return str(row[0])
