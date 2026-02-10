from __future__ import annotations

import logging
import re
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from shared.app_paths import get_db_path

logger = logging.getLogger("profile_store")

DB_PATH = str(get_db_path())


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _now_iso() -> str:
    return datetime.now().isoformat()


def normalize_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def normalize_last10(value: str) -> str:
    digits = normalize_digits(value)
    if len(digits) == 11 and digits.startswith("1"):
        return digits[1:]
    if len(digits) >= 10:
        return digits[-10:]
    return digits


def format_phone(last10: str) -> str:
    digits = normalize_digits(last10)
    if len(digits) == 10:
        return f"+1-{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    return digits


def _derive_jd_title(jd_text: str) -> str:
    if not jd_text:
        return ""
    for line in jd_text.splitlines():
        title = line.strip()
        if title:
            return title[:60] + ("..." if len(title) > 60 else "")
    return ""


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
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
        CREATE TABLE IF NOT EXISTS research_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_digits TEXT NOT NULL,
            ts TEXT NOT NULL,
            note_text TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_research_profiles_phone_digits
            ON research_profiles(phone_digits);
        CREATE INDEX IF NOT EXISTS idx_research_notes_phone_digits
            ON research_notes(phone_digits);
        """
    )
    conn.commit()


def load_profile(phone_digits: str) -> Optional[Dict[str, Any]]:
    last10 = normalize_last10(phone_digits)
    if not last10:
        logger.warning("load_profile: invalid phone_digits=%s", phone_digits)
        return None
    logger.info("load_profile: phone_digits=%s last10=%s", phone_digits, last10)
    with _connect() as conn:
        _ensure_schema(conn)
        profile = conn.execute(
            "SELECT * FROM research_profiles WHERE phone_digits = ?",
            (last10,),
        ).fetchone()
        jd_row = conn.execute(
            "SELECT jd_text FROM research_jd WHERE phone_digits = ?",
            (last10,),
        ).fetchone()
        resume_row = conn.execute(
            "SELECT resume_text FROM research_resume_lines WHERE phone_digits = ?",
            (last10,),
        ).fetchone()
        notes_rows = conn.execute(
            "SELECT id, ts, note_text FROM research_notes WHERE phone_digits = ? ORDER BY ts DESC",
            (last10,),
        ).fetchall()

    vendor_name = profile["vendor_name"] if profile else ""
    vendor_company = profile["vendor_company"] if profile else ""
    vendor_title = profile["vendor_title"] if profile else ""
    jd_text = str(jd_row["jd_text"]) if jd_row and jd_row["jd_text"] else ""
    resume_text = (
        str(resume_row["resume_text"]) if resume_row and resume_row["resume_text"] else ""
    )
    last4 = last10[-4:] if len(last10) >= 4 else ""

    notes = [dict(row) for row in notes_rows]
    
    logger.info(
        "load_profile: result vendor_name=%s jd_text_len=%d resume_text_len=%d",
        vendor_name,
        len(jd_text),
        len(resume_text),
    )

    return {
        "phone_digits": last10,
        "phone_e164": format_phone(last10),
        "phone_last4": last4,
        "name": vendor_name,
        "company": vendor_company,
        "vendor": vendor_name,
        "title": vendor_title,
        "jd_title": _derive_jd_title(jd_text),
        "jd_text": jd_text,
        "resume_text": resume_text,
        "notes": notes,
        "updated_at": _now_iso(),
    }


def save_profile(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    last10 = normalize_last10(payload.get("phone_digits", ""))
    if not last10:
        logger.warning("save_profile: invalid phone_digits in payload=%s", payload)
        return None
    last4 = last10[-4:] if len(last10) >= 4 else ""
    vendor_name = payload.get("name") or payload.get("vendor_name") or ""
    vendor_company = payload.get("company") or payload.get("vendor_company") or ""
    vendor_title = payload.get("title") or payload.get("vendor_title") or ""
    jd_text = payload.get("jd_text")
    resume_text = payload.get("resume_text")
    
    logger.info(
        "save_profile: last10=%s vendor_name=%s jd_text=%s resume_text=%s",
        last10,
        vendor_name,
        "provided" if jd_text is not None else "None",
        "provided" if resume_text is not None else "None",
    )

    with _connect() as conn:
        _ensure_schema(conn)
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
        if jd_text is not None:
            logger.info("save_profile: saving jd_text len=%d", len(jd_text))
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
        if resume_text is not None:
            logger.info("save_profile: saving resume_text len=%d", len(resume_text))
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
        logger.info("save_profile: committed for last10=%s", last10)

    return load_profile(last10)


def add_note(phone_digits: str, note_text: str) -> List[Dict[str, Any]]:
    last10 = normalize_last10(phone_digits)
    if not last10 or not note_text:
        return []
    with _connect() as conn:
        _ensure_schema(conn)
        conn.execute(
            "INSERT INTO research_notes (phone_digits, ts, note_text) VALUES (?, ?, ?)",
            (last10, _now_iso(), note_text),
        )
        conn.commit()
    return list_notes(last10)


def list_notes(phone_digits: str) -> List[Dict[str, Any]]:
    last10 = normalize_last10(phone_digits)
    if not last10:
        return []
    with _connect() as conn:
        _ensure_schema(conn)
        rows = conn.execute(
            "SELECT id, ts, note_text FROM research_notes WHERE phone_digits = ? ORDER BY ts DESC",
            (last10,),
        ).fetchall()
        return [dict(row) for row in rows]
