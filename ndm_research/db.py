from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from shared.app_paths import get_db_path
from shared.sqlite_utils import connect_sqlite

DB_PATH = str(get_db_path())


def _now_iso() -> str:
    return datetime.now().isoformat()


def get_db() -> sqlite3.Connection:
    return connect_sqlite(DB_PATH)


def init_db() -> None:
    with connect_sqlite(DB_PATH) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_start TEXT NOT NULL,
                ts_end TEXT,
                phone_digits TEXT NOT NULL,
                last10 TEXT,
                display_name TEXT,
                status TEXT,
                call_subject TEXT,
                audio_path TEXT,
                notes_preview TEXT
            );
            CREATE TABLE IF NOT EXISTS call_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                call_id INTEGER NOT NULL,
                ts TEXT NOT NULL,
                note_text TEXT NOT NULL,
                note_preview TEXT,
                FOREIGN KEY(call_id) REFERENCES calls(id)
            );
            CREATE TABLE IF NOT EXISTS email_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                opportunity_id INTEGER,
                phone_digits TEXT,
                gmail_message_id TEXT,
                subject TEXT,
                from_addr TEXT,
                date TEXT,
                snippet TEXT,
                gmail_link TEXT,
                is_pinned_jd INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS research_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_digits TEXT NOT NULL UNIQUE,
                last4 TEXT NOT NULL,
                vendor_name TEXT,
                vendor_company TEXT,
                vendor_title TEXT,
                created_at TEXT,
                updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS research_jd (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_digits TEXT NOT NULL UNIQUE,
                jd_text TEXT NOT NULL DEFAULT '',
                updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS research_resume_lines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_digits TEXT NOT NULL UNIQUE,
                resume_text TEXT NOT NULL DEFAULT '',
                updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS research_recordings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_digits TEXT NOT NULL,
                file_path TEXT NOT NULL,
                created_at TEXT,
                duration_sec INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS research_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_digits TEXT NOT NULL,
                ts TEXT NOT NULL,
                note_text TEXT NOT NULL
            );
            """
        )
        columns = [row[1] for row in conn.execute("PRAGMA table_info(calls)")]
        if "last10" not in columns:
            conn.execute("ALTER TABLE calls ADD COLUMN last10 TEXT")
        conn.execute(
            "UPDATE calls SET last10 = substr(phone_digits, -10) "
            "WHERE (last10 IS NULL OR last10 = '') AND phone_digits IS NOT NULL"
        )

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_calls_phone_digits ON calls(phone_digits)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_calls_last10 ON calls(last10)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_email_links_phone_digits ON email_links(phone_digits)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_research_profiles_phone_digits "
            "ON research_profiles(phone_digits)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_research_profiles_last4 "
            "ON research_profiles(last4)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_research_notes_phone_digits "
            "ON research_notes(phone_digits)"
        )
        conn.commit()


def search_calls_by_last10(
    conn: sqlite3.Connection, last10: str, limit: int
) -> List[Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT COALESCE(last10, substr(phone_digits, -10)) AS phone_digits,
               MAX(ts_start) AS last_call_ts,
               COUNT(*) AS call_count,
               MAX(display_name) AS display_name
        FROM calls
        WHERE last10 = ? OR phone_digits = ?
        GROUP BY COALESCE(last10, substr(phone_digits, -10))
        ORDER BY last_call_ts DESC
        LIMIT ?
        """,
        (last10, last10, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def search_calls_by_last4(
    conn: sqlite3.Connection, last4: str, limit: int
) -> List[Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT COALESCE(last10, substr(phone_digits, -10)) AS phone_digits,
               MAX(ts_start) AS last_call_ts,
               COUNT(*) AS call_count,
               MAX(display_name) AS display_name
        FROM calls
        WHERE substr(COALESCE(last10, phone_digits), -4) = ?
        GROUP BY COALESCE(last10, substr(phone_digits, -10))
        ORDER BY last_call_ts DESC
        LIMIT ?
        """,
        (last4, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def search_calls_by_partial(
    conn: sqlite3.Connection, partial: str, limit: int
) -> List[Dict[str, Any]]:
    pattern = f"%{partial}%"
    rows = conn.execute(
        """
        SELECT COALESCE(last10, substr(phone_digits, -10)) AS phone_digits,
               MAX(ts_start) AS last_call_ts,
               COUNT(*) AS call_count,
               MAX(display_name) AS display_name
        FROM calls
        WHERE last10 LIKE ? OR phone_digits LIKE ?
        GROUP BY COALESCE(last10, substr(phone_digits, -10))
        ORDER BY last_call_ts DESC
        LIMIT ?
        """,
        (pattern, pattern, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def search_profiles_by_last10(
    conn: sqlite3.Connection, last10: str, limit: int
) -> List[Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT phone_digits, last4, vendor_name, vendor_company, vendor_title
        FROM research_profiles
        WHERE phone_digits = ?
        LIMIT ?
        """,
        (last10, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def search_profiles_by_last4(
    conn: sqlite3.Connection, last4: str, limit: int
) -> List[Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT phone_digits, last4, vendor_name, vendor_company, vendor_title
        FROM research_profiles
        WHERE last4 = ?
        LIMIT ?
        """,
        (last4, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def search_profiles_by_partial(
    conn: sqlite3.Connection, partial: str, limit: int
) -> List[Dict[str, Any]]:
    pattern = f"%{partial}%"
    rows = conn.execute(
        """
        SELECT phone_digits, last4, vendor_name, vendor_company, vendor_title
        FROM research_profiles
        WHERE phone_digits LIKE ?
        LIMIT ?
        """,
        (pattern, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def list_all_numbers(
    conn: sqlite3.Connection,
    limit: int = 500,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    rows = conn.execute(
        """
        WITH call_stats AS (
            SELECT COALESCE(last10, substr(phone_digits, -10)) AS phone_digits,
                   MAX(ts_start) AS last_call_ts,
                   COUNT(*) AS call_count,
                   MAX(display_name) AS display_name
            FROM calls
            GROUP BY COALESCE(last10, substr(phone_digits, -10))
        ),
        all_numbers AS (
            SELECT phone_digits FROM research_profiles
            UNION
            SELECT phone_digits FROM call_stats
        )
        SELECT all_numbers.phone_digits,
               call_stats.last_call_ts,
               COALESCE(call_stats.call_count, 0) AS call_count,
               call_stats.display_name,
               research_profiles.vendor_name
        FROM all_numbers
        LEFT JOIN call_stats
            ON call_stats.phone_digits = all_numbers.phone_digits
        LEFT JOIN research_profiles
            ON research_profiles.phone_digits = all_numbers.phone_digits
        ORDER BY call_stats.last_call_ts DESC, all_numbers.phone_digits ASC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    ).fetchall()
    return [dict(row) for row in rows]


def list_calls(
    conn: sqlite3.Connection,
    last10: str,
    limit: int,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM calls
        WHERE last10 = ? OR phone_digits = ?
        ORDER BY ts_start DESC
        LIMIT ? OFFSET ?
        """,
        (last10, last10, limit, offset),
    ).fetchall()
    return [dict(row) for row in rows]


def list_call_notes(
    conn: sqlite3.Connection, last10: str, limit: int
) -> List[Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT call_notes.id, call_notes.call_id, call_notes.ts, call_notes.note_text
        FROM call_notes
        JOIN calls ON call_notes.call_id = calls.id
        WHERE calls.last10 = ? OR calls.phone_digits = ?
        ORDER BY call_notes.ts DESC
        LIMIT ?
        """,
        (last10, last10, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def list_research_notes(
    conn: sqlite3.Connection, last10: str, limit: int
) -> List[Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, phone_digits, ts, note_text
        FROM research_notes
        WHERE phone_digits = ?
        ORDER BY ts DESC
        LIMIT ?
        """,
        (last10, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def list_email_links(
    conn: sqlite3.Connection, last10: str
) -> List[Dict[str, Any]]:
    pattern = f"%{last10}%"
    rows = conn.execute(
        """
        SELECT * FROM email_links
        WHERE phone_digits = ? OR phone_digits LIKE ?
        ORDER BY id DESC
        """,
        (last10, pattern),
    ).fetchall()
    return [dict(row) for row in rows]


def list_recordings(
    conn: sqlite3.Connection, last10: str
) -> List[Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM research_recordings
        WHERE phone_digits = ?
        ORDER BY created_at DESC
        """,
        (last10,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_latest_call_id(conn: sqlite3.Connection, last10: str) -> Optional[int]:
    row = conn.execute(
        """
        SELECT id FROM calls
        WHERE last10 = ? OR phone_digits = ?
        ORDER BY ts_start DESC
        LIMIT 1
        """,
        (last10, last10),
    ).fetchone()
    return int(row[0]) if row else None


def get_latest_call_display_name(
    conn: sqlite3.Connection, last10: str
) -> Optional[str]:
    row = conn.execute(
        """
        SELECT display_name FROM calls
        WHERE last10 = ? OR phone_digits = ?
        ORDER BY ts_start DESC
        LIMIT 1
        """,
        (last10, last10),
    ).fetchone()
    return str(row[0]) if row and row[0] else None


def get_call_stats(conn: sqlite3.Connection, last10: str) -> Dict[str, Any]:
    row = conn.execute(
        """
        SELECT COUNT(*) AS call_count, MAX(ts_start) AS last_call_ts
        FROM calls
        WHERE last10 = ? OR phone_digits = ?
        """,
        (last10, last10),
    ).fetchone()
    return dict(row) if row else {"call_count": 0, "last_call_ts": None}


def get_profile(conn: sqlite3.Connection, last10: str) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        """
        SELECT * FROM research_profiles WHERE phone_digits = ?
        """,
        (last10,),
    ).fetchone()
    return dict(row) if row else None


def upsert_profile(
    conn: sqlite3.Connection,
    last10: str,
    last4: str,
    vendor_name: Optional[str],
    vendor_company: Optional[str],
    vendor_title: Optional[str],
) -> None:
    now = _now_iso()
    conn.execute(
        """
        INSERT INTO research_profiles
        (phone_digits, last4, vendor_name, vendor_company, vendor_title, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(phone_digits) DO UPDATE SET
            last4 = excluded.last4,
            vendor_name = excluded.vendor_name,
            vendor_company = excluded.vendor_company,
            vendor_title = excluded.vendor_title,
            updated_at = excluded.updated_at
        """,
        (last10, last4, vendor_name, vendor_company, vendor_title, now, now),
    )
    conn.commit()


def ensure_profile(conn: sqlite3.Connection, last10: str, last4: str) -> None:
    now = _now_iso()
    conn.execute(
        """
        INSERT OR IGNORE INTO research_profiles
        (phone_digits, last4, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        (last10, last4, now, now),
    )
    conn.commit()


def get_jd_text(conn: sqlite3.Connection, last10: str) -> str:
    row = conn.execute(
        "SELECT jd_text FROM research_jd WHERE phone_digits = ?",
        (last10,),
    ).fetchone()
    return str(row[0]) if row and row[0] else ""


def upsert_jd(conn: sqlite3.Connection, last10: str, jd_text: str) -> None:
    now = _now_iso()
    conn.execute(
        """
        INSERT INTO research_jd (phone_digits, jd_text, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(phone_digits) DO UPDATE SET
            jd_text = excluded.jd_text,
            updated_at = excluded.updated_at
        """,
        (last10, jd_text, now),
    )
    conn.commit()


def ensure_jd(conn: sqlite3.Connection, last10: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO research_jd (phone_digits, jd_text, updated_at) VALUES (?, '', ?)",
        (last10, _now_iso()),
    )
    conn.commit()


def get_resume_text(conn: sqlite3.Connection, last10: str) -> str:
    row = conn.execute(
        "SELECT resume_text FROM research_resume_lines WHERE phone_digits = ?",
        (last10,),
    ).fetchone()
    return str(row[0]) if row and row[0] else ""


def upsert_resume(conn: sqlite3.Connection, last10: str, resume_text: str) -> None:
    now = _now_iso()
    conn.execute(
        """
        INSERT INTO research_resume_lines (phone_digits, resume_text, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(phone_digits) DO UPDATE SET
            resume_text = excluded.resume_text,
            updated_at = excluded.updated_at
        """,
        (last10, resume_text, now),
    )
    conn.commit()


def ensure_resume(conn: sqlite3.Connection, last10: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO research_resume_lines (phone_digits, resume_text, updated_at) VALUES (?, '', ?)",
        (last10, _now_iso()),
    )
    conn.commit()


def add_call_note(
    conn: sqlite3.Connection, call_id: int, note_text: str
) -> Dict[str, Any]:
    ts = _now_iso()
    preview = note_text[:140]
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO call_notes (call_id, ts, note_text, note_preview)
        VALUES (?, ?, ?, ?)
        """,
        (call_id, ts, note_text, preview),
    )
    conn.commit()
    return {
        "id": int(cur.lastrowid),
        "call_id": call_id,
        "ts": ts,
        "note_text": note_text,
        "note_preview": preview,
    }


def add_research_note(
    conn: sqlite3.Connection, last10: str, note_text: str
) -> Dict[str, Any]:
    ts = _now_iso()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO research_notes (phone_digits, ts, note_text)
        VALUES (?, ?, ?)
        """,
        (last10, ts, note_text),
    )
    conn.commit()
    return {"id": int(cur.lastrowid), "ts": ts, "note_text": note_text}


def update_note_any(conn: sqlite3.Connection, note_id: int, note_text: str) -> bool:
    preview = note_text[:140]
    cur = conn.execute(
        "UPDATE research_notes SET note_text = ? WHERE id = ?",
        (note_text, note_id),
    )
    if cur.rowcount:
        conn.commit()
        return True

    cur = conn.execute(
        "UPDATE call_notes SET note_text = ?, note_preview = ? WHERE id = ?",
        (note_text, preview, note_id),
    )
    conn.commit()
    return bool(cur.rowcount)


def delete_note_any(conn: sqlite3.Connection, note_id: int) -> bool:
    cur = conn.execute("DELETE FROM research_notes WHERE id = ?", (note_id,))
    if cur.rowcount:
        conn.commit()
        return True

    cur = conn.execute("DELETE FROM call_notes WHERE id = ?", (note_id,))
    conn.commit()
    return bool(cur.rowcount)


def delete_call(conn: sqlite3.Connection, call_id: int) -> None:
    conn.execute("DELETE FROM call_notes WHERE call_id = ?", (call_id,))
    conn.execute("DELETE FROM calls WHERE id = ?", (call_id,))
    conn.commit()
