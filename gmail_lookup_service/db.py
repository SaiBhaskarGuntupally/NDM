from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from gmail_lookup_service.app_paths import get_db_path

DB_PATH = str(get_db_path())


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
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
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS call_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                call_id INTEGER NOT NULL,
                ts TEXT NOT NULL,
                note_text TEXT NOT NULL,
                note_preview TEXT,
                FOREIGN KEY(call_id) REFERENCES calls(id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS contacts (
                phone_digits TEXT PRIMARY KEY,
                display_name TEXT,
                company TEXT,
                tags TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS opportunities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_digits TEXT NOT NULL,
                jd_title TEXT,
                jd_text TEXT,
                resume_match_text TEXT,
                talk_track_text TEXT,
                status TEXT,
                updated_at TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS email_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                opportunity_id INTEGER,
                phone_digits TEXT,
                gmail_message_id TEXT,
                rfc_message_id TEXT,
                mailbox_email TEXT,
                account_index TEXT,
                subject TEXT,
                from_addr TEXT,
                date TEXT,
                snippet TEXT,
                gmail_link TEXT,
                is_pinned_jd INTEGER DEFAULT 0,
                FOREIGN KEY(opportunity_id) REFERENCES opportunities(id)
            )
            """
        )
        conn.commit()

        columns = [row[1] for row in conn.execute("PRAGMA table_info(calls)")]
        if "last10" not in columns:
            conn.execute("ALTER TABLE calls ADD COLUMN last10 TEXT")
            conn.commit()

        email_columns = [row[1] for row in conn.execute("PRAGMA table_info(email_links)")]
        if "rfc_message_id" not in email_columns:
            conn.execute("ALTER TABLE email_links ADD COLUMN rfc_message_id TEXT")
            conn.commit()
        if "mailbox_email" not in email_columns:
            conn.execute("ALTER TABLE email_links ADD COLUMN mailbox_email TEXT")
            conn.commit()
        if "account_index" not in email_columns:
            conn.execute("ALTER TABLE email_links ADD COLUMN account_index TEXT")
            conn.commit()


def _now_iso() -> str:
    return datetime.now().isoformat()


def _last10_digits(digits: str) -> str:
    if not digits:
        return ""
    return digits[-10:] if len(digits) >= 10 else digits


def create_call(phone_digits: str, status: str = "incoming") -> int:
    last10 = _last10_digits(phone_digits)
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO calls (ts_start, phone_digits, last10, status)
            VALUES (?, ?, ?, ?)
            """,
            (_now_iso(), phone_digits, last10, status),
        )
        conn.commit()
        return int(cur.lastrowid)


def update_call_end(call_id: int) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE calls SET ts_end = ?, status = ? WHERE id = ?",
            (_now_iso(), "ended", call_id),
        )
        conn.commit()


def update_call_audio(call_id: int, audio_path: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE calls SET audio_path = ? WHERE id = ?",
            (audio_path, call_id),
        )
        conn.commit()


def get_latest_call(phone_digits: str) -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM calls WHERE phone_digits = ? ORDER BY ts_start DESC LIMIT 1",
            (phone_digits,),
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        if not data.get("last10"):
            data["last10"] = _last10_digits(data.get("phone_digits", ""))
        return data


def list_recent_calls(limit: int = 20) -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM calls ORDER BY ts_start DESC LIMIT ?", (limit,)
        ).fetchall()
        results = []
        for row in rows:
            data = dict(row)
            if not data.get("last10"):
                data["last10"] = _last10_digits(data.get("phone_digits", ""))
            results.append(data)
        return results


def list_call_history(
    digits: Optional[str],
    last10: Optional[str],
    limit: int = 3,
) -> List[Dict[str, Any]]:
    if not digits and not last10:
        return []

    with _connect() as conn:
        if digits:
            rows = conn.execute(
                "SELECT * FROM calls WHERE phone_digits = ? ORDER BY ts_start DESC LIMIT ?",
                (digits, limit),
            ).fetchall()
            if rows:
                results = []
                for row in rows:
                    data = dict(row)
                    if not data.get("last10"):
                        data["last10"] = _last10_digits(data.get("phone_digits", ""))
                    results.append(data)
                return results

        if digits and not last10:
            last10 = _last10_digits(digits)

        rows = conn.execute(
            "SELECT * FROM calls WHERE last10 = ? ORDER BY ts_start DESC LIMIT ?",
            (last10, limit),
        ).fetchall()
        results = []
        for row in rows:
            data = dict(row)
            if not data.get("last10"):
                data["last10"] = _last10_digits(data.get("phone_digits", ""))
            results.append(data)
        return results


def clear_all() -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM call_notes")
        conn.execute("DELETE FROM calls")
        conn.execute("DELETE FROM email_links")
        conn.execute("DELETE FROM opportunities")
        conn.execute("DELETE FROM contacts")
        conn.commit()


def get_notes(call_id: int) -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM call_notes WHERE call_id = ? ORDER BY ts DESC",
            (call_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def add_note(call_id: int, note_text: str) -> Dict[str, Any]:
    preview = note_text[:140]
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO call_notes (call_id, ts, note_text, note_preview)
            VALUES (?, ?, ?, ?)
            """,
            (call_id, _now_iso(), note_text, preview),
        )
        conn.commit()
        note_id = int(cur.lastrowid)
    return {
        "id": note_id,
        "call_id": call_id,
        "ts": _now_iso(),
        "note_text": note_text,
        "note_preview": preview,
    }


def get_opportunity(phone_digits: str) -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM opportunities WHERE phone_digits = ?",
            (phone_digits,),
        ).fetchone()
        return dict(row) if row else None


def upsert_opportunity(data: Dict[str, Any]) -> int:
    phone_digits = data.get("phone_digits")
    if not phone_digits:
        raise ValueError("phone_digits required")

    existing = get_opportunity(phone_digits)
    with _connect() as conn:
        if existing:
            conn.execute(
                """
                UPDATE opportunities
                SET jd_title = ?, jd_text = ?, resume_match_text = ?,
                    talk_track_text = ?, status = ?, updated_at = ?
                WHERE phone_digits = ?
                """,
                (
                    data.get("jd_title"),
                    data.get("jd_text"),
                    data.get("resume_match_text"),
                    data.get("talk_track_text"),
                    data.get("status"),
                    _now_iso(),
                    phone_digits,
                ),
            )
            conn.commit()
            return int(existing["id"])

        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO opportunities
            (phone_digits, jd_title, jd_text, resume_match_text, talk_track_text, status, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                phone_digits,
                data.get("jd_title"),
                data.get("jd_text"),
                data.get("resume_match_text"),
                data.get("talk_track_text"),
                data.get("status"),
                _now_iso(),
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def save_email_links(
    phone_digits: str,
    emails: List[Dict[str, Any]],
    opportunity_id: Optional[int] = None,
) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM email_links WHERE phone_digits = ?", (phone_digits,))
        for e in emails:
            conn.execute(
                """
                INSERT INTO email_links
                (opportunity_id, phone_digits, gmail_message_id, rfc_message_id, mailbox_email, account_index,
                 subject, from_addr, date, snippet, gmail_link, is_pinned_jd)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    opportunity_id,
                    phone_digits,
                    e.get("gmail_message_id") or e.get("gmailMessageId"),
                    e.get("rfc_message_id") or e.get("rfcMessageId"),
                    e.get("mailbox_email") or e.get("mailboxEmail"),
                    e.get("account_index") or e.get("accountIndex"),
                    e.get("subject"),
                    e.get("from"),
                    e.get("date"),
                    e.get("snippet"),
                    e.get("link"),
                    0,
                ),
            )
        conn.commit()


def list_email_links(phone_digits: str) -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM email_links WHERE phone_digits = ? ORDER BY id DESC",
            (phone_digits,),
        ).fetchall()
        return [dict(row) for row in rows]
